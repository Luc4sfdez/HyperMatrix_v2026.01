"""
HyperMatrix v2026 - HTML Parser
Extracts tags, attributes, scripts, styles and document structure.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from html.parser import HTMLParser as BaseHTMLParser


class HTMLElementType(Enum):
    """Type of HTML element."""
    TAG = "TAG"
    SCRIPT = "SCRIPT"
    STYLE = "STYLE"
    LINK = "LINK"
    META = "META"
    FORM = "FORM"
    INPUT = "INPUT"
    COMMENT = "COMMENT"


@dataclass
class HTMLTagInfo:
    """Information about an HTML tag."""
    name: str
    lineno: int
    attributes: dict = field(default_factory=dict)
    has_id: bool = False
    has_class: bool = False
    is_self_closing: bool = False


@dataclass
class HTMLScriptInfo:
    """Information about a script tag."""
    src: Optional[str]
    lineno: int
    is_external: bool = False
    is_module: bool = False
    content_length: int = 0


@dataclass
class HTMLStyleInfo:
    """Information about a style tag."""
    lineno: int
    content_length: int = 0
    media: Optional[str] = None


@dataclass
class HTMLLinkInfo:
    """Information about a link tag (stylesheet, etc)."""
    href: str
    rel: str
    lineno: int
    media: Optional[str] = None


@dataclass
class HTMLFormInfo:
    """Information about a form element."""
    action: Optional[str]
    method: str
    lineno: int
    input_count: int = 0


@dataclass
class HTMLMetaInfo:
    """Information about a meta tag."""
    name: Optional[str]
    content: Optional[str]
    lineno: int
    charset: Optional[str] = None
    property: Optional[str] = None


@dataclass
class HTMLParseResult:
    """Result of parsing an HTML file."""
    tags: list[HTMLTagInfo] = field(default_factory=list)
    scripts: list[HTMLScriptInfo] = field(default_factory=list)
    styles: list[HTMLStyleInfo] = field(default_factory=list)
    links: list[HTMLLinkInfo] = field(default_factory=list)
    forms: list[HTMLFormInfo] = field(default_factory=list)
    metas: list[HTMLMetaInfo] = field(default_factory=list)
    title: Optional[str] = None
    doctype: Optional[str] = None
    tag_count: int = 0
    unique_tags: set = field(default_factory=set)
    has_scripts: bool = False
    has_styles: bool = False
    line_count: int = 0


class HTMLContentParser(BaseHTMLParser):
    """HTML content parser that extracts structural information."""

    def __init__(self):
        super().__init__()
        self.result = HTMLParseResult()
        self.current_tag = None
        self.in_script = False
        self.in_style = False
        self.in_title = False
        self.script_content = ""
        self.style_content = ""
        self.title_content = ""
        self.lineno = 1

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.result.tag_count += 1
        self.result.unique_tags.add(tag.lower())

        tag_info = HTMLTagInfo(
            name=tag.lower(),
            lineno=self.lineno,
            attributes=attrs_dict,
            has_id='id' in attrs_dict,
            has_class='class' in attrs_dict,
        )
        self.result.tags.append(tag_info)

        if tag.lower() == 'script':
            self.in_script = True
            self.script_content = ""
            src = attrs_dict.get('src')
            self.result.scripts.append(HTMLScriptInfo(
                src=src,
                lineno=self.lineno,
                is_external=src is not None,
                is_module=attrs_dict.get('type') == 'module',
            ))
            self.result.has_scripts = True

        elif tag.lower() == 'style':
            self.in_style = True
            self.style_content = ""
            self.result.styles.append(HTMLStyleInfo(
                lineno=self.lineno,
                media=attrs_dict.get('media'),
            ))
            self.result.has_styles = True

        elif tag.lower() == 'link' and attrs_dict.get('rel') == 'stylesheet':
            self.result.links.append(HTMLLinkInfo(
                href=attrs_dict.get('href', ''),
                rel=attrs_dict.get('rel', ''),
                lineno=self.lineno,
                media=attrs_dict.get('media'),
            ))
            self.result.has_styles = True

        elif tag.lower() == 'form':
            self.result.forms.append(HTMLFormInfo(
                action=attrs_dict.get('action'),
                method=attrs_dict.get('method', 'GET').upper(),
                lineno=self.lineno,
            ))

        elif tag.lower() == 'meta':
            self.result.metas.append(HTMLMetaInfo(
                name=attrs_dict.get('name'),
                content=attrs_dict.get('content'),
                lineno=self.lineno,
                charset=attrs_dict.get('charset'),
                property=attrs_dict.get('property'),
            ))

        elif tag.lower() == 'title':
            self.in_title = True
            self.title_content = ""

    def handle_endtag(self, tag):
        if tag.lower() == 'script' and self.in_script:
            self.in_script = False
            if self.result.scripts:
                self.result.scripts[-1].content_length = len(self.script_content)

        elif tag.lower() == 'style' and self.in_style:
            self.in_style = False
            if self.result.styles:
                self.result.styles[-1].content_length = len(self.style_content)

        elif tag.lower() == 'title' and self.in_title:
            self.in_title = False
            self.result.title = self.title_content.strip()

    def handle_data(self, data):
        if self.in_script:
            self.script_content += data
        elif self.in_style:
            self.style_content += data
        elif self.in_title:
            self.title_content += data

    def handle_decl(self, decl):
        if decl.lower().startswith('doctype'):
            self.result.doctype = decl


class HTMLParser:
    """Parser for HTML documents."""

    def parse_file(self, filepath: str) -> HTMLParseResult:
        """Parse an HTML file and return structural information."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.parse_content(content)
        except Exception as e:
            return HTMLParseResult()

    def parse_content(self, content: str) -> HTMLParseResult:
        """Parse HTML content string."""
        parser = HTMLContentParser()
        parser.result.line_count = content.count('\n') + 1

        try:
            parser.feed(content)
        except Exception:
            pass  # Handle malformed HTML gracefully

        return parser.result
