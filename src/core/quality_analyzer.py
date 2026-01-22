"""
HyperMatrix v2026 - Quality Analyzer
Evaluates code quality metrics for better master file selection.
"""

import ast
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Comprehensive quality metrics for a file."""
    filepath: str

    # Documentation metrics
    has_module_docstring: bool = False
    docstring_coverage: float = 0.0  # Percentage of functions/classes with docstrings
    comment_ratio: float = 0.0  # Comments / total lines

    # Type safety
    has_type_hints: bool = False
    type_hint_coverage: float = 0.0  # Percentage of functions with type hints
    uses_typing_module: bool = False

    # Testing
    has_tests: bool = False
    test_coverage_estimate: float = 0.0  # Based on test file presence
    testable_functions: int = 0

    # Code structure
    function_count: int = 0
    class_count: int = 0
    avg_function_length: float = 0.0
    max_function_length: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0

    # Maintainability
    maintainability_index: float = 0.0
    lines_of_code: int = 0
    blank_lines: int = 0
    comment_lines: int = 0

    # Code smells
    code_smells: List[str] = field(default_factory=list)
    long_functions: List[str] = field(default_factory=list)
    complex_functions: List[str] = field(default_factory=list)

    # Error handling
    has_error_handling: bool = False
    try_except_count: int = 0

    # Final score
    quality_score: float = 0.0


@dataclass
class QualityComparison:
    """Comparison of quality between multiple files."""
    files: List[QualityMetrics]
    best_quality_file: str
    quality_rankings: List[Dict]
    recommendation: str
    confidence: float


class QualityAnalyzer:
    """
    Analyzes code quality to inform master file selection.

    Quality factors considered:
    - Documentation (docstrings, comments)
    - Type hints coverage
    - Test presence
    - Code complexity
    - Maintainability index
    - Code smells
    """

    # Thresholds for code smells
    MAX_FUNCTION_LENGTH = 50
    MAX_COMPLEXITY = 10
    MAX_ARGS = 5

    def __init__(self):
        self._test_file_patterns = [
            r"test_.*\.py$",
            r".*_test\.py$",
            r"tests?/.*\.py$",
            r"spec_.*\.py$",
        ]

    def analyze_file(self, filepath: str) -> QualityMetrics:
        """
        Analyze a single file and return quality metrics.
        """
        path = Path(filepath)
        metrics = QualityMetrics(filepath=filepath)

        if not path.exists() or path.suffix != ".py":
            return metrics

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            tree = ast.parse(content)
        except SyntaxError:
            metrics.code_smells.append("SYNTAX_ERROR: File has syntax errors")
            return metrics
        except Exception as e:
            metrics.code_smells.append(f"PARSE_ERROR: {str(e)}")
            return metrics

        # Basic line counts
        metrics.lines_of_code = len([l for l in lines if l.strip() and not l.strip().startswith("#")])
        metrics.blank_lines = len([l for l in lines if not l.strip()])
        metrics.comment_lines = len([l for l in lines if l.strip().startswith("#")])

        if metrics.lines_of_code > 0:
            metrics.comment_ratio = metrics.comment_lines / metrics.lines_of_code

        # Analyze AST
        self._analyze_ast(tree, content, metrics)

        # Check for tests
        metrics.has_tests = self._check_for_tests(filepath)

        # Calculate maintainability index
        metrics.maintainability_index = self._calculate_maintainability(metrics)

        # Calculate final quality score
        metrics.quality_score = self._calculate_quality_score(metrics)

        return metrics

    def _analyze_ast(self, tree: ast.AST, content: str, metrics: QualityMetrics):
        """Analyze AST for various metrics."""
        functions = []
        classes = []
        has_typing_import = False

        for node in ast.walk(tree):
            # Check module docstring
            if isinstance(node, ast.Module):
                metrics.has_module_docstring = ast.get_docstring(node) is not None

            # Analyze functions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = self._analyze_function(node, content)
                functions.append(func_info)

                # Check for type hints
                if func_info["has_return_hint"] or func_info["has_arg_hints"]:
                    metrics.has_type_hints = True

                # Check for docstring
                if not func_info["has_docstring"]:
                    pass  # Count later

                # Check for code smells
                if func_info["length"] > self.MAX_FUNCTION_LENGTH:
                    metrics.long_functions.append(func_info["name"])
                    metrics.code_smells.append(f"LONG_FUNCTION: {func_info['name']} ({func_info['length']} lines)")

                if func_info["complexity"] > self.MAX_COMPLEXITY:
                    metrics.complex_functions.append(func_info["name"])
                    metrics.code_smells.append(f"HIGH_COMPLEXITY: {func_info['name']} (complexity {func_info['complexity']})")

                if func_info["arg_count"] > self.MAX_ARGS:
                    metrics.code_smells.append(f"TOO_MANY_ARGS: {func_info['name']} ({func_info['arg_count']} args)")

            # Analyze classes
            elif isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node)
                classes.append(class_info)

            # Check for typing import
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "typing" or alias.name.startswith("typing."):
                        has_typing_import = True

            elif isinstance(node, ast.ImportFrom):
                if node.module == "typing":
                    has_typing_import = True

            # Check for error handling
            elif isinstance(node, ast.Try):
                metrics.has_error_handling = True
                metrics.try_except_count += 1

        # Calculate aggregates
        metrics.function_count = len(functions)
        metrics.class_count = len(classes)
        metrics.uses_typing_module = has_typing_import

        if functions:
            metrics.avg_function_length = sum(f["length"] for f in functions) / len(functions)
            metrics.max_function_length = max(f["length"] for f in functions)
            metrics.avg_complexity = sum(f["complexity"] for f in functions) / len(functions)
            metrics.max_complexity = max(f["complexity"] for f in functions)
            metrics.testable_functions = len([f for f in functions if not f["name"].startswith("_")])

            # Docstring coverage
            with_docstrings = sum(1 for f in functions if f["has_docstring"])
            metrics.docstring_coverage = with_docstrings / len(functions)

            # Type hint coverage
            with_hints = sum(1 for f in functions if f["has_return_hint"] or f["has_arg_hints"])
            metrics.type_hint_coverage = with_hints / len(functions)

    def _analyze_function(self, node: ast.FunctionDef, content: str) -> Dict:
        """Analyze a single function."""
        # Calculate length
        start_line = node.lineno
        end_line = node.end_lineno or start_line
        length = end_line - start_line + 1

        # Calculate complexity
        complexity = 1  # Base complexity
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                  ast.With, ast.Assert, ast.comprehension)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        # Check for docstring
        has_docstring = ast.get_docstring(node) is not None

        # Check for type hints
        has_return_hint = node.returns is not None
        has_arg_hints = any(arg.annotation is not None for arg in node.args.args)

        # Count arguments
        arg_count = len(node.args.args)
        if node.args.vararg:
            arg_count += 1
        if node.args.kwarg:
            arg_count += 1

        return {
            "name": node.name,
            "length": length,
            "complexity": complexity,
            "has_docstring": has_docstring,
            "has_return_hint": has_return_hint,
            "has_arg_hints": has_arg_hints,
            "arg_count": arg_count,
        }

    def _analyze_class(self, node: ast.ClassDef) -> Dict:
        """Analyze a single class."""
        has_docstring = ast.get_docstring(node) is not None
        method_count = sum(1 for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))

        return {
            "name": node.name,
            "has_docstring": has_docstring,
            "method_count": method_count,
        }

    def _check_for_tests(self, filepath: str) -> bool:
        """Check if tests exist for this file."""
        path = Path(filepath)
        filename = path.stem

        # Check if this IS a test file
        for pattern in self._test_file_patterns:
            if re.match(pattern, path.name):
                return True

        # Look for corresponding test file
        parent = path.parent
        possible_test_locations = [
            parent / f"test_{filename}.py",
            parent / f"{filename}_test.py",
            parent / "tests" / f"test_{filename}.py",
            parent.parent / "tests" / f"test_{filename}.py",
        ]

        return any(p.exists() for p in possible_test_locations)

    def _calculate_maintainability(self, metrics: QualityMetrics) -> float:
        """
        Calculate maintainability index (0-100 scale).

        Based on Visual Studio's formula:
        MI = 171 - 5.2 * ln(HV) - 0.23 * CC - 16.2 * ln(LOC)

        Simplified version using available metrics.
        """
        import math

        loc = max(metrics.lines_of_code, 1)
        avg_complexity = max(metrics.avg_complexity, 1)

        # Simplified maintainability calculation
        base = 171
        complexity_penalty = 0.23 * avg_complexity * metrics.function_count
        loc_penalty = 16.2 * math.log(loc)

        mi = base - complexity_penalty - loc_penalty

        # Normalize to 0-100
        mi = max(0, min(100, mi))

        # Bonuses for good practices
        if metrics.docstring_coverage > 0.8:
            mi += 5
        if metrics.type_hint_coverage > 0.5:
            mi += 5
        if metrics.has_error_handling:
            mi += 2
        if metrics.has_tests:
            mi += 5

        return round(min(100, mi), 2)

    def _calculate_quality_score(self, metrics: QualityMetrics) -> float:
        """
        Calculate overall quality score (0-100).

        Weighted combination of various factors.
        """
        score = 0.0

        # Documentation (25%)
        doc_score = 0
        if metrics.has_module_docstring:
            doc_score += 30
        doc_score += metrics.docstring_coverage * 50
        doc_score += min(metrics.comment_ratio * 100, 20)
        score += doc_score * 0.25

        # Type safety (15%)
        type_score = metrics.type_hint_coverage * 100
        if metrics.uses_typing_module:
            type_score += 10
        score += min(type_score, 100) * 0.15

        # Code structure (25%)
        structure_score = 100
        # Penalize for code smells
        structure_score -= len(metrics.code_smells) * 10
        # Penalize for high complexity
        if metrics.avg_complexity > 5:
            structure_score -= (metrics.avg_complexity - 5) * 5
        # Penalize for very long functions
        if metrics.max_function_length > 100:
            structure_score -= 20
        score += max(0, structure_score) * 0.25

        # Testing (15%)
        test_score = 50 if metrics.has_tests else 0
        test_score += min(metrics.testable_functions * 5, 50)
        score += test_score * 0.15

        # Error handling (10%)
        error_score = 0
        if metrics.has_error_handling:
            error_score = min(metrics.try_except_count * 20, 100)
        score += error_score * 0.10

        # Maintainability (10%)
        score += metrics.maintainability_index * 0.10

        return round(score, 2)

    def compare_files(self, filepaths: List[str]) -> QualityComparison:
        """
        Compare quality metrics across multiple files.

        Returns a comparison with rankings and recommendation.
        """
        metrics_list = [self.analyze_file(fp) for fp in filepaths]

        # Sort by quality score
        sorted_metrics = sorted(metrics_list, key=lambda m: m.quality_score, reverse=True)

        rankings = []
        for i, m in enumerate(sorted_metrics):
            rankings.append({
                "rank": i + 1,
                "filepath": m.filepath,
                "filename": Path(m.filepath).name,
                "quality_score": m.quality_score,
                "maintainability": m.maintainability_index,
                "docstring_coverage": m.docstring_coverage,
                "type_hint_coverage": m.type_hint_coverage,
                "has_tests": m.has_tests,
                "code_smells_count": len(m.code_smells),
            })

        best = sorted_metrics[0] if sorted_metrics else None
        second = sorted_metrics[1] if len(sorted_metrics) > 1 else None

        # Calculate confidence based on score difference
        if best and second:
            diff = best.quality_score - second.quality_score
            confidence = min(0.5 + diff / 50, 1.0)
        else:
            confidence = 0.8 if best else 0.0

        # Generate recommendation
        if best:
            recommendation = f"Recommend {Path(best.filepath).name} as master (score: {best.quality_score})"
            if best.code_smells:
                recommendation += f" - Note: {len(best.code_smells)} code smells detected"
        else:
            recommendation = "No files to compare"

        return QualityComparison(
            files=metrics_list,
            best_quality_file=best.filepath if best else "",
            quality_rankings=rankings,
            recommendation=recommendation,
            confidence=round(confidence, 2)
        )

    def get_quality_factor_for_master_selection(
        self,
        metrics: QualityMetrics,
        weight: float = 0.2
    ) -> float:
        """
        Get a quality-based factor to adjust master selection scoring.

        This can be used in combination with existing consolidation scoring.
        """
        # Normalize quality score to a factor
        return (metrics.quality_score / 100) * weight
