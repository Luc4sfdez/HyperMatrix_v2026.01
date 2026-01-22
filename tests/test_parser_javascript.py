"""
HyperMatrix v2026 - JavaScript Parser Tests
"""

import pytest
from src.parsers import (
    JavaScriptParser,
    JSParseResult,
    JSFunctionInfo,
    JSClassInfo,
    JSVariableInfo,
    JSImportInfo,
    JSExportInfo,
    JSDataFlowInfo,
    JSDataFlowType,
)


class TestJavaScriptParser:
    """Tests for JavaScriptParser class."""

    def test_parser_initialization(self):
        """Test parser can be instantiated."""
        parser = JavaScriptParser()
        assert parser is not None

    def test_parse_returns_result(self, sample_javascript_code):
        """Test parse returns JSParseResult."""
        parser = JavaScriptParser()
        result = parser.parse(sample_javascript_code)
        assert isinstance(result, JSParseResult)

    def test_parse_empty_code(self):
        """Test parsing empty code."""
        parser = JavaScriptParser()
        result = parser.parse("")
        assert isinstance(result, JSParseResult)
        assert len(result.functions) == 0
        assert len(result.classes) == 0


class TestFunctionExtraction:
    """Tests for JavaScript function extraction."""

    def test_extract_simple_function(self):
        """Test extracting a simple function."""
        code = '''
function hello(name) {
    return "Hello, " + name;
}
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        assert len(result.functions) >= 1
        func = next((f for f in result.functions if f.name == "hello"), None)
        assert func is not None
        assert "name" in func.params

    def test_extract_async_function(self):
        """Test extracting async function."""
        code = '''
async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        func = next((f for f in result.functions if f.name == "fetchData"), None)
        assert func is not None
        assert func.is_async is True

    def test_extract_generator_function(self):
        """Test extracting generator function."""
        code = '''
function* generator(n) {
    for (let i = 0; i < n; i++) {
        yield i;
    }
}
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        func = next((f for f in result.functions if f.name == "generator"), None)
        assert func is not None
        assert func.is_generator is True

    def test_extract_arrow_function(self):
        """Test extracting arrow function."""
        code = '''
const greet = (name) => {
    return `Hello, ${name}!`;
};
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        func = next((f for f in result.functions if f.name == "greet"), None)
        assert func is not None
        assert func.is_arrow is True

    def test_extract_async_arrow_function(self):
        """Test extracting async arrow function."""
        code = '''
const fetchUser = async (id) => {
    return await api.getUser(id);
};
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        func = next((f for f in result.functions if f.name == "fetchUser"), None)
        assert func is not None
        assert func.is_async is True
        assert func.is_arrow is True


class TestClassExtraction:
    """Tests for JavaScript class extraction."""

    def test_extract_simple_class(self):
        """Test extracting a simple class."""
        code = '''
class MyClass {
    constructor(value) {
        this.value = value;
    }

    getValue() {
        return this.value;
    }
}
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "MyClass"
        assert "constructor" in cls.methods
        assert "getValue" in cls.methods

    def test_extract_class_with_extends(self):
        """Test extracting class with inheritance."""
        code = '''
class ChildClass extends ParentClass {
    constructor() {
        super();
    }
}
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "ChildClass"
        assert cls.extends == "ParentClass"

    def test_extract_class_with_static_method(self):
        """Test extracting class with static methods."""
        code = '''
class Utility {
    static helper() {
        return true;
    }

    async fetchData() {
        return await api.get();
    }
}
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        cls = result.classes[0]
        assert "helper" in cls.methods
        assert "fetchData" in cls.methods


class TestImportExtraction:
    """Tests for JavaScript import extraction."""

    def test_extract_default_import(self):
        """Test extracting default import."""
        code = "import React from 'react';"
        parser = JavaScriptParser()
        result = parser.parse(code)

        assert len(result.imports) >= 1
        imp = next((i for i in result.imports if i.module == "react"), None)
        assert imp is not None
        assert imp.is_default is True

    def test_extract_named_imports(self):
        """Test extracting named imports."""
        code = "import { useState, useEffect } from 'react';"
        parser = JavaScriptParser()
        result = parser.parse(code)

        imp = next((i for i in result.imports if i.module == "react"), None)
        assert imp is not None
        assert "useState" in imp.names or "useEffect" in imp.names

    def test_extract_namespace_import(self):
        """Test extracting namespace import."""
        code = "import * as utils from './utils';"
        parser = JavaScriptParser()
        result = parser.parse(code)

        imp = next((i for i in result.imports if i.module == "./utils"), None)
        assert imp is not None
        assert imp.is_namespace is True

    def test_extract_multiple_imports(self, sample_javascript_code):
        """Test extracting multiple imports."""
        parser = JavaScriptParser()
        result = parser.parse(sample_javascript_code)

        assert len(result.imports) >= 2


class TestExportExtraction:
    """Tests for JavaScript export extraction."""

    def test_extract_default_export(self):
        """Test extracting default export."""
        code = "export default MyClass;"
        parser = JavaScriptParser()
        result = parser.parse(code)

        exports = [e for e in result.exports if e.is_default]
        assert len(exports) >= 1

    def test_extract_named_export(self):
        """Test extracting named exports."""
        code = "export { foo, bar };"
        parser = JavaScriptParser()
        result = parser.parse(code)

        assert len(result.exports) >= 1

    def test_extract_export_function(self):
        """Test extracting exported function."""
        code = '''
export function helper() {
    return true;
}
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        export = next((e for e in result.exports if e.name == "helper"), None)
        assert export is not None


class TestVariableExtraction:
    """Tests for JavaScript variable extraction."""

    def test_extract_const(self):
        """Test extracting const declaration."""
        code = "const API_URL = 'https://api.example.com';"
        parser = JavaScriptParser()
        result = parser.parse(code)

        var = next((v for v in result.variables if v.name == "API_URL"), None)
        assert var is not None
        assert var.kind == "const"

    def test_extract_let(self):
        """Test extracting let declaration."""
        code = "let counter = 0;"
        parser = JavaScriptParser()
        result = parser.parse(code)

        var = next((v for v in result.variables if v.name == "counter"), None)
        assert var is not None
        assert var.kind == "let"

    def test_extract_var(self):
        """Test extracting var declaration."""
        code = "var oldStyle = true;"
        parser = JavaScriptParser()
        result = parser.parse(code)

        var = next((v for v in result.variables if v.name == "oldStyle"), None)
        assert var is not None
        assert var.kind == "var"


class TestDataFlowExtraction:
    """Tests for JavaScript data flow extraction."""

    def test_extract_write_operation(self):
        """Test extracting WRITE data flow."""
        code = "let x = 10;"
        parser = JavaScriptParser()
        result = parser.parse(code)

        writes = [df for df in result.data_flow if df.flow_type == JSDataFlowType.WRITE]
        assert any(df.variable == "x" for df in writes)

    def test_extract_read_operation(self):
        """Test extracting READ data flow."""
        code = '''
let x = 10;
let y = x + 5;
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        reads = [df for df in result.data_flow if df.flow_type == JSDataFlowType.READ]
        assert any(df.variable == "x" for df in reads)


class TestParseFile:
    """Tests for file parsing."""

    def test_parse_file(self, create_temp_file, sample_javascript_code):
        """Test parsing a JavaScript file."""
        filepath = create_temp_file("test_module.js", sample_javascript_code)

        parser = JavaScriptParser()
        result = parser.parse_file(filepath)

        assert isinstance(result, JSParseResult)
        assert len(result.functions) > 0
        assert len(result.classes) > 0

    def test_parse_file_not_found(self):
        """Test parsing non-existent file raises error."""
        parser = JavaScriptParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_file("nonexistent_file.js")


class TestEdgeCases:
    """Tests for edge cases."""

    def test_anonymous_function(self):
        """Test anonymous function in callback."""
        code = '''
array.map(function(item) {
    return item * 2;
});
'''
        parser = JavaScriptParser()
        result = parser.parse(code)

        # Anonymous functions may or may not be captured
        assert isinstance(result, JSParseResult)

    def test_iife(self):
        """Test Immediately Invoked Function Expression."""
        code = '''
(function() {
    console.log("IIFE");
})();
'''
        parser = JavaScriptParser()
        result = parser.parse(code)
        assert isinstance(result, JSParseResult)

    def test_object_method_shorthand(self):
        """Test object method shorthand."""
        code = '''
const obj = {
    method() {
        return true;
    }
};
'''
        parser = JavaScriptParser()
        result = parser.parse(code)
        assert isinstance(result, JSParseResult)

    def test_destructuring_not_captured_as_function(self):
        """Test destructuring doesn't create false function."""
        code = "const { a, b } = obj;"
        parser = JavaScriptParser()
        result = parser.parse(code)

        # Should not create functions named 'a' or 'b'
        func_names = [f.name for f in result.functions]
        assert "a" not in func_names
        assert "b" not in func_names
