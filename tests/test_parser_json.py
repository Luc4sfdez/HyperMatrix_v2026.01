"""
HyperMatrix v2026 - JSON Parser Tests
"""

import pytest
from src.parsers import (
    JSONParser,
    JSONParseResult,
    JSONKeyInfo,
    JSONArrayInfo,
    JSONObjectInfo,
    JSONSchemaInfo,
    JSONDataFlowInfo,
    JSONValueType,
    JSONDataFlowType,
)


class TestJSONParser:
    """Tests for JSONParser class."""

    def test_parser_initialization(self):
        """Test parser can be instantiated."""
        parser = JSONParser()
        assert parser is not None

    def test_parse_returns_result(self, sample_json_code):
        """Test parse returns JSONParseResult."""
        parser = JSONParser()
        result = parser.parse(sample_json_code)
        assert isinstance(result, JSONParseResult)

    def test_parse_empty_object(self):
        """Test parsing empty object."""
        parser = JSONParser()
        result = parser.parse("{}")
        assert isinstance(result, JSONParseResult)
        assert result.is_valid is True
        assert result.root_type == JSONValueType.OBJECT

    def test_parse_empty_array(self):
        """Test parsing empty array."""
        parser = JSONParser()
        result = parser.parse("[]")
        assert result.is_valid is True
        assert result.root_type == JSONValueType.ARRAY


class TestValidation:
    """Tests for JSON validation."""

    def test_valid_json(self):
        """Test valid JSON passes validation."""
        parser = JSONParser()
        is_valid, error = parser.validate('{"key": "value"}')
        assert is_valid is True
        assert error is None

    def test_invalid_json(self):
        """Test invalid JSON fails validation."""
        parser = JSONParser()
        is_valid, error = parser.validate('{invalid}')
        assert is_valid is False
        assert error is not None

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        parser = JSONParser()
        result = parser.parse('{not valid json}')
        assert result.is_valid is False
        assert result.error_message is not None


class TestKeyExtraction:
    """Tests for key extraction."""

    def test_extract_simple_keys(self):
        """Test extracting simple keys."""
        json_str = '{"name": "test", "value": 42}'
        parser = JSONParser()
        result = parser.parse(json_str)

        key_names = [k.key for k in result.keys]
        assert "name" in key_names
        assert "value" in key_names

    def test_extract_nested_keys(self):
        """Test extracting nested keys."""
        json_str = '{"outer": {"inner": "value"}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        key_names = [k.key for k in result.keys]
        assert "outer" in key_names
        assert "inner" in key_names

    def test_key_paths(self):
        """Test key paths are correct."""
        json_str = '{"a": {"b": {"c": 1}}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        paths = [k.path for k in result.keys]
        assert "$.a" in paths
        assert "$.a.b" in paths
        assert "$.a.b.c" in paths

    def test_key_value_types(self):
        """Test key value types are detected."""
        json_str = '''
{
    "string": "text",
    "number": 42,
    "boolean": true,
    "null_val": null,
    "array": [],
    "object": {}
}
'''
        parser = JSONParser()
        result = parser.parse(json_str)

        types_by_key = {k.key: k.value_type for k in result.keys}
        assert types_by_key["string"] == JSONValueType.STRING
        assert types_by_key["number"] == JSONValueType.NUMBER
        assert types_by_key["boolean"] == JSONValueType.BOOLEAN
        assert types_by_key["null_val"] == JSONValueType.NULL
        assert types_by_key["array"] == JSONValueType.ARRAY
        assert types_by_key["object"] == JSONValueType.OBJECT


class TestArrayExtraction:
    """Tests for array extraction."""

    def test_extract_simple_array(self):
        """Test extracting simple array."""
        json_str = '{"items": [1, 2, 3]}'
        parser = JSONParser()
        result = parser.parse(json_str)

        arrays = [a for a in result.arrays if "items" in a.path]
        assert len(arrays) == 1
        assert arrays[0].length == 3

    def test_extract_array_item_types(self):
        """Test array item types are detected."""
        json_str = '{"mixed": [1, "text", true, null]}'
        parser = JSONParser()
        result = parser.parse(json_str)

        array = next(a for a in result.arrays if "mixed" in a.path)
        assert JSONValueType.NUMBER in array.item_types
        assert JSONValueType.STRING in array.item_types
        assert JSONValueType.BOOLEAN in array.item_types
        assert JSONValueType.NULL in array.item_types

    def test_extract_nested_arrays(self):
        """Test extracting nested arrays."""
        json_str = '{"matrix": [[1, 2], [3, 4]]}'
        parser = JSONParser()
        result = parser.parse(json_str)

        # Should have outer array and inner arrays
        assert len(result.arrays) >= 3

    def test_root_array(self):
        """Test root-level array."""
        json_str = '[1, 2, 3]'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.root_type == JSONValueType.ARRAY
        root_array = next(a for a in result.arrays if a.path == "$")
        assert root_array.length == 3


class TestObjectExtraction:
    """Tests for object extraction."""

    def test_extract_simple_object(self):
        """Test extracting simple object."""
        json_str = '{"config": {"debug": true}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        objects = [o for o in result.objects if "config" in o.path]
        assert len(objects) >= 1

    def test_object_keys(self):
        """Test object keys are captured."""
        json_str = '{"person": {"name": "John", "age": 30}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        person_obj = next(o for o in result.objects if o.path == "$.person")
        assert "name" in person_obj.keys
        assert "age" in person_obj.keys

    def test_object_depth(self):
        """Test object depth is tracked."""
        json_str = '{"a": {"b": {"c": {}}}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        depths = [o.depth for o in result.objects]
        assert max(depths) >= 3


class TestSchemaInference:
    """Tests for schema inference."""

    def test_schema_captures_types(self):
        """Test schema captures value types."""
        json_str = '{"name": "test", "count": 5}'
        parser = JSONParser()
        result = parser.parse(json_str)

        schema_by_path = {s.path: s for s in result.schema}
        assert schema_by_path["$.name"].value_type == JSONValueType.STRING
        assert schema_by_path["$.count"].value_type == JSONValueType.NUMBER

    def test_schema_nullable(self):
        """Test schema detects nullable values."""
        json_str = '{"nullable": null}'
        parser = JSONParser()
        result = parser.parse(json_str)

        nullable_schema = next(s for s in result.schema if "nullable" in s.path)
        assert nullable_schema.nullable is True


class TestDataFlow:
    """Tests for data flow tracking."""

    def test_data_flow_read(self):
        """Test READ data flow is tracked."""
        json_str = '{"key": "value"}'
        parser = JSONParser()
        result = parser.parse(json_str)

        reads = [df for df in result.data_flow if df.flow_type == JSONDataFlowType.READ]
        assert len(reads) > 0

    def test_data_flow_write(self):
        """Test WRITE data flow is tracked for keys."""
        json_str = '{"key": "value"}'
        parser = JSONParser()
        result = parser.parse(json_str)

        writes = [df for df in result.data_flow if df.flow_type == JSONDataFlowType.WRITE]
        assert any("key" in df.path for df in writes)


class TestDepthAndTotals:
    """Tests for depth and totals calculation."""

    def test_max_depth(self):
        """Test max depth calculation."""
        json_str = '{"a": {"b": {"c": {"d": 1}}}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.max_depth >= 4

    def test_total_keys(self):
        """Test total keys count."""
        json_str = '{"a": 1, "b": 2, "c": {"d": 3}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.total_keys == 4  # a, b, c, d


class TestPathNavigation:
    """Tests for path navigation."""

    def test_get_paths(self):
        """Test getting all paths."""
        json_str = '{"a": {"b": 1}, "c": [1, 2]}'
        parser = JSONParser()
        paths = parser.get_paths(json_str)

        assert "$.a" in paths
        assert "$.a.b" in paths
        assert "$.c" in paths

    def test_get_value_at_path_root(self):
        """Test getting value at root path."""
        json_str = '{"key": "value"}'
        parser = JSONParser()
        value = parser.get_value_at_path(json_str, "$")

        assert value == {"key": "value"}

    def test_get_value_at_path_nested(self):
        """Test getting value at nested path."""
        json_str = '{"outer": {"inner": 42}}'
        parser = JSONParser()
        value = parser.get_value_at_path(json_str, "$.outer.inner")

        assert value == 42

    def test_get_value_at_path_array_index(self):
        """Test getting value at array index."""
        json_str = '{"items": [10, 20, 30]}'
        parser = JSONParser()
        value = parser.get_value_at_path(json_str, "$.items[1]")

        assert value == 20


class TestParseFile:
    """Tests for file parsing."""

    def test_parse_file(self, create_temp_file, sample_json_code):
        """Test parsing a JSON file."""
        filepath = create_temp_file("test.json", sample_json_code)

        parser = JSONParser()
        result = parser.parse_file(filepath)

        assert isinstance(result, JSONParseResult)
        assert result.is_valid is True
        assert len(result.keys) > 0

    def test_parse_file_not_found(self):
        """Test parsing non-existent file raises error."""
        parser = JSONParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_file("nonexistent.json")


class TestEdgeCases:
    """Tests for edge cases."""

    def test_unicode_strings(self):
        """Test JSON with unicode strings."""
        json_str = '{"message": "Hello, \\u4e16\\u754c"}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.is_valid is True

    def test_large_numbers(self):
        """Test JSON with large numbers."""
        json_str = '{"big": 12345678901234567890}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.is_valid is True

    def test_float_numbers(self):
        """Test JSON with float numbers."""
        json_str = '{"pi": 3.14159, "negative": -2.5, "exp": 1.23e10}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.is_valid is True
        types = {k.key: k.value_type for k in result.keys}
        assert types["pi"] == JSONValueType.NUMBER

    def test_empty_string_key(self):
        """Test JSON with empty string value."""
        json_str = '{"empty": ""}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.is_valid is True

    def test_special_characters_in_string(self):
        """Test JSON with special characters."""
        json_str = '{"special": "line1\\nline2\\ttab"}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.is_valid is True

    def test_deeply_nested(self):
        """Test deeply nested JSON."""
        json_str = '{"a":{"b":{"c":{"d":{"e":{"f":1}}}}}}'
        parser = JSONParser()
        result = parser.parse(json_str)

        assert result.is_valid is True
        assert result.max_depth >= 6

    def test_complex_sample(self, sample_json_code):
        """Test complex sample JSON."""
        parser = JSONParser()
        result = parser.parse(sample_json_code)

        assert result.is_valid is True
        assert result.total_keys > 5
        assert len(result.arrays) >= 2  # extensions and authors
