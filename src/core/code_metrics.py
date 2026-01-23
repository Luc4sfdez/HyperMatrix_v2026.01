"""
HyperMatrix v2026 - Code Metrics Calculator
Calculates code quality metrics like cyclomatic complexity, documentation coverage, etc.
"""

import ast
import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class FunctionMetrics:
    """Metrics for a single function."""
    name: str
    lineno: int
    lines: int
    complexity: int  # Cyclomatic complexity
    has_docstring: bool
    parameters: int
    nested_depth: int


@dataclass
class FileMetrics:
    """Metrics for a single file."""
    filepath: str
    lines_total: int
    lines_code: int
    lines_comment: int
    lines_blank: int
    functions: List[FunctionMetrics]
    classes: int
    imports: int
    avg_complexity: float
    max_complexity: int
    doc_coverage: float  # Percentage of functions with docstrings
    tech_debt_score: float  # 0-100, higher is worse


@dataclass
class ProjectMetrics:
    """Aggregated metrics for a project."""
    total_files: int
    total_lines: int
    total_functions: int
    total_classes: int
    avg_complexity: float
    max_complexity: int
    max_complexity_file: str
    doc_coverage: float
    tech_debt_score: float
    hotspots: List[Dict]  # Files with high complexity
    circular_deps: List[Tuple[str, str]]  # Pairs of circular imports
    files_by_complexity: List[Dict]


class ComplexityVisitor(ast.NodeVisitor):
    """AST visitor to calculate cyclomatic complexity."""

    def __init__(self):
        self.complexity = 1  # Base complexity
        self.nested_depth = 0
        self.max_depth = 0

    def visit_If(self, node):
        self.complexity += 1
        self._check_depth(node)
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self._check_depth(node)
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self._check_depth(node)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self._check_depth(node)
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # Each 'and' or 'or' adds to complexity
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def _check_depth(self, node):
        """Track nesting depth."""
        self.nested_depth += 1
        self.max_depth = max(self.max_depth, self.nested_depth)
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self.nested_depth -= 1


def calculate_function_complexity(node: ast.FunctionDef) -> Tuple[int, int]:
    """Calculate cyclomatic complexity and max nesting for a function."""
    visitor = ComplexityVisitor()
    visitor.visit(node)
    return visitor.complexity, visitor.max_depth


def has_docstring(node) -> bool:
    """Check if a function or class has a docstring."""
    if not node.body:
        return False
    first = node.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, (ast.Str, ast.Constant)):
        if isinstance(first.value, ast.Constant):
            return isinstance(first.value.value, str)
        return True
    return False


def count_lines(content: str) -> Tuple[int, int, int, int]:
    """Count total, code, comment, and blank lines."""
    lines = content.split('\n')
    total = len(lines)
    blank = 0
    comment = 0
    code = 0

    in_multiline_string = False
    multiline_char = None

    for line in lines:
        stripped = line.strip()

        if not stripped:
            blank += 1
            continue

        # Handle multiline strings
        if in_multiline_string:
            if multiline_char in stripped:
                in_multiline_string = False
            comment += 1  # Count as comment-like
            continue

        if stripped.startswith('"""') or stripped.startswith("'''"):
            multiline_char = stripped[:3]
            if stripped.count(multiline_char) == 1:
                in_multiline_string = True
            comment += 1
            continue

        if stripped.startswith('#'):
            comment += 1
        else:
            code += 1

    return total, code, comment, blank


def calculate_tech_debt(
    avg_complexity: float,
    max_complexity: int,
    doc_coverage: float,
    lines_code: int
) -> float:
    """
    Calculate a technical debt score (0-100, higher is worse).

    Factors:
    - High cyclomatic complexity
    - Low documentation coverage
    - Very large files
    """
    score = 0.0

    # Complexity factor (0-40 points)
    if avg_complexity > 10:
        score += min(40, (avg_complexity - 10) * 4)
    elif avg_complexity > 5:
        score += (avg_complexity - 5) * 2

    # Max complexity penalty (0-20 points)
    if max_complexity > 20:
        score += min(20, (max_complexity - 20))
    elif max_complexity > 10:
        score += (max_complexity - 10) * 0.5

    # Documentation coverage (0-25 points)
    if doc_coverage < 0.5:
        score += (0.5 - doc_coverage) * 50  # 0% coverage = +25

    # File size penalty (0-15 points)
    if lines_code > 500:
        score += min(15, (lines_code - 500) / 100)

    return min(100, max(0, score))


def analyze_file_metrics(filepath: str) -> Optional[FileMetrics]:
    """Analyze a single Python file and return its metrics."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        logger.debug(f"Could not read {filepath}: {e}")
        return None

    try:
        tree = ast.parse(content)
    except SyntaxError:
        logger.debug(f"Syntax error in {filepath}")
        return None

    # Count lines
    total, code, comment, blank = count_lines(content)

    # Analyze functions
    functions = []
    classes = 0
    imports = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports += len(node.names)
        elif isinstance(node, ast.ImportFrom):
            imports += len(node.names) if node.names else 1
        elif isinstance(node, ast.ClassDef):
            classes += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity, depth = calculate_function_complexity(node)
            end_lineno = getattr(node, 'end_lineno', node.lineno + 10)
            func_lines = end_lineno - node.lineno + 1

            functions.append(FunctionMetrics(
                name=node.name,
                lineno=node.lineno,
                lines=func_lines,
                complexity=complexity,
                has_docstring=has_docstring(node),
                parameters=len(node.args.args),
                nested_depth=depth,
            ))

    # Calculate aggregates
    if functions:
        avg_complexity = sum(f.complexity for f in functions) / len(functions)
        max_complexity = max(f.complexity for f in functions)
        doc_coverage = sum(1 for f in functions if f.has_docstring) / len(functions)
    else:
        avg_complexity = 1.0
        max_complexity = 1
        doc_coverage = 1.0  # No functions = full coverage

    tech_debt = calculate_tech_debt(avg_complexity, max_complexity, doc_coverage, code)

    return FileMetrics(
        filepath=filepath,
        lines_total=total,
        lines_code=code,
        lines_comment=comment,
        lines_blank=blank,
        functions=functions,
        classes=classes,
        imports=imports,
        avg_complexity=round(avg_complexity, 2),
        max_complexity=max_complexity,
        doc_coverage=round(doc_coverage, 2),
        tech_debt_score=round(tech_debt, 1),
    )


def detect_circular_imports(filepaths: List[str], root_path: str) -> List[Tuple[str, str]]:
    """
    Detect potential circular imports in a set of Python files.

    Returns pairs of files that import each other.
    """
    # Build import graph
    imports_graph: Dict[str, Set[str]] = defaultdict(set)
    root = Path(root_path)

    for filepath in filepaths:
        if not filepath.endswith('.py'):
            continue

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content)
        except Exception:
            continue

        rel_path = str(Path(filepath).relative_to(root))
        module_name = rel_path.replace('/', '.').replace('\\', '.').replace('.py', '')

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports_graph[module_name].add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports_graph[module_name].add(node.module.split('.')[0])

    # Find cycles (simple A->B and B->A detection)
    circular = []
    checked = set()

    for module_a, imports_a in imports_graph.items():
        for imported in imports_a:
            if imported in imports_graph:
                if module_a.split('.')[0] in imports_graph[imported]:
                    pair = tuple(sorted([module_a, imported]))
                    if pair not in checked:
                        checked.add(pair)
                        circular.append(pair)

    return circular


def analyze_project_metrics(
    root_path: str,
    filepaths: Optional[List[str]] = None,
    max_files: int = 500
) -> ProjectMetrics:
    """
    Analyze metrics for an entire project.

    Args:
        root_path: Project root directory
        filepaths: Optional list of file paths to analyze
        max_files: Maximum number of files to process

    Returns:
        ProjectMetrics with aggregated data
    """
    root = Path(root_path)

    # Get Python files if not provided
    if filepaths is None:
        filepaths = []
        for pyfile in root.rglob('*.py'):
            # Skip common non-source directories
            parts = pyfile.parts
            if any(skip in parts for skip in ['node_modules', '.git', 'venv', '.venv', '__pycache__', 'dist', 'build']):
                continue
            filepaths.append(str(pyfile))
            if len(filepaths) >= max_files:
                break

    # Analyze each file
    file_metrics: List[FileMetrics] = []
    for filepath in filepaths[:max_files]:
        if filepath.endswith('.py'):
            metrics = analyze_file_metrics(filepath)
            if metrics:
                file_metrics.append(metrics)

    if not file_metrics:
        return ProjectMetrics(
            total_files=0,
            total_lines=0,
            total_functions=0,
            total_classes=0,
            avg_complexity=0,
            max_complexity=0,
            max_complexity_file="",
            doc_coverage=0,
            tech_debt_score=0,
            hotspots=[],
            circular_deps=[],
            files_by_complexity=[],
        )

    # Aggregate metrics
    total_lines = sum(m.lines_code for m in file_metrics)
    total_functions = sum(len(m.functions) for m in file_metrics)
    total_classes = sum(m.classes for m in file_metrics)

    all_complexities = [f.complexity for m in file_metrics for f in m.functions]
    avg_complexity = sum(all_complexities) / len(all_complexities) if all_complexities else 1
    max_complexity = max(all_complexities) if all_complexities else 1

    # Find file with max complexity
    max_complexity_file = ""
    for m in file_metrics:
        for f in m.functions:
            if f.complexity == max_complexity:
                max_complexity_file = m.filepath
                break

    # Documentation coverage
    total_with_docs = sum(1 for m in file_metrics for f in m.functions if f.has_docstring)
    doc_coverage = total_with_docs / total_functions if total_functions > 0 else 1.0

    # Tech debt
    avg_debt = sum(m.tech_debt_score for m in file_metrics) / len(file_metrics)

    # Hotspots (high complexity files)
    hotspots = sorted(
        [
            {
                "filepath": m.filepath,
                "complexity": m.avg_complexity,
                "max_complexity": m.max_complexity,
                "functions": len(m.functions),
                "tech_debt": m.tech_debt_score,
            }
            for m in file_metrics
            if m.avg_complexity > 5 or m.max_complexity > 10
        ],
        key=lambda x: x["max_complexity"],
        reverse=True
    )[:10]

    # Circular dependencies
    circular = detect_circular_imports(filepaths, root_path)

    # Files sorted by complexity
    files_by_complexity = sorted(
        [
            {
                "filepath": str(Path(m.filepath).relative_to(root)) if m.filepath.startswith(str(root)) else m.filepath,
                "avg_complexity": m.avg_complexity,
                "max_complexity": m.max_complexity,
                "doc_coverage": m.doc_coverage,
                "tech_debt": m.tech_debt_score,
                "lines": m.lines_code,
            }
            for m in file_metrics
        ],
        key=lambda x: x["max_complexity"],
        reverse=True
    )[:20]

    return ProjectMetrics(
        total_files=len(file_metrics),
        total_lines=total_lines,
        total_functions=total_functions,
        total_classes=total_classes,
        avg_complexity=round(avg_complexity, 2),
        max_complexity=max_complexity,
        max_complexity_file=max_complexity_file,
        doc_coverage=round(doc_coverage, 2),
        tech_debt_score=round(avg_debt, 1),
        hotspots=hotspots,
        circular_deps=circular,
        files_by_complexity=files_by_complexity,
    )
