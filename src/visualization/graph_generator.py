"""
HyperMatrix v2026 - Graph Generator
Generates dependency graphs in various formats.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from enum import Enum

from ..core.lineage import LineageResolver, DependencyGraph, ImportType


class GraphFormat(Enum):
    """Output format for graphs."""
    DOT = "dot"           # Graphviz DOT format
    JSON = "json"         # D3.js compatible JSON
    MERMAID = "mermaid"   # Mermaid diagram
    CYTOSCAPE = "cytoscape"  # Cytoscape.js format


@dataclass
class GraphNode:
    """Node in the visual graph."""
    id: str
    label: str
    node_type: str = "file"
    depth: int = 0
    size: int = 0
    color: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Edge in the visual graph."""
    source: str
    target: str
    edge_type: str = "imports"
    weight: float = 1.0
    label: Optional[str] = None


class GraphGenerator:
    """Generate visual dependency graphs."""

    # Color schemes for different file types
    FILE_COLORS = {
        ".py": "#3572A5",      # Python blue
        ".js": "#F7DF1E",      # JavaScript yellow
        ".ts": "#3178C6",      # TypeScript blue
        ".jsx": "#61DAFB",     # React cyan
        ".tsx": "#61DAFB",
        ".json": "#292929",    # JSON dark
        ".md": "#083FA1",      # Markdown blue
        ".yaml": "#CB171E",    # YAML red
        ".yml": "#CB171E",
    }

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.resolver = LineageResolver(str(self.project_root))
        self.nodes: list[GraphNode] = []
        self.edges: list[GraphEdge] = []

    def build_from_lineage(
        self,
        entry_files: Optional[list[str]] = None,
        include_external: bool = False,
    ) -> "GraphGenerator":
        """Build graph from lineage resolver."""
        graph = self.resolver.build_dependency_graph(entry_files)

        self.nodes = []
        self.edges = []

        # Create nodes
        for filepath, node in graph.nodes.items():
            path = Path(filepath)
            rel_path = self._get_relative_path(filepath)

            graph_node = GraphNode(
                id=filepath,
                label=rel_path,
                node_type="file",
                depth=node.depth,
                color=self.FILE_COLORS.get(path.suffix.lower(), "#999999"),
                metadata={
                    "extension": path.suffix,
                    "import_count": len(node.imports),
                    "imported_by_count": len(node.imported_by),
                }
            )
            self.nodes.append(graph_node)

            # Create edges
            for imp in node.imports:
                if imp.resolved_path:
                    if include_external or imp.import_type == ImportType.LOCAL:
                        edge = GraphEdge(
                            source=filepath,
                            target=imp.resolved_path,
                            edge_type="imports",
                            label=imp.module,
                        )
                        self.edges.append(edge)

        return self

    def build_from_database(self, db_manager, project_id: int) -> "GraphGenerator":
        """Build graph from database records."""
        self.nodes = []
        self.edges = []

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # Get all files
            cursor.execute("""
                SELECT id, filepath, file_type FROM files WHERE project_id = ?
            """, (project_id,))
            files = {row["id"]: row for row in cursor.fetchall()}

            # Create nodes
            for file_id, file_info in files.items():
                filepath = file_info["filepath"]
                path = Path(filepath)

                node = GraphNode(
                    id=str(file_id),
                    label=self._get_relative_path(filepath),
                    node_type=file_info["file_type"],
                    color=self.FILE_COLORS.get(path.suffix.lower(), "#999999"),
                )
                self.nodes.append(node)

            # Get imports and create edges
            cursor.execute("""
                SELECT i.file_id, i.module, fi.filepath
                FROM imports i
                JOIN files fi ON i.file_id = fi.id
                WHERE fi.project_id = ?
            """, (project_id,))

            for row in cursor.fetchall():
                # Try to match import to a file
                module = row["module"]
                source_id = str(row["file_id"])

                # Simple matching - could be improved
                for file_id, file_info in files.items():
                    if module.replace(".", "/") in file_info["filepath"]:
                        edge = GraphEdge(
                            source=source_id,
                            target=str(file_id),
                            edge_type="imports",
                            label=module,
                        )
                        self.edges.append(edge)
                        break

        return self

    def _get_relative_path(self, filepath: str) -> str:
        """Get path relative to project root."""
        try:
            return str(Path(filepath).relative_to(self.project_root))
        except ValueError:
            return Path(filepath).name

    def to_dot(self, title: str = "Dependency Graph") -> str:
        """Export to Graphviz DOT format."""
        lines = [
            f'digraph "{title}" {{',
            '    rankdir=LR;',
            '    node [shape=box, style=filled, fontname="Arial"];',
            '    edge [fontname="Arial", fontsize=10];',
            '',
        ]

        # Add nodes
        for node in self.nodes:
            color = node.color or "#CCCCCC"
            label = node.label.replace("\\", "/")
            lines.append(f'    "{node.id}" [label="{label}", fillcolor="{color}"];')

        lines.append('')

        # Add edges
        for edge in self.edges:
            label = f' [label="{edge.label}"]' if edge.label else ''
            lines.append(f'    "{edge.source}" -> "{edge.target}"{label};')

        lines.append('}')
        return '\n'.join(lines)

    def to_json(self) -> str:
        """Export to D3.js compatible JSON."""
        data = {
            "nodes": [
                {
                    "id": node.id,
                    "label": node.label,
                    "type": node.node_type,
                    "depth": node.depth,
                    "color": node.color,
                    **node.metadata,
                }
                for node in self.nodes
            ],
            "links": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.edge_type,
                    "label": edge.label,
                }
                for edge in self.edges
            ],
        }
        return json.dumps(data, indent=2)

    def to_mermaid(self, title: str = "Dependency Graph") -> str:
        """Export to Mermaid diagram format."""
        lines = [
            f'---',
            f'title: {title}',
            f'---',
            'flowchart LR',
            '',
        ]

        # Create node ID mapping (Mermaid needs simple IDs)
        id_map = {}
        for i, node in enumerate(self.nodes):
            simple_id = f'N{i}'
            id_map[node.id] = simple_id
            label = node.label.replace("\\", "/").replace('"', "'")
            lines.append(f'    {simple_id}["{label}"]')

        lines.append('')

        # Add edges
        for edge in self.edges:
            source = id_map.get(edge.source, edge.source)
            target = id_map.get(edge.target, edge.target)
            if source and target:
                lines.append(f'    {source} --> {target}')

        return '\n'.join(lines)

    def to_cytoscape(self) -> str:
        """Export to Cytoscape.js format."""
        elements = []

        # Add nodes
        for node in self.nodes:
            elements.append({
                "data": {
                    "id": node.id,
                    "label": node.label,
                    "type": node.node_type,
                    "color": node.color,
                },
                "group": "nodes",
            })

        # Add edges
        for i, edge in enumerate(self.edges):
            elements.append({
                "data": {
                    "id": f"e{i}",
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.label,
                },
                "group": "edges",
            })

        return json.dumps({"elements": elements}, indent=2)

    def export(
        self,
        output_path: str,
        format: GraphFormat = GraphFormat.DOT,
        title: str = "Dependency Graph",
    ) -> str:
        """Export graph to file."""
        if format == GraphFormat.DOT:
            content = self.to_dot(title)
        elif format == GraphFormat.JSON:
            content = self.to_json()
        elif format == GraphFormat.MERMAID:
            content = self.to_mermaid(title)
        elif format == GraphFormat.CYTOSCAPE:
            content = self.to_cytoscape()
        else:
            raise ValueError(f"Unknown format: {format}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path

    def get_stats(self) -> dict:
        """Get graph statistics."""
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "avg_connections": len(self.edges) / len(self.nodes) if self.nodes else 0,
            "isolated_nodes": len([n for n in self.nodes
                                  if not any(e.source == n.id or e.target == n.id
                                           for e in self.edges)]),
        }
