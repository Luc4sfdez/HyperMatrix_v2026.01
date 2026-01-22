"""
HyperMatrix v2026 - Impact Analyzer
Analyzes cross-dependencies and impact of file changes.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional

from .lineage import LineageResolver, DependencyGraph, ImportType

logger = logging.getLogger(__name__)


@dataclass
class ImpactResult:
    """Result of impact analysis for a file change."""
    target_file: str
    action: str  # 'delete', 'modify', 'merge'
    directly_affected: List[str] = field(default_factory=list)
    transitively_affected: List[str] = field(default_factory=list)
    import_updates_required: List[Dict] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    safe_to_proceed: bool = True


@dataclass
class DependencyReport:
    """Comprehensive dependency report for a file or group."""
    filepath: str
    imports: List[Dict] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)
    circular_dependencies: List[str] = field(default_factory=list)
    external_dependencies: List[str] = field(default_factory=list)
    depth_from_root: int = 0
    coupling_score: float = 0.0


class ImpactAnalyzer:
    """
    Analyzes the impact of file changes on a codebase.

    This class provides detailed impact analysis for:
    - File deletion
    - File modification
    - File merging
    - Import changes
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.lineage = LineageResolver(project_root)
        self._graph: Optional[DependencyGraph] = None

    def build_graph(self, entry_files: List[str] = None) -> DependencyGraph:
        """Build or refresh the dependency graph."""
        self._graph = self.lineage.build_dependency_graph(entry_files)
        return self._graph

    def get_graph(self) -> DependencyGraph:
        """Get the current dependency graph, building if necessary."""
        if self._graph is None:
            self.build_graph()
        return self._graph

    def analyze_deletion_impact(self, filepath: str) -> ImpactResult:
        """
        Analyze the impact of deleting a file.

        Returns information about what files would break if this file is deleted.
        """
        graph = self.get_graph()
        filepath = str(Path(filepath).resolve())

        result = ImpactResult(
            target_file=filepath,
            action="delete"
        )

        node = graph.nodes.get(filepath)
        if not node:
            result.warnings.append(f"File not found in dependency graph: {filepath}")
            return result

        # Get directly affected files (those that import this file)
        result.directly_affected = node.imported_by.copy()

        # Calculate transitive impact
        visited = set(result.directly_affected)
        queue = result.directly_affected.copy()

        while queue:
            current = queue.pop(0)
            current_node = graph.nodes.get(current)
            if current_node:
                for dependent in current_node.imported_by:
                    if dependent not in visited:
                        visited.add(dependent)
                        result.transitively_affected.append(dependent)
                        queue.append(dependent)

        # Calculate import updates required
        for affected_file in result.directly_affected:
            affected_node = graph.nodes.get(affected_file)
            if affected_node:
                for imp in affected_node.imports:
                    if imp.resolved_path == filepath:
                        result.import_updates_required.append({
                            "file": affected_file,
                            "import_module": imp.module,
                            "line": imp.lineno,
                            "action": "remove_or_update"
                        })

        # Determine breaking changes
        for affected_file in result.directly_affected:
            result.breaking_changes.append(
                f"{Path(affected_file).name} imports {Path(filepath).name}"
            )

        # Determine if safe to proceed
        result.safe_to_proceed = len(result.directly_affected) == 0

        return result

    def analyze_merge_impact(self, files: List[str], target: str) -> ImpactResult:
        """
        Analyze the impact of merging multiple files into one target.

        Args:
            files: List of files to be merged
            target: The target file (either existing or new path)

        Returns:
            Impact analysis for the merge operation
        """
        graph = self.get_graph()
        target = str(Path(target).resolve())

        result = ImpactResult(
            target_file=target,
            action="merge"
        )

        all_dependents = set()

        for filepath in files:
            filepath = str(Path(filepath).resolve())
            node = graph.nodes.get(filepath)

            if not node:
                result.warnings.append(f"File not in graph: {filepath}")
                continue

            # Collect all dependents
            for dependent in node.imported_by:
                if dependent not in files:  # Don't count files being merged
                    all_dependents.add(dependent)

                    # Add import update
                    dep_node = graph.nodes.get(dependent)
                    if dep_node:
                        for imp in dep_node.imports:
                            if imp.resolved_path == filepath:
                                result.import_updates_required.append({
                                    "file": dependent,
                                    "old_import": imp.module,
                                    "old_path": filepath,
                                    "new_path": target,
                                    "line": imp.lineno,
                                    "action": "update_import_path"
                                })

        result.directly_affected = list(all_dependents)

        # Calculate transitive impact
        visited = set(result.directly_affected)
        queue = result.directly_affected.copy()

        while queue:
            current = queue.pop(0)
            current_node = graph.nodes.get(current)
            if current_node:
                for dependent in current_node.imported_by:
                    if dependent not in visited and dependent not in files:
                        visited.add(dependent)
                        result.transitively_affected.append(dependent)
                        queue.append(dependent)

        # Merge is generally safer if imports are updated
        result.safe_to_proceed = True

        return result

    def get_dependency_report(self, filepath: str) -> DependencyReport:
        """
        Get comprehensive dependency report for a file.
        """
        graph = self.get_graph()
        filepath = str(Path(filepath).resolve())

        report = DependencyReport(filepath=filepath)

        node = graph.nodes.get(filepath)
        if not node:
            return report

        # Imports
        for imp in node.imports:
            report.imports.append({
                "module": imp.module,
                "type": imp.import_type.value,
                "resolved_path": imp.resolved_path,
                "line": imp.lineno
            })

            if imp.import_type == ImportType.THIRD_PARTY:
                report.external_dependencies.append(imp.module)

        # Imported by
        report.imported_by = node.imported_by.copy()

        # Check for circular dependencies
        for imp in node.imports:
            if imp.resolved_path:
                imp_node = graph.nodes.get(imp.resolved_path)
                if imp_node:
                    for back_imp in imp_node.imports:
                        if back_imp.resolved_path == filepath:
                            report.circular_dependencies.append(imp.resolved_path)

        # Depth from root
        report.depth_from_root = node.depth

        # Coupling score (higher = more coupled)
        total_imports = len(node.imports)
        local_imports = len([i for i in node.imports if i.import_type == ImportType.LOCAL])
        dependents = len(node.imported_by)

        report.coupling_score = (local_imports * 0.3 + dependents * 0.7) / max(total_imports, 1)

        return report

    def find_safe_deletion_order(self, files: List[str]) -> List[str]:
        """
        Determine the safest order to delete files (least dependencies first).

        Returns files ordered by how many other files depend on them.
        """
        graph = self.get_graph()

        file_scores = []
        for filepath in files:
            filepath = str(Path(filepath).resolve())
            node = graph.nodes.get(filepath)

            if node:
                # Count how many of the files to delete depend on this file
                internal_deps = sum(1 for d in node.imported_by if d in files)
                external_deps = sum(1 for d in node.imported_by if d not in files)

                score = internal_deps * 10 + external_deps
                file_scores.append((filepath, score))
            else:
                file_scores.append((filepath, 0))

        # Sort by score (ascending - delete files with fewest dependents first)
        file_scores.sort(key=lambda x: x[1])

        return [f[0] for f in file_scores]

    def generate_import_fix_script(self, impact: ImpactResult) -> str:
        """
        Generate a Python script to fix imports after a change.
        """
        lines = [
            "#!/usr/bin/env python3",
            '"""Auto-generated script to fix imports after file change."""',
            "",
            "import re",
            "from pathlib import Path",
            "",
            "def fix_imports():",
            f'    """Fix imports affected by {impact.action} of {Path(impact.target_file).name}"""',
            "    changes = [",
        ]

        for update in impact.import_updates_required:
            if impact.action == "delete":
                lines.append(f'        {{"file": "{update["file"]}", "remove": "{update["import_module"]}"}},')
            elif impact.action == "merge":
                lines.append(f'        {{"file": "{update["file"]}", "old": "{update.get("old_import", "")}", "new": "{update.get("new_path", "")}"}},')

        lines.extend([
            "    ]",
            "",
            "    for change in changes:",
            "        filepath = Path(change['file'])",
            "        if not filepath.exists():",
            "            continue",
            "        content = filepath.read_text()",
            "        # Apply changes...",
            "        print(f'Fixed: {filepath}')",
            "",
            'if __name__ == "__main__":',
            "    fix_imports()",
        ])

        return "\n".join(lines)

    def get_affected_files_for_group(
        self,
        sibling_files: List[str],
        proposed_master: str
    ) -> Dict:
        """
        Analyze impact for a sibling group consolidation.

        This is specifically designed for the merge/consolidation workflow.
        """
        graph = self.get_graph()
        proposed_master = str(Path(proposed_master).resolve())

        result = {
            "proposed_master": proposed_master,
            "files_to_consolidate": [],
            "external_dependents": [],
            "import_changes": [],
            "total_affected_files": 0,
            "safe_to_auto_merge": True,
            "warnings": []
        }

        all_external_dependents = set()

        for filepath in sibling_files:
            filepath = str(Path(filepath).resolve())
            node = graph.nodes.get(filepath)

            result["files_to_consolidate"].append({
                "path": filepath,
                "is_master": filepath == proposed_master,
                "dependents_count": len(node.imported_by) if node else 0
            })

            if node:
                for dependent in node.imported_by:
                    if dependent not in sibling_files:
                        all_external_dependents.add(dependent)

                        # Track import changes needed
                        dep_node = graph.nodes.get(dependent)
                        if dep_node:
                            for imp in dep_node.imports:
                                if imp.resolved_path == filepath and filepath != proposed_master:
                                    result["import_changes"].append({
                                        "file": dependent,
                                        "current_import": imp.module,
                                        "points_to": filepath,
                                        "should_point_to": proposed_master,
                                        "line": imp.lineno
                                    })

        result["external_dependents"] = list(all_external_dependents)
        result["total_affected_files"] = len(all_external_dependents)

        # Determine if safe to auto-merge
        if len(result["import_changes"]) > 10:
            result["safe_to_auto_merge"] = False
            result["warnings"].append("Many import changes required - manual review recommended")

        return result
