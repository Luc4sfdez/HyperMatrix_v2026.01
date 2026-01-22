"""
HyperMatrix v2026 - TypeScript Parser
Extracts code elements from TypeScript files using regex patterns.
Handles TypeScript-specific features like interfaces, types, enums, and generics.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TypeScriptFunction:
    """Represents a TypeScript function."""
    name: str
    lineno: int
    parameters: list[str] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    is_exported: bool = False
    is_arrow: bool = False
    generics: Optional[str] = None
    docstring: Optional[str] = None


@dataclass
class TypeScriptClass:
    """Represents a TypeScript class."""
    name: str
    lineno: int
    extends: Optional[str] = None
    implements: list[str] = field(default_factory=list)
    is_abstract: bool = False
    is_exported: bool = False
    generics: Optional[str] = None
    methods: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class TypeScriptInterface:
    """Represents a TypeScript interface."""
    name: str
    lineno: int
    extends: list[str] = field(default_factory=list)
    is_exported: bool = False
    generics: Optional[str] = None
    properties: list[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class TypeScriptType:
    """Represents a TypeScript type alias."""
    name: str
    lineno: int
    definition: str = ""
    is_exported: bool = False
    generics: Optional[str] = None


@dataclass
class TypeScriptEnum:
    """Represents a TypeScript enum."""
    name: str
    lineno: int
    members: list[str] = field(default_factory=list)
    is_exported: bool = False
    is_const: bool = False


@dataclass
class TypeScriptImport:
    """Represents a TypeScript import."""
    module: str
    lineno: int
    names: list[str] = field(default_factory=list)
    default_import: Optional[str] = None
    namespace_import: Optional[str] = None
    is_type_only: bool = False


@dataclass
class TypeScriptVariable:
    """Represents a TypeScript variable."""
    name: str
    lineno: int
    var_type: Optional[str] = None
    is_const: bool = False
    is_let: bool = False
    is_exported: bool = False


@dataclass
class TypeScriptDataFlow:
    """Data flow operation."""
    variable: str
    operation: str  # READ or WRITE
    lineno: int
    context: Optional[str] = None


class TypeScriptParser:
    """Parser for TypeScript files."""

    # Regex patterns for TypeScript
    PATTERNS = {
        # Function patterns
        "function": re.compile(
            r'^(?P<export>export\s+)?(?P<async>async\s+)?function\s+(?P<name>\w+)'
            r'(?P<generics><[^>]+>)?\s*\((?P<params>[^)]*)\)(?:\s*:\s*(?P<return>[^{]+))?\s*\{',
            re.MULTILINE
        ),
        "arrow_function": re.compile(
            r'^(?P<export>export\s+)?(?P<const>const|let|var)\s+(?P<name>\w+)'
            r'(?:\s*:\s*[^=]+)?\s*=\s*(?P<async>async\s+)?(?P<generics><[^>]+>)?\s*'
            r'\((?P<params>[^)]*)\)(?:\s*:\s*(?P<return>[^=]+))?\s*=>',
            re.MULTILINE
        ),
        "method": re.compile(
            r'^\s+(?P<modifier>public|private|protected|static|async|\s)*'
            r'(?P<name>\w+)(?P<generics><[^>]+>)?\s*\((?P<params>[^)]*)\)'
            r'(?:\s*:\s*(?P<return>[^{]+))?\s*\{',
            re.MULTILINE
        ),

        # Class patterns
        "class": re.compile(
            r'^(?P<export>export\s+)?(?P<abstract>abstract\s+)?class\s+(?P<name>\w+)'
            r'(?P<generics><[^>]+>)?(?:\s+extends\s+(?P<extends>[\w.]+))?'
            r'(?:\s+implements\s+(?P<implements>[^{]+))?\s*\{',
            re.MULTILINE
        ),

        # Interface patterns
        "interface": re.compile(
            r'^(?P<export>export\s+)?interface\s+(?P<name>\w+)'
            r'(?P<generics><[^>]+>)?(?:\s+extends\s+(?P<extends>[^{]+))?\s*\{',
            re.MULTILINE
        ),

        # Type alias patterns
        "type_alias": re.compile(
            r'^(?P<export>export\s+)?type\s+(?P<name>\w+)(?P<generics><[^>]+>)?\s*=\s*(?P<def>.+?)(?:;|$)',
            re.MULTILINE
        ),

        # Enum patterns
        "enum": re.compile(
            r'^(?P<export>export\s+)?(?P<const>const\s+)?enum\s+(?P<name>\w+)\s*\{',
            re.MULTILINE
        ),

        # Import patterns
        "import": re.compile(
            r'^import\s+(?P<type>type\s+)?(?:'
            r'(?P<default>\w+)|'
            r'\*\s+as\s+(?P<namespace>\w+)|'
            r'\{(?P<named>[^}]+)\}'
            r')?\s*(?:,\s*\{(?P<named2>[^}]+)\})?\s*from\s*["\'](?P<module>[^"\']+)["\']',
            re.MULTILINE
        ),
        "import_side_effect": re.compile(
            r'^import\s+["\'](?P<module>[^"\']+)["\']',
            re.MULTILINE
        ),

        # Variable patterns
        "variable": re.compile(
            r'^(?P<export>export\s+)?(?P<kind>const|let|var)\s+(?P<name>\w+)'
            r'(?:\s*:\s*(?P<type>[^=;]+))?\s*(?:=|;)',
            re.MULTILINE
        ),

        # Decorator patterns
        "decorator": re.compile(r'^@(\w+)(?:\([^)]*\))?', re.MULTILINE),

        # JSDoc comment pattern
        "jsdoc": re.compile(r'/\*\*\s*([\s\S]*?)\s*\*/'),
    }

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.content = ""
        self.lines = []

    def parse(self) -> dict:
        """Parse the TypeScript file and extract all elements."""
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            self.content = f.read()
        self.lines = self.content.split('\n')

        return {
            "functions": self._extract_functions(),
            "classes": self._extract_classes(),
            "interfaces": self._extract_interfaces(),
            "types": self._extract_types(),
            "enums": self._extract_enums(),
            "imports": self._extract_imports(),
            "variables": self._extract_variables(),
            "data_flow": self._extract_data_flow(),
        }

    def _get_lineno(self, pos: int) -> int:
        """Get line number from character position."""
        return self.content[:pos].count('\n') + 1

    def _find_preceding_jsdoc(self, pos: int) -> Optional[str]:
        """Find JSDoc comment preceding a position."""
        # Look backwards from position for JSDoc
        text_before = self.content[:pos].rstrip()
        match = re.search(r'/\*\*\s*([\s\S]*?)\s*\*/\s*$', text_before)
        if match:
            doc = match.group(1)
            # Clean up the doc
            lines = doc.split('\n')
            cleaned = []
            for line in lines:
                line = re.sub(r'^\s*\*\s?', '', line)
                cleaned.append(line)
            return '\n'.join(cleaned).strip()
        return None

    def _extract_functions(self) -> list[TypeScriptFunction]:
        """Extract all functions."""
        functions = []

        # Regular functions
        for match in self.PATTERNS["function"].finditer(self.content):
            lineno = self._get_lineno(match.start())
            params = self._parse_params(match.group("params"))
            docstring = self._find_preceding_jsdoc(match.start())

            func = TypeScriptFunction(
                name=match.group("name"),
                lineno=lineno,
                parameters=params,
                return_type=match.group("return").strip() if match.group("return") else None,
                is_async=bool(match.group("async")),
                is_exported=bool(match.group("export")),
                generics=match.group("generics"),
                docstring=docstring,
            )
            functions.append(func)

        # Arrow functions
        for match in self.PATTERNS["arrow_function"].finditer(self.content):
            lineno = self._get_lineno(match.start())
            params = self._parse_params(match.group("params"))
            docstring = self._find_preceding_jsdoc(match.start())

            func = TypeScriptFunction(
                name=match.group("name"),
                lineno=lineno,
                parameters=params,
                return_type=match.group("return").strip() if match.group("return") else None,
                is_async=bool(match.group("async")),
                is_exported=bool(match.group("export")),
                is_arrow=True,
                generics=match.group("generics"),
                docstring=docstring,
            )
            functions.append(func)

        return functions

    def _extract_classes(self) -> list[TypeScriptClass]:
        """Extract all classes."""
        classes = []

        for match in self.PATTERNS["class"].finditer(self.content):
            lineno = self._get_lineno(match.start())
            docstring = self._find_preceding_jsdoc(match.start())

            # Parse implements
            implements = []
            if match.group("implements"):
                implements = [i.strip() for i in match.group("implements").split(",")]

            # Find class body and extract methods/properties
            class_start = match.end()
            methods, properties = self._extract_class_members(class_start)

            cls = TypeScriptClass(
                name=match.group("name"),
                lineno=lineno,
                extends=match.group("extends"),
                implements=implements,
                is_abstract=bool(match.group("abstract")),
                is_exported=bool(match.group("export")),
                generics=match.group("generics"),
                methods=methods,
                properties=properties,
                docstring=docstring,
            )
            classes.append(cls)

        return classes

    def _extract_class_members(self, start_pos: int) -> tuple[list[str], list[str]]:
        """Extract methods and properties from class body."""
        methods = []
        properties = []

        # Find the matching closing brace
        brace_count = 1
        pos = start_pos
        while pos < len(self.content) and brace_count > 0:
            if self.content[pos] == '{':
                brace_count += 1
            elif self.content[pos] == '}':
                brace_count -= 1
            pos += 1

        class_body = self.content[start_pos:pos-1]

        # Find methods
        for match in self.PATTERNS["method"].finditer(class_body):
            methods.append(match.group("name"))

        # Find properties
        prop_pattern = re.compile(
            r'^\s+(?:public|private|protected|static|readonly|\s)*'
            r'(\w+)(?:\?)?(?:\s*:\s*[^;=]+)?(?:\s*=|;)',
            re.MULTILINE
        )
        for match in prop_pattern.finditer(class_body):
            name = match.group(1)
            if name not in methods and name not in ['constructor']:
                properties.append(name)

        return methods, properties

    def _extract_interfaces(self) -> list[TypeScriptInterface]:
        """Extract all interfaces."""
        interfaces = []

        for match in self.PATTERNS["interface"].finditer(self.content):
            lineno = self._get_lineno(match.start())
            docstring = self._find_preceding_jsdoc(match.start())

            # Parse extends
            extends = []
            if match.group("extends"):
                extends = [e.strip() for e in match.group("extends").split(",")]

            # Find interface body and extract properties
            interface_start = match.end()
            properties = self._extract_interface_properties(interface_start)

            iface = TypeScriptInterface(
                name=match.group("name"),
                lineno=lineno,
                extends=extends,
                is_exported=bool(match.group("export")),
                generics=match.group("generics"),
                properties=properties,
                docstring=docstring,
            )
            interfaces.append(iface)

        return interfaces

    def _extract_interface_properties(self, start_pos: int) -> list[str]:
        """Extract properties from interface body."""
        properties = []

        # Find the matching closing brace
        brace_count = 1
        pos = start_pos
        while pos < len(self.content) and brace_count > 0:
            if self.content[pos] == '{':
                brace_count += 1
            elif self.content[pos] == '}':
                brace_count -= 1
            pos += 1

        interface_body = self.content[start_pos:pos-1]

        # Find properties
        prop_pattern = re.compile(r'^\s*(?:readonly\s+)?(\w+)(?:\?)?(?:\s*:\s*[^;,]+)?[;,]?', re.MULTILINE)
        for match in prop_pattern.finditer(interface_body):
            name = match.group(1)
            if name and not name.startswith('//'):
                properties.append(name)

        return properties

    def _extract_types(self) -> list[TypeScriptType]:
        """Extract all type aliases."""
        types = []

        for match in self.PATTERNS["type_alias"].finditer(self.content):
            lineno = self._get_lineno(match.start())

            ts_type = TypeScriptType(
                name=match.group("name"),
                lineno=lineno,
                definition=match.group("def").strip(),
                is_exported=bool(match.group("export")),
                generics=match.group("generics"),
            )
            types.append(ts_type)

        return types

    def _extract_enums(self) -> list[TypeScriptEnum]:
        """Extract all enums."""
        enums = []

        for match in self.PATTERNS["enum"].finditer(self.content):
            lineno = self._get_lineno(match.start())

            # Find enum body and extract members
            enum_start = match.end()
            members = self._extract_enum_members(enum_start)

            enum = TypeScriptEnum(
                name=match.group("name"),
                lineno=lineno,
                members=members,
                is_exported=bool(match.group("export")),
                is_const=bool(match.group("const")),
            )
            enums.append(enum)

        return enums

    def _extract_enum_members(self, start_pos: int) -> list[str]:
        """Extract members from enum body."""
        members = []

        # Find the matching closing brace
        brace_count = 1
        pos = start_pos
        while pos < len(self.content) and brace_count > 0:
            if self.content[pos] == '{':
                brace_count += 1
            elif self.content[pos] == '}':
                brace_count -= 1
            pos += 1

        enum_body = self.content[start_pos:pos-1]

        # Find members
        member_pattern = re.compile(r'(\w+)(?:\s*=\s*[^,}]+)?', re.MULTILINE)
        for match in member_pattern.finditer(enum_body):
            name = match.group(1)
            if name:
                members.append(name)

        return members

    def _extract_imports(self) -> list[TypeScriptImport]:
        """Extract all imports."""
        imports = []

        # Standard imports
        for match in self.PATTERNS["import"].finditer(self.content):
            lineno = self._get_lineno(match.start())

            names = []
            named = match.group("named") or match.group("named2")
            if named:
                names = [n.strip().split(' as ')[0].strip()
                        for n in named.split(',')]

            imp = TypeScriptImport(
                module=match.group("module"),
                lineno=lineno,
                names=names,
                default_import=match.group("default"),
                namespace_import=match.group("namespace"),
                is_type_only=bool(match.group("type")),
            )
            imports.append(imp)

        # Side-effect imports
        for match in self.PATTERNS["import_side_effect"].finditer(self.content):
            # Skip if already matched by standard import
            if "from" not in self.content[match.start():match.end()+20]:
                lineno = self._get_lineno(match.start())
                imp = TypeScriptImport(
                    module=match.group("module"),
                    lineno=lineno,
                )
                imports.append(imp)

        return imports

    def _extract_variables(self) -> list[TypeScriptVariable]:
        """Extract all top-level variables."""
        variables = []

        for match in self.PATTERNS["variable"].finditer(self.content):
            lineno = self._get_lineno(match.start())
            kind = match.group("kind")

            var = TypeScriptVariable(
                name=match.group("name"),
                lineno=lineno,
                var_type=match.group("type").strip() if match.group("type") else None,
                is_const=kind == "const",
                is_let=kind == "let",
                is_exported=bool(match.group("export")),
            )
            variables.append(var)

        return variables

    def _extract_data_flow(self) -> list[TypeScriptDataFlow]:
        """Extract data flow operations."""
        data_flow = []

        # Variable assignments (WRITE)
        write_pattern = re.compile(r'(\w+)\s*(?:=|\+=|-=|\*=|\/=)', re.MULTILINE)
        for match in write_pattern.finditer(self.content):
            name = match.group(1)
            if name not in ['const', 'let', 'var', 'if', 'while', 'for', 'return']:
                lineno = self._get_lineno(match.start())
                data_flow.append(TypeScriptDataFlow(
                    variable=name,
                    operation="WRITE",
                    lineno=lineno,
                ))

        # Variable reads in expressions (simplified)
        read_pattern = re.compile(r'(?:return|console\.\w+|=)\s*(\w+)(?:\s*[;,\)]|\s*\+|\s*-)', re.MULTILINE)
        for match in read_pattern.finditer(self.content):
            name = match.group(1)
            if name not in ['true', 'false', 'null', 'undefined', 'this', 'new']:
                lineno = self._get_lineno(match.start())
                data_flow.append(TypeScriptDataFlow(
                    variable=name,
                    operation="READ",
                    lineno=lineno,
                ))

        return data_flow

    def _parse_params(self, params_str: str) -> list[str]:
        """Parse parameter string into list."""
        if not params_str or not params_str.strip():
            return []

        params = []
        depth = 0
        current = ""

        for char in params_str:
            if char in '<([{':
                depth += 1
                current += char
            elif char in '>)]}':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                param = current.strip()
                if param:
                    # Extract just the parameter name
                    name = param.split(':')[0].split('?')[0].strip()
                    if name and not name.startswith('...'):
                        params.append(name)
                    elif name.startswith('...'):
                        params.append(name[3:])
                current = ""
            else:
                current += char

        if current.strip():
            param = current.strip()
            name = param.split(':')[0].split('?')[0].strip()
            if name and not name.startswith('...'):
                params.append(name)
            elif name.startswith('...'):
                params.append(name[3:])

        return params


def parse_typescript_file(filepath: str) -> dict:
    """Convenience function to parse a TypeScript file."""
    parser = TypeScriptParser(filepath)
    return parser.parse()
