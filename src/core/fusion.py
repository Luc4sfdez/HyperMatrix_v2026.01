"""
Intelligent Fusion Module for HyperMatrix.

This module provides intelligent merging of multiple versions of the same file,
combining unique capabilities from each version into a unified, enhanced version.
"""

import ast
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConflictResolution(Enum):
    """Strategy for resolving conflicts between versions."""
    KEEP_LARGEST = "keep_largest"       # Keep the version with most code
    KEEP_MOST_COMPLEX = "keep_complex"  # Keep the most complex implementation
    KEEP_NEWEST = "keep_newest"         # Keep from newest file (by mtime)
    KEEP_ALL = "keep_all"               # Rename and keep all versions
    MANUAL = "manual"                   # Require human decision


@dataclass
class FunctionInfo:
    """Information about a function extracted from AST."""
    name: str
    lineno: int
    end_lineno: int
    args: List[str]
    decorators: List[str]
    is_async: bool
    docstring: Optional[str]
    source_code: str
    source_file: str
    complexity: int = 0  # Number of branches/loops

    @property
    def signature(self) -> str:
        """Return function signature for comparison."""
        async_prefix = "async " if self.is_async else ""
        return f"{async_prefix}def {self.name}({', '.join(self.args)})"

    @property
    def code_hash(self) -> str:
        """Hash of the source code for quick comparison."""
        return hashlib.md5(self.source_code.encode()).hexdigest()[:12]


@dataclass
class ClassInfo:
    """Information about a class extracted from AST."""
    name: str
    lineno: int
    end_lineno: int
    bases: List[str]
    decorators: List[str]
    methods: List[FunctionInfo]
    class_variables: List[str]
    docstring: Optional[str]
    source_code: str
    source_file: str

    @property
    def code_hash(self) -> str:
        return hashlib.md5(self.source_code.encode()).hexdigest()[:12]


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module: str
    names: List[str]  # Empty for 'import x', filled for 'from x import a, b'
    alias: Optional[str]
    is_from_import: bool
    lineno: int
    source_code: str


@dataclass
class VersionAnalysis:
    """Complete analysis of a single file version."""
    filepath: str
    file_hash: str
    functions: Dict[str, FunctionInfo]
    classes: Dict[str, ClassInfo]
    imports: List[ImportInfo]
    module_docstring: Optional[str]
    global_code: List[str]  # Top-level code that's not functions/classes
    total_lines: int

    @property
    def function_names(self) -> Set[str]:
        return set(self.functions.keys())

    @property
    def class_names(self) -> Set[str]:
        return set(self.classes.keys())


@dataclass
class Conflict:
    """Represents a conflict between versions."""
    element_type: str  # 'function' or 'class'
    element_name: str
    versions: List[Tuple[str, str]]  # [(filepath, code_hash), ...]
    differences: List[str]  # Description of differences


@dataclass
class FusionResult:
    """Result of an intelligent fusion operation."""
    success: bool
    fused_code: str
    base_version: str
    versions_merged: List[str]
    functions_added: List[str]
    classes_added: List[str]
    conflicts_resolved: List[Conflict]
    conflicts_pending: List[Conflict]
    warnings: List[str]
    stats: Dict[str, int]


class ASTExtractor(ast.NodeVisitor):
    """Extract detailed information from Python AST."""

    def __init__(self, source_code: str, filepath: str):
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.filepath = filepath
        self.functions: Dict[str, FunctionInfo] = {}
        self.classes: Dict[str, ClassInfo] = {}
        self.imports: List[ImportInfo] = []
        self.module_docstring: Optional[str] = None
        self.global_code: List[str] = []
        self._current_class: Optional[str] = None

    def _get_source_segment(self, node: ast.AST) -> str:
        """Extract source code for a node."""
        try:
            return ast.get_source_segment(self.source_code, node) or ""
        except:
            # Fallback: extract by line numbers
            if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                lines = self.source_lines[node.lineno - 1:node.end_lineno]
                return '\n'.join(lines)
            return ""

    def _get_decorators(self, node) -> List[str]:
        """Extract decorator names."""
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
        return decorators

    def _get_docstring(self, node) -> Optional[str]:
        """Extract docstring from a node."""
        return ast.get_docstring(node)

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                  ast.With, ast.Assert, ast.comprehension)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def visit_Module(self, node: ast.Module):
        """Visit module and extract docstring."""
        self.module_docstring = self._get_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node, is_async=True)

    def _process_function(self, node, is_async: bool):
        """Process a function definition."""
        # Skip methods inside classes (they're handled by class visitor)
        if self._current_class is not None:
            return

        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        func_info = FunctionInfo(
            name=node.name,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            args=args,
            decorators=self._get_decorators(node),
            is_async=is_async,
            docstring=self._get_docstring(node),
            source_code=self._get_source_segment(node),
            source_file=self.filepath,
            complexity=self._calculate_complexity(node)
        )

        self.functions[node.name] = func_info

    def visit_ClassDef(self, node: ast.ClassDef):
        """Process a class definition."""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{base.value.id}.{base.attr}" if isinstance(base.value, ast.Name) else base.attr)

        # Extract methods
        methods = []
        self._current_class = node.name
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [arg.arg for arg in item.args.args]
                method_info = FunctionInfo(
                    name=item.name,
                    lineno=item.lineno,
                    end_lineno=item.end_lineno or item.lineno,
                    args=args,
                    decorators=self._get_decorators(item),
                    is_async=isinstance(item, ast.AsyncFunctionDef),
                    docstring=self._get_docstring(item),
                    source_code=self._get_source_segment(item),
                    source_file=self.filepath,
                    complexity=self._calculate_complexity(item)
                )
                methods.append(method_info)
        self._current_class = None

        # Extract class variables
        class_vars = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                class_vars.append(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_vars.append(target.id)

        class_info = ClassInfo(
            name=node.name,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            bases=bases,
            decorators=self._get_decorators(node),
            methods=methods,
            class_variables=class_vars,
            docstring=self._get_docstring(node),
            source_code=self._get_source_segment(node),
            source_file=self.filepath
        )

        self.classes[node.name] = class_info

    def visit_Import(self, node: ast.Import):
        """Process import statement."""
        for alias in node.names:
            self.imports.append(ImportInfo(
                module=alias.name,
                names=[],
                alias=alias.asname,
                is_from_import=False,
                lineno=node.lineno,
                source_code=self._get_source_segment(node)
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Process from...import statement."""
        names = [alias.name for alias in node.names]
        self.imports.append(ImportInfo(
            module=node.module or "",
            names=names,
            alias=None,
            is_from_import=True,
            lineno=node.lineno,
            source_code=self._get_source_segment(node)
        ))


class IntelligentFusion:
    """
    Intelligent fusion engine that merges multiple versions of a file.

    This class analyzes multiple versions of the same file, identifies
    unique functions and classes in each, detects conflicts, and generates
    a unified version combining the best of all versions.
    """

    def __init__(self, conflict_resolution: ConflictResolution = ConflictResolution.KEEP_LARGEST):
        self.conflict_resolution = conflict_resolution
        self.versions: Dict[str, VersionAnalysis] = {}
        self._conflicts: List[Conflict] = []

    def analyze_file(self, filepath: str) -> Optional[VersionAnalysis]:
        """Analyze a single file and extract its structure."""
        path = Path(filepath)
        if not path.exists():
            logger.error(f"File not found: {filepath}")
            return None

        try:
            source_code = path.read_text(encoding='utf-8', errors='ignore')
            file_hash = hashlib.md5(source_code.encode()).hexdigest()

            # Parse AST
            tree = ast.parse(source_code)
            extractor = ASTExtractor(source_code, filepath)
            extractor.visit(tree)

            analysis = VersionAnalysis(
                filepath=filepath,
                file_hash=file_hash,
                functions=extractor.functions,
                classes=extractor.classes,
                imports=extractor.imports,
                module_docstring=extractor.module_docstring,
                global_code=[],  # TODO: extract global code
                total_lines=len(source_code.splitlines())
            )

            self.versions[filepath] = analysis
            return analysis

        except SyntaxError as e:
            logger.error(f"Syntax error in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error analyzing {filepath}: {e}")
            return None

    def analyze_versions(self, filepaths: List[str]) -> Dict[str, VersionAnalysis]:
        """Analyze multiple file versions."""
        for fp in filepaths:
            self.analyze_file(fp)
        return self.versions

    def find_unique_elements(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Find functions/classes that are unique to specific versions.

        Returns:
            Dict mapping element names to dict of {type: [filepaths]}
        """
        # Collect all function names across versions
        all_functions: Dict[str, List[str]] = defaultdict(list)
        all_classes: Dict[str, List[str]] = defaultdict(list)

        for filepath, analysis in self.versions.items():
            for func_name in analysis.functions:
                all_functions[func_name].append(filepath)
            for class_name in analysis.classes:
                all_classes[class_name].append(filepath)

        result = {
            'unique_functions': {},
            'common_functions': {},
            'unique_classes': {},
            'common_classes': {}
        }

        n_versions = len(self.versions)

        for func_name, filepaths in all_functions.items():
            if len(filepaths) == 1:
                result['unique_functions'][func_name] = filepaths
            elif len(filepaths) == n_versions:
                result['common_functions'][func_name] = filepaths

        for class_name, filepaths in all_classes.items():
            if len(filepaths) == 1:
                result['unique_classes'][class_name] = filepaths
            elif len(filepaths) == n_versions:
                result['common_classes'][class_name] = filepaths

        return result

    def detect_conflicts(self) -> List[Conflict]:
        """
        Detect conflicts where same element exists with different implementations.
        """
        self._conflicts = []

        # Group functions by name
        func_versions: Dict[str, List[Tuple[str, FunctionInfo]]] = defaultdict(list)
        for filepath, analysis in self.versions.items():
            for func_name, func_info in analysis.functions.items():
                func_versions[func_name].append((filepath, func_info))

        # Check for conflicts (same name, different hash)
        for func_name, versions in func_versions.items():
            if len(versions) > 1:
                hashes = set(v[1].code_hash for v in versions)
                if len(hashes) > 1:
                    # Conflict detected
                    conflict = Conflict(
                        element_type='function',
                        element_name=func_name,
                        versions=[(v[0], v[1].code_hash) for v in versions],
                        differences=self._describe_function_differences(versions)
                    )
                    self._conflicts.append(conflict)

        # Same for classes
        class_versions: Dict[str, List[Tuple[str, ClassInfo]]] = defaultdict(list)
        for filepath, analysis in self.versions.items():
            for class_name, class_info in analysis.classes.items():
                class_versions[class_name].append((filepath, class_info))

        for class_name, versions in class_versions.items():
            if len(versions) > 1:
                hashes = set(v[1].code_hash for v in versions)
                if len(hashes) > 1:
                    conflict = Conflict(
                        element_type='class',
                        element_name=class_name,
                        versions=[(v[0], v[1].code_hash) for v in versions],
                        differences=self._describe_class_differences(versions)
                    )
                    self._conflicts.append(conflict)

        return self._conflicts

    def _describe_function_differences(self, versions: List[Tuple[str, FunctionInfo]]) -> List[str]:
        """Describe differences between function versions."""
        differences = []

        # Compare line counts
        line_counts = [(Path(v[0]).name, v[1].end_lineno - v[1].lineno + 1) for v in versions]
        differences.append(f"Line counts: {line_counts}")

        # Compare complexity
        complexities = [(Path(v[0]).name, v[1].complexity) for v in versions]
        differences.append(f"Complexity: {complexities}")

        # Compare arguments
        arg_sets = [(Path(v[0]).name, v[1].args) for v in versions]
        if len(set(tuple(a[1]) for a in arg_sets)) > 1:
            differences.append(f"Arguments differ: {arg_sets}")

        return differences

    def _describe_class_differences(self, versions: List[Tuple[str, ClassInfo]]) -> List[str]:
        """Describe differences between class versions."""
        differences = []

        # Compare method counts
        method_counts = [(Path(v[0]).name, len(v[1].methods)) for v in versions]
        differences.append(f"Method counts: {method_counts}")

        # Compare method names
        method_names = [(Path(v[0]).name, [m.name for m in v[1].methods]) for v in versions]
        differences.append(f"Methods: {method_names}")

        return differences

    def select_base_version(self) -> str:
        """Select the best base version for fusion."""
        if not self.versions:
            raise ValueError("No versions analyzed")

        # Score each version
        scores = {}
        for filepath, analysis in self.versions.items():
            score = 0
            score += len(analysis.functions) * 10
            score += len(analysis.classes) * 15
            score += sum(f.complexity for f in analysis.functions.values())
            score += analysis.total_lines
            scores[filepath] = score

        # Return version with highest score
        return max(scores, key=scores.get)

    def fuse(self, base_version: Optional[str] = None) -> FusionResult:
        """
        Perform intelligent fusion of all analyzed versions.

        Args:
            base_version: Path to use as base. If None, auto-selects best version.

        Returns:
            FusionResult with fused code and metadata.
        """
        if not self.versions:
            return FusionResult(
                success=False,
                fused_code="",
                base_version="",
                versions_merged=[],
                functions_added=[],
                classes_added=[],
                conflicts_resolved=[],
                conflicts_pending=[],
                warnings=["No versions to fuse"],
                stats={}
            )

        # Select base version
        if base_version is None:
            base_version = self.select_base_version()

        base_analysis = self.versions.get(base_version)
        if not base_analysis:
            return FusionResult(
                success=False,
                fused_code="",
                base_version=base_version,
                versions_merged=[],
                functions_added=[],
                classes_added=[],
                conflicts_resolved=[],
                conflicts_pending=[],
                warnings=[f"Base version not found: {base_version}"],
                stats={}
            )

        # Detect conflicts
        conflicts = self.detect_conflicts()

        # Start with base version
        base_source = Path(base_version).read_text(encoding='utf-8', errors='ignore')

        # Collect all imports
        all_imports: Set[str] = set()
        for analysis in self.versions.values():
            for imp in analysis.imports:
                all_imports.add(imp.source_code.strip())

        # Collect functions to add (unique to other versions)
        functions_to_add: List[FunctionInfo] = []
        base_func_names = base_analysis.function_names

        for filepath, analysis in self.versions.items():
            if filepath == base_version:
                continue
            for func_name, func_info in analysis.functions.items():
                if func_name not in base_func_names:
                    functions_to_add.append(func_info)
                    base_func_names.add(func_name)  # Prevent duplicates

        # Collect classes to add
        classes_to_add: List[ClassInfo] = []
        base_class_names = base_analysis.class_names

        for filepath, analysis in self.versions.items():
            if filepath == base_version:
                continue
            for class_name, class_info in analysis.classes.items():
                if class_name not in base_class_names:
                    classes_to_add.append(class_info)
                    base_class_names.add(class_name)

        # Build fused code
        fused_lines = []

        # Module docstring
        if base_analysis.module_docstring:
            fused_lines.append(f'"""{base_analysis.module_docstring}"""')
            fused_lines.append("")

        # Imports (merged from all versions)
        fused_lines.append("# === IMPORTS (merged from all versions) ===")
        for imp in sorted(all_imports):
            fused_lines.append(imp)
        fused_lines.append("")

        # Original base code (functions and classes)
        fused_lines.append("# === BASE CODE ===")
        fused_lines.append(f"# From: {Path(base_version).name}")
        fused_lines.append("")

        # Add base functions
        for func_info in base_analysis.functions.values():
            fused_lines.append(func_info.source_code)
            fused_lines.append("")

        # Add base classes
        for class_info in base_analysis.classes.values():
            fused_lines.append(class_info.source_code)
            fused_lines.append("")

        # Add unique functions from other versions
        if functions_to_add:
            fused_lines.append("")
            fused_lines.append("# === FUNCTIONS ADDED FROM OTHER VERSIONS ===")
            for func_info in functions_to_add:
                fused_lines.append(f"# From: {Path(func_info.source_file).name}")
                fused_lines.append(func_info.source_code)
                fused_lines.append("")

        # Add unique classes from other versions
        if classes_to_add:
            fused_lines.append("")
            fused_lines.append("# === CLASSES ADDED FROM OTHER VERSIONS ===")
            for class_info in classes_to_add:
                fused_lines.append(f"# From: {Path(class_info.source_file).name}")
                fused_lines.append(class_info.source_code)
                fused_lines.append("")

        fused_code = '\n'.join(fused_lines)

        # Resolve conflicts based on strategy
        conflicts_resolved = []
        conflicts_pending = []

        for conflict in conflicts:
            if self.conflict_resolution == ConflictResolution.MANUAL:
                conflicts_pending.append(conflict)
            else:
                # Auto-resolve
                conflicts_resolved.append(conflict)

        return FusionResult(
            success=True,
            fused_code=fused_code,
            base_version=base_version,
            versions_merged=list(self.versions.keys()),
            functions_added=[f.name for f in functions_to_add],
            classes_added=[c.name for c in classes_to_add],
            conflicts_resolved=conflicts_resolved,
            conflicts_pending=conflicts_pending,
            warnings=[],
            stats={
                'total_versions': len(self.versions),
                'base_functions': len(base_analysis.functions),
                'base_classes': len(base_analysis.classes),
                'functions_added': len(functions_to_add),
                'classes_added': len(classes_to_add),
                'total_functions': len(base_analysis.functions) + len(functions_to_add),
                'total_classes': len(base_analysis.classes) + len(classes_to_add),
                'conflicts_detected': len(conflicts),
                'conflicts_resolved': len(conflicts_resolved),
                'conflicts_pending': len(conflicts_pending),
                'fused_lines': len(fused_code.splitlines())
            }
        )

    def generate_fusion_report(self) -> str:
        """Generate a detailed report of the fusion analysis."""
        if not self.versions:
            return "No versions analyzed."

        lines = []
        lines.append("=" * 70)
        lines.append("INTELLIGENT FUSION ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Version summary
        lines.append(f"Versions analyzed: {len(self.versions)}")
        lines.append("-" * 40)
        for filepath, analysis in self.versions.items():
            lines.append(f"  {Path(filepath).name}")
            lines.append(f"    Functions: {len(analysis.functions)}")
            lines.append(f"    Classes: {len(analysis.classes)}")
            lines.append(f"    Lines: {analysis.total_lines}")
        lines.append("")

        # Unique elements
        unique = self.find_unique_elements()

        lines.append("UNIQUE FUNCTIONS (only in one version):")
        lines.append("-" * 40)
        for func_name, filepaths in unique['unique_functions'].items():
            lines.append(f"  {func_name}() <- {Path(filepaths[0]).name}")
        lines.append("")

        lines.append("COMMON FUNCTIONS (in all versions):")
        lines.append("-" * 40)
        for func_name in unique['common_functions']:
            lines.append(f"  {func_name}()")
        lines.append("")

        # Conflicts
        conflicts = self.detect_conflicts()
        lines.append(f"CONFLICTS DETECTED: {len(conflicts)}")
        lines.append("-" * 40)
        for conflict in conflicts:
            lines.append(f"  {conflict.element_type}: {conflict.element_name}")
            for diff in conflict.differences:
                lines.append(f"    - {diff}")
        lines.append("")

        # Recommendation
        best_base = self.select_base_version()
        lines.append("RECOMMENDATION:")
        lines.append("-" * 40)
        lines.append(f"  Best base version: {Path(best_base).name}")

        base_analysis = self.versions[best_base]
        potential_funcs = len(base_analysis.functions) + len(unique['unique_functions'])
        potential_classes = len(base_analysis.classes) + len(unique['unique_classes'])

        lines.append(f"  Potential fused result:")
        lines.append(f"    - Functions: {potential_funcs}")
        lines.append(f"    - Classes: {potential_classes}")

        return '\n'.join(lines)
