"""
HyperMatrix v2026 - JavaScript Parser
Extracts functions, classes, variables, imports and data flow using regex patterns.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class JSDataFlowType(Enum):
    """Type of data flow operation."""
    READ = "READ"
    WRITE = "WRITE"


@dataclass
class JSFunctionInfo:
    """Information about a JavaScript function."""
    name: str
    lineno: int
    params: list[str] = field(default_factory=list)
    is_async: bool = False
    is_arrow: bool = False
    is_generator: bool = False
    is_method: bool = False


@dataclass
class JSClassInfo:
    """Information about a JavaScript class."""
    name: str
    lineno: int
    extends: Optional[str] = None
    methods: list[str] = field(default_factory=list)


@dataclass
class JSVariableInfo:
    """Information about a JavaScript variable."""
    name: str
    lineno: int
    kind: str = "var"  # var, let, const
    scope: str = "global"


@dataclass
class JSImportInfo:
    """Information about a JavaScript import."""
    module: str
    lineno: int
    names: list[str] = field(default_factory=list)
    is_default: bool = False
    is_namespace: bool = False


@dataclass
class JSExportInfo:
    """Information about a JavaScript export."""
    name: str
    lineno: int
    is_default: bool = False


@dataclass
class JSDataFlowInfo:
    """Information about data flow."""
    variable: str
    lineno: int
    flow_type: JSDataFlowType
    scope: str = "global"


@dataclass
class JSParseResult:
    """Result of parsing a JavaScript file."""
    functions: list[JSFunctionInfo] = field(default_factory=list)
    classes: list[JSClassInfo] = field(default_factory=list)
    variables: list[JSVariableInfo] = field(default_factory=list)
    imports: list[JSImportInfo] = field(default_factory=list)
    exports: list[JSExportInfo] = field(default_factory=list)
    data_flow: list[JSDataFlowInfo] = field(default_factory=list)


class JavaScriptParser:
    """Parser for JavaScript source code using regex patterns."""

    # Regex patterns
    FUNCTION_PATTERN = re.compile(
        r'(async\s+)?function\s*(\*)?\s*(\w+)?\s*\(([^)]*)\)',
        re.MULTILINE
    )
    ARROW_FUNCTION_PATTERN = re.compile(
        r'(?:const|let|var)\s+(\w+)\s*=\s*(async\s+)?\(?([^)=]*)\)?\s*=>',
        re.MULTILINE
    )
    CLASS_PATTERN = re.compile(
        r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{',
        re.MULTILINE
    )
    METHOD_PATTERN = re.compile(
        r'(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?(\w+)\s*\([^)]*\)\s*\{',
        re.MULTILINE
    )
    VARIABLE_PATTERN = re.compile(
        r'(var|let|const)\s+(\w+)(?:\s*=)?',
        re.MULTILINE
    )
    IMPORT_PATTERN = re.compile(
        r'import\s+(?:(\w+)|(?:\{([^}]+)\})|(\*\s+as\s+\w+))?\s*(?:,\s*(?:\{([^}]+)\}))?\s*from\s*[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    )
    EXPORT_PATTERN = re.compile(
        r'export\s+(default\s+)?(?:(?:const|let|var|function|class)\s+)?(\w+)?',
        re.MULTILINE
    )
    ASSIGNMENT_PATTERN = re.compile(
        r'(\w+)\s*(?:\+|-|\*|\/)?=\s*([^;]+)',
        re.MULTILINE
    )

    def __init__(self):
        self.result = JSParseResult()
        self._current_scope = "global"

    def parse(self, source: str) -> JSParseResult:
        """Parse JavaScript source code and extract elements."""
        self.result = JSParseResult()
        lines = source.split('\n')

        self._extract_imports(source, lines)
        self._extract_exports(source, lines)
        self._extract_classes(source, lines)
        self._extract_functions(source, lines)
        self._extract_arrow_functions(source, lines)
        self._extract_variables(source, lines)
        self._extract_data_flow(source, lines)

        return self.result

    def parse_file(self, filepath: str) -> JSParseResult:
        """Parse a JavaScript file and extract elements."""
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        return self.parse(source)

    def _get_lineno(self, source: str, match_start: int) -> int:
        """Get line number from match position."""
        return source[:match_start].count('\n') + 1

    def _extract_functions(self, source: str, lines: list):
        """Extract function declarations."""
        for match in self.FUNCTION_PATTERN.finditer(source):
            is_async = bool(match.group(1))
            is_generator = bool(match.group(2))
            name = match.group(3) or "anonymous"
            params_str = match.group(4)
            params = [p.strip() for p in params_str.split(',') if p.strip()]

            func_info = JSFunctionInfo(
                name=name,
                lineno=self._get_lineno(source, match.start()),
                params=params,
                is_async=is_async,
                is_generator=is_generator,
            )
            self.result.functions.append(func_info)

    def _extract_arrow_functions(self, source: str, lines: list):
        """Extract arrow function declarations."""
        for match in self.ARROW_FUNCTION_PATTERN.finditer(source):
            name = match.group(1)
            is_async = bool(match.group(2))
            params_str = match.group(3)
            params = [p.strip() for p in params_str.split(',') if p.strip()]

            func_info = JSFunctionInfo(
                name=name,
                lineno=self._get_lineno(source, match.start()),
                params=params,
                is_async=is_async,
                is_arrow=True,
            )
            self.result.functions.append(func_info)

    def _extract_classes(self, source: str, lines: list):
        """Extract class declarations."""
        for match in self.CLASS_PATTERN.finditer(source):
            name = match.group(1)
            extends = match.group(2)
            lineno = self._get_lineno(source, match.start())

            # Find methods within class body
            class_start = match.end()
            brace_count = 1
            class_end = class_start

            for i, char in enumerate(source[class_start:], class_start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        class_end = i
                        break

            class_body = source[class_start:class_end]
            methods = []
            for method_match in self.METHOD_PATTERN.finditer(class_body):
                method_name = method_match.group(1)
                if method_name not in ('if', 'for', 'while', 'switch'):
                    methods.append(method_name)

            class_info = JSClassInfo(
                name=name,
                lineno=lineno,
                extends=extends,
                methods=methods,
            )
            self.result.classes.append(class_info)

    def _extract_variables(self, source: str, lines: list):
        """Extract variable declarations."""
        for match in self.VARIABLE_PATTERN.finditer(source):
            kind = match.group(1)
            name = match.group(2)

            var_info = JSVariableInfo(
                name=name,
                lineno=self._get_lineno(source, match.start()),
                kind=kind,
            )
            self.result.variables.append(var_info)

    def _extract_imports(self, source: str, lines: list):
        """Extract import statements."""
        for match in self.IMPORT_PATTERN.finditer(source):
            default_import = match.group(1)
            named_imports = match.group(2) or match.group(4)
            namespace_import = match.group(3)
            module = match.group(5)

            names = []
            is_default = False
            is_namespace = False

            if default_import:
                names.append(default_import)
                is_default = True
            if named_imports:
                names.extend([n.strip().split(' as ')[0] for n in named_imports.split(',')])
            if namespace_import:
                is_namespace = True
                names.append(namespace_import.replace('* as ', '').strip())

            import_info = JSImportInfo(
                module=module,
                lineno=self._get_lineno(source, match.start()),
                names=names,
                is_default=is_default,
                is_namespace=is_namespace,
            )
            self.result.imports.append(import_info)

    def _extract_exports(self, source: str, lines: list):
        """Extract export statements."""
        for match in self.EXPORT_PATTERN.finditer(source):
            is_default = bool(match.group(1))
            name = match.group(2) or "default"

            export_info = JSExportInfo(
                name=name,
                lineno=self._get_lineno(source, match.start()),
                is_default=is_default,
            )
            self.result.exports.append(export_info)

    def _extract_data_flow(self, source: str, lines: list):
        """Extract data flow (READ/WRITE operations)."""
        # WRITE operations from assignments
        for match in self.ASSIGNMENT_PATTERN.finditer(source):
            var_name = match.group(1)
            lineno = self._get_lineno(source, match.start())

            # Skip keywords
            if var_name in ('if', 'for', 'while', 'return', 'const', 'let', 'var'):
                continue

            self.result.data_flow.append(JSDataFlowInfo(
                variable=var_name,
                lineno=lineno,
                flow_type=JSDataFlowType.WRITE,
            ))

            # Extract READs from right side
            right_side = match.group(2)
            identifiers = re.findall(r'\b([a-zA-Z_]\w*)\b', right_side)
            for ident in identifiers:
                if ident not in ('true', 'false', 'null', 'undefined', 'this', 'new'):
                    self.result.data_flow.append(JSDataFlowInfo(
                        variable=ident,
                        lineno=lineno,
                        flow_type=JSDataFlowType.READ,
                    ))
