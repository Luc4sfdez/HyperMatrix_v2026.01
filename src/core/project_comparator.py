"""
HyperMatrix v2026 - Project Comparator
Compares code across different projects to find shared/duplicated code.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class FileMatch:
    """A match between files in different projects."""
    project1_file: str
    project2_file: str
    project1_name: str
    project2_name: str
    similarity: float
    match_type: str  # 'exact', 'similar', 'partial'
    common_lines: int
    differences: List[str] = field(default_factory=list)


@dataclass
class FunctionMatch:
    """A match between functions across projects."""
    project1_file: str
    project1_function: str
    project2_file: str
    project2_function: str
    similarity: float
    is_exact: bool


@dataclass
class ProjectComparisonReport:
    """Report comparing two or more projects."""
    project_names: List[str]
    project_paths: List[str]
    total_files: Dict[str, int]
    exact_matches: List[FileMatch]
    similar_matches: List[FileMatch]
    shared_code_ratio: Dict[str, float]  # Per project
    unique_files: Dict[str, List[str]]
    common_patterns: List[Dict]
    function_matches: List[FunctionMatch]
    summary: Dict


@dataclass
class ProjectSnapshot:
    """Snapshot of a project's code for comparison."""
    name: str
    path: str
    files: Dict[str, str]  # relative_path -> content_hash
    contents: Dict[str, str]  # relative_path -> content (for similar matching)
    functions: Dict[str, List[Dict]]  # file -> list of functions


class ProjectComparator:
    """
    Compares code across different projects.

    Features:
    - Find exact duplicate files
    - Find similar files (above threshold)
    - Detect shared code patterns
    - Compare function-level similarities
    - Track code migration between projects
    """

    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
        self._snapshots: Dict[str, ProjectSnapshot] = {}

    def create_snapshot(
        self,
        project_path: str,
        project_name: str,
        extensions: List[str] = None
    ) -> ProjectSnapshot:
        """
        Create a snapshot of a project for comparison.

        Args:
            project_path: Root path of the project
            project_name: Name identifier for the project
            extensions: File extensions to include (default: ['.py'])

        Returns:
            ProjectSnapshot containing file hashes and contents
        """
        if extensions is None:
            extensions = ['.py']

        root = Path(project_path)
        if not root.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        files: Dict[str, str] = {}
        contents: Dict[str, str] = {}
        functions: Dict[str, List[Dict]] = {}

        for ext in extensions:
            for filepath in root.rglob(f"*{ext}"):
                # Skip common non-code directories
                if any(p in filepath.parts for p in [
                    '__pycache__', '.git', 'node_modules', '.venv', 'venv',
                    'dist', 'build', '.pytest_cache'
                ]):
                    continue

                try:
                    content = filepath.read_text(encoding='utf-8', errors='ignore')
                    relative = str(filepath.relative_to(root))

                    # Store hash
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    files[relative] = content_hash

                    # Store content for similar matching
                    contents[relative] = content

                    # Extract functions for Python files
                    if ext == '.py':
                        funcs = self._extract_functions(content)
                        if funcs:
                            functions[relative] = funcs

                except Exception as e:
                    logger.debug(f"Error reading {filepath}: {e}")

        snapshot = ProjectSnapshot(
            name=project_name,
            path=str(root),
            files=files,
            contents=contents,
            functions=functions,
        )

        self._snapshots[project_name] = snapshot
        return snapshot

    def compare_projects(
        self,
        project1: str,
        project2: str,
        deep_compare: bool = True
    ) -> ProjectComparisonReport:
        """
        Compare two projects.

        Args:
            project1: Name or path of first project
            project2: Name or path of second project
            deep_compare: If True, do function-level comparison

        Returns:
            ProjectComparisonReport with all matches
        """
        # Get or create snapshots
        snap1 = self._get_snapshot(project1)
        snap2 = self._get_snapshot(project2)

        # Find exact matches (same hash)
        exact_matches = self._find_exact_matches(snap1, snap2)

        # Find similar matches
        similar_matches = self._find_similar_matches(snap1, snap2, exact_matches)

        # Find function-level matches
        function_matches = []
        if deep_compare:
            function_matches = self._find_function_matches(snap1, snap2)

        # Calculate unique files
        exact_files_1 = {m.project1_file for m in exact_matches}
        exact_files_2 = {m.project2_file for m in exact_matches}
        similar_files_1 = {m.project1_file for m in similar_matches}
        similar_files_2 = {m.project2_file for m in similar_matches}

        unique_files = {
            snap1.name: [
                f for f in snap1.files.keys()
                if f not in exact_files_1 and f not in similar_files_1
            ],
            snap2.name: [
                f for f in snap2.files.keys()
                if f not in exact_files_2 and f not in similar_files_2
            ],
        }

        # Calculate shared code ratios
        shared_ratio = {
            snap1.name: (len(exact_files_1) + len(similar_files_1)) / len(snap1.files)
            if snap1.files else 0.0,
            snap2.name: (len(exact_files_2) + len(similar_files_2)) / len(snap2.files)
            if snap2.files else 0.0,
        }

        # Detect common patterns
        common_patterns = self._detect_common_patterns(snap1, snap2)

        return ProjectComparisonReport(
            project_names=[snap1.name, snap2.name],
            project_paths=[snap1.path, snap2.path],
            total_files={snap1.name: len(snap1.files), snap2.name: len(snap2.files)},
            exact_matches=exact_matches,
            similar_matches=similar_matches,
            shared_code_ratio=shared_ratio,
            unique_files=unique_files,
            common_patterns=common_patterns,
            function_matches=function_matches,
            summary={
                'exact_matches': len(exact_matches),
                'similar_matches': len(similar_matches),
                'function_matches': len(function_matches),
                'unique_in_project1': len(unique_files[snap1.name]),
                'unique_in_project2': len(unique_files[snap2.name]),
                'shared_ratio_avg': (shared_ratio[snap1.name] + shared_ratio[snap2.name]) / 2,
            }
        )

    def compare_multiple_projects(
        self,
        projects: List[Tuple[str, str]]  # List of (path, name) tuples
    ) -> Dict[str, ProjectComparisonReport]:
        """
        Compare multiple projects pairwise.

        Returns:
            Dict with keys like "project1_vs_project2" and comparison reports
        """
        reports = {}

        # Create snapshots for all projects
        for path, name in projects:
            if name not in self._snapshots:
                self.create_snapshot(path, name)

        # Compare pairwise
        project_names = [name for _, name in projects]
        for i, name1 in enumerate(project_names):
            for name2 in project_names[i + 1:]:
                key = f"{name1}_vs_{name2}"
                reports[key] = self.compare_projects(name1, name2)

        return reports

    def find_code_origin(
        self,
        file_path: str,
        search_projects: List[str]
    ) -> List[Dict]:
        """
        Find where code might have originated from.

        Args:
            file_path: Path to the file to trace
            search_projects: Project names to search in

        Returns:
            List of potential origin matches
        """
        try:
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            content_hash = hashlib.sha256(content.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return []

        origins = []

        for project_name in search_projects:
            if project_name not in self._snapshots:
                continue

            snapshot = self._snapshots[project_name]

            # Check for exact match
            for rel_path, hash_val in snapshot.files.items():
                if hash_val == content_hash:
                    origins.append({
                        'project': project_name,
                        'file': rel_path,
                        'match_type': 'exact',
                        'similarity': 1.0,
                    })

            # Check for similar matches
            for rel_path, snap_content in snapshot.contents.items():
                similarity = self._calculate_similarity(content, snap_content)
                if similarity >= self.similarity_threshold:
                    # Avoid duplicating exact matches
                    if not any(o['file'] == rel_path and o['project'] == project_name
                              for o in origins):
                        origins.append({
                            'project': project_name,
                            'file': rel_path,
                            'match_type': 'similar',
                            'similarity': similarity,
                        })

        # Sort by similarity descending
        return sorted(origins, key=lambda x: x['similarity'], reverse=True)

    def _get_snapshot(self, project: str) -> ProjectSnapshot:
        """Get snapshot by name or create from path."""
        if project in self._snapshots:
            return self._snapshots[project]

        # Treat as path
        path = Path(project)
        if path.exists():
            name = path.name
            return self.create_snapshot(str(path), name)

        raise ValueError(f"Project not found: {project}")

    def _find_exact_matches(
        self,
        snap1: ProjectSnapshot,
        snap2: ProjectSnapshot
    ) -> List[FileMatch]:
        """Find files with identical content."""
        matches = []

        # Create hash to files mapping for snap2
        hash_to_files: Dict[str, List[str]] = defaultdict(list)
        for rel_path, content_hash in snap2.files.items():
            hash_to_files[content_hash].append(rel_path)

        # Find matches
        for rel_path1, content_hash in snap1.files.items():
            if content_hash in hash_to_files:
                for rel_path2 in hash_to_files[content_hash]:
                    matches.append(FileMatch(
                        project1_file=rel_path1,
                        project2_file=rel_path2,
                        project1_name=snap1.name,
                        project2_name=snap2.name,
                        similarity=1.0,
                        match_type='exact',
                        common_lines=snap1.contents[rel_path1].count('\n') + 1,
                    ))

        return matches

    def _find_similar_matches(
        self,
        snap1: ProjectSnapshot,
        snap2: ProjectSnapshot,
        exact_matches: List[FileMatch]
    ) -> List[FileMatch]:
        """Find files with similar content."""
        matches = []

        # Get files already matched exactly
        exact_pairs = {(m.project1_file, m.project2_file) for m in exact_matches}

        # Compare files with same name first (most likely matches)
        name_to_files1: Dict[str, List[str]] = defaultdict(list)
        name_to_files2: Dict[str, List[str]] = defaultdict(list)

        for rel_path in snap1.files:
            name_to_files1[Path(rel_path).name].append(rel_path)
        for rel_path in snap2.files:
            name_to_files2[Path(rel_path).name].append(rel_path)

        # Compare same-named files
        for filename in set(name_to_files1.keys()) & set(name_to_files2.keys()):
            for path1 in name_to_files1[filename]:
                for path2 in name_to_files2[filename]:
                    if (path1, path2) in exact_pairs:
                        continue

                    content1 = snap1.contents.get(path1, '')
                    content2 = snap2.contents.get(path2, '')

                    similarity = self._calculate_similarity(content1, content2)

                    if similarity >= self.similarity_threshold:
                        # Calculate common lines
                        lines1 = set(content1.split('\n'))
                        lines2 = set(content2.split('\n'))
                        common = len(lines1 & lines2)

                        # Get differences
                        differences = self._get_differences(content1, content2)

                        matches.append(FileMatch(
                            project1_file=path1,
                            project2_file=path2,
                            project1_name=snap1.name,
                            project2_name=snap2.name,
                            similarity=similarity,
                            match_type='similar' if similarity >= 0.9 else 'partial',
                            common_lines=common,
                            differences=differences[:5],  # Top 5 differences
                        ))

        return matches

    def _find_function_matches(
        self,
        snap1: ProjectSnapshot,
        snap2: ProjectSnapshot
    ) -> List[FunctionMatch]:
        """Find matching functions across projects."""
        matches = []

        # Build function index for snap2
        func_index: Dict[str, List[Tuple[str, Dict]]] = defaultdict(list)
        for file_path, functions in snap2.functions.items():
            for func in functions:
                func_index[func['name']].append((file_path, func))

        # Find matches
        for file_path1, functions1 in snap1.functions.items():
            for func1 in functions1:
                # Check same-named functions
                if func1['name'] in func_index:
                    for file_path2, func2 in func_index[func1['name']]:
                        similarity = self._compare_functions(func1, func2)
                        if similarity >= self.similarity_threshold:
                            matches.append(FunctionMatch(
                                project1_file=file_path1,
                                project1_function=func1['name'],
                                project2_file=file_path2,
                                project2_function=func2['name'],
                                similarity=similarity,
                                is_exact=similarity >= 0.99,
                            ))

        return matches

    def _extract_functions(self, content: str) -> List[Dict]:
        """Extract function signatures from Python code."""
        import ast
        functions = []

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_source = ast.get_source_segment(content, node) or ""
                    functions.append({
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'lineno': node.lineno,
                        'source_hash': hashlib.md5(func_source.encode()).hexdigest(),
                        'body_lines': (node.end_lineno or node.lineno) - node.lineno + 1,
                    })
        except SyntaxError:
            pass

        return functions

    def _compare_functions(self, func1: Dict, func2: Dict) -> float:
        """Compare two functions for similarity."""
        # Same hash = exact match
        if func1.get('source_hash') == func2.get('source_hash'):
            return 1.0

        # Compare arguments
        args1 = set(func1.get('args', []))
        args2 = set(func2.get('args', []))

        if args1 and args2:
            arg_similarity = len(args1 & args2) / len(args1 | args2)
        else:
            arg_similarity = 1.0 if args1 == args2 else 0.5

        # Compare size
        lines1 = func1.get('body_lines', 0)
        lines2 = func2.get('body_lines', 0)
        size_similarity = 1.0 - abs(lines1 - lines2) / max(lines1, lines2, 1)

        return (arg_similarity + size_similarity) / 2

    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two strings."""
        if not content1 and not content2:
            return 1.0
        if not content1 or not content2:
            return 0.0

        return SequenceMatcher(None, content1, content2).ratio()

    def _get_differences(self, content1: str, content2: str) -> List[str]:
        """Get main differences between two contents."""
        lines1 = set(content1.split('\n'))
        lines2 = set(content2.split('\n'))

        only_in_1 = lines1 - lines2
        only_in_2 = lines2 - lines1

        differences = []
        for line in list(only_in_1)[:3]:
            if line.strip():
                differences.append(f"- {line[:100]}")
        for line in list(only_in_2)[:3]:
            if line.strip():
                differences.append(f"+ {line[:100]}")

        return differences

    def _detect_common_patterns(
        self,
        snap1: ProjectSnapshot,
        snap2: ProjectSnapshot
    ) -> List[Dict]:
        """Detect common coding patterns between projects."""
        patterns = []

        # Detect common imports
        imports1 = self._extract_imports(snap1)
        imports2 = self._extract_imports(snap2)
        common_imports = imports1 & imports2

        if common_imports:
            patterns.append({
                'type': 'common_imports',
                'description': 'Shared library dependencies',
                'items': list(common_imports)[:20],
                'count': len(common_imports),
            })

        # Detect common class names
        classes1 = self._extract_class_names(snap1)
        classes2 = self._extract_class_names(snap2)
        common_classes = classes1 & classes2

        if common_classes:
            patterns.append({
                'type': 'common_classes',
                'description': 'Classes with same names',
                'items': list(common_classes),
                'count': len(common_classes),
            })

        return patterns

    def _extract_imports(self, snapshot: ProjectSnapshot) -> Set[str]:
        """Extract all import statements from a project."""
        imports = set()

        for content in snapshot.contents.values():
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    # Extract module name
                    if line.startswith('from '):
                        parts = line.split()
                        if len(parts) >= 2:
                            imports.add(parts[1].split('.')[0])
                    else:
                        parts = line.replace('import ', '').split(',')
                        for part in parts:
                            imports.add(part.strip().split('.')[0].split(' ')[0])

        return imports

    def _extract_class_names(self, snapshot: ProjectSnapshot) -> Set[str]:
        """Extract all class names from a project."""
        classes = set()

        for content in snapshot.contents.values():
            import ast
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.add(node.name)
            except SyntaxError:
                pass

        return classes
