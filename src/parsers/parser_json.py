"""
HyperMatrix v2026 - JSON Parser
Extracts structure, keys, values and validates JSON documents.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class JSONValueType(Enum):
    """Type of JSON value."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"
    ARRAY = "array"
    OBJECT = "object"


class JSONDataFlowType(Enum):
    """Type of data flow operation."""
    READ = "READ"
    WRITE = "WRITE"


@dataclass
class JSONKeyInfo:
    """Information about a JSON key."""
    key: str
    path: str
    value_type: JSONValueType
    depth: int


@dataclass
class JSONArrayInfo:
    """Information about a JSON array."""
    path: str
    length: int
    depth: int
    item_types: list[JSONValueType] = field(default_factory=list)


@dataclass
class JSONObjectInfo:
    """Information about a JSON object."""
    path: str
    keys: list[str]
    depth: int


@dataclass
class JSONSchemaInfo:
    """Inferred schema information."""
    path: str
    value_type: JSONValueType
    required: bool = True
    nullable: bool = False


@dataclass
class JSONDataFlowInfo:
    """Information about data flow."""
    path: str
    flow_type: JSONDataFlowType
    value_type: JSONValueType


@dataclass
class JSONParseResult:
    """Result of parsing a JSON file."""
    keys: list[JSONKeyInfo] = field(default_factory=list)
    arrays: list[JSONArrayInfo] = field(default_factory=list)
    objects: list[JSONObjectInfo] = field(default_factory=list)
    schema: list[JSONSchemaInfo] = field(default_factory=list)
    data_flow: list[JSONDataFlowInfo] = field(default_factory=list)
    is_valid: bool = True
    error_message: Optional[str] = None
    root_type: Optional[JSONValueType] = None
    max_depth: int = 0
    total_keys: int = 0


class JSONParser:
    """Parser for JSON documents."""

    def __init__(self):
        self.result = JSONParseResult()
        self._max_depth = 0

    def parse(self, source: str) -> JSONParseResult:
        """Parse JSON source and extract structure."""
        self.result = JSONParseResult()
        self._max_depth = 0

        try:
            data = json.loads(source)
            self.result.is_valid = True
            self.result.root_type = self._get_value_type(data)
            self._traverse(data, "$", 0)
            self.result.max_depth = self._max_depth
            self.result.total_keys = len(self.result.keys)
        except json.JSONDecodeError as e:
            self.result.is_valid = False
            self.result.error_message = str(e)

        return self.result

    def parse_file(self, filepath: str) -> JSONParseResult:
        """Parse a JSON file and extract structure."""
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        return self.parse(source)

    def _get_value_type(self, value: Any) -> JSONValueType:
        """Determine the JSON type of a value."""
        if value is None:
            return JSONValueType.NULL
        elif isinstance(value, bool):
            return JSONValueType.BOOLEAN
        elif isinstance(value, (int, float)):
            return JSONValueType.NUMBER
        elif isinstance(value, str):
            return JSONValueType.STRING
        elif isinstance(value, list):
            return JSONValueType.ARRAY
        elif isinstance(value, dict):
            return JSONValueType.OBJECT
        return JSONValueType.STRING

    def _traverse(self, data: Any, path: str, depth: int):
        """Recursively traverse JSON structure."""
        self._max_depth = max(self._max_depth, depth)
        value_type = self._get_value_type(data)

        # Record data flow READ
        self.result.data_flow.append(JSONDataFlowInfo(
            path=path,
            flow_type=JSONDataFlowType.READ,
            value_type=value_type,
        ))

        # Record schema info
        self.result.schema.append(JSONSchemaInfo(
            path=path,
            value_type=value_type,
            nullable=data is None,
        ))

        if isinstance(data, dict):
            self._process_object(data, path, depth)
        elif isinstance(data, list):
            self._process_array(data, path, depth)

    def _process_object(self, data: dict, path: str, depth: int):
        """Process a JSON object."""
        keys = list(data.keys())

        obj_info = JSONObjectInfo(
            path=path,
            keys=keys,
            depth=depth,
        )
        self.result.objects.append(obj_info)

        for key, value in data.items():
            key_path = f"{path}.{key}"
            value_type = self._get_value_type(value)

            key_info = JSONKeyInfo(
                key=key,
                path=key_path,
                value_type=value_type,
                depth=depth + 1,
            )
            self.result.keys.append(key_info)

            # Record WRITE for key assignment
            self.result.data_flow.append(JSONDataFlowInfo(
                path=key_path,
                flow_type=JSONDataFlowType.WRITE,
                value_type=value_type,
            ))

            self._traverse(value, key_path, depth + 1)

    def _process_array(self, data: list, path: str, depth: int):
        """Process a JSON array."""
        item_types = [self._get_value_type(item) for item in data]
        unique_types = list(set(item_types))

        array_info = JSONArrayInfo(
            path=path,
            length=len(data),
            depth=depth,
            item_types=unique_types,
        )
        self.result.arrays.append(array_info)

        for i, item in enumerate(data):
            item_path = f"{path}[{i}]"
            self._traverse(item, item_path, depth + 1)

    def validate(self, source: str) -> tuple[bool, Optional[str]]:
        """Validate JSON and return (is_valid, error_message)."""
        try:
            json.loads(source)
            return True, None
        except json.JSONDecodeError as e:
            return False, str(e)

    def get_paths(self, source: str) -> list[str]:
        """Get all paths in the JSON document."""
        result = self.parse(source)
        paths = [key.path for key in result.keys]
        paths.extend([arr.path for arr in result.arrays])
        paths.extend([obj.path for obj in result.objects])
        return sorted(set(paths))

    def get_value_at_path(self, source: str, path: str) -> Any:
        """Get value at a specific JSON path."""
        data = json.loads(source)

        if path == "$":
            return data

        # Parse path
        parts = path.replace("$.", "").replace("[", ".[").split(".")
        parts = [p for p in parts if p]

        current = data
        for part in parts:
            if part.startswith("[") and part.endswith("]"):
                index = int(part[1:-1])
                current = current[index]
            else:
                current = current[part]

        return current
