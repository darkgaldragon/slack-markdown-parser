"""Core conversion utilities for Slack Block Kit output.

This module converts LLM-generated Markdown text into Slack Block Kit blocks,
with support for Slack table blocks and robust fallback text generation.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional

ZWSP = "\u200b"

ANSI_ESCAPE_PATTERN = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x1B\x07]*(?:\x07|\x1B\\))"
)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
SLACK_ANGLE_TOKEN_PATTERN = re.compile(r"<[^>\n]+>")

TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
LOOSE_TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{3,}\s*(\|\s*:?-{3,}\s*)+\|?\s*$"
)
TABLE_TOKEN_PATTERN = re.compile(
    r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)"
    r"|<(https?://[^>\s|]+)(?:\|([^>\n]+))?>"
    r"|(`[^`]+`|~~[^~]+~~|\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*))"
)
ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS = (
    re.compile(r"^<https?://[^>\s|]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<mailto:[^>\s|]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<@[UW][A-Z0-9]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<#[CG][A-Z0-9]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<!(?:here|channel|everyone)>$"),
    re.compile(r"^<!subteam\^[A-Z0-9]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<!date\^[^>\n]+>$"),
)


def decode_html_entities(text: str) -> str:
    """Decode HTML entities that may appear in model output."""
    if not text:
        return text
    return html.unescape(text)


def strip_zero_width_spaces(text: str) -> str:
    """Strip zero-width spaces from text."""
    return re.sub(r"[\u200B\uFEFF]", "", text or "")


def _is_allowed_slack_angle_token(token: str) -> bool:
    return any(pattern.match(token) for pattern in ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS)


def sanitize_slack_text(text: str) -> str:
    """Remove control noise and neutralize invalid Slack angle tokens."""
    if not text:
        return text

    cleaned = ANSI_ESCAPE_PATTERN.sub("", text)
    cleaned = CONTROL_CHAR_PATTERN.sub("", cleaned)

    def replace_invalid_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if _is_allowed_slack_angle_token(token):
            return token
        return f"＜{token[1:-1]}＞"

    return SLACK_ANGLE_TOKEN_PATTERN.sub(replace_invalid_token, cleaned)


def add_zero_width_spaces_to_markdown(text: str) -> str:
    """Stabilize markdown rendering by padding style markers with ZWSP.

    Code fences are preserved untouched.
    """
    if not text:
        return text

    boundary_chars = {" ", "\t", "\n", "\r", ZWSP}

    def wrap_match(match: re.Match[str], source: str) -> str:
        start, end = match.start(), match.end()
        before_safe = start > 0 and source[start - 1] in boundary_chars
        after_safe = end < len(source) and source[end] in boundary_chars
        if before_safe and after_safe:
            return match.group(0)

        # When either outer edge is tightly coupled to surrounding text or
        # punctuation, wrap the whole token so Slack can treat the decoration
        # as a standalone span.
        prefix = ZWSP
        suffix = ZWSP
        return f"{prefix}{match.group(0)}{suffix}"

    def wrap_segment(segment: str) -> str:
        if not segment:
            return segment
        patterns = [
            r"(?<!`)`[^`\n]+`(?!`)",
            r"(?<!\*)\*\*(.+?)\*\*(?!\*)",
            r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
            r"~~(.+?)~~",
        ]
        for pattern in patterns:
            segment = re.sub(
                pattern,
                lambda m, s=segment: wrap_match(m, s),
                segment,
                flags=re.DOTALL,
            )
        return re.sub(f"{ZWSP}+", ZWSP, segment)

    code_fence_pattern = r"(```.*?```)"
    parts = re.split(code_fence_pattern, text, flags=re.DOTALL)
    for idx, part in enumerate(parts):
        if re.fullmatch(code_fence_pattern, part or "", flags=re.DOTALL):
            continue
        parts[idx] = wrap_segment(part)
    return "".join(parts)


# Backward-compatible alias
add_zero_width_spaces = add_zero_width_spaces_to_markdown


def _is_strict_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and stripped.startswith("|") and stripped.endswith("|")


def _split_markdown_table_cells(line: str) -> List[str]:
    """Split markdown table cells while preserving pipes inside <...|...> links."""
    working = line.strip()
    if not working:
        return []

    if working.startswith("|"):
        working = working[1:]
    if working.endswith("|"):
        working = working[:-1]

    cells: List[str] = []
    current: List[str] = []
    in_angle = False
    in_inline_code = False
    escaped = False

    for ch in working:
        if escaped:
            current.append(ch)
            escaped = False
            continue

        if ch == "\\":
            current.append(ch)
            escaped = True
            continue

        if ch == "`":
            in_inline_code = not in_inline_code
            current.append(ch)
            continue

        if not in_inline_code:
            if ch == "<":
                in_angle = True
            elif ch == ">" and in_angle:
                in_angle = False

        if ch == "|" and not in_angle and not in_inline_code:
            cells.append("".join(current).strip())
            current = []
            continue

        current.append(ch)

    cells.append("".join(current).strip())
    return cells


def _split_heading_and_table_row(line: str) -> Optional[tuple[str, str]]:
    """Split lines like '# Heading |a|b|' into heading and table row."""
    if "|" not in line:
        return None

    in_code = False
    first_pipe = -1
    for i, ch in enumerate(line):
        if ch == "`":
            in_code = not in_code
        elif ch == "|" and not in_code:
            first_pipe = i
            break

    if first_pipe < 0:
        return None

    heading_part = line[:first_pipe].rstrip()
    table_part = line[first_pipe:].strip()

    if not heading_part or not heading_part.lstrip().startswith("#"):
        return None

    heading_text = heading_part
    table_prefix = ""
    if " " in heading_part.strip():
        head, tail = heading_part.rsplit(" ", 1)
        heading_text = head
        table_prefix = tail

    table_line = (table_prefix + " " + table_part).strip()
    if "|" not in table_line:
        return None
    if not table_line.startswith("|"):
        table_line = "|" + table_line
    if not table_line.endswith("|"):
        table_line = table_line + "|"

    return heading_text, table_line


def normalize_markdown_tables(markdown_text: str) -> str:
    """Normalize markdown tables: pipe completion, separator completion, column sizing."""
    if not markdown_text:
        return markdown_text

    lines = markdown_text.splitlines()
    normalized: List[str] = []
    buffer: List[str] = []

    def is_table_block(candidates: List[str]) -> bool:
        if len(candidates) < 2:
            return False
        if any(
            LOOSE_TABLE_SEPARATOR_PATTERN.match(line.strip()) for line in candidates
        ):
            return True

        column_counts: List[int] = []
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

    for line in lines:
        stripped = line.strip()

        heading_and_table = _split_heading_and_table_row(line)
        if heading_and_table:
            flush_buffer()
            heading_text, table_line = heading_and_table
            normalized.append(heading_text)
            buffer.append(table_line)
        elif "|" in stripped:
            buffer.append(line)
        else:
            flush_buffer()
            normalized.append(line)
    flush_buffer()

    return "\n".join(normalized)


def looks_like_markdown_table(text: str) -> bool:
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


def _create_table_cell(text: str) -> Dict[str, Any]:
    """Build Slack rich_text cell from markdown fragment."""
    clean_text = strip_zero_width_spaces(text or "")
    clean_text = clean_text.replace("\\|", "|")
    if not clean_text.strip():
        clean_text = "-"
    elements: List[Dict[str, Any]] = []
    last_index = 0

    for match in TABLE_TOKEN_PATTERN.finditer(clean_text):
        if match.start() > last_index:
            prefix = clean_text[last_index : match.start()]
            if prefix:
                elements.append({"type": "text", "text": prefix})

        markdown_label, markdown_url, angle_url, angle_label, token = match.groups()
        element: Dict[str, Any]
        if markdown_label and markdown_url:
            element = {"type": "link", "url": markdown_url, "text": markdown_label}
        elif angle_url:
            element = {
                "type": "link",
                "url": angle_url,
                "text": angle_label or angle_url,
            }
        else:
            style: Dict[str, bool] = {}
            content = token or ""

            if content.startswith("`") and content.endswith("`"):
                content = content[1:-1]
                style["code"] = True
            elif content.startswith("~~") and content.endswith("~~"):
                content = content[2:-2]
                style["strike"] = True
            elif content.startswith("**") and content.endswith("**"):
                content = content[2:-2]
                style["bold"] = True
            elif content.startswith("*") and content.endswith("*"):
                content = content[1:-1]
                style["italic"] = True

            element = {"type": "text", "text": content}
            if style:
                element["style"] = style
        elements.append(element)
        last_index = match.end()

    if last_index < len(clean_text):
        suffix = clean_text[last_index:]
        elements.append({"type": "text", "text": suffix})

    if not elements:
        elements.append({"type": "text", "text": clean_text})

    return {
        "type": "rich_text",
        "elements": [{"type": "rich_text_section", "elements": elements}],
    }


def extract_plain_text_from_table_cell(cell: Dict[str, Any]) -> str:
    """Extract plain text from a Slack table cell object."""
    if not isinstance(cell, dict):
        return ""

    if cell.get("type") == "rich_text":
        texts: List[str] = []
        for element in cell.get("elements", []):
            if not isinstance(element, dict):
                continue
            if element.get("type") == "rich_text_section":
                for child in element.get("elements", []):
                    if isinstance(child, dict):
                        if child.get("type") == "link":
                            texts.append(str(child.get("text") or child.get("url", "")))
                        else:
                            texts.append(child.get("text", ""))
            elif "text" in element:
                texts.append(str(element.get("text", "")))
        return "".join(texts)

    return str(cell.get("text", ""))


def markdown_table_to_slack_table(table_markdown: str) -> Optional[Dict[str, Any]]:
    """Convert markdown table text to Slack table block."""
    lines = [
        line.rstrip() for line in table_markdown.strip().splitlines() if line.strip()
    ]
    rows: List[List[Dict[str, Any]]] = []
    expected_columns: Optional[int] = None

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


def split_markdown_into_segments(markdown_text: str) -> List[Dict[str, str]]:
    """Split markdown into alternating text/table segments."""
    segments: List[Dict[str, str]] = []
    if not markdown_text:
        return segments

    lines = markdown_text.splitlines()
    current: List[str] = []
    current_is_table: Optional[bool] = None

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

    for line in lines:
        stripped = line.strip()
        is_table_line = stripped.startswith("|") and stripped.endswith("|")

        if current_is_table is None:
            current_is_table = is_table_line
            current.append(line)
            continue

        if is_table_line == current_is_table:
            current.append(line)
        else:
            flush()
            current_is_table = is_table_line
            current.append(line)

    flush()
    return segments


def convert_markdown_to_slack_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """Convert markdown text into Slack markdown/table blocks."""
    if not markdown_text:
        return []

    markdown_text = decode_html_entities(markdown_text)
    markdown_text = sanitize_slack_text(markdown_text)
    markdown_text = normalize_markdown_tables(markdown_text)
    blocks: List[Dict[str, Any]] = []

    for segment in split_markdown_into_segments(markdown_text):
        content = segment.get("content", "")
        if not content.strip():
            continue

        if segment.get("type") == "table" and looks_like_markdown_table(content):
            table_block = markdown_table_to_slack_table(content)
            if table_block:
                blocks.append(table_block)
                continue

        formatted = add_zero_width_spaces_to_markdown(content)
        if formatted.strip():
            blocks.append({"type": "markdown", "text": formatted})

    return blocks


# Backward-compatible alias
convert_markdown_text_to_blocks = convert_markdown_to_slack_blocks


def split_blocks_by_table(blocks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Split blocks into multiple messages to satisfy one-table-per-message constraint."""
    messages: List[List[Dict[str, Any]]] = []
    current_message: List[Dict[str, Any]] = []

    for block in blocks or []:
        if isinstance(block, dict) and block.get("type") == "table":
            if current_message:
                messages.append(current_message)
            messages.append([block])
            current_message = []
        else:
            current_message.append(block)

    if current_message:
        messages.append(current_message)

    return messages


def convert_markdown_to_slack_messages(
    markdown_text: str,
) -> List[List[Dict[str, Any]]]:
    """Convert markdown text into a list of Slack message block groups."""
    blocks = convert_markdown_to_slack_blocks(markdown_text)
    if not blocks:
        return []
    return split_blocks_by_table(blocks)


def convert_markdown_to_slack_payloads(
    markdown_text: str,
) -> List[Dict[str, Any]]:
    """Convert markdown text into Slack-ready payload dicts with fallback text."""
    payloads: List[Dict[str, Any]] = []
    for blocks in convert_markdown_to_slack_messages(markdown_text):
        fallback_text = build_fallback_text_from_blocks(blocks).strip()
        if not fallback_text:
            fallback_text = blocks_to_plain_text(blocks).strip()
        payloads.append({"blocks": blocks, "text": fallback_text or " "})
    return payloads


def blocks_to_plain_text(blocks: List[Dict[str, Any]]) -> str:
    """Build plain text representation from Slack blocks."""
    parts: List[str] = []

    for block in blocks or []:
        block_type = block.get("type") if isinstance(block, dict) else None

        if block_type == "markdown":
            text = block.get("text", "")
            if text:
                parts.append(strip_zero_width_spaces(text))
        elif block_type == "table":
            rows = block.get("rows") or []
            for row in rows:
                cell_texts: List[str] = []
                if not isinstance(row, list):
                    continue
                for cell in row:
                    cell_text = extract_plain_text_from_table_cell(cell)
                    if cell_text:
                        cell_texts.append(strip_zero_width_spaces(cell_text))
                if cell_texts:
                    parts.append(" | ".join(cell_texts))
        elif isinstance(block, dict):
            text = block.get("text", "")
            if text:
                parts.append(str(text))

    return "\n".join([p for p in parts if p]).strip()


def build_fallback_text_from_blocks(blocks: List[Dict[str, Any]]) -> str:
    """Build Slack fallback text from block structure."""
    plain_parts: List[str] = []

    for block in blocks or []:
        if not isinstance(block, dict):
            continue

        if block.get("type") == "markdown":
            text = strip_zero_width_spaces(block.get("text", ""))
            if text.strip():
                plain_parts.append(text)
        elif block.get("type") == "table":
            table_lines: List[str] = []
            for row in block.get("rows", []):
                if not isinstance(row, list):
                    continue
                cells = [extract_plain_text_from_table_cell(cell) for cell in row]
                if cells:
                    table_lines.append(" | ".join(cells))
            if table_lines:
                plain_parts.append("\n".join(table_lines))

    return "\n\n".join([part for part in plain_parts if part.strip()])


# Backward-compatible helper retained for existing imports.
def parse_markdown_table(table_text: str) -> List[List[str]]:
    """Parse markdown table into row/cell text matrix."""
    rows: List[List[str]] = []
    for line in [line for line in table_text.strip().splitlines() if line.strip()]:
        if TABLE_SEPARATOR_PATTERN.match(line.strip()):
            continue
        if "|" not in line:
            continue
        rows.append(_split_markdown_table_cells(line))
    return rows
