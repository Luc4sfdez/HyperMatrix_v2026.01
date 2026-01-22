"""
HyperMatrix v2026 - Python Parser Tests
"""

import pytest
from src.parsers import (
    PythonParser,
    PythonASTVisitor,
    ParseResult,
    FunctionInfo,
    ClassInfo,
    VariableInfo,
    ImportInfo,
    DataFlowInfo,
    DataFlowType,
)


class TestPythonParser:
    """Tests for PythonParser class."""

    def test_parser_initialization(self):
        """Test parser can be instantiated."""
        parser = PythonParser()
        assert parser is not None

    def test_parse_returns_result(self, sample_python_code):
        """Test parse returns ParseResult."""
        parser = PythonParser()
        result = parser.parse(sample_python_code)
        assert isinstance(result, ParseResult)

    def test_parse_empty_code(self):
        """Test parsing empty code."""
        parser = PythonParser()
        result = parser.parse("")
        assert isinstance(result, ParseResult)
        assert len(result.functions) == 0
        assert len(result.classes) == 0


class TestFunctionExtraction:
    """Tests for function extraction."""

    def test_extract_simple_function(self):
        """Test extracting a simple function."""
        code = '''
def hello(name):
    return f"Hello, {name}"
'''
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "hello"
        assert func.args == ["name"]
        assert func.is_async is False

    def test_extract_function_with_types(self):
        """Test extracting function with type annotations."""
        code = '''
def greet(name: str, count: int = 1) -> str:
    """Greet someone."""
    return name * count
'''
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"
        assert func.args == ["name", "count"]
        assert func.returns == "str"
        assert func.docstring == "Greet someone."

    def test_extract_async_function(self):
        """Test extracting async function."""
        code = '''
async def fetch_data(url: str) -> dict:
    response = await client.get(url)
    return response.json()
'''
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "fetch_data"
        assert func.is_async is True

    def test_extract_decorated_function(self):
        """Test extracting function with decorators."""
        code = '''
@decorator
@another_decorator
def decorated_func():
    pass
'''
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.functions) == 1
        func = result.functions[0]
        assert "decorator" in func.decorators
        assert "another_decorator" in func.decorators

    def test_extract_multiple_functions(self, sample_python_code):
        """Test extracting multiple functions."""
        parser = PythonParser()
        result = parser.parse(sample_python_code)

        func_names = [f.name for f in result.functions]
        assert "simple_function" in func_names
        assert "function_with_types" in func_names
        assert "async_function" in func_names


class TestClassExtraction:
    """Tests for class extraction."""

    def test_extract_simple_class(self):
        """Test extracting a simple class."""
        code = '''
class MyClass:
    def __init__(self):
        self.value = 0

    def get_value(self):
        return self.value
'''
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "MyClass"
        assert "__init__" in cls.methods
        assert "get_value" in cls.methods

    def test_extract_class_with_inheritance(self):
        """Test extracting class with base classes."""
        code = '''
class ChildClass(ParentClass, MixinClass):
    """Child class docstring."""
    pass
'''
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "ChildClass"
        assert "ParentClass" in cls.bases
        assert "MixinClass" in cls.bases
        assert cls.docstring == "Child class docstring."

    def test_extract_decorated_class(self):
        """Test extracting class with decorators."""
        code = '''
@dataclass
@frozen
class DataClass:
    name: str
    value: int
'''
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert "dataclass" in cls.decorators
        assert "frozen" in cls.decorators

    def test_extract_multiple_classes(self, sample_python_code):
        """Test extracting multiple classes."""
        parser = PythonParser()
        result = parser.parse(sample_python_code)

        class_names = [c.name for c in result.classes]
        assert "BaseClass" in class_names
        assert "ChildClass" in class_names


class TestImportExtraction:
    """Tests for import extraction."""

    def test_extract_simple_import(self):
        """Test extracting simple import."""
        code = "import os"
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "os"
        assert imp.is_from_import is False

    def test_extract_from_import(self):
        """Test extracting from import."""
        code = "from pathlib import Path, PurePath"
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.module == "pathlib"
        assert imp.is_from_import is True
        assert "Path" in imp.names
        assert "PurePath" in imp.names

    def test_extract_multiple_imports(self, sample_python_code):
        """Test extracting multiple imports."""
        parser = PythonParser()
        result = parser.parse(sample_python_code)

        modules = [i.module for i in result.imports]
        assert "os" in modules
        assert "pathlib" in modules
        assert "typing" in modules


class TestVariableExtraction:
    """Tests for variable extraction."""

    def test_extract_simple_assignment(self):
        """Test extracting simple variable assignment."""
        code = "x = 10"
        parser = PythonParser()
        result = parser.parse(code)

        var_names = [v.name for v in result.variables]
        assert "x" in var_names

    def test_extract_annotated_assignment(self):
        """Test extracting annotated variable."""
        code = "name: str = 'test'"
        parser = PythonParser()
        result = parser.parse(code)

        assert len(result.variables) >= 1
        var = next((v for v in result.variables if v.name == "name"), None)
        assert var is not None
        assert var.type_annotation == "str"

    def test_extract_tuple_unpacking(self):
        """Test extracting tuple unpacking."""
        code = "x, y = 1, 2"
        parser = PythonParser()
        result = parser.parse(code)

        var_names = [v.name for v in result.variables]
        assert "x" in var_names
        assert "y" in var_names


class TestDataFlowExtraction:
    """Tests for data flow extraction."""

    def test_extract_write_operation(self):
        """Test extracting WRITE data flow."""
        code = "x = 10"
        parser = PythonParser()
        result = parser.parse(code)

        writes = [df for df in result.data_flow if df.flow_type == DataFlowType.WRITE]
        assert any(df.variable == "x" for df in writes)

    def test_extract_read_operation(self):
        """Test extracting READ data flow."""
        code = '''
x = 10
y = x + 5
'''
        parser = PythonParser()
        result = parser.parse(code)

        reads = [df for df in result.data_flow if df.flow_type == DataFlowType.READ]
        assert any(df.variable == "x" for df in reads)

    def test_extract_augmented_assignment(self):
        """Test extracting augmented assignment (+=)."""
        code = '''
x = 0
x += 1
'''
        parser = PythonParser()
        result = parser.parse(code)

        # x += 1 should create both READ and WRITE
        x_flows = [df for df in result.data_flow if df.variable == "x"]
        flow_types = [df.flow_type for df in x_flows]
        assert DataFlowType.READ in flow_types
        assert DataFlowType.WRITE in flow_types


class TestParseFile:
    """Tests for file parsing."""

    def test_parse_file(self, create_temp_file, sample_python_code):
        """Test parsing a file."""
        filepath = create_temp_file("test_module.py", sample_python_code)

        parser = PythonParser()
        result = parser.parse_file(filepath)

        assert isinstance(result, ParseResult)
        assert len(result.functions) > 0
        assert len(result.classes) > 0

    def test_parse_file_not_found(self):
        """Test parsing non-existent file raises error."""
        parser = PythonParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_file("nonexistent_file.py")

    def test_parse_syntax_error(self):
        """Test parsing code with syntax error."""
        code = "def broken("  # Invalid syntax
        parser = PythonParser()

        with pytest.raises(SyntaxError):
            parser.parse(code)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_nested_functions(self):
        """Test parsing nested functions."""
        code = '''
def outer():
    def inner():
        pass
    return inner
'''
        parser = PythonParser()
        result = parser.parse(code)

        func_names = [f.name for f in result.functions]
        assert "outer" in func_names
        assert "inner" in func_names

    def test_nested_classes(self):
        """Test parsing nested classes."""
        code = '''
class Outer:
    class Inner:
        pass
'''
        parser = PythonParser()
        result = parser.parse(code)

        class_names = [c.name for c in result.classes]
        assert "Outer" in class_names
        assert "Inner" in class_names

    def test_lambda_not_extracted(self):
        """Test that lambdas are not extracted as functions."""
        code = "f = lambda x: x * 2"
        parser = PythonParser()
        result = parser.parse(code)

        # Lambda should not be in functions list
        assert len(result.functions) == 0

    def test_comprehension_variables(self):
        """Test variables in comprehensions."""
        code = "squares = [x**2 for x in range(10)]"
        parser = PythonParser()
        result = parser.parse(code)

        var_names = [v.name for v in result.variables]
        assert "squares" in var_names
