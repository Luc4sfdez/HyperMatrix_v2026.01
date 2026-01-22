"""
HyperMatrix v2026 - Dead Code Detector
Detects unused functions, classes, imports, and variables.
"""

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class DeadCodeItem:
    """An item of potentially dead code."""
    filepath: str
    name: str
    item_type: str  # 'function', 'class', 'import', 'variable'
    line_number: int
    confidence: float  # 0.0 to 1.0
    reason: str
    used_by: List[str] = field(default_factory=list)  # If any usages found
    suggestion: str = ""


@dataclass
class DeadCodeReport:
    """Report of dead code analysis."""
    total_definitions: int
    dead_functions: List[DeadCodeItem]
    dead_classes: List[DeadCodeItem]
    dead_imports: List[DeadCodeItem]
    dead_variables: List[DeadCodeItem]
    potential_savings_lines: int
    summary: Dict


class UsageCollector(ast.NodeVisitor):
    """Collects all name usages in code."""

    def __init__(self):
        self.names_used: Set[str] = set()
        self.calls: Set[str] = set()
        self.attributes: Set[str] = set()
        self.imports: Dict[str, Set[str]] = defaultdict(set)  # module -> names used from it

    def visit_Name(self, node: ast.Name):
        self.names_used.add(node.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.add(node.func.attr)
            if isinstance(node.func.value, ast.Name):
                self.imports[node.func.value.id].add(node.func.attr)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        self.attributes.add(node.attr)
        if isinstance(node.value, ast.Name):
            self.imports[node.value.id].add(node.attr)
        self.generic_visit(node)


class DefinitionCollector(ast.NodeVisitor):
    """Collects all definitions in code."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions: List[Dict] = []
        self.classes: List[Dict] = []
        self.imports: List[Dict] = []
        self.variables: List[Dict] = []
        self._in_class = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not self._in_class:  # Skip methods
            self.functions.append({
                'name': node.name,
                'line': node.lineno,
                'end_line': node.end_lineno or node.lineno,
                'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
                'is_private': node.name.startswith('_'),
                'is_dunder': node.name.startswith('__') and node.name.endswith('__'),
            })
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not self._in_class:
            self.functions.append({
                'name': node.name,
                'line': node.lineno,
                'end_line': node.end_lineno or node.lineno,
                'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
                'is_private': node.name.startswith('_'),
                'is_dunder': node.name.startswith('__') and node.name.endswith('__'),
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes.append({
            'name': node.name,
            'line': node.lineno,
            'end_line': node.end_lineno or node.lineno,
            'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
            'is_private': node.name.startswith('_'),
        })
        # Mark that we're inside a class
        old_in_class = self._in_class
        self._in_class = True
        self.generic_visit(node)
        self._in_class = old_in_class

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append({
                'name': alias.name,
                'alias': alias.asname,
                'line': node.lineno,
                'is_from': False,
            })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            self.imports.append({
                'name': f"{node.module}.{alias.name}" if node.module else alias.name,
                'alias': alias.asname,
                'short_name': alias.name,
                'module': node.module,
                'line': node.lineno,
                'is_from': True,
            })

    def visit_Assign(self, node: ast.Assign):
        # Only capture module-level variables
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.variables.append({
                    'name': target.id,
                    'line': node.lineno,
                    'is_constant': target.id.isupper(),
                })
        self.generic_visit(node)

    def _get_decorator_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
            elif isinstance(node.func, ast.Attribute):
                return node.func.attr
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ''


class DeadCodeDetector:
    """
    Detects dead (unused) code in a codebase.

    Detects:
    - Unused functions
    - Unused classes
    - Unused imports
    - Unused variables

    Confidence levels based on:
    - Private names (_name) are more likely dead
    - Public names might be used externally
    - Decorated functions might be used by frameworks
    """

    # Decorators that indicate external usage
    FRAMEWORK_DECORATORS = {
        'property', 'staticmethod', 'classmethod', 'abstractmethod',
        'route', 'get', 'post', 'put', 'delete', 'patch',
        'app', 'api', 'endpoint', 'command', 'task',
        'pytest', 'fixture', 'test', 'parametrize',
        'click', 'option', 'argument',
        'dataclass', 'validator', 'field',
    }

    # Names that are commonly used by frameworks
    SPECIAL_NAMES = {
        'main', 'setup', 'teardown', 'run', 'execute',
        'init', 'config', 'settings', 'app', 'application',
        '__init__', '__main__', '__all__', '__version__',
    }

    def __init__(self):
        self._definitions: Dict[str, Dict] = {}  # filepath -> definitions
        self._usages: Dict[str, Set[str]] = {}  # filepath -> used names
        self._all_usages: Set[str] = set()
        self._all_calls: Set[str] = set()

    def analyze_file(self, filepath: str) -> Tuple[Dict, Set[str]]:
        """Analyze a single file for definitions and usages."""
        path = Path(filepath)
        if not path.exists() or path.suffix != '.py':
            return {}, set()

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(content)
        except SyntaxError:
            return {}, set()

        # Collect definitions
        def_collector = DefinitionCollector(filepath)
        def_collector.visit(tree)

        definitions = {
            'functions': def_collector.functions,
            'classes': def_collector.classes,
            'imports': def_collector.imports,
            'variables': def_collector.variables,
        }

        # Collect usages
        usage_collector = UsageCollector()
        usage_collector.visit(tree)

        usages = usage_collector.names_used | usage_collector.calls

        self._definitions[filepath] = definitions
        self._usages[filepath] = usages

        return definitions, usages

    def analyze_project(self, files: List[str]) -> DeadCodeReport:
        """
        Analyze entire project for dead code.

        Args:
            files: List of Python file paths

        Returns:
            DeadCodeReport with all dead code items
        """
        # Reset state
        self._definitions = {}
        self._usages = {}
        self._all_usages = set()
        self._all_calls = set()

        total_definitions = 0

        # First pass: collect all definitions and usages
        for filepath in files:
            if not filepath.endswith('.py'):
                continue

            definitions, usages = self.analyze_file(filepath)
            self._all_usages.update(usages)

            total_definitions += len(definitions.get('functions', []))
            total_definitions += len(definitions.get('classes', []))
            total_definitions += len(definitions.get('imports', []))
            total_definitions += len(definitions.get('variables', []))

        # Second pass: find dead code
        dead_functions = []
        dead_classes = []
        dead_imports = []
        dead_variables = []
        potential_savings = 0

        for filepath, definitions in self._definitions.items():
            # Check functions
            for func in definitions.get('functions', []):
                if self._is_function_dead(func, filepath):
                    item = self._create_dead_item(func, filepath, 'function')
                    dead_functions.append(item)
                    potential_savings += func['end_line'] - func['line'] + 1

            # Check classes
            for cls in definitions.get('classes', []):
                if self._is_class_dead(cls, filepath):
                    item = self._create_dead_item(cls, filepath, 'class')
                    dead_classes.append(item)
                    potential_savings += cls['end_line'] - cls['line'] + 1

            # Check imports
            for imp in definitions.get('imports', []):
                if self._is_import_dead(imp, filepath):
                    item = self._create_dead_import(imp, filepath)
                    dead_imports.append(item)
                    potential_savings += 1

            # Check variables
            for var in definitions.get('variables', []):
                if self._is_variable_dead(var, filepath):
                    item = self._create_dead_variable(var, filepath)
                    dead_variables.append(item)
                    potential_savings += 1

        return DeadCodeReport(
            total_definitions=total_definitions,
            dead_functions=dead_functions,
            dead_classes=dead_classes,
            dead_imports=dead_imports,
            dead_variables=dead_variables,
            potential_savings_lines=potential_savings,
            summary={
                'total_dead': len(dead_functions) + len(dead_classes) + len(dead_imports) + len(dead_variables),
                'dead_functions': len(dead_functions),
                'dead_classes': len(dead_classes),
                'dead_imports': len(dead_imports),
                'dead_variables': len(dead_variables),
                'files_analyzed': len(self._definitions),
                'potential_lines_saved': potential_savings,
            }
        )

    def _is_function_dead(self, func: Dict, filepath: str) -> bool:
        """Check if a function is potentially dead."""
        name = func['name']

        # Skip dunder methods
        if func['is_dunder']:
            return False

        # Skip special framework names
        if name in self.SPECIAL_NAMES:
            return False

        # Skip decorated functions (might be used by framework)
        for dec in func.get('decorators', []):
            if dec.lower() in self.FRAMEWORK_DECORATORS:
                return False

        # Check if name is used anywhere
        return name not in self._all_usages

    def _is_class_dead(self, cls: Dict, filepath: str) -> bool:
        """Check if a class is potentially dead."""
        name = cls['name']

        # Skip special names
        if name in self.SPECIAL_NAMES:
            return False

        # Skip decorated classes
        for dec in cls.get('decorators', []):
            if dec.lower() in self.FRAMEWORK_DECORATORS:
                return False

        return name not in self._all_usages

    def _is_import_dead(self, imp: Dict, filepath: str) -> bool:
        """Check if an import is potentially dead."""
        # Get the name that would be used in code
        used_name = imp.get('alias') or imp.get('short_name') or imp['name'].split('.')[-1]

        # Check in the same file's usages
        file_usages = self._usages.get(filepath, set())

        return used_name not in file_usages

    def _is_variable_dead(self, var: Dict, filepath: str) -> bool:
        """Check if a variable is potentially dead."""
        name = var['name']

        # Skip constants (might be used for configuration)
        if var.get('is_constant'):
            return False

        # Skip special names
        if name.startswith('__') or name in {'app', 'config', 'settings', 'logger'}:
            return False

        return name not in self._all_usages

    def _create_dead_item(self, item: Dict, filepath: str, item_type: str) -> DeadCodeItem:
        """Create a DeadCodeItem from definition."""
        name = item['name']

        # Calculate confidence
        confidence = 0.7  # Base confidence

        if item.get('is_private'):
            confidence = 0.9  # Private items more likely dead
        elif item.get('decorators'):
            confidence = 0.5  # Decorated might be used by framework

        # Generate suggestion
        if item_type == 'function':
            suggestion = f"Consider removing function '{name}' or marking it with @deprecated"
        else:
            suggestion = f"Consider removing class '{name}' if truly unused"

        return DeadCodeItem(
            filepath=filepath,
            name=name,
            item_type=item_type,
            line_number=item['line'],
            confidence=confidence,
            reason=f"No usage found in analyzed files",
            suggestion=suggestion,
        )

    def _create_dead_import(self, imp: Dict, filepath: str) -> DeadCodeItem:
        """Create a DeadCodeItem for unused import."""
        name = imp.get('short_name') or imp['name']

        return DeadCodeItem(
            filepath=filepath,
            name=name,
            item_type='import',
            line_number=imp['line'],
            confidence=0.95,  # Imports are easy to verify
            reason="Import is not used in this file",
            suggestion=f"Remove unused import: {imp['name']}",
        )

    def _create_dead_variable(self, var: Dict, filepath: str) -> DeadCodeItem:
        """Create a DeadCodeItem for unused variable."""
        return DeadCodeItem(
            filepath=filepath,
            name=var['name'],
            item_type='variable',
            line_number=var['line'],
            confidence=0.8,
            reason="Variable is assigned but never used",
            suggestion=f"Remove or use variable '{var['name']}'",
        )

    def find_dead_in_file(self, filepath: str, project_files: List[str] = None) -> List[DeadCodeItem]:
        """
        Find dead code in a specific file.

        If project_files is provided, checks usage across the project.
        Otherwise, only checks within the file.
        """
        if project_files:
            report = self.analyze_project(project_files)
            return [
                item for item in
                report.dead_functions + report.dead_classes +
                report.dead_imports + report.dead_variables
                if item.filepath == filepath
            ]
        else:
            # Analyze single file
            report = self.analyze_project([filepath])
            return (
                report.dead_functions + report.dead_classes +
                report.dead_imports + report.dead_variables
            )
