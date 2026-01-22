"""
HyperMatrix v2026 - Python AST Parser
Extracts functions, classes, variables, imports and data flow.
"""

import ast
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class DataFlowType(Enum):
    """Type of data flow operation."""
    READ = "READ"
    WRITE = "WRITE"


@dataclass
class FunctionInfo:
    """Information about a function."""
    name: str
    lineno: int
    col_offset: int
    args: list[str] = field(default_factory=list)
    returns: Optional[str] = None
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False
    docstring: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    lineno: int
    col_offset: int
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class VariableInfo:
    """Information about a variable."""
    name: str
    lineno: int
    col_offset: int
    type_annotation: Optional[str] = None
    scope: str = "global"


@dataclass
class ImportInfo:
    """Information about an import."""
    module: str
    lineno: int
    names: list[str] = field(default_factory=list)
    is_from_import: bool = False


@dataclass
class DataFlowInfo:
    """Information about data flow."""
    variable: str
    lineno: int
    col_offset: int
    flow_type: DataFlowType
    scope: str = "global"


@dataclass
class ParseResult:
    """Result of parsing a Python file."""
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    variables: list[VariableInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    data_flow: list[DataFlowInfo] = field(default_factory=list)


class PythonASTVisitor(ast.NodeVisitor):
    """AST Visitor to extract code elements from Python source."""

    def __init__(self):
        self.result = ParseResult()
        self._current_scope = "global"
        self._scope_stack = []

    def _push_scope(self, name: str):
        """Push a new scope onto the stack."""
        self._scope_stack.append(self._current_scope)
        self._current_scope = f"{self._current_scope}.{name}" if self._current_scope != "global" else name

    def _pop_scope(self):
        """Pop the current scope from the stack."""
        if self._scope_stack:
            self._current_scope = self._scope_stack.pop()
        else:
            self._current_scope = "global"

    def _get_decorator_names(self, decorators: list) -> list[str]:
        """Extract decorator names from decorator nodes."""
        names = []
        for dec in decorators:
            if isinstance(dec, ast.Name):
                names.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                names.append(ast.unparse(dec))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    names.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    names.append(ast.unparse(dec.func))
        return names

    def _get_docstring(self, node) -> Optional[str]:
        """Extract docstring from a node."""
        if node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, ast.Constant):
                if isinstance(node.body[0].value.value, str):
                    return node.body[0].value.value
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit a function definition."""
        args = [arg.arg for arg in node.args.args]
        returns = ast.unparse(node.returns) if node.returns else None

        func_info = FunctionInfo(
            name=node.name,
            lineno=node.lineno,
            col_offset=node.col_offset,
            args=args,
            returns=returns,
            decorators=self._get_decorator_names(node.decorator_list),
            is_async=False,
            docstring=self._get_docstring(node),
        )
        self.result.functions.append(func_info)

        self._push_scope(node.name)
        self.generic_visit(node)
        self._pop_scope()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit an async function definition."""
        args = [arg.arg for arg in node.args.args]
        returns = ast.unparse(node.returns) if node.returns else None

        func_info = FunctionInfo(
            name=node.name,
            lineno=node.lineno,
            col_offset=node.col_offset,
            args=args,
            returns=returns,
            decorators=self._get_decorator_names(node.decorator_list),
            is_async=True,
            docstring=self._get_docstring(node),
        )
        self.result.functions.append(func_info)

        self._push_scope(node.name)
        self.generic_visit(node)
        self._pop_scope()

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit a class definition."""
        bases = [ast.unparse(base) for base in node.bases]
        methods = [
            item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        class_info = ClassInfo(
            name=node.name,
            lineno=node.lineno,
            col_offset=node.col_offset,
            bases=bases,
            methods=methods,
            decorators=self._get_decorator_names(node.decorator_list),
            docstring=self._get_docstring(node),
        )
        self.result.classes.append(class_info)

        self._push_scope(node.name)
        self.generic_visit(node)
        self._pop_scope()

    def visit_Import(self, node: ast.Import):
        """Visit an import statement."""
        for alias in node.names:
            import_info = ImportInfo(
                module=alias.name,
                lineno=node.lineno,
                names=[alias.asname or alias.name],
                is_from_import=False,
            )
            self.result.imports.append(import_info)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Visit a from...import statement."""
        module = node.module or ""
        names = [alias.name for alias in node.names]

        import_info = ImportInfo(
            module=module,
            lineno=node.lineno,
            names=names,
            is_from_import=True,
        )
        self.result.imports.append(import_info)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Visit an assignment (WRITE operation)."""
        for target in node.targets:
            self._extract_write_targets(target)
        self._extract_reads(node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Visit an annotated assignment."""
        if isinstance(node.target, ast.Name):
            type_ann = ast.unparse(node.annotation) if node.annotation else None
            var_info = VariableInfo(
                name=node.target.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                type_annotation=type_ann,
                scope=self._current_scope,
            )
            self.result.variables.append(var_info)

            flow_info = DataFlowInfo(
                variable=node.target.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                flow_type=DataFlowType.WRITE,
                scope=self._current_scope,
            )
            self.result.data_flow.append(flow_info)

        if node.value:
            self._extract_reads(node.value)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        """Visit an augmented assignment (e.g., +=)."""
        if isinstance(node.target, ast.Name):
            # Both READ and WRITE
            self.result.data_flow.append(DataFlowInfo(
                variable=node.target.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                flow_type=DataFlowType.READ,
                scope=self._current_scope,
            ))
            self.result.data_flow.append(DataFlowInfo(
                variable=node.target.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                flow_type=DataFlowType.WRITE,
                scope=self._current_scope,
            ))
        self._extract_reads(node.value)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        """Visit a name node (READ operation when in Load context)."""
        if isinstance(node.ctx, ast.Load):
            flow_info = DataFlowInfo(
                variable=node.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                flow_type=DataFlowType.READ,
                scope=self._current_scope,
            )
            self.result.data_flow.append(flow_info)
        self.generic_visit(node)

    def _extract_write_targets(self, target):
        """Extract WRITE targets from assignment."""
        if isinstance(target, ast.Name):
            var_info = VariableInfo(
                name=target.id,
                lineno=target.lineno,
                col_offset=target.col_offset,
                scope=self._current_scope,
            )
            self.result.variables.append(var_info)

            flow_info = DataFlowInfo(
                variable=target.id,
                lineno=target.lineno,
                col_offset=target.col_offset,
                flow_type=DataFlowType.WRITE,
                scope=self._current_scope,
            )
            self.result.data_flow.append(flow_info)

        elif isinstance(target, ast.Tuple):
            for elt in target.elts:
                self._extract_write_targets(elt)

        elif isinstance(target, ast.List):
            for elt in target.elts:
                self._extract_write_targets(elt)

    def _extract_reads(self, node):
        """Extract READ operations from an expression."""
        if isinstance(node, ast.Name):
            flow_info = DataFlowInfo(
                variable=node.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                flow_type=DataFlowType.READ,
                scope=self._current_scope,
            )
            self.result.data_flow.append(flow_info)

        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for elt in node.elts:
                self._extract_reads(elt)

        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if key:
                    self._extract_reads(key)
            for value in node.values:
                self._extract_reads(value)

        elif isinstance(node, ast.BinOp):
            self._extract_reads(node.left)
            self._extract_reads(node.right)

        elif isinstance(node, ast.Call):
            self._extract_reads(node.func)
            for arg in node.args:
                self._extract_reads(arg)


class PythonParser:
    """Parser for Python source code."""

    def parse(self, source: str) -> ParseResult:
        """Parse Python source code and extract elements."""
        tree = ast.parse(source)
        visitor = PythonASTVisitor()
        visitor.visit(tree)
        return visitor.result

    def parse_file(self, filepath: str) -> ParseResult:
        """Parse a Python file and extract elements."""
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        return self.parse(source)
