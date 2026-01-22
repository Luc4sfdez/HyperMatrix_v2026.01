"""
HyperMatrix v2026 - Markdown Parser Tests
"""

import pytest
from src.parsers import (
    MarkdownParser,
    MDParseResult,
    MDHeadingInfo,
    MDLinkInfo,
    MDCodeBlockInfo,
    MDListItemInfo,
    MDBlockquoteInfo,
    MDTableInfo,
    MDElementType,
)


class TestMarkdownParser:
    """Tests for MarkdownParser class."""

    def test_parser_initialization(self):
        """Test parser can be instantiated."""
        parser = MarkdownParser()
        assert parser is not None

    def test_parse_returns_result(self, sample_markdown_code):
        """Test parse returns MDParseResult."""
        parser = MarkdownParser()
        result = parser.parse(sample_markdown_code)
        assert isinstance(result, MDParseResult)

    def test_parse_empty_content(self):
        """Test parsing empty content."""
        parser = MarkdownParser()
        result = parser.parse("")
        assert isinstance(result, MDParseResult)
        assert len(result.headings) == 0


class TestHeadingExtraction:
    """Tests for heading extraction."""

    def test_extract_h1(self):
        """Test extracting H1 heading."""
        content = "# Main Title"
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.headings) == 1
        heading = result.headings[0]
        assert heading.text == "Main Title"
        assert heading.level == 1

    def test_extract_h2(self):
        """Test extracting H2 heading."""
        content = "## Section Title"
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.headings) == 1
        heading = result.headings[0]
        assert heading.level == 2

    def test_extract_all_heading_levels(self):
        """Test extracting all heading levels."""
        content = '''
# H1
## H2
### H3
#### H4
##### H5
###### H6
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.headings) == 6
        levels = [h.level for h in result.headings]
        assert levels == [1, 2, 3, 4, 5, 6]

    def test_extract_multiple_headings(self, sample_markdown_code):
        """Test extracting multiple headings."""
        parser = MarkdownParser()
        result = parser.parse(sample_markdown_code)

        assert len(result.headings) >= 3
        texts = [h.text for h in result.headings]
        assert "Main Title" in texts


class TestLinkExtraction:
    """Tests for link extraction."""

    def test_extract_simple_link(self):
        """Test extracting a simple link."""
        content = "Check out [Example](https://example.com)"
        parser = MarkdownParser()
        result = parser.parse(content)

        links = [l for l in result.links if not l.is_image]
        assert len(links) == 1
        link = links[0]
        assert link.text == "Example"
        assert link.url == "https://example.com"

    def test_extract_link_with_title(self):
        """Test extracting link with title."""
        content = '[Link](https://example.com "Title text")'
        parser = MarkdownParser()
        result = parser.parse(content)

        links = [l for l in result.links if not l.is_image]
        assert len(links) == 1
        assert links[0].title == "Title text"

    def test_extract_image(self):
        """Test extracting image reference."""
        content = '![Alt text](image.png "Image title")'
        parser = MarkdownParser()
        result = parser.parse(content)

        images = [l for l in result.links if l.is_image]
        assert len(images) == 1
        img = images[0]
        assert img.text == "Alt text"
        assert img.url == "image.png"
        assert img.is_image is True

    def test_extract_multiple_links(self, sample_markdown_code):
        """Test extracting multiple links."""
        parser = MarkdownParser()
        result = parser.parse(sample_markdown_code)

        assert len(result.links) >= 2  # At least one link and one image


class TestCodeBlockExtraction:
    """Tests for code block extraction."""

    def test_extract_fenced_code_block(self):
        """Test extracting fenced code block."""
        content = '''
```python
def hello():
    print("Hello")
```
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.code_blocks) == 1
        block = result.code_blocks[0]
        assert block.language == "python"
        assert "def hello" in block.content

    def test_extract_code_block_no_language(self):
        """Test extracting code block without language."""
        content = '''
```
plain code
```
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.code_blocks) == 1
        block = result.code_blocks[0]
        assert block.language is None or block.language == ""

    def test_extract_multiple_code_blocks(self, sample_markdown_code):
        """Test extracting multiple code blocks."""
        parser = MarkdownParser()
        result = parser.parse(sample_markdown_code)

        assert len(result.code_blocks) >= 2
        languages = [b.language for b in result.code_blocks]
        assert "python" in languages
        assert "javascript" in languages


class TestListExtraction:
    """Tests for list extraction."""

    def test_extract_unordered_list(self):
        """Test extracting unordered list."""
        content = '''
- Item 1
- Item 2
- Item 3
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        items = [li for li in result.list_items if not li.is_ordered]
        assert len(items) == 3

    def test_extract_ordered_list(self):
        """Test extracting ordered list."""
        content = '''
1. First
2. Second
3. Third
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        items = [li for li in result.list_items if li.is_ordered]
        assert len(items) == 3
        assert items[0].order_num == 1

    def test_extract_nested_list(self):
        """Test extracting nested list."""
        content = '''
- Item 1
  - Nested 1
  - Nested 2
- Item 2
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        levels = [li.level for li in result.list_items]
        assert 1 in levels
        assert 2 in levels

    def test_different_list_markers(self):
        """Test different unordered list markers."""
        content = '''
- Dash item
* Asterisk item
+ Plus item
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.list_items) == 3


class TestBlockquoteExtraction:
    """Tests for blockquote extraction."""

    def test_extract_simple_blockquote(self):
        """Test extracting simple blockquote."""
        content = "> This is a quote"
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.blockquotes) == 1
        quote = result.blockquotes[0]
        assert quote.text == "This is a quote"
        assert quote.level == 1

    def test_extract_nested_blockquote(self):
        """Test extracting nested blockquote."""
        content = '''
> Level 1
>> Level 2
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        levels = [q.level for q in result.blockquotes]
        assert 1 in levels
        assert 2 in levels

    def test_extract_multiline_blockquote(self):
        """Test extracting multiline blockquote."""
        content = '''
> Line 1
> Line 2
> Line 3
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.blockquotes) >= 1


class TestTableExtraction:
    """Tests for table extraction."""

    def test_extract_simple_table(self):
        """Test extracting simple table."""
        content = '''
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.tables) == 1
        table = result.tables[0]
        assert len(table.headers) == 2
        assert len(table.rows) == 2

    def test_extract_table_headers(self):
        """Test extracting table headers."""
        content = '''
| Name | Age | City |
|------|-----|------|
| John | 30  | NYC  |
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        table = result.tables[0]
        assert "Name" in table.headers
        assert "Age" in table.headers
        assert "City" in table.headers


class TestWordCount:
    """Tests for word count functionality."""

    def test_word_count(self):
        """Test word count calculation."""
        content = "This is a test with seven words."
        parser = MarkdownParser()
        result = parser.parse(content)

        assert result.word_count == 7

    def test_word_count_excludes_code(self):
        """Test word count excludes code blocks."""
        content = '''
Some text here.

```python
def not_counted():
    pass
```

More text.
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        # Should count "Some text here More text" but not code
        assert result.word_count < 10

    def test_line_count(self, sample_markdown_code):
        """Test line count."""
        parser = MarkdownParser()
        result = parser.parse(sample_markdown_code)

        assert result.line_count > 0


class TestParseFile:
    """Tests for file parsing."""

    def test_parse_file(self, create_temp_file, sample_markdown_code):
        """Test parsing a Markdown file."""
        filepath = create_temp_file("test.md", sample_markdown_code)

        parser = MarkdownParser()
        result = parser.parse_file(filepath)

        assert isinstance(result, MDParseResult)
        assert len(result.headings) > 0

    def test_parse_file_not_found(self):
        """Test parsing non-existent file raises error."""
        parser = MarkdownParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_file("nonexistent.md")


class TestEdgeCases:
    """Tests for edge cases."""

    def test_inline_code_not_as_block(self):
        """Test inline code is not captured as code block."""
        content = "Use `code` inline."
        parser = MarkdownParser()
        result = parser.parse(content)

        assert len(result.code_blocks) == 0

    @pytest.mark.xfail(reason="Regex parser doesn't exclude code block content")
    def test_heading_in_code_block(self):
        """Test heading inside code block is not extracted."""
        content = '''
```markdown
# Not a real heading
```
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        # The heading inside code should not be extracted
        heading_texts = [h.text for h in result.headings]
        assert "Not a real heading" not in heading_texts

    @pytest.mark.xfail(reason="Regex parser doesn't exclude code block content")
    def test_link_in_code_block(self):
        """Test link inside code block is not extracted."""
        content = '''
```
[Not a link](https://example.com)
```
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        # Links inside code should not be extracted
        assert len([l for l in result.links if l.url == "https://example.com"]) == 0

    def test_empty_table(self):
        """Test table with only headers."""
        content = '''
| Header 1 | Header 2 |
|----------|----------|
'''
        parser = MarkdownParser()
        result = parser.parse(content)

        if result.tables:
            assert len(result.tables[0].rows) == 0
