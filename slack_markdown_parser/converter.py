"""Core conversion pipeline for Slack Block Kit output.

This module orchestrates the conversion of LLM-generated Markdown text into
Slack Block Kit blocks. The implementation lives in focused internal modules
(``_sanitize``, ``_emphasis``, ``_tables``, ``_rich_blocks``, ``_splitting``,
...); every name that was historically importable from
``slack_markdown_parser.converter`` is re-exported here so existing imports
keep working."""

from __future__ import annotations

from typing import Any

# Backward-compatible re-exports: everything that used to be defined in this
# module remains importable from ``slack_markdown_parser.converter``. The
# orchestration functions below use a subset of these names directly.
from ._code_regions import (
    _find_inline_code_span_end as _find_inline_code_span_end,
    _is_fence_close as _is_fence_close,
    _iter_fence_states as _iter_fence_states,
    _iter_inline_code_spans as _iter_inline_code_spans,
    _match_fence_open as _match_fence_open,
    _multiline_code_span_line_map as _multiline_code_span_line_map,
    _split_fenced_code_chunks as _split_fenced_code_chunks,
    _transform_outside_code_regions as _transform_outside_code_regions,
    _transform_outside_inline_code as _transform_outside_inline_code,
)
from ._constants import (
    _CODE_SPAN_BLANK_LINE_PATTERN as _CODE_SPAN_BLANK_LINE_PATTERN,
    _MARKDOWN_EXPANSION_ITEMS_TARGET as _MARKDOWN_EXPANSION_ITEMS_TARGET,
    _MARKDOWN_SPLIT_TARGET_LENGTH as _MARKDOWN_SPLIT_TARGET_LENGTH,
    _MESSAGE_BLOCKS_TEXT_TARGET as _MESSAGE_BLOCKS_TEXT_TARGET,
    _QUOTE_MARKER_PREFIX_PATTERN as _QUOTE_MARKER_PREFIX_PATTERN,
    _TEXT_SIZE_KEYS as _TEXT_SIZE_KEYS,
    _URL_CJK_BOUNDARY_CHARS as _URL_CJK_BOUNDARY_CHARS,
    _URL_STOP_CHARS as _URL_STOP_CHARS,
    _URL_TRAILING_PUNCTUATION as _URL_TRAILING_PUNCTUATION,
    ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS as ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS,
    ANSI_ESCAPE_PATTERN as ANSI_ESCAPE_PATTERN,
    ATX_HEADING_PATTERN as ATX_HEADING_PATTERN,
    BARE_URL_PATTERN as BARE_URL_PATTERN,
    CONTROL_CHAR_PATTERN as CONTROL_CHAR_PATTERN,
    DOUBLE_UNDERSCORE_EMPHASIS_PATTERN as DOUBLE_UNDERSCORE_EMPHASIS_PATTERN,
    EMPHASIS_PATTERNS as EMPHASIS_PATTERNS,
    FENCE_OPEN_PATTERN as FENCE_OPEN_PATTERN,
    INLINE_CODE_PLACEHOLDER_PATTERN as INLINE_CODE_PLACEHOLDER_PATTERN,
    INTERNAL_MARKER_CHAR_PATTERN as INTERNAL_MARKER_CHAR_PATTERN,
    LIST_ITEM_PATTERN as LIST_ITEM_PATTERN,
    LOOSE_TABLE_SEPARATOR_PATTERN as LOOSE_TABLE_SEPARATOR_PATTERN,
    MARKDOWN_BACKSLASH_ESCAPE_PATTERN as MARKDOWN_BACKSLASH_ESCAPE_PATTERN,
    MARKDOWN_LINK_PATTERN as MARKDOWN_LINK_PATTERN,
    NBSP as NBSP,
    PROTECTED_UNDERSCORE_SPAN_PATTERN as PROTECTED_UNDERSCORE_SPAN_PATTERN,
    REFERENCE_DEFINITION_PATTERN as REFERENCE_DEFINITION_PATTERN,
    SETEXT_HEADING_UNDERLINE_PATTERN as SETEXT_HEADING_UNDERLINE_PATTERN,
    SINGLE_UNDERSCORE_EMPHASIS_PATTERN as SINGLE_UNDERSCORE_EMPHASIS_PATTERN,
    SLACK_ANGLE_TOKEN_PATTERN as SLACK_ANGLE_TOKEN_PATTERN,
    SLACK_MAX_BLOCKS_PER_MESSAGE as SLACK_MAX_BLOCKS_PER_MESSAGE,
    SLACK_MAX_EXPANSION_ITEMS_PER_MESSAGE as SLACK_MAX_EXPANSION_ITEMS_PER_MESSAGE,
    SLACK_MAX_MARKDOWN_TEXT_LENGTH as SLACK_MAX_MARKDOWN_TEXT_LENGTH,
    SLACK_MAX_MESSAGE_BLOCKS_TEXT_LENGTH as SLACK_MAX_MESSAGE_BLOCKS_TEXT_LENGTH,
    STANDALONE_IMAGE_PATTERN as STANDALONE_IMAGE_PATTERN,
    STRIP_LEFT_ZWSP_MARKER as STRIP_LEFT_ZWSP_MARKER,
    STRIP_RIGHT_ZWSP_MARKER as STRIP_RIGHT_ZWSP_MARKER,
    SYNTH_SPACE_MARKER as SYNTH_SPACE_MARKER,
    TABLE_SEPARATOR_PATTERN as TABLE_SEPARATOR_PATTERN,
    TABLE_TOKEN_PATTERN as TABLE_TOKEN_PATTERN,
    TASK_LIST_MARKER_PATTERN as TASK_LIST_MARKER_PATTERN,
    THEMATIC_BREAK_PATTERN as THEMATIC_BREAK_PATTERN,
    VISIBLE_BOUNDARY_CHARS as VISIBLE_BOUNDARY_CHARS,
    ZWSP as ZWSP,
)
from ._emphasis import (
    _format_markdown_with_spacing_metadata as _format_markdown_with_spacing_metadata,
    _is_han_or_kana_char as _is_han_or_kana_char,
    _is_hangul_char as _is_hangul_char,
    _is_punctuation_like as _is_punctuation_like,
    _needs_inner_code_spacing as _needs_inner_code_spacing,
    _nested_code_space_strategy as _nested_code_space_strategy,
    _normalize_underscore_emphasis_chunk as _normalize_underscore_emphasis_chunk,
    _normalize_underscore_emphasis_prose as _normalize_underscore_emphasis_prose,
    _remove_synthetic_space_markers as _remove_synthetic_space_markers,
    _should_preserve_raw_punctuation_emphasis as _should_preserve_raw_punctuation_emphasis,
    add_zero_width_spaces as add_zero_width_spaces,
    add_zero_width_spaces_to_markdown as add_zero_width_spaces_to_markdown,
    normalize_underscore_emphasis as normalize_underscore_emphasis,
)
from ._fallback import (
    _blocks_to_downgrade_parts as _blocks_to_downgrade_parts,
    _build_markdown_block_plain_text as _build_markdown_block_plain_text,
    _markdown_block_to_plain_text as _markdown_block_to_plain_text,
    _normalize_markdown_block_plain_text as _normalize_markdown_block_plain_text,
    _strip_synthetic_spaces_from_plain_text as _strip_synthetic_spaces_from_plain_text,
    blocks_to_plain_text as blocks_to_plain_text,
    build_fallback_text_from_blocks as build_fallback_text_from_blocks,
)
from ._lines import (
    _blank_run_follows_list_context as _blank_run_follows_list_context,
    _has_markdown_backslash_escape as _has_markdown_backslash_escape,
    _indent_width as _indent_width,
    _inject_visual_blank_line_placeholders as _inject_visual_blank_line_placeholders,
    _inject_visual_blank_line_placeholders_in_chunk as _inject_visual_blank_line_placeholders_in_chunk,
    _is_ambiguous_rich_list_indent as _is_ambiguous_rich_list_indent,
    _is_ordered_list_marker as _is_ordered_list_marker,
    _is_thematic_break_line as _is_thematic_break_line,
    _line_belongs_to_list_context as _line_belongs_to_list_context,
    _list_indent_level as _list_indent_level,
    _list_item_content_indent as _list_item_content_indent,
    _ordered_list_marker_number as _ordered_list_marker_number,
    _ordered_list_marker_starts_at_one as _ordered_list_marker_starts_at_one,
    _starts_root_list_item as _starts_root_list_item,
    _strip_synthetic_blank_line_placeholders as _strip_synthetic_blank_line_placeholders,
)
from ._rich_blocks import (
    _consume_fenced_code_block as _consume_fenced_code_block,
    _consume_list_block as _consume_list_block,
    _consume_quote_block as _consume_quote_block,
    _consume_rich_markdown_block as _consume_rich_markdown_block,
    _create_divider_block_from_line as _create_divider_block_from_line,
    _create_image_block_from_line as _create_image_block_from_line,
    _create_rich_text_block as _create_rich_text_block,
    _find_fence_close_index as _find_fence_close_index,
    _is_http_url as _is_http_url,
    _is_setext_heading_underline as _is_setext_heading_underline,
    _parse_simple_list_item as _parse_simple_list_item,
    _quote_lines_are_simple as _quote_lines_are_simple,
    _strip_quote_marker as _strip_quote_marker,
    _truncate_plain_text as _truncate_plain_text,
)
from ._rich_text import (
    _create_rich_text_inline_elements as _create_rich_text_inline_elements,
    _create_rich_text_section as _create_rich_text_section,
    _plain_text_from_markdown_fragment as _plain_text_from_markdown_fragment,
    _rich_text_block_to_plain_text as _rich_text_block_to_plain_text,
    _rich_text_inline_elements_to_plain_text as _rich_text_inline_elements_to_plain_text,
    _rich_text_object_to_plain_text as _rich_text_object_to_plain_text,
    _slack_mention_element as _slack_mention_element,
    _slack_mention_element_to_token as _slack_mention_element_to_token,
)
from ._sanitize import (
    _is_allowed_slack_angle_token as _is_allowed_slack_angle_token,
    _is_url_boundary_char as _is_url_boundary_char,
    _match_slack_angle_token_end as _match_slack_angle_token_end,
    _trim_bare_url as _trim_bare_url,
    decode_html_entities as decode_html_entities,
    normalize_bare_urls_for_slack_markdown as normalize_bare_urls_for_slack_markdown,
    sanitize_slack_text as sanitize_slack_text,
    strip_zero_width_spaces as strip_zero_width_spaces,
)
from ._splitting import (
    _AnnotatedSlackBlock as _AnnotatedSlackBlock,
    _block_expansion_weight as _block_expansion_weight,
    _block_text_size as _block_text_size,
    _create_markdown_block as _create_markdown_block,
    _create_markdown_blocks as _create_markdown_blocks,
    _estimate_markdown_expansion_items as _estimate_markdown_expansion_items,
    _is_markdown_expansion_breaker_line as _is_markdown_expansion_breaker_line,
    _markdown_block_fits_slack_limits as _markdown_block_fits_slack_limits,
    _split_line_verbatim_to_length as _split_line_verbatim_to_length,
    _split_lines_to_length as _split_lines_to_length,
    _split_single_line_to_length as _split_single_line_to_length,
    _split_text_at_blank_lines as _split_text_at_blank_lines,
    split_blocks_by_table as split_blocks_by_table,
)
from ._tables import (
    _count_cell_words as _count_cell_words,
    _create_table_cell as _create_table_cell,
    _looks_like_markdown_table as _looks_like_markdown_table,
    _split_heading_and_table_row as _split_heading_and_table_row,
    _split_heading_prefix_and_first_cell as _split_heading_prefix_and_first_cell,
    _split_markdown_table_cells as _split_markdown_table_cells,
    extract_plain_text_from_table_cell as extract_plain_text_from_table_cell,
    markdown_table_to_slack_table as markdown_table_to_slack_table,
    markdown_table_to_table_block as markdown_table_to_table_block,
    normalize_markdown_tables as normalize_markdown_tables,
    parse_markdown_table as parse_markdown_table,
)


def _convert_markdown_text_segment_to_blocks(
    content: str, *, preserve_visual_blank_lines: bool = False
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    markdown_buffer: list[str] = []
    lines = content.splitlines()
    span_interior, _ = _multiline_code_span_line_map(lines)
    cursor = 0

    def flush_markdown_buffer() -> None:
        nonlocal markdown_buffer
        if not markdown_buffer:
            return
        while markdown_buffer and not markdown_buffer[0].strip():
            markdown_buffer.pop(0)
        while markdown_buffer and not markdown_buffer[-1].strip():
            markdown_buffer.pop()
        if not markdown_buffer:
            return
        blocks.extend(
            _create_markdown_blocks(
                "\n".join(markdown_buffer),
                preserve_visual_blank_lines=preserve_visual_blank_lines,
            )
        )
        markdown_buffer = []

    while cursor < len(lines):
        if span_interior[cursor]:
            # Part of a multi-line inline code span: Slack renders the
            # stretch as code, so a block-looking line inside it (an image,
            # a divider, a quote or list marker) must stay literal text.
            markdown_buffer.append(lines[cursor])
            cursor += 1
            continue

        fence = _match_fence_open(lines[cursor])
        if fence is not None and _find_fence_close_index(lines, cursor, fence) is None:
            markdown_buffer.extend(lines[cursor:])
            cursor = len(lines)
            break

        consumed = _consume_rich_markdown_block(lines, cursor)
        if consumed:
            block, next_cursor = consumed
            consumed_range_hits_span = any(
                span_interior[index] for index in range(cursor, next_cursor)
            )
            if (
                block is None
                or consumed_range_hits_span
                or _block_text_size(block) > _MESSAGE_BLOCKS_TEXT_TARGET
            ):
                # The region was recognized but must not post as one promoted
                # block: either the consumer flagged it markdown-only (e.g. a
                # quote whose code span crosses lines), or it is oversized —
                # a promoted block posts as-is with no splitting machinery,
                # so one oversized rich_text would fail the whole message
                # with ``msg_blocks_too_long``. Keep the raw lines in the
                # markdown buffer, whose splitter handles any size.
                markdown_buffer.extend(lines[cursor:next_cursor])
                cursor = next_cursor
                continue
            flush_markdown_buffer()
            blocks.append(block)
            cursor = next_cursor
            while cursor < len(lines) and not lines[cursor].strip():
                cursor += 1
            continue

        markdown_buffer.append(lines[cursor])
        cursor += 1

    flush_markdown_buffer()
    return blocks


def split_markdown_into_segments(markdown_text: str) -> list[dict[str, str]]:
    """Split markdown into alternating text/table segments."""
    segments: list[dict[str, str]] = []
    if not markdown_text:
        return segments

    lines = markdown_text.splitlines()
    current: list[str] = []
    current_is_table: bool | None = None

    def flush() -> None:
        nonlocal current, current_is_table
        if current:
            segments.append(
                {
                    "type": "table" if current_is_table else "text",
                    "content": "\n".join(current),
                }
            )
        current = []
        current_is_table = None

    span_interior, _ = _multiline_code_span_line_map(lines)

    for index, (line, is_fenced, _) in enumerate(_iter_fence_states(lines)):
        stripped = line.strip()
        is_table_line = (
            False
            if is_fenced or span_interior[index]
            else stripped.startswith("|") and stripped.endswith("|")
        )

        if current_is_table is None:
            current_is_table = is_table_line
            current.append(line)
        elif is_table_line == current_is_table:
            current.append(line)
        else:
            flush()
            current_is_table = is_table_line
            current.append(line)

    flush()
    return segments


def convert_markdown_to_slack_blocks(
    markdown_text: str, *, preserve_visual_blank_lines: bool = False
) -> list[dict[str, Any]]:
    """Convert markdown text into Slack markdown/table blocks."""
    if not markdown_text:
        return []

    markdown_text = decode_html_entities(markdown_text)
    markdown_text = sanitize_slack_text(markdown_text)
    markdown_text = normalize_underscore_emphasis(markdown_text)
    markdown_text = normalize_bare_urls_for_slack_markdown(markdown_text)
    markdown_text = normalize_markdown_tables(markdown_text)
    blocks: list[dict[str, Any]] = []

    for segment in split_markdown_into_segments(markdown_text):
        content = segment.get("content", "")
        if not content.strip():
            continue

        if segment.get("type") == "table" and _looks_like_markdown_table(content):
            table_block = markdown_table_to_slack_table(content)
            if table_block:
                blocks.append(table_block)
                continue

        blocks.extend(
            _convert_markdown_text_segment_to_blocks(
                content,
                preserve_visual_blank_lines=preserve_visual_blank_lines,
            )
        )

    return blocks


# Backward-compatible alias
convert_markdown_text_to_blocks = convert_markdown_to_slack_blocks


def convert_markdown_to_slack_messages(
    markdown_text: str,
    *,
    preserve_visual_blank_lines: bool = False,
) -> list[list[dict[str, Any]]]:
    """Convert markdown text into a list of Slack message block groups."""
    blocks = convert_markdown_to_slack_blocks(
        markdown_text, preserve_visual_blank_lines=preserve_visual_blank_lines
    )
    if not blocks:
        return []
    return split_blocks_by_table(blocks)


def convert_markdown_to_slack_payloads(
    markdown_text: str,
    *,
    preserve_visual_blank_lines: bool = False,
) -> list[dict[str, Any]]:
    """Convert markdown text into Slack-ready payload dicts with fallback text."""
    payloads: list[dict[str, Any]] = []
    for blocks in convert_markdown_to_slack_messages(
        markdown_text, preserve_visual_blank_lines=preserve_visual_blank_lines
    ):
        fallback_text = build_fallback_text_from_blocks(blocks).strip()
        payloads.append({"blocks": blocks, "text": fallback_text or " "})
    return payloads
