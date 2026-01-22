"""
HyperMatrix v2026 - Markdown Parser
Extracts headings, links, code blocks, lists and document structure.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class MDElementType(Enum):
    """Type of Markdown element."""
    HEADING = "HEADING"
    LINK = "LINK"
    IMAGE = "IMAGE"
    CODE_BLOCK = "CODE_BLOCK"
    INLINE_CODE = "INLINE_CODE"
    LIST_ITEM = "LIST_ITEM"
    BLOCKQUOTE = "BLOCKQUOTE"
    TABLE = "TABLE"
    HORIZONTAL_RULE = "HORIZONTAL_RULE"


@dataclass
class MDHeadingInfo:
    """Information about a Markdown heading."""
    text: str
    level: int
    lineno: int


@dataclass
class MDLinkInfo:
    """Information about a Markdown link."""
    text: str
    url: str
    lineno: int
    is_image: bool = False
    title: Optional[str] = None


@dataclass
class MDCodeBlockInfo:
    """Information about a code block."""
    content: str
    language: Optional[str]
    lineno: int
    end_lineno: int


@dataclass
class MDListItemInfo:
    """Information about a list item."""
    text: str
    lineno: int
    level: int
    is_ordered: bool = False
    order_num: Optional[int] = None


@dataclass
class MDBlockquoteInfo:
    """Information about a blockquote."""
    text: str
    lineno: int
    level: int


@dataclass
class MDTableInfo:
    """Information about a table."""
    headers: list[str]
    rows: list[list[str]]
    lineno: int


@dataclass
class MDParseResult:
    """Result of parsing a Markdown file."""
    headings: list[MDHeadingInfo] = field(default_factory=list)
    links: list[MDLinkInfo] = field(default_factory=list)
    code_blocks: list[MDCodeBlockInfo] = field(default_factory=list)
    list_items: list[MDListItemInfo] = field(default_factory=list)
    blockquotes: list[MDBlockquoteInfo] = field(default_factory=list)
    tables: list[MDTableInfo] = field(default_factory=list)
    word_count: int = 0
    line_count: int = 0


class MarkdownParser:
    """Parser for Markdown documents."""

    # Regex patterns
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]+)")?\)')
    IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]+)")?\)')
    CODE_BLOCK_PATTERN = re.compile(r'^```(\w*)\n(.*?)^```', re.MULTILINE | re.DOTALL)
    INLINE_CODE_PATTERN = re.compile(r'`([^`]+)`')
    UNORDERED_LIST_PATTERN = re.compile(r'^(\s*)[-*+]\s+(.+)$', re.MULTILINE)
    ORDERED_LIST_PATTERN = re.compile(r'^(\s*)(\d+)\.\s+(.+)$', re.MULTILINE)
    BLOCKQUOTE_PATTERN = re.compile(r'^(>+)\s*(.*)$', re.MULTILINE)
    TABLE_ROW_PATTERN = re.compile(r'^\|(.+)\|$', re.MULTILINE)
    HORIZONTAL_RULE_PATTERN = re.compile(r'^(?:---|\*\*\*|___)\s*$', re.MULTILINE)

    def __init__(self):
        self.result = MDParseResult()

    def parse(self, source: str) -> MDParseResult:
        """Parse Markdown source and extract elements."""
        self.result = MDParseResult()
        lines = source.split('\n')
        self.result.line_count = len(lines)

        self._extract_headings(source)
        self._extract_code_blocks(source)
        self._extract_links(source)
        self._extract_images(source)
        self._extract_lists(source)
        self._extract_blockquotes(source)
        self._extract_tables(source, lines)
        self._count_words(source)

        return self.result

    def parse_file(self, filepath: str) -> MDParseResult:
        """Parse a Markdown file and extract elements."""
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        return self.parse(source)

    def _get_lineno(self, source: str, match_start: int) -> int:
        """Get line number from match position."""
        return source[:match_start].count('\n') + 1

    def _extract_headings(self, source: str):
        """Extract heading elements."""
        for match in self.HEADING_PATTERN.finditer(source):
            level = len(match.group(1))
            text = match.group(2).strip()

            heading_info = MDHeadingInfo(
                text=text,
                level=level,
                lineno=self._get_lineno(source, match.start()),
            )
            self.result.headings.append(heading_info)

    def _extract_code_blocks(self, source: str):
        """Extract fenced code blocks."""
        for match in self.CODE_BLOCK_PATTERN.finditer(source):
            language = match.group(1) or None
            content = match.group(2)
            lineno = self._get_lineno(source, match.start())
            end_lineno = self._get_lineno(source, match.end())

            code_info = MDCodeBlockInfo(
                content=content.strip(),
                language=language,
                lineno=lineno,
                end_lineno=end_lineno,
            )
            self.result.code_blocks.append(code_info)

    def _extract_links(self, source: str):
        """Extract links (excluding images)."""
        # Remove images first to avoid capturing them
        source_no_images = self.IMAGE_PATTERN.sub('', source)

        for match in self.LINK_PATTERN.finditer(source_no_images):
            text = match.group(1)
            url = match.group(2)
            title = match.group(3)

            link_info = MDLinkInfo(
                text=text,
                url=url,
                lineno=self._get_lineno(source, match.start()),
                title=title,
            )
            self.result.links.append(link_info)

    def _extract_images(self, source: str):
        """Extract image references."""
        for match in self.IMAGE_PATTERN.finditer(source):
            alt_text = match.group(1)
            url = match.group(2)
            title = match.group(3)

            image_info = MDLinkInfo(
                text=alt_text,
                url=url,
                lineno=self._get_lineno(source, match.start()),
                is_image=True,
                title=title,
            )
            self.result.links.append(image_info)

    def _extract_lists(self, source: str):
        """Extract list items."""
        # Unordered lists
        for match in self.UNORDERED_LIST_PATTERN.finditer(source):
            indent = len(match.group(1))
            level = indent // 2 + 1
            text = match.group(2)

            list_info = MDListItemInfo(
                text=text,
                lineno=self._get_lineno(source, match.start()),
                level=level,
                is_ordered=False,
            )
            self.result.list_items.append(list_info)

        # Ordered lists
        for match in self.ORDERED_LIST_PATTERN.finditer(source):
            indent = len(match.group(1))
            level = indent // 2 + 1
            order_num = int(match.group(2))
            text = match.group(3)

            list_info = MDListItemInfo(
                text=text,
                lineno=self._get_lineno(source, match.start()),
                level=level,
                is_ordered=True,
                order_num=order_num,
            )
            self.result.list_items.append(list_info)

    def _extract_blockquotes(self, source: str):
        """Extract blockquotes."""
        for match in self.BLOCKQUOTE_PATTERN.finditer(source):
            level = len(match.group(1))
            text = match.group(2).strip()

            if text:  # Skip empty blockquote lines
                quote_info = MDBlockquoteInfo(
                    text=text,
                    lineno=self._get_lineno(source, match.start()),
                    level=level,
                )
                self.result.blockquotes.append(quote_info)

    def _extract_tables(self, source: str, lines: list):
        """Extract tables."""
        i = 0
        while i < len(lines):
            line = lines[i]
            if '|' in line and i + 1 < len(lines):
                # Check if next line is separator
                next_line = lines[i + 1]
                if re.match(r'^\|[\s\-:|]+\|$', next_line):
                    # Found table header
                    headers = [cell.strip() for cell in line.strip('|').split('|')]

                    # Collect rows
                    rows = []
                    j = i + 2
                    while j < len(lines) and '|' in lines[j]:
                        if not re.match(r'^\|[\s\-:|]+\|$', lines[j]):
                            row = [cell.strip() for cell in lines[j].strip('|').split('|')]
                            rows.append(row)
                        j += 1

                    table_info = MDTableInfo(
                        headers=headers,
                        rows=rows,
                        lineno=i + 1,
                    )
                    self.result.tables.append(table_info)
                    i = j
                    continue
            i += 1

    def _count_words(self, source: str):
        """Count words in the document (excluding code blocks)."""
        # Remove code blocks
        text = self.CODE_BLOCK_PATTERN.sub('', source)
        text = self.INLINE_CODE_PATTERN.sub('', text)

        # Remove markdown syntax
        text = re.sub(r'[#*_\[\]()>`]', ' ', text)

        # Count words
        words = text.split()
        self.result.word_count = len(words)
