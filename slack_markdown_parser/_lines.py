"""Line-oriented classifiers (lists, thematic breaks, indentation) and the
optional visual blank-line placeholder machinery."""

from __future__ import annotations

import re

from ._code_regions import _split_fenced_code_chunks
from ._constants import (
    LIST_ITEM_PATTERN,
    MARKDOWN_BACKSLASH_ESCAPE_PATTERN,
    NBSP,
    REFERENCE_DEFINITION_PATTERN,
    SETEXT_HEADING_UNDERLINE_PATTERN,
    THEMATIC_BREAK_PATTERN,
)


def _indent_width(text: str) -> int:
    width = 0
    for char in text:
        if char == " ":
            width += 1
        elif char == "\t":
            # Treat tabs conservatively for list-continuation heuristics.
            width += 4
        else:
            break
    return width


def _list_item_content_indent(match: re.Match[str]) -> int:
    spacing = match.group("spacing") or ""
    spacing_width = _indent_width(spacing) if spacing else 1
    return (
        _indent_width(match.group("indent") or "")
        + len(match.group("marker") or "")
        + spacing_width
    )


def _is_ordered_list_marker(marker: str) -> bool:
    return bool(marker) and marker[0].isdigit()


def _ordered_list_marker_number(marker: str) -> int:
    if not _is_ordered_list_marker(marker):
        return 1
    try:
        return int(marker[:-1])
    except ValueError:
        return 1


def _list_indent_level(indent: str) -> int:
    width = _indent_width(indent or "")
    if width <= 3:
        return 0
    return min(8, ((width - 4) // 4) + 1)


def _is_ambiguous_rich_list_indent(indent: str) -> bool:
    width = _indent_width(indent or "")
    return 0 < width <= 3


def _has_markdown_backslash_escape(text: str) -> bool:
    return bool(MARKDOWN_BACKSLASH_ESCAPE_PATTERN.search(text or ""))


def _is_thematic_break_line(line: str) -> bool:
    return bool(THEMATIC_BREAK_PATTERN.match(line))


def _ordered_list_marker_starts_at_one(marker: str) -> bool:
    if not _is_ordered_list_marker(marker):
        return False
    return marker[:-1] == "1"


def _starts_root_list_item(lines: list[str], marker_index: int) -> bool:
    line = lines[marker_index]
    if _is_thematic_break_line(line):
        return False
    match = LIST_ITEM_PATTERN.match(line)
    if not match or _indent_width(match.group("indent") or "") > 3:
        return False

    marker = match.group("marker") or ""
    if marker_index == 0 or not lines[marker_index - 1].strip(" \t\r"):
        return True

    if not _is_ordered_list_marker(marker):
        return True

    return _ordered_list_marker_starts_at_one(marker)


def _line_belongs_to_list_context(
    lines: list[str], *, marker_index: int, target_index: int
) -> bool:
    marker_match = LIST_ITEM_PATTERN.match(lines[marker_index])
    if not marker_match:
        return False

    list_indent_stack = [
        (
            _indent_width(marker_match.group("indent") or ""),
            _list_item_content_indent(marker_match),
        )
    ]

    for idx in range(marker_index + 1, target_index + 1):
        line = lines[idx]
        if not line.strip(" \t\r"):
            return False

        line_indent = _indent_width(line)
        nested_match = LIST_ITEM_PATTERN.match(line)
        if nested_match and not _is_thematic_break_line(line):
            marker_indent = _indent_width(nested_match.group("indent") or "")
            while list_indent_stack and marker_indent < list_indent_stack[-1][0]:
                list_indent_stack.pop()

            if not list_indent_stack:
                return False

            if marker_indent == list_indent_stack[-1][0]:
                list_indent_stack[-1] = (
                    marker_indent,
                    _list_item_content_indent(nested_match),
                )
                continue

            if marker_indent >= list_indent_stack[-1][1]:
                list_indent_stack.append(
                    (
                        marker_indent,
                        _list_item_content_indent(nested_match),
                    )
                )
                continue

            return False

        while len(list_indent_stack) > 1 and line_indent < list_indent_stack[-1][0]:
            list_indent_stack.pop()

        if line_indent >= list_indent_stack[-1][1]:
            continue

        return False

    return True


def _blank_run_follows_list_context(lines: list[str], blank_start: int) -> bool:
    previous_visible_index = blank_start - 1
    if previous_visible_index < 0 or not lines[previous_visible_index].strip(" \t\r"):
        return False

    block_start = previous_visible_index
    while block_start > 0 and lines[block_start - 1].strip(" \t\r"):
        block_start -= 1

    for marker_index in range(previous_visible_index, block_start - 1, -1):
        if not _starts_root_list_item(lines, marker_index):
            continue
        if _line_belongs_to_list_context(
            lines, marker_index=marker_index, target_index=previous_visible_index
        ):
            return True

    return False


def _inject_visual_blank_line_placeholders_in_chunk(
    text: str,
) -> tuple[str, list[int]]:
    """Replace internal blank lines with NBSP-only lines for Slack rendering."""
    if not text or "\n" not in text:
        return text, []

    lines = text.split("\n")
    rewritten: list[tuple[str, bool]] = []
    i = 0

    while i < len(lines):
        if lines[i].strip(" \t\r"):
            rewritten.append((lines[i], False))
            i += 1
            continue

        blank_start = i
        while i < len(lines) and not lines[i].strip(" \t\r"):
            i += 1

        has_visible_line_before = blank_start > 0 and bool(
            lines[blank_start - 1].strip(" \t\r")
        )
        has_visible_line_after = i < len(lines) and bool(lines[i].strip(" \t\r"))
        blank_run_follows_list_context = has_visible_line_before and (
            _blank_run_follows_list_context(lines, blank_start)
        )
        next_visible_starts_reference_definition = has_visible_line_after and bool(
            REFERENCE_DEFINITION_PATTERN.match(lines[i])
        )
        next_visible_starts_setext_heading = has_visible_line_after and i + 1 < len(
            lines
        )
        next_visible_starts_setext_heading = bool(
            next_visible_starts_setext_heading
            and lines[i].strip(" \t\r")
            and SETEXT_HEADING_UNDERLINE_PATTERN.match(lines[i + 1])
        )

        if (
            has_visible_line_before
            and has_visible_line_after
            and not blank_run_follows_list_context
            and not next_visible_starts_reference_definition
            and not next_visible_starts_setext_heading
        ):
            rewritten.extend((NBSP, True) for _ in range(i - blank_start))
        else:
            rewritten.extend((line, False) for line in lines[blank_start:i])

    rebuilt_parts: list[str] = []
    synthetic_indices: list[int] = []
    offset = 0

    for idx, (line, is_synthetic) in enumerate(rewritten):
        if idx > 0:
            rebuilt_parts.append("\n")
            offset += 1
        if is_synthetic:
            synthetic_indices.append(offset)
        rebuilt_parts.append(line)
        offset += len(line)

    return "".join(rebuilt_parts), synthetic_indices


def _inject_visual_blank_line_placeholders(text: str) -> tuple[str, list[int]]:
    """Replace internal blank lines outside fenced code blocks."""
    if not text or "\n" not in text:
        return text, []

    rebuilt_parts: list[str] = []
    synthetic_indices: list[int] = []
    offset = 0

    for is_fenced, chunk in _split_fenced_code_chunks(text):
        if is_fenced:
            rebuilt_parts.append(chunk)
            offset += len(chunk)
            continue

        rewritten_chunk, chunk_indices = (
            _inject_visual_blank_line_placeholders_in_chunk(chunk)
        )
        rebuilt_parts.append(rewritten_chunk)
        synthetic_indices.extend(offset + idx for idx in chunk_indices)
        offset += len(rewritten_chunk)

    return "".join(rebuilt_parts), synthetic_indices


def _strip_synthetic_blank_line_placeholders(
    text: str, synthetic_blank_line_indices: list[int] | None = None
) -> str:
    if not text or not synthetic_blank_line_indices:
        return text

    indices = set(synthetic_blank_line_indices)
    return "".join(
        char for idx, char in enumerate(text) if not (idx in indices and char == NBSP)
    )
