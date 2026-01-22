"""
HyperMatrix v2026 - Import Lineage Resolver
Resolves import dependencies and builds dependency graph.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from enum import Enum

from ..parsers import PythonParser, JavaScriptParser


class ImportType(Enum):
    """Type of import."""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    THIRD_PARTY = "third_party"
    BUILTIN = "builtin"
    LOCAL = "local"


@dataclass
class ResolvedImport:
    """A resolved import with its source."""
    module: str
    names: list[str]
    import_type: ImportType
    resolved_path: Optional[str] = None
    lineno: int = 0


@dataclass
class DependencyNode:
    """Node in dependency graph."""
    filepath: str
    imports: list[ResolvedImport] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    depth: int = 0


@dataclass
class DependencyGraph:
    """Complete dependency graph for a project."""
    nodes: dict[str, DependencyNode] = field(default_factory=dict)
    root_files: list[str] = field(default_factory=list)
    circular_deps: list[tuple[str, str]] = field(default_factory=list)


class LineageResolver:
    """Resolves import lineage and builds dependency graphs."""

    PYTHON_BUILTINS = {
        "os", "sys", "re", "json", "math", "datetime", "collections",
        "itertools", "functools", "pathlib", "typing", "dataclasses",
        "abc", "io", "logging", "unittest", "argparse", "subprocess",
        "threading", "multiprocessing", "asyncio", "socket", "http",
        "urllib", "email", "html", "xml", "sqlite3", "pickle", "copy",
        "enum", "contextlib", "hashlib", "random", "time", "calendar",
    }

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.python_parser = PythonParser()
        self.js_parser = JavaScriptParser()
        self._cache: dict[str, list[ResolvedImport]] = {}

    def resolve_python_import(
        self,
        module: str,
        source_file: str,
        is_from_import: bool = False,
    ) -> ResolvedImport:
        """Resolve a Python import to its source."""
        names = module.split(".")

        # Check if builtin
        if names[0] in self.PYTHON_BUILTINS:
            return ResolvedImport(
                module=module,
                names=names,
                import_type=ImportType.BUILTIN,
            )

        # Check if relative import
        if module.startswith("."):
            return self._resolve_relative_import(module, source_file)

        # Try to resolve as local import
        resolved_path = self._find_local_module(module, source_file)
        if resolved_path:
            return ResolvedImport(
                module=module,
                names=names,
                import_type=ImportType.LOCAL,
                resolved_path=str(resolved_path),
            )

        # Assume third-party
        return ResolvedImport(
            module=module,
            names=names,
            import_type=ImportType.THIRD_PARTY,
        )

    def _resolve_relative_import(
        self,
        module: str,
        source_file: str,
    ) -> ResolvedImport:
        """Resolve a relative import."""
        source_path = Path(source_file).resolve()
        source_dir = source_path.parent

        # Count leading dots
        dots = 0
        for char in module:
            if char == ".":
                dots += 1
            else:
                break

        # Go up directories
        target_dir = source_dir
        for _ in range(dots - 1):
            target_dir = target_dir.parent

        # Get module name after dots
        module_name = module[dots:]
        if module_name:
            parts = module_name.split(".")
            for part in parts[:-1]:
                target_dir = target_dir / part

            # Check for file or package
            target_file = target_dir / f"{parts[-1]}.py"
            target_package = target_dir / parts[-1] / "__init__.py"

            if target_file.exists():
                resolved_path = target_file
            elif target_package.exists():
                resolved_path = target_package
            else:
                resolved_path = None
        else:
            resolved_path = target_dir / "__init__.py"
            if not resolved_path.exists():
                resolved_path = None

        return ResolvedImport(
            module=module,
            names=module_name.split(".") if module_name else [],
            import_type=ImportType.RELATIVE,
            resolved_path=str(resolved_path) if resolved_path else None,
        )

    def _find_local_module(
        self,
        module: str,
        source_file: str,
    ) -> Optional[Path]:
        """Find a local module in the project."""
        parts = module.split(".")

        # Search from project root
        search_paths = [
            self.project_root,
            self.project_root / "src",
            Path(source_file).parent,
        ]

        for search_path in search_paths:
            # Try as package
            package_path = search_path
            for part in parts:
                package_path = package_path / part

            init_file = package_path / "__init__.py"
            if init_file.exists():
                return init_file

            # Try as module file
            if len(parts) > 1:
                module_path = search_path
                for part in parts[:-1]:
                    module_path = module_path / part
                module_file = module_path / f"{parts[-1]}.py"
            else:
                module_file = search_path / f"{parts[0]}.py"

            if module_file.exists():
                return module_file

        return None

    def resolve_js_import(
        self,
        module: str,
        source_file: str,
    ) -> ResolvedImport:
        """Resolve a JavaScript/TypeScript import."""
        source_path = Path(source_file).resolve()
        source_dir = source_path.parent

        # Check if relative import
        if module.startswith("."):
            resolved = self._resolve_js_relative(module, source_dir)
            return ResolvedImport(
                module=module,
                names=[module.split("/")[-1]],
                import_type=ImportType.RELATIVE if resolved else ImportType.LOCAL,
                resolved_path=resolved,
            )

        # Check if local alias (@/)
        if module.startswith("@/"):
            local_path = module.replace("@/", "")
            resolved = self._find_js_file(self.project_root / "src" / local_path)
            return ResolvedImport(
                module=module,
                names=[module.split("/")[-1]],
                import_type=ImportType.LOCAL,
                resolved_path=resolved,
            )

        # Assume third-party (node_modules)
        return ResolvedImport(
            module=module,
            names=[module.split("/")[0]],
            import_type=ImportType.THIRD_PARTY,
        )

    def _resolve_js_relative(
        self,
        module: str,
        source_dir: Path,
    ) -> Optional[str]:
        """Resolve a relative JS import."""
        target = source_dir / module
        resolved = self._find_js_file(target)
        return resolved

    def _find_js_file(self, base_path: Path) -> Optional[str]:
        """Find a JS/TS file with various extensions."""
        extensions = [".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.ts"]

        for ext in extensions:
            full_path = Path(str(base_path) + ext)
            if full_path.exists():
                return str(full_path)

        return None

    def build_dependency_graph(self, entry_files: list[str] = None) -> DependencyGraph:
        """Build complete dependency graph for the project."""
        graph = DependencyGraph()

        if entry_files:
            files_to_process = [Path(f).resolve() for f in entry_files]
        else:
            files_to_process = list(self.project_root.rglob("*.py"))

        graph.root_files = [str(f) for f in files_to_process]

        processed = set()
        queue = [(f, 0) for f in files_to_process]

        while queue:
            filepath, depth = queue.pop(0)
            filepath_str = str(filepath)

            if filepath_str in processed:
                continue

            processed.add(filepath_str)

            # Create node
            node = DependencyNode(filepath=filepath_str, depth=depth)

            # Parse file and resolve imports
            try:
                if filepath.suffix == ".py":
                    result = self.python_parser.parse_file(filepath_str)
                    for imp in result.imports:
                        resolved = self.resolve_python_import(
                            imp.module, filepath_str, imp.is_from_import
                        )
                        resolved.lineno = imp.lineno
                        node.imports.append(resolved)

                        # Add to queue if local
                        if resolved.resolved_path and resolved.import_type == ImportType.LOCAL:
                            dep_path = Path(resolved.resolved_path)
                            if dep_path not in processed:
                                queue.append((dep_path, depth + 1))

                                # Check for circular dependency
                                if filepath_str in graph.nodes:
                                    for existing_imp in graph.nodes[filepath_str].imports:
                                        if existing_imp.resolved_path == resolved.resolved_path:
                                            graph.circular_deps.append(
                                                (filepath_str, resolved.resolved_path)
                                            )

            except Exception:
                pass  # Skip files that can't be parsed

            graph.nodes[filepath_str] = node

        # Build imported_by relationships
        for filepath, node in graph.nodes.items():
            for imp in node.imports:
                if imp.resolved_path and imp.resolved_path in graph.nodes:
                    graph.nodes[imp.resolved_path].imported_by.append(filepath)

        return graph

    def get_import_chain(
        self,
        graph: DependencyGraph,
        from_file: str,
        to_file: str,
    ) -> list[str]:
        """Find import chain between two files."""
        from_file = str(Path(from_file).resolve())
        to_file = str(Path(to_file).resolve())

        if from_file not in graph.nodes or to_file not in graph.nodes:
            return []

        # BFS to find path
        visited = {from_file}
        queue = [(from_file, [from_file])]

        while queue:
            current, path = queue.pop(0)

            if current == to_file:
                return path

            node = graph.nodes.get(current)
            if not node:
                continue

            for imp in node.imports:
                if imp.resolved_path and imp.resolved_path not in visited:
                    visited.add(imp.resolved_path)
                    queue.append((imp.resolved_path, path + [imp.resolved_path]))

        return []

    def get_dependents(self, graph: DependencyGraph, filepath: str) -> list[str]:
        """Get all files that depend on a given file."""
        filepath = str(Path(filepath).resolve())
        node = graph.nodes.get(filepath)
        return node.imported_by if node else []

    def get_dependencies(self, graph: DependencyGraph, filepath: str) -> list[str]:
        """Get all files that a given file depends on."""
        filepath = str(Path(filepath).resolve())
        node = graph.nodes.get(filepath)
        if not node:
            return []

        return [
            imp.resolved_path for imp in node.imports
            if imp.resolved_path and imp.import_type == ImportType.LOCAL
        ]
