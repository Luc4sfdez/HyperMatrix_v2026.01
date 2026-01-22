"""
HyperMatrix v2026 - Code Metrics Calculator
Calculates various code quality metrics.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ComplexityMetrics:
    """Cyclomatic complexity metrics for a function."""
    name: str
    complexity: int
    lineno: int
    filepath: str
    risk_level: str = "low"  # low, moderate, high, very_high


@dataclass
class FileMetrics:
    """Metrics for a single file."""
    filepath: str
    lines_of_code: int = 0
    lines_blank: int = 0
    lines_comment: int = 0
    lines_total: int = 0
    functions_count: int = 0
    classes_count: int = 0
    imports_count: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    maintainability_index: float = 0.0


@dataclass
class ProjectMetrics:
    """Aggregate metrics for a project."""
    total_files: int = 0
    total_loc: int = 0
    total_blank: int = 0
    total_comments: int = 0
    total_functions: int = 0
    total_classes: int = 0
    avg_file_size: float = 0.0
    avg_complexity: float = 0.0
    high_complexity_functions: int = 0
    avg_maintainability: float = 0.0
    duplication_ratio: float = 0.0
    coupling_score: float = 0.0


@dataclass
class CouplingMetrics:
    """Coupling metrics between modules."""
    module: str
    afferent_coupling: int = 0  # Modules that depend on this
    efferent_coupling: int = 0  # Modules this depends on
    instability: float = 0.0    # Efferent / (Afferent + Efferent)
    abstractness: float = 0.0   # Abstract classes / Total classes
    distance_from_main: float = 0.0  # |A + I - 1|


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """AST visitor to calculate cyclomatic complexity."""

    def __init__(self):
        self.complexity = 1  # Base complexity

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
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

    def visit_IfExp(self, node):
        # Ternary expression
        self.complexity += 1
        self.generic_visit(node)

    def visit_Match(self, node):
        # Python 3.10+ match statement
        self.complexity += len(node.cases)
        self.generic_visit(node)


class MetricsCalculator:
    """Calculate code metrics."""

    COMPLEXITY_THRESHOLDS = {
        "low": (1, 5),
        "moderate": (6, 10),
        "high": (11, 20),
        "very_high": (21, float('inf')),
    }

    def __init__(self):
        self.file_metrics: list[FileMetrics] = []
        self.function_complexities: list[ComplexityMetrics] = []

    def analyze_file(self, filepath: str) -> Optional[FileMetrics]:
        """Analyze a single file."""
        path = Path(filepath)

        if not path.exists():
            return None

        # Check file type
        ext = path.suffix.lower()

        if ext == '.py':
            return self._analyze_python_file(filepath)
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            return self._analyze_js_file(filepath)
        else:
            return self._analyze_generic_file(filepath)

    def _analyze_python_file(self, filepath: str) -> FileMetrics:
        """Analyze a Python file."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.split('\n')

        # Count line types
        loc = 0
        blank = 0
        comments = 0
        in_multiline_string = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                blank += 1
                continue

            # Check for multiline strings (docstrings)
            if '"""' in stripped or "'''" in stripped:
                quotes = '"""' if '"""' in stripped else "'''"
                count = stripped.count(quotes)
                if count == 1:
                    in_multiline_string = not in_multiline_string
                comments += 1
                continue

            if in_multiline_string:
                comments += 1
                continue

            if stripped.startswith('#'):
                comments += 1
            else:
                loc += 1

        # Parse AST for complexity
        try:
            tree = ast.parse(content)
            complexities = self._calculate_complexity_python(tree, filepath)
            functions_count = len(complexities)
            classes_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            imports_count = sum(1 for node in ast.walk(tree)
                              if isinstance(node, (ast.Import, ast.ImportFrom)))

            avg_complexity = sum(c.complexity for c in complexities) / len(complexities) if complexities else 0
            max_complexity = max((c.complexity for c in complexities), default=0)

            self.function_complexities.extend(complexities)

        except SyntaxError:
            functions_count = 0
            classes_count = 0
            imports_count = 0
            avg_complexity = 0
            max_complexity = 0

        # Calculate maintainability index
        mi = self._calculate_maintainability_index(
            loc=loc,
            complexity=avg_complexity,
            comment_ratio=comments / (loc + comments) if (loc + comments) > 0 else 0,
        )

        metrics = FileMetrics(
            filepath=filepath,
            lines_of_code=loc,
            lines_blank=blank,
            lines_comment=comments,
            lines_total=len(lines),
            functions_count=functions_count,
            classes_count=classes_count,
            imports_count=imports_count,
            avg_complexity=avg_complexity,
            max_complexity=max_complexity,
            maintainability_index=mi,
        )

        self.file_metrics.append(metrics)
        return metrics

    def _calculate_complexity_python(self, tree: ast.AST, filepath: str) -> list[ComplexityMetrics]:
        """Calculate cyclomatic complexity for Python functions."""
        complexities = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visitor = CyclomaticComplexityVisitor()
                visitor.visit(node)

                risk = self._get_risk_level(visitor.complexity)

                metrics = ComplexityMetrics(
                    name=node.name,
                    complexity=visitor.complexity,
                    lineno=node.lineno,
                    filepath=filepath,
                    risk_level=risk,
                )
                complexities.append(metrics)

        return complexities

    def _get_risk_level(self, complexity: int) -> str:
        """Get risk level based on complexity."""
        for level, (low, high) in self.COMPLEXITY_THRESHOLDS.items():
            if low <= complexity <= high:
                return level
        return "very_high"

    def _analyze_js_file(self, filepath: str) -> FileMetrics:
        """Analyze a JavaScript/TypeScript file."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.split('\n')

        # Count line types
        loc = 0
        blank = 0
        comments = 0
        in_multiline_comment = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                blank += 1
                continue

            if in_multiline_comment:
                comments += 1
                if '*/' in stripped:
                    in_multiline_comment = False
                continue

            if stripped.startswith('/*'):
                comments += 1
                if '*/' not in stripped:
                    in_multiline_comment = True
                continue

            if stripped.startswith('//'):
                comments += 1
            else:
                loc += 1

        # Estimate complexity using regex
        complexity_patterns = [
            r'\bif\s*\(',
            r'\belse\s+if\s*\(',
            r'\bfor\s*\(',
            r'\bwhile\s*\(',
            r'\bswitch\s*\(',
            r'\bcatch\s*\(',
            r'\?\s*[^:]+\s*:',  # ternary
            r'\&\&',
            r'\|\|',
        ]

        total_complexity = 1
        for pattern in complexity_patterns:
            matches = re.findall(pattern, content)
            total_complexity += len(matches)

        # Count functions and classes
        functions_count = len(re.findall(r'\bfunction\s+\w+\s*\(|=>\s*\{?|(\w+)\s*\([^)]*\)\s*\{', content))
        classes_count = len(re.findall(r'\bclass\s+\w+', content))
        imports_count = len(re.findall(r'\bimport\s+', content))

        avg_complexity = total_complexity / functions_count if functions_count > 0 else total_complexity

        mi = self._calculate_maintainability_index(
            loc=loc,
            complexity=avg_complexity,
            comment_ratio=comments / (loc + comments) if (loc + comments) > 0 else 0,
        )

        metrics = FileMetrics(
            filepath=filepath,
            lines_of_code=loc,
            lines_blank=blank,
            lines_comment=comments,
            lines_total=len(lines),
            functions_count=functions_count,
            classes_count=classes_count,
            imports_count=imports_count,
            avg_complexity=avg_complexity,
            max_complexity=int(total_complexity),
            maintainability_index=mi,
        )

        self.file_metrics.append(metrics)
        return metrics

    def _analyze_generic_file(self, filepath: str) -> FileMetrics:
        """Analyze a generic text file."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.split('\n')

        loc = 0
        blank = 0

        for line in lines:
            if not line.strip():
                blank += 1
            else:
                loc += 1

        metrics = FileMetrics(
            filepath=filepath,
            lines_of_code=loc,
            lines_blank=blank,
            lines_comment=0,
            lines_total=len(lines),
            maintainability_index=100.0,  # Default for non-code files
        )

        self.file_metrics.append(metrics)
        return metrics

    def _calculate_maintainability_index(
        self,
        loc: int,
        complexity: float,
        comment_ratio: float,
    ) -> float:
        """
        Calculate Maintainability Index (0-100).
        Based on the Microsoft formula.
        """
        import math

        if loc == 0:
            return 100.0

        # Halstead Volume approximation (simplified)
        halstead_volume = loc * math.log2(loc + 1)

        # Original formula: 171 - 5.2*ln(V) - 0.23*G - 16.2*ln(L)
        # Normalized to 0-100 scale

        mi = 171 - 5.2 * math.log(halstead_volume + 1) - 0.23 * complexity - 16.2 * math.log(loc + 1)

        # Bonus for comments
        mi = mi + 50 * comment_ratio

        # Normalize to 0-100
        mi = max(0, min(100, mi * 100 / 171))

        return round(mi, 2)

    def get_project_metrics(self) -> ProjectMetrics:
        """Calculate aggregate project metrics."""
        if not self.file_metrics:
            return ProjectMetrics()

        total_loc = sum(f.lines_of_code for f in self.file_metrics)
        total_blank = sum(f.lines_blank for f in self.file_metrics)
        total_comments = sum(f.lines_comment for f in self.file_metrics)
        total_functions = sum(f.functions_count for f in self.file_metrics)
        total_classes = sum(f.classes_count for f in self.file_metrics)

        # High complexity functions
        high_complexity = sum(1 for c in self.function_complexities
                             if c.risk_level in ["high", "very_high"])

        # Average metrics
        avg_file_size = total_loc / len(self.file_metrics)
        avg_complexity = sum(f.avg_complexity for f in self.file_metrics) / len(self.file_metrics)
        avg_maintainability = sum(f.maintainability_index for f in self.file_metrics) / len(self.file_metrics)

        return ProjectMetrics(
            total_files=len(self.file_metrics),
            total_loc=total_loc,
            total_blank=total_blank,
            total_comments=total_comments,
            total_functions=total_functions,
            total_classes=total_classes,
            avg_file_size=round(avg_file_size, 2),
            avg_complexity=round(avg_complexity, 2),
            high_complexity_functions=high_complexity,
            avg_maintainability=round(avg_maintainability, 2),
        )

    def get_hotspots(self, top_n: int = 10) -> list[ComplexityMetrics]:
        """Get top N most complex functions."""
        sorted_complexities = sorted(
            self.function_complexities,
            key=lambda x: x.complexity,
            reverse=True
        )
        return sorted_complexities[:top_n]

    def get_maintainability_report(self) -> dict:
        """Get maintainability report grouped by risk level."""
        report = {
            "excellent": [],  # MI >= 80
            "good": [],       # 60 <= MI < 80
            "moderate": [],   # 40 <= MI < 60
            "poor": [],       # 20 <= MI < 40
            "critical": [],   # MI < 20
        }

        for f in self.file_metrics:
            mi = f.maintainability_index
            if mi >= 80:
                report["excellent"].append(f.filepath)
            elif mi >= 60:
                report["good"].append(f.filepath)
            elif mi >= 40:
                report["moderate"].append(f.filepath)
            elif mi >= 20:
                report["poor"].append(f.filepath)
            else:
                report["critical"].append(f.filepath)

        return report


class CouplingAnalyzer:
    """Analyze module coupling."""

    def __init__(self):
        self.dependencies: dict[str, set[str]] = {}  # module -> set of imports

    def add_module(self, module: str, imports: list[str]):
        """Add module and its imports."""
        self.dependencies[module] = set(imports)

    def calculate_coupling(self) -> list[CouplingMetrics]:
        """Calculate coupling metrics for all modules."""
        metrics = []

        for module in self.dependencies:
            # Efferent coupling (Ce) - modules this depends on
            efferent = len(self.dependencies[module])

            # Afferent coupling (Ca) - modules that depend on this
            afferent = sum(1 for deps in self.dependencies.values()
                         if module in deps or any(module in d for d in deps))

            # Instability I = Ce / (Ca + Ce)
            total = afferent + efferent
            instability = efferent / total if total > 0 else 0

            # Distance from main sequence |A + I - 1|
            # Assuming abstractness = 0 for simplicity
            distance = abs(0 + instability - 1)

            metrics.append(CouplingMetrics(
                module=module,
                afferent_coupling=afferent,
                efferent_coupling=efferent,
                instability=round(instability, 2),
                distance_from_main=round(distance, 2),
            ))

        return metrics


def calculate_file_metrics(filepath: str) -> Optional[FileMetrics]:
    """Convenience function to calculate metrics for a file."""
    calculator = MetricsCalculator()
    return calculator.analyze_file(filepath)


def calculate_project_metrics(filepaths: list[str]) -> ProjectMetrics:
    """Convenience function to calculate metrics for multiple files."""
    calculator = MetricsCalculator()
    for filepath in filepaths:
        calculator.analyze_file(filepath)
    return calculator.get_project_metrics()
