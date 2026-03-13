"""slack-markdown-parser public package API."""

__version__ = "2.2.5"
__license__ = "MIT"

from .converter import (
    add_zero_width_spaces,
    add_zero_width_spaces_to_markdown,
    blocks_to_plain_text,
    build_fallback_text_from_blocks,
    convert_markdown_text_to_blocks,
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    convert_markdown_to_slack_payloads,
    decode_html_entities,
    extract_plain_text_from_table_cell,
    markdown_table_to_slack_table,
    normalize_markdown_tables,
    normalize_underscore_emphasis,
    parse_markdown_table,
    sanitize_slack_text,
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
    "convert_markdown_to_slack_payloads",
    "decode_html_entities",
    "extract_plain_text_from_table_cell",
    "markdown_table_to_slack_table",
    "normalize_markdown_tables",
    "normalize_underscore_emphasis",
    "parse_markdown_table",
    "sanitize_slack_text",
    "split_blocks_by_table",
    "split_markdown_into_segments",
    "strip_zero_width_spaces",
]
