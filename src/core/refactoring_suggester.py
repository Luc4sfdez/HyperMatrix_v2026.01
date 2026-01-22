"""
HyperMatrix v2026 - Refactoring Suggester
Analyzes code and provides intelligent refactoring suggestions.
"""

import ast
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RefactoringSuggestion:
    """A single refactoring suggestion."""
    filepath: str
    line_number: int
    end_line: int
    suggestion_type: str  # 'extract_method', 'rename', 'simplify', etc.
    severity: str  # 'high', 'medium', 'low'
    title: str
    description: str
    code_snippet: str
    suggested_code: str = ""
    effort: str = "low"  # 'low', 'medium', 'high'
    impact: str = "medium"  # 'low', 'medium', 'high'
    category: str = ""  # 'readability', 'performance', 'maintainability', etc.


@dataclass
class RefactoringReport:
    """Complete refactoring analysis report."""
    filepath: str
    total_suggestions: int
    suggestions_by_type: Dict[str, int]
    suggestions_by_severity: Dict[str, int]
    suggestions: List[RefactoringSuggestion]
    overall_score: float  # 0-100, higher is better (less refactoring needed)
    priority_suggestions: List[RefactoringSuggestion]


class ComplexityVisitor(ast.NodeVisitor):
    """Analyzes code complexity for refactoring opportunities."""

    def __init__(self, source_lines: List[str]):
        self.source_lines = source_lines
        self.suggestions: List[RefactoringSuggestion] = []
        self.filepath = ""
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        self.nesting_level = 0
        self.function_complexities: Dict[str, int] = {}

    def _get_source(self, node) -> str:
        """Get source code for a node."""
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            start = node.lineno - 1
            end = node.end_lineno
            return '\n'.join(self.source_lines[start:end])
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_function = self.current_function
        self.current_function = node.name

        # Check function length
        func_length = (node.end_lineno or node.lineno) - node.lineno + 1
        if func_length > 50:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                suggestion_type="extract_method",
                severity="high" if func_length > 100 else "medium",
                title=f"Function '{node.name}' is too long ({func_length} lines)",
                description="Consider breaking this function into smaller, focused functions. "
                           "Each function should ideally do one thing well.",
                code_snippet=self._get_source(node)[:500],
                effort="medium",
                impact="high",
                category="maintainability"
            ))

        # Check number of parameters
        params = len(node.args.args) + len(node.args.kwonlyargs)
        if params > 5:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.lineno,
                suggestion_type="reduce_parameters",
                severity="medium",
                title=f"Function '{node.name}' has too many parameters ({params})",
                description="Consider grouping related parameters into a dataclass or dictionary. "
                           "This improves readability and makes the function easier to call.",
                code_snippet=f"def {node.name}({', '.join(a.arg for a in node.args.args[:5])}...)",
                effort="medium",
                impact="medium",
                category="readability"
            ))

        # Calculate cyclomatic complexity
        complexity = self._calculate_complexity(node)
        self.function_complexities[node.name] = complexity
        if complexity > 10:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                suggestion_type="reduce_complexity",
                severity="high" if complexity > 20 else "medium",
                title=f"Function '{node.name}' has high cyclomatic complexity ({complexity})",
                description="High complexity makes code harder to test and maintain. "
                           "Consider extracting conditional logic into separate functions or using polymorphism.",
                code_snippet=self._get_source(node)[:300],
                effort="high",
                impact="high",
                category="maintainability"
            ))

        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Reuse FunctionDef logic
        func_node = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            lineno=node.lineno,
            col_offset=node.col_offset,
            end_lineno=node.end_lineno,
            end_col_offset=node.end_col_offset,
        )
        self.visit_FunctionDef(func_node)

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name

        # Count methods
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if len(methods) > 20:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                suggestion_type="split_class",
                severity="medium",
                title=f"Class '{node.name}' has too many methods ({len(methods)})",
                description="Consider splitting this class into smaller, more focused classes. "
                           "Each class should have a single responsibility.",
                code_snippet=f"class {node.name}: # {len(methods)} methods",
                effort="high",
                impact="high",
                category="maintainability"
            ))

        # Check class length
        class_length = (node.end_lineno or node.lineno) - node.lineno + 1
        if class_length > 300:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                suggestion_type="split_class",
                severity="high",
                title=f"Class '{node.name}' is too long ({class_length} lines)",
                description="Large classes are hard to understand and maintain. "
                           "Consider extracting functionality into separate classes or modules.",
                code_snippet=f"class {node.name}: # {class_length} lines",
                effort="high",
                impact="high",
                category="maintainability"
            ))

        self.generic_visit(node)
        self.current_class = old_class

    def visit_If(self, node: ast.If):
        self.nesting_level += 1
        if self.nesting_level > 4:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                suggestion_type="reduce_nesting",
                severity="medium",
                title=f"Deeply nested code (level {self.nesting_level})",
                description="Deep nesting makes code hard to follow. Consider early returns, "
                           "guard clauses, or extracting nested logic into separate functions.",
                code_snippet=self._get_source(node)[:200],
                effort="low",
                impact="medium",
                category="readability"
            ))
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_For(self, node: ast.For):
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_While(self, node: ast.While):
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_Try(self, node: ast.Try):
        # Check for bare except
        for handler in node.handlers:
            if handler.type is None:
                self.suggestions.append(RefactoringSuggestion(
                    filepath=self.filepath,
                    line_number=handler.lineno,
                    end_line=handler.end_lineno or handler.lineno,
                    suggestion_type="specific_exception",
                    severity="medium",
                    title="Bare except clause",
                    description="Catching all exceptions can hide bugs. "
                               "Catch specific exceptions instead (e.g., ValueError, TypeError).",
                    code_snippet="except:",
                    suggested_code="except Exception as e:",
                    effort="low",
                    impact="medium",
                    category="reliability"
                ))
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        # Check for comparison chain simplification
        if len(node.ops) > 2:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.lineno,
                suggestion_type="simplify_comparison",
                severity="low",
                title="Complex comparison chain",
                description="Consider breaking down complex comparisons into named variables "
                           "for better readability.",
                code_snippet=self._get_source(node),
                effort="low",
                impact="low",
                category="readability"
            ))
        self.generic_visit(node)

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a node."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, (ast.Assert, ast.comprehension)):
                complexity += 1
        return complexity


class CodeSmellDetector(ast.NodeVisitor):
    """Detects common code smells and anti-patterns."""

    def __init__(self, source_lines: List[str]):
        self.source_lines = source_lines
        self.suggestions: List[RefactoringSuggestion] = []
        self.filepath = ""
        self.variables_used: Dict[str, int] = defaultdict(int)
        self.variables_assigned: Dict[str, Tuple[int, ast.AST]] = {}

    def _get_source(self, node) -> str:
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            start = node.lineno - 1
            end = node.end_lineno
            return '\n'.join(self.source_lines[start:end])
        return ""

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.variables_assigned[target.id] = (node.lineno, node)

        # Check for magic numbers
        if isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, (int, float)):
                val = node.value.value
                if isinstance(val, int) and val > 10 and val not in {100, 1000, 1024}:
                    # Check if it's assigned to an ALL_CAPS name (constant)
                    for target in node.targets:
                        if isinstance(target, ast.Name) and not target.id.isupper():
                            self.suggestions.append(RefactoringSuggestion(
                                filepath=self.filepath,
                                line_number=node.lineno,
                                end_line=node.lineno,
                                suggestion_type="extract_constant",
                                severity="low",
                                title=f"Magic number: {val}",
                                description="Consider extracting this number into a named constant "
                                           "to make its purpose clear.",
                                code_snippet=self._get_source(node),
                                suggested_code=f"{target.id.upper()} = {val}  # Descriptive name",
                                effort="low",
                                impact="low",
                                category="readability"
                            ))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.variables_used[node.id] += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check for duplicate code in consecutive statements
        self._check_duplicate_statements(node.body)

        # Check for long parameter lists with defaults
        defaults_count = len(node.args.defaults)
        if defaults_count > 3:
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.lineno,
                suggestion_type="use_kwargs",
                severity="low",
                title=f"Function '{node.name}' has many default parameters ({defaults_count})",
                description="Consider using **kwargs or a configuration object "
                           "for functions with many optional parameters.",
                code_snippet=f"def {node.name}(...)",
                effort="medium",
                impact="low",
                category="maintainability"
            ))

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        # Check for string concatenation in loops
        if isinstance(node.op, ast.Add):
            if isinstance(node.left, ast.Str) or isinstance(node.right, ast.Str):
                self.suggestions.append(RefactoringSuggestion(
                    filepath=self.filepath,
                    line_number=node.lineno,
                    end_line=node.lineno,
                    suggestion_type="use_fstring",
                    severity="low",
                    title="String concatenation",
                    description="Consider using f-strings or str.join() for better "
                               "performance and readability.",
                    code_snippet=self._get_source(node),
                    effort="low",
                    impact="low",
                    category="performance"
                ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check for type() instead of isinstance()
        if isinstance(node.func, ast.Name) and node.func.id == 'type':
            self.suggestions.append(RefactoringSuggestion(
                filepath=self.filepath,
                line_number=node.lineno,
                end_line=node.lineno,
                suggestion_type="use_isinstance",
                severity="low",
                title="Consider using isinstance()",
                description="isinstance() is preferred over type() for type checking "
                           "as it handles inheritance correctly.",
                code_snippet=self._get_source(node),
                effort="low",
                impact="low",
                category="best_practice"
            ))
        self.generic_visit(node)

    def _check_duplicate_statements(self, body: List[ast.stmt]):
        """Check for similar consecutive statements."""
        if len(body) < 2:
            return

        for i in range(len(body) - 1):
            if type(body[i]) == type(body[i + 1]):
                if isinstance(body[i], ast.Assign) and isinstance(body[i + 1], ast.Assign):
                    # Check if they're structurally similar
                    if len(body[i].targets) == len(body[i + 1].targets):
                        if type(body[i].value) == type(body[i + 1].value):
                            # Could be repetitive pattern
                            pass  # More sophisticated check needed


class RefactoringSuggester:
    """
    Analyzes code and provides intelligent refactoring suggestions.

    Categories of suggestions:
    - extract_method: Long functions that should be split
    - reduce_complexity: High cyclomatic complexity
    - reduce_nesting: Deeply nested code
    - split_class: Classes with too many methods
    - reduce_parameters: Functions with too many parameters
    - extract_constant: Magic numbers that should be constants
    - simplify: Code that can be simplified
    - naming: Poor naming conventions
    """

    # Naming patterns
    GOOD_NAMES_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')  # snake_case
    GOOD_CLASS_PATTERN = re.compile(r'^[A-Z][a-zA-Z0-9]*$')  # PascalCase
    GOOD_CONST_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')  # UPPER_CASE

    def __init__(self):
        pass

    def analyze_file(self, filepath: str) -> RefactoringReport:
        """Analyze a single file for refactoring opportunities."""
        path = Path(filepath)
        if not path.exists() or path.suffix != '.py':
            return self._empty_report(filepath)

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
            source_lines = content.split('\n')
            tree = ast.parse(content)
        except SyntaxError:
            return self._empty_report(filepath)

        suggestions = []

        # Complexity analysis
        complexity_visitor = ComplexityVisitor(source_lines)
        complexity_visitor.filepath = filepath
        complexity_visitor.visit(tree)
        suggestions.extend(complexity_visitor.suggestions)

        # Code smell detection
        smell_detector = CodeSmellDetector(source_lines)
        smell_detector.filepath = filepath
        smell_detector.visit(tree)
        suggestions.extend(smell_detector.suggestions)

        # Naming analysis
        naming_suggestions = self._analyze_naming(tree, filepath, source_lines)
        suggestions.extend(naming_suggestions)

        # Duplicate code detection (simple)
        duplicate_suggestions = self._detect_duplicates(tree, filepath, source_lines)
        suggestions.extend(duplicate_suggestions)

        # Calculate statistics
        suggestions_by_type = defaultdict(int)
        suggestions_by_severity = defaultdict(int)
        for s in suggestions:
            suggestions_by_type[s.suggestion_type] += 1
            suggestions_by_severity[s.severity] += 1

        # Calculate overall score (100 = perfect, lower = more issues)
        overall_score = self._calculate_score(suggestions, len(source_lines))

        # Priority suggestions (high severity first, then by impact)
        priority_suggestions = sorted(
            suggestions,
            key=lambda s: (
                {'high': 0, 'medium': 1, 'low': 2}[s.severity],
                {'high': 0, 'medium': 1, 'low': 2}[s.impact],
            )
        )[:10]

        return RefactoringReport(
            filepath=filepath,
            total_suggestions=len(suggestions),
            suggestions_by_type=dict(suggestions_by_type),
            suggestions_by_severity=dict(suggestions_by_severity),
            suggestions=suggestions,
            overall_score=overall_score,
            priority_suggestions=priority_suggestions,
        )

    def analyze_files(self, filepaths: List[str]) -> Dict[str, RefactoringReport]:
        """Analyze multiple files."""
        return {fp: self.analyze_file(fp) for fp in filepaths}

    def get_quick_wins(self, report: RefactoringReport) -> List[RefactoringSuggestion]:
        """Get suggestions that are low effort but have medium/high impact."""
        return [
            s for s in report.suggestions
            if s.effort == 'low' and s.impact in ('medium', 'high')
        ]

    def _analyze_naming(
        self, tree: ast.AST, filepath: str, source_lines: List[str]
    ) -> List[RefactoringSuggestion]:
        """Analyze naming conventions."""
        suggestions = []

        for node in ast.walk(tree):
            # Check function names
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith('_'):
                    if not self.GOOD_NAMES_PATTERN.match(node.name):
                        if not (node.name.startswith('__') and node.name.endswith('__')):
                            suggestions.append(RefactoringSuggestion(
                                filepath=filepath,
                                line_number=node.lineno,
                                end_line=node.lineno,
                                suggestion_type="naming",
                                severity="low",
                                title=f"Function '{node.name}' doesn't follow snake_case",
                                description="Function names should use snake_case convention "
                                           "for consistency with PEP 8.",
                                code_snippet=f"def {node.name}(...):",
                                suggested_code=f"def {self._to_snake_case(node.name)}(...):",
                                effort="low",
                                impact="low",
                                category="readability"
                            ))

            # Check class names
            elif isinstance(node, ast.ClassDef):
                if not self.GOOD_CLASS_PATTERN.match(node.name):
                    suggestions.append(RefactoringSuggestion(
                        filepath=filepath,
                        line_number=node.lineno,
                        end_line=node.lineno,
                        suggestion_type="naming",
                        severity="low",
                        title=f"Class '{node.name}' doesn't follow PascalCase",
                        description="Class names should use PascalCase convention "
                                   "for consistency with PEP 8.",
                        code_snippet=f"class {node.name}:",
                        suggested_code=f"class {self._to_pascal_case(node.name)}:",
                        effort="low",
                        impact="low",
                        category="readability"
                    ))

        return suggestions

    def _detect_duplicates(
        self, tree: ast.AST, filepath: str, source_lines: List[str]
    ) -> List[RefactoringSuggestion]:
        """Detect duplicate code blocks."""
        suggestions = []
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

        # Simple duplicate detection: functions with very similar structure
        for i, func1 in enumerate(functions):
            for func2 in functions[i + 1:]:
                if self._functions_similar(func1, func2):
                    suggestions.append(RefactoringSuggestion(
                        filepath=filepath,
                        line_number=func1.lineno,
                        end_line=func1.end_lineno or func1.lineno,
                        suggestion_type="extract_method",
                        severity="medium",
                        title=f"Functions '{func1.name}' and '{func2.name}' appear similar",
                        description="These functions have similar structure. Consider combining "
                                   "them into a single function with parameters.",
                        code_snippet=f"def {func1.name}(...)\ndef {func2.name}(...)",
                        effort="medium",
                        impact="medium",
                        category="maintainability"
                    ))

        return suggestions

    def _functions_similar(self, func1: ast.FunctionDef, func2: ast.FunctionDef) -> bool:
        """Check if two functions are structurally similar."""
        # Compare number of statements
        if abs(len(func1.body) - len(func2.body)) > 2:
            return False

        # Compare structure
        types1 = [type(n).__name__ for n in func1.body]
        types2 = [type(n).__name__ for n in func2.body]

        if types1 == types2 and len(types1) > 3:
            return True

        return False

    def _calculate_score(self, suggestions: List[RefactoringSuggestion], total_lines: int) -> float:
        """Calculate overall code quality score (0-100)."""
        if total_lines == 0:
            return 100.0

        # Start with 100, deduct based on suggestions
        score = 100.0

        for s in suggestions:
            if s.severity == 'high':
                score -= 5
            elif s.severity == 'medium':
                score -= 2
            else:
                score -= 0.5

        # Normalize based on file size
        lines_factor = min(total_lines / 100, 5)  # Cap at 500 lines normalization
        if lines_factor > 1:
            score = score * (1 + (lines_factor - 1) * 0.1)

        return max(0.0, min(100.0, score))

    def _to_snake_case(self, name: str) -> str:
        """Convert name to snake_case."""
        result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        result = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', result)
        return result.lower()

    def _to_pascal_case(self, name: str) -> str:
        """Convert name to PascalCase."""
        words = re.split(r'[_\s]+', name)
        return ''.join(word.capitalize() for word in words)

    def _empty_report(self, filepath: str) -> RefactoringReport:
        """Create an empty report."""
        return RefactoringReport(
            filepath=filepath,
            total_suggestions=0,
            suggestions_by_type={},
            suggestions_by_severity={},
            suggestions=[],
            overall_score=100.0,
            priority_suggestions=[],
        )
