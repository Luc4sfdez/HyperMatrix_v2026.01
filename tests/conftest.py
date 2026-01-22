"""
HyperMatrix v2026 - Test Configuration
Shared fixtures for all tests.
"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_python_code():
    """Sample Python code for testing."""
    return '''
"""Module docstring."""

import os
from pathlib import Path
from typing import Optional, List

GLOBAL_VAR = "test"
counter = 0


class BaseClass:
    """Base class docstring."""

    def __init__(self, name: str):
        self.name = name
        self.value = 0

    def get_name(self) -> str:
        """Get the name."""
        return self.name


class ChildClass(BaseClass):
    """Child class with inheritance."""

    def __init__(self, name: str, age: int):
        super().__init__(name)
        self.age = age

    @property
    def info(self) -> str:
        return f"{self.name}: {self.age}"

    @staticmethod
    def static_method():
        pass

    async def async_method(self):
        await some_async_call()


def simple_function(x, y):
    result = x + y
    return result


def function_with_types(name: str, count: int = 0) -> Optional[str]:
    """Function with type annotations."""
    if count > 0:
        return name * count
    return None


async def async_function(data: List[str]) -> int:
    """Async function example."""
    total = 0
    for item in data:
        total += len(item)
    return total


# Variable assignments
x = 10
y = 20
x, y = y, x
result = simple_function(x, y)
'''


@pytest.fixture
def sample_javascript_code():
    """Sample JavaScript code for testing."""
    return '''
import React from 'react';
import { useState, useEffect } from 'react';
import * as utils from './utils';

const API_URL = "https://api.example.com";
let counter = 0;

class UserService {
    constructor(apiUrl) {
        this.apiUrl = apiUrl;
        this.cache = {};
    }

    async fetchUser(id) {
        const response = await fetch(`${this.apiUrl}/users/${id}`);
        return response.json();
    }

    static getInstance() {
        return new UserService(API_URL);
    }
}

function calculateTotal(items) {
    let total = 0;
    for (const item of items) {
        total += item.price;
    }
    return total;
}

const processData = async (data) => {
    const result = await transform(data);
    return result;
};

const greet = (name) => `Hello, ${name}!`;

export default UserService;
export { calculateTotal, processData };
'''


@pytest.fixture
def sample_markdown_code():
    """Sample Markdown content for testing."""
    return '''
# Main Title

This is an introduction paragraph.

## Section One

Some text with a [link](https://example.com) and an image:

![Alt text](image.png "Image title")

### Subsection

- Item 1
- Item 2
  - Nested item
- Item 3

1. First
2. Second
3. Third

## Code Examples

Here is some inline `code` example.

```python
def hello():
    print("Hello, World!")
```

```javascript
const x = 42;
```

## Table Example

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |

> This is a blockquote
> with multiple lines

---

## Final Section

The end.
'''


@pytest.fixture
def sample_json_code():
    """Sample JSON content for testing."""
    return '''
{
    "name": "HyperMatrix",
    "version": "2026.1.0",
    "description": "Code analysis engine",
    "config": {
        "debug": false,
        "maxDepth": 10,
        "extensions": [".py", ".js", ".md"]
    },
    "authors": [
        {
            "name": "Developer 1",
            "email": "dev1@example.com"
        },
        {
            "name": "Developer 2",
            "email": "dev2@example.com"
        }
    ],
    "dependencies": {
        "pytest": ">=8.0.0",
        "tqdm": ">=4.66.0"
    },
    "metadata": null,
    "enabled": true,
    "count": 42
}
'''


@pytest.fixture
def create_temp_file(temp_dir):
    """Factory fixture to create temporary files."""
    def _create_file(filename: str, content: str) -> str:
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    return _create_file
