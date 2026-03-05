"""slack-markdown-parser public package API."""

__version__ = "2.0.1"
__license__ = "MIT"

from .converter import (
    add_zero_width_spaces,
    add_zero_width_spaces_to_markdown,
    blocks_to_plain_text,
    build_fallback_text_from_blocks,
    convert_markdown_text_to_blocks,
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    decode_html_entities,
    extract_plain_text_from_table_cell,
    markdown_table_to_slack_table,
    normalize_markdown_tables,
    parse_markdown_table,
    split_blocks_by_table,
    split_markdown_into_segments,
    strip_zero_width_spaces,
)

__all__ = [
    "add_zero_width_spaces",
    "add_zero_width_spaces_to_markdown",
    "blocks_to_plain_text",
    "build_fallback_text_from_blocks",
    "convert_markdown_text_to_blocks",
    "convert_markdown_to_slack_blocks",
    "convert_markdown_to_slack_messages",
    "decode_html_entities",
    "extract_plain_text_from_table_cell",
    "markdown_table_to_slack_table",
    "normalize_markdown_tables",
    "parse_markdown_table",
    "split_blocks_by_table",
    "split_markdown_into_segments",
    "strip_zero_width_spaces",
]
