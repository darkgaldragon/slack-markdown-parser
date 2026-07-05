"""Markdown table detection, normalization, cell splitting, and Slack
table block generation."""

from __future__ import annotations

import re
from typing import Any

from ._code_regions import (
    _find_inline_code_span_end,
    _iter_fence_states,
    _multiline_code_span_line_map,
)
from ._constants import (
    ATX_HEADING_PATTERN,
    LOOSE_TABLE_SEPARATOR_PATTERN,
    TABLE_SEPARATOR_PATTERN,
)
from ._rich_text import (
    _create_rich_text_section,
    _rich_text_inline_elements_to_plain_text,
)
from ._sanitize import _match_slack_angle_token_end


def _split_markdown_table_cells(line: str) -> list[str]:
    """Split markdown table cells while preserving pipes inside Slack tokens."""
    working = line.strip()
    if not working:
        return []

    if working.startswith("|"):
        working = working[1:]
    if working.endswith("|"):
        working = working[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    cursor = 0

    while cursor < len(working):
        ch = working[cursor]
        if escaped:
            current.append(ch)
            escaped = False
            cursor += 1
            continue

        if ch == "\\":
            current.append(ch)
            escaped = True
            cursor += 1
            continue

        if ch == "`":
            code_span_end = _find_inline_code_span_end(working, cursor)
            if code_span_end is not None:
                current.append(working[cursor:code_span_end])
                cursor = code_span_end
                continue

        if ch == "<":
            token_end = _match_slack_angle_token_end(working, cursor)
            if token_end is not None:
                current.append(working[cursor:token_end])
                cursor = token_end
                continue

        if ch == "|":
            cells.append("".join(current).strip())
            current = []
            cursor += 1
            continue

        current.append(ch)
        cursor += 1

    cells.append("".join(current).strip())
    return cells


def _count_cell_words(cell_text: str) -> int:
    tokens = [token for token in cell_text.strip().split() if token]
    return len(tokens) or 1


def _split_heading_prefix_and_first_cell(
    heading_prefix: str, reference_cell: str | None
) -> tuple[str, str] | None:
    tokens = [token for token in heading_prefix.strip().split() if token]
    if len(tokens) < 2:
        return None

    reference_words = _count_cell_words(reference_cell or "")
    first_cell_words = min(reference_words, len(tokens) - 1)
    if first_cell_words <= 0:
        return None
    if first_cell_words != reference_words:
        # The heading tail cannot supply a first cell shaped like the
        # reference row's first cell, so this is a heading that merely
        # contains a pipe (``## Phase 1 | Overview`` followed by prose with
        # a pipe), not a glued table header.
        return None

    heading_tokens = tokens[:-first_cell_words]
    first_cell_tokens = tokens[-first_cell_words:]
    if not heading_tokens or not first_cell_tokens:
        return None

    return " ".join(heading_tokens), " ".join(first_cell_tokens)


def _split_heading_and_table_row(
    line: str, next_line: str | None = None
) -> tuple[str, str] | None:
    """Split lines like '# Heading |a|b|' into heading and table row.

    The split targets one specific LLM failure mode: a table's header row
    glued onto the heading line, with the real data rows following. A heading
    that merely contains a pipe (``## Phase 1 | Overview``) is not that
    pattern, so the split requires a table-like (pipe-carrying) next line;
    without one the heading is left intact.
    """
    if "|" not in line:
        return None
    if not next_line or "|" not in next_line:
        return None

    escaped = False
    first_pipe = -1
    cursor = 0
    while cursor < len(line):
        ch = line[cursor]
        if escaped:
            escaped = False
            cursor += 1
            continue
        if ch == "\\":
            escaped = True
            cursor += 1
            continue
        if ch == "`":
            code_span_end = _find_inline_code_span_end(line, cursor)
            if code_span_end is not None:
                cursor = code_span_end
                continue
        if ch == "<":
            token_end = _match_slack_angle_token_end(line, cursor)
            if token_end is not None:
                cursor = token_end
                continue
        if ch == "|":
            first_pipe = cursor
            break
        cursor += 1

    if first_pipe < 0:
        return None

    heading_part = line[:first_pipe].rstrip()
    table_part = line[first_pipe:].strip()

    if not heading_part or not heading_part.lstrip().startswith("#"):
        return None

    heading_match = re.match(r"^([ \t]{0,3}#{1,6})\s+(.+)$", heading_part)
    if not heading_match:
        return None

    heading_marker = heading_match.group(1)
    heading_body = heading_match.group(2).strip()

    if not table_part.startswith("|"):
        table_part = "|" + table_part
    if not table_part.endswith("|"):
        table_part = table_part + "|"

    explicit_cells = _split_markdown_table_cells(table_part)
    if not explicit_cells:
        return None

    reference_cell: str | None = None
    if (
        next_line
        and "|" in next_line
        and not LOOSE_TABLE_SEPARATOR_PATTERN.match(next_line.strip())
    ):
        next_working = next_line.strip()
        if not next_working.startswith("|"):
            next_working = "|" + next_working
        if not next_working.endswith("|"):
            next_working = next_working + "|"
        next_cells = _split_markdown_table_cells(next_working)
        if next_cells:
            reference_cell = next_cells[0]

    if reference_cell is None and explicit_cells:
        reference_cell = explicit_cells[0]

    split_heading = _split_heading_prefix_and_first_cell(heading_body, reference_cell)
    if not split_heading:
        return None

    heading_text_body, first_cell = split_heading
    heading_text = f"{heading_marker} {heading_text_body}"
    table_cells = [first_cell] + explicit_cells
    table_line = "|" + "|".join(table_cells) + "|"

    return heading_text, table_line


def normalize_markdown_tables(markdown_text: str) -> str:
    """Normalize markdown tables: pipe completion, separator completion, column sizing."""
    if not markdown_text:
        return markdown_text

    lines = markdown_text.splitlines()
    normalized: list[str] = []
    buffer: list[str] = []

    def is_table_block(candidates: list[str]) -> bool:
        if len(candidates) < 2:
            return False
        if any(
            LOOSE_TABLE_SEPARATOR_PATTERN.match(line.strip()) for line in candidates
        ):
            return True

        column_counts: list[int] = []
        for line in candidates:
            working = line.strip()
            if "|" not in working:
                continue
            if not working.startswith("|"):
                working = "|" + working
            if not working.endswith("|"):
                working = working + "|"
            if TABLE_SEPARATOR_PATTERN.match(working):
                continue
            column_counts.append(len(_split_markdown_table_cells(working)))

        if len(column_counts) < 2:
            return False

        min_cols, max_cols = min(column_counts), max(column_counts)
        if max_cols < 2:
            return False

        return max_cols - min_cols <= 1

    def flush_buffer() -> None:
        nonlocal buffer
        if buffer and is_table_block(buffer):
            header_line = buffer[0].strip()
            if not header_line.startswith("|"):
                header_line = "|" + header_line
            if not header_line.endswith("|"):
                header_line = header_line + "|"
            header_cells = _split_markdown_table_cells(header_line)
            column_count = max(1, len(header_cells))

            def normalize_row(raw_line: str) -> str:
                if LOOSE_TABLE_SEPARATOR_PATTERN.match(raw_line.strip()):
                    return ""
                working = raw_line.strip()
                if "|" not in working:
                    return ""
                if not working.startswith("|"):
                    working = "|" + working
                if not working.endswith("|"):
                    working = working + "|"
                cells = _split_markdown_table_cells(working)
                cells = (cells + [""] * column_count)[:column_count]
                return "|" + "|".join(cells) + "|"

            normalized.append(normalize_row(buffer[0]))
            normalized.append("|" + "|".join(["---"] * column_count) + "|")
            for line in buffer[1:]:
                row = normalize_row(line)
                if row:
                    normalized.append(row)
        else:
            normalized.extend(buffer)
        buffer = []

    span_interior, _ = _multiline_code_span_line_map(lines)

    for idx, (line, is_fenced, is_opening) in enumerate(_iter_fence_states(lines)):
        if is_fenced:
            if is_opening:
                flush_buffer()
            normalized.append(line)
            continue

        if span_interior[idx]:
            # The line carries part of a multi-line inline code span: Slack
            # renders that stretch as code, so it is never a table row or a
            # glued heading, however pipe-like it looks.
            flush_buffer()
            normalized.append(line)
            continue

        stripped = line.strip()

        next_line = lines[idx + 1] if idx + 1 < len(lines) else None
        if next_line is not None and span_interior[idx + 1]:
            # A line carrying part of a multi-line code span is code, not
            # table evidence: it must neither justify a glued-heading split
            # nor count as the separator behind an ATX-looking header row.
            next_line = None
        heading_and_table = _split_heading_and_table_row(line, next_line)
        if heading_and_table:
            flush_buffer()
            heading_text, table_line = heading_and_table
            normalized.append(heading_text)
            buffer.append(table_line)
        elif "|" in stripped and (
            buffer
            or not ATX_HEADING_PATTERN.match(line)
            or bool(
                next_line is not None
                and LOOSE_TABLE_SEPARATOR_PATTERN.match(next_line.strip())
            )
        ):
            # A heading-looking line whose glued-header split was rejected
            # only escapes buffering when it would *start* a candidate run: a
            # heading that merely contains a pipe must not seed the
            # pipe-completion heuristic. Inside an already-buffered run it is
            # kept — there it is a data row whose first cell begins with '#'
            # — and a following separator row proves a table context, so a
            # header row whose first cell begins with '#' seeds the run too.
            buffer.append(line)
        else:
            flush_buffer()
            normalized.append(line)
    flush_buffer()

    return "\n".join(normalized)


def _looks_like_markdown_table(text: str) -> bool:
    """Heuristic check for markdown table candidates."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    table_like_lines = sum(
        1
        for line in lines
        if line.strip().startswith("|") and line.strip().endswith("|")
    )
    return table_like_lines >= 2


def _create_table_cell(text: str) -> dict[str, Any]:
    """Build Slack rich_text cell from markdown fragment."""
    return {
        "type": "rich_text",
        "elements": [_create_rich_text_section(text, empty_text="-")],
    }


def extract_plain_text_from_table_cell(cell: dict[str, Any]) -> str:
    """Extract plain text from a Slack table cell object."""
    if not isinstance(cell, dict):
        return ""

    if cell.get("type") == "rich_text":
        texts: list[str] = []
        for element in cell.get("elements", []):
            if not isinstance(element, dict):
                continue
            if element.get("type") == "rich_text_section":
                texts.append(
                    _rich_text_inline_elements_to_plain_text(
                        element.get("elements", [])
                    )
                )
            elif "text" in element:
                texts.append(str(element.get("text", "")))
        return "".join(texts)

    return str(cell.get("text", ""))


def markdown_table_to_slack_table(table_markdown: str) -> dict[str, Any] | None:
    """Convert markdown table text to Slack table block."""
    lines = [
        line.rstrip() for line in table_markdown.strip().splitlines() if line.strip()
    ]
    rows: list[list[dict[str, Any]]] = []
    expected_columns: int | None = None

    for line in lines:
        if TABLE_SEPARATOR_PATTERN.match(line):
            continue
        if "|" not in line:
            continue

        cells = _split_markdown_table_cells(line)
        if not cells:
            continue

        if expected_columns is None:
            expected_columns = max(1, len(cells))
        else:
            cells = (cells + [""] * expected_columns)[:expected_columns]

        rows.append(
            [_create_table_cell(cell if cell.strip() else "-") for cell in cells]
        )

    if not rows:
        return None

    return {"type": "table", "rows": rows}


# Backward-compatible alias
markdown_table_to_table_block = markdown_table_to_slack_table


# Backward-compatible helper retained for existing imports.
def parse_markdown_table(table_text: str) -> list[list[str]]:
    """Parse markdown table into row/cell text matrix."""
    rows: list[list[str]] = []
    for line in [line for line in table_text.strip().splitlines() if line.strip()]:
        if TABLE_SEPARATOR_PATTERN.match(line.strip()):
            continue
        if "|" not in line:
            continue
        rows.append(_split_markdown_table_cells(line))
    return rows
