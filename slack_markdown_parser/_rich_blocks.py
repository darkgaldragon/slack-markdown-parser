"""Promotion of unambiguous standalone Markdown constructs (images,
dividers, quotes, lists, fenced code) into native Block Kit blocks."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ._code_regions import _is_fence_close, _iter_inline_code_spans, _match_fence_open
from ._constants import (
    FENCE_OPEN_PATTERN,
    LIST_ITEM_PATTERN,
    STANDALONE_IMAGE_PATTERN,
    TASK_LIST_MARKER_PATTERN,
)
from ._lines import (
    _has_markdown_backslash_escape,
    _indent_width,
    _is_ambiguous_rich_list_indent,
    _is_ordered_list_marker,
    _is_thematic_break_line,
    _list_indent_level,
    _ordered_list_marker_number,
)
from ._rich_text import (
    _create_rich_text_inline_elements,
    _create_rich_text_section,
    _plain_text_from_markdown_fragment,
)
from ._splitting import _AnnotatedSlackBlock


def _truncate_plain_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _create_rich_text_block(
    elements: list[dict[str, Any]], *, plain_text: str | None = None
) -> dict[str, Any]:
    block = _AnnotatedSlackBlock({"type": "rich_text", "elements": elements})
    if plain_text is not None:
        block._plain_text = plain_text
    return block


def _create_image_block_from_line(line: str) -> dict[str, Any] | None:
    match = STANDALONE_IMAGE_PATTERN.match(line)
    if not match:
        return None

    image_url = match.group("url").strip()
    if not _is_http_url(image_url) or len(image_url) > 3000:
        return None

    alt_text = _plain_text_from_markdown_fragment(match.group("alt") or "")
    alt_text = _truncate_plain_text(alt_text or "Image", 2000)
    return {"type": "image", "image_url": image_url, "alt_text": alt_text}


def _is_setext_heading_underline(lines: list[str], index: int) -> bool:
    if index <= 0:
        return False
    line = lines[index].strip()
    if not line or set(line) != {"-"}:
        return False
    return bool(lines[index - 1].strip())


def _create_divider_block_from_line(
    lines: list[str], index: int
) -> dict[str, Any] | None:
    if not _is_thematic_break_line(lines[index]):
        return None
    if _is_setext_heading_underline(lines, index):
        return None
    block = _AnnotatedSlackBlock({"type": "divider"})
    block._plain_text = lines[index].strip()
    return block


def _strip_quote_marker(line: str) -> str | None:
    match = re.match(r"^[ \t]{0,3}>[ \t]?(?P<text>.*)$", line)
    if not match:
        return None
    return match.group("text")


def _quote_lines_are_simple(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            return False
        if stripped.startswith(">"):
            return False
        if LIST_ITEM_PATTERN.match(stripped):
            return False
        if _match_fence_open(stripped):
            return False
        if _has_markdown_backslash_escape(stripped):
            return False
    return True


def _consume_quote_block(
    lines: list[str], start: int
) -> tuple[dict[str, Any] | None, int] | None:
    if _strip_quote_marker(lines[start]) is None:
        return None

    quote_lines: list[str] = []
    cursor = start
    while cursor < len(lines):
        stripped = _strip_quote_marker(lines[cursor])
        if stripped is None:
            break
        quote_lines.append(stripped)
        cursor += 1

    if not _quote_lines_are_simple(quote_lines):
        return None

    quote_text = "\n".join(quote_lines).strip()
    if not quote_text:
        return None

    if any(
        "\n" in quote_text[span_start:span_end]
        for span_start, span_end in _iter_inline_code_spans(quote_text)
    ):
        # A code span crossing quote lines cannot be expressed by the
        # single-line rich_text tokenizer; the whole quote region falls back
        # to the markdown path (where Slack renders the span as code) —
        # returning it line by line would let a later line re-promote alone.
        return None, cursor

    block = _create_rich_text_block(
        [
            {
                "type": "rich_text_quote",
                "elements": _create_rich_text_inline_elements(quote_text),
            }
        ],
        plain_text="\n".join(lines[start:cursor]),
    )
    return block, cursor


def _parse_simple_list_item(line: str) -> dict[str, Any] | None:
    if _is_thematic_break_line(line):
        return None

    match = LIST_ITEM_PATTERN.match(line)
    if not match:
        return None

    text = line[match.end() :].rstrip()
    if TASK_LIST_MARKER_PATTERN.match(text):
        return None

    indent = match.group("indent") or ""
    if _is_ambiguous_rich_list_indent(indent):
        return None
    if _has_markdown_backslash_escape(text):
        return None

    marker = match.group("marker")
    return {
        "style": "ordered" if _is_ordered_list_marker(marker) else "bullet",
        "number": _ordered_list_marker_number(marker),
        "indent": _list_indent_level(indent),
        "text": text.strip() or " ",
    }


def _consume_list_block(
    lines: list[str], start: int
) -> tuple[dict[str, Any], int] | None:
    first_entry = _parse_simple_list_item(lines[start])
    if first_entry is None:
        return None

    first_match = LIST_ITEM_PATTERN.match(lines[start])
    first_indent = _indent_width(first_match.group("indent") if first_match else "")
    if first_indent > 3:
        return None

    if start > 0 and lines[start - 1].strip():
        return None

    entries: list[dict[str, Any]] = []
    cursor = start
    while cursor < len(lines) and lines[cursor].strip():
        entry = _parse_simple_list_item(lines[cursor])
        if entry is None:
            return None
        entries.append(entry)
        cursor += 1

    if not entries:
        return None

    lookahead = cursor
    while lookahead < len(lines) and not lines[lookahead].strip():
        lookahead += 1
    if lookahead < len(lines):
        next_line = lines[lookahead]
        if _indent_width(next_line) > 0 and _parse_simple_list_item(next_line) is None:
            return None

    rich_elements: list[dict[str, Any]] = []
    current_group: dict[str, Any] | None = None

    def flush_group() -> None:
        nonlocal current_group
        if current_group:
            rich_elements.append(current_group)
        current_group = None

    for entry in entries:
        group_key = (entry["style"], entry["indent"])
        if current_group is None or current_group["_key"] != group_key:
            flush_group()
            current_group = {
                "type": "rich_text_list",
                "style": entry["style"],
                "indent": entry["indent"],
                "elements": [],
                "_key": group_key,
            }
            if entry["style"] == "ordered" and entry["number"] > 1:
                current_group["offset"] = entry["number"] - 1

        current_group["elements"].append(_create_rich_text_section(entry["text"]))

    flush_group()
    for element in rich_elements:
        element.pop("_key", None)

    return (
        _create_rich_text_block(
            rich_elements,
            plain_text="\n".join(lines[start:cursor]),
        ),
        cursor,
    )


def _find_fence_close_index(
    lines: list[str], start: int, fence: tuple[str, int]
) -> int | None:
    cursor = start + 1
    while cursor < len(lines):
        if _is_fence_close(lines[cursor], fence):
            return cursor
        cursor += 1
    return None


def _consume_fenced_code_block(
    lines: list[str], start: int
) -> tuple[dict[str, Any], int] | None:
    open_match = FENCE_OPEN_PATTERN.match(lines[start])
    if not open_match:
        return None

    fence = _match_fence_open(lines[start])
    if fence is None:
        return None

    close_index = _find_fence_close_index(lines, start, fence)
    if close_index is None:
        return None

    info = (open_match.group(2) or "").strip()
    language = info.split()[0] if info else ""
    code_text = "\n".join(lines[start + 1 : close_index])
    preformatted: dict[str, Any] = {
        "type": "rich_text_preformatted",
        "elements": [{"type": "text", "text": code_text}],
    }
    if language and re.match(r"^[A-Za-z0-9_+.#-]+$", language):
        preformatted["language"] = language
    return (
        _create_rich_text_block(
            [preformatted],
            plain_text="\n".join(lines[start : close_index + 1]),
        ),
        close_index + 1,
    )


def _consume_rich_markdown_block(
    lines: list[str], index: int
) -> tuple[dict[str, Any] | None, int] | None:
    """Consume one promotable construct starting at ``index``.

    Returns ``None`` when nothing was consumed, or ``(block, next_index)``.
    ``block`` may be ``None`` when the construct was recognized but must stay
    on the markdown path as a whole region (the caller buffers the raw
    lines)."""
    if not lines[index].strip():
        return None

    consumers = (
        lambda: _consume_fenced_code_block(lines, index),
        lambda: (
            (block, index + 1)
            if (block := _create_image_block_from_line(lines[index]))
            else None
        ),
        lambda: (
            (block, index + 1)
            if (block := _create_divider_block_from_line(lines, index))
            else None
        ),
        lambda: _consume_quote_block(lines, index),
        lambda: _consume_list_block(lines, index),
    )

    for consumer in consumers:
        consumed = consumer()
        if consumed:
            return consumed
    return None
