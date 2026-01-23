"""
HyperMatrix v2026 - CSS Parser
Extracts selectors, properties, media queries and stylesheet structure.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class CSSElementType(Enum):
    """Type of CSS element."""
    SELECTOR = "SELECTOR"
    PROPERTY = "PROPERTY"
    MEDIA_QUERY = "MEDIA_QUERY"
    KEYFRAME = "KEYFRAME"
    IMPORT = "IMPORT"
    VARIABLE = "VARIABLE"
    FONT_FACE = "FONT_FACE"


@dataclass
class CSSSelectorInfo:
    """Information about a CSS selector."""
    selector: str
    lineno: int
    property_count: int = 0
    is_class: bool = False
    is_id: bool = False
    is_element: bool = False
    is_pseudo: bool = False


@dataclass
class CSSPropertyInfo:
    """Information about a CSS property."""
    property: str
    value: str
    lineno: int
    selector: str
    is_important: bool = False
    is_variable: bool = False


@dataclass
class CSSMediaQueryInfo:
    """Information about a media query."""
    query: str
    lineno: int
    selector_count: int = 0


@dataclass
class CSSKeyframeInfo:
    """Information about a keyframe animation."""
    name: str
    lineno: int
    step_count: int = 0


@dataclass
class CSSImportInfo:
    """Information about a CSS import."""
    url: str
    lineno: int
    media: Optional[str] = None


@dataclass
class CSSVariableInfo:
    """Information about a CSS custom property (variable)."""
    name: str
    value: str
    lineno: int
    scope: str = ":root"


@dataclass
class CSSFontFaceInfo:
    """Information about a font-face declaration."""
    family: Optional[str]
    src: Optional[str]
    lineno: int


@dataclass
class CSSParseResult:
    """Result of parsing a CSS file."""
    selectors: list[CSSSelectorInfo] = field(default_factory=list)
    properties: list[CSSPropertyInfo] = field(default_factory=list)
    media_queries: list[CSSMediaQueryInfo] = field(default_factory=list)
    keyframes: list[CSSKeyframeInfo] = field(default_factory=list)
    imports: list[CSSImportInfo] = field(default_factory=list)
    variables: list[CSSVariableInfo] = field(default_factory=list)
    font_faces: list[CSSFontFaceInfo] = field(default_factory=list)
    selector_count: int = 0
    property_count: int = 0
    unique_selectors: set = field(default_factory=set)
    unique_properties: set = field(default_factory=set)
    has_media_queries: bool = False
    has_variables: bool = False
    has_animations: bool = False
    line_count: int = 0


class CSSParser:
    """Parser for CSS stylesheets."""

    # Regex patterns
    SELECTOR_PATTERN = re.compile(r'([^{]+)\s*\{([^}]*)\}', re.MULTILINE | re.DOTALL)
    PROPERTY_PATTERN = re.compile(r'([a-zA-Z-]+)\s*:\s*([^;]+);?')
    MEDIA_QUERY_PATTERN = re.compile(r'@media\s+([^{]+)\s*\{', re.MULTILINE)
    KEYFRAME_PATTERN = re.compile(r'@keyframes\s+([^\s{]+)', re.MULTILINE)
    IMPORT_PATTERN = re.compile(r'@import\s+(?:url\()?[\'"]?([^\'")]+)[\'"]?\)?([^;]*);', re.MULTILINE)
    VARIABLE_PATTERN = re.compile(r'(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);')
    FONT_FACE_PATTERN = re.compile(r'@font-face\s*\{([^}]+)\}', re.MULTILINE | re.DOTALL)

    def parse_file(self, filepath: str) -> CSSParseResult:
        """Parse a CSS file and return structural information."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.parse_content(content)
        except Exception as e:
            return CSSParseResult()

    def parse_content(self, content: str) -> CSSParseResult:
        """Parse CSS content string."""
        result = CSSParseResult()
        result.line_count = content.count('\n') + 1

        # Remove comments
        content_no_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Parse imports
        for match in self.IMPORT_PATTERN.finditer(content_no_comments):
            url = match.group(1)
            media = match.group(2).strip() or None
            lineno = content_no_comments[:match.start()].count('\n') + 1
            result.imports.append(CSSImportInfo(url=url, lineno=lineno, media=media))

        # Parse media queries
        for match in self.MEDIA_QUERY_PATTERN.finditer(content_no_comments):
            query = match.group(1).strip()
            lineno = content_no_comments[:match.start()].count('\n') + 1
            result.media_queries.append(CSSMediaQueryInfo(query=query, lineno=lineno))
            result.has_media_queries = True

        # Parse keyframes
        for match in self.KEYFRAME_PATTERN.finditer(content_no_comments):
            name = match.group(1).strip()
            lineno = content_no_comments[:match.start()].count('\n') + 1
            result.keyframes.append(CSSKeyframeInfo(name=name, lineno=lineno))
            result.has_animations = True

        # Parse font-faces
        for match in self.FONT_FACE_PATTERN.finditer(content_no_comments):
            block = match.group(1)
            lineno = content_no_comments[:match.start()].count('\n') + 1

            family_match = re.search(r'font-family\s*:\s*[\'"]?([^\'";]+)', block)
            src_match = re.search(r'src\s*:\s*([^;]+)', block)

            result.font_faces.append(CSSFontFaceInfo(
                family=family_match.group(1).strip() if family_match else None,
                src=src_match.group(1).strip() if src_match else None,
                lineno=lineno,
            ))

        # Parse selectors and properties
        for match in self.SELECTOR_PATTERN.finditer(content_no_comments):
            selector = match.group(1).strip()
            properties_block = match.group(2)
            lineno = content_no_comments[:match.start()].count('\n') + 1

            # Skip at-rules that we've already processed
            if selector.startswith('@'):
                continue

            # Determine selector type
            is_class = '.' in selector
            is_id = '#' in selector
            is_element = bool(re.match(r'^[a-zA-Z]', selector.split()[0] if selector else ''))
            is_pseudo = ':' in selector

            selector_info = CSSSelectorInfo(
                selector=selector,
                lineno=lineno,
                is_class=is_class,
                is_id=is_id,
                is_element=is_element,
                is_pseudo=is_pseudo,
            )

            # Parse properties within this selector
            property_count = 0
            for prop_match in self.PROPERTY_PATTERN.finditer(properties_block):
                prop_name = prop_match.group(1).strip()
                prop_value = prop_match.group(2).strip()
                prop_lineno = lineno + properties_block[:prop_match.start()].count('\n')

                is_important = '!important' in prop_value
                is_variable = prop_name.startswith('--')

                result.properties.append(CSSPropertyInfo(
                    property=prop_name,
                    value=prop_value,
                    lineno=prop_lineno,
                    selector=selector,
                    is_important=is_important,
                    is_variable=is_variable,
                ))

                result.unique_properties.add(prop_name)
                property_count += 1

                # Track CSS variables
                if is_variable:
                    result.variables.append(CSSVariableInfo(
                        name=prop_name,
                        value=prop_value.replace('!important', '').strip(),
                        lineno=prop_lineno,
                        scope=selector,
                    ))
                    result.has_variables = True

            selector_info.property_count = property_count
            result.selectors.append(selector_info)
            result.unique_selectors.add(selector)
            result.selector_count += 1
            result.property_count += property_count

        return result
