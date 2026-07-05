"""Preview / fallback plain-text generation from generated blocks."""

from __future__ import annotations

import re
from typing import Any

from ._lines import _strip_synthetic_blank_line_placeholders
from ._rich_text import _rich_text_block_to_plain_text
from ._sanitize import strip_zero_width_spaces
from ._tables import extract_plain_text_from_table_cell


def _normalize_markdown_block_plain_text(text: str) -> str:
    if not text:
        return text

    return re.sub(r"<(https?://[^>\s|]+)>", r"\1", text)


def _build_markdown_block_plain_text(
    text: str, synthetic_space_indices: list[int] | None = None
) -> str:
    """Build fallback/plain text for a markdown block before visual-only rewrites."""
    return _normalize_markdown_block_plain_text(
        _strip_synthetic_spaces_from_plain_text(
            strip_zero_width_spaces(text),
            synthetic_space_indices,
        )
    )


def _strip_synthetic_spaces_from_plain_text(
    text: str, synthetic_space_indices: list[int] | None = None
) -> str:
    if not text or not synthetic_space_indices:
        return text

    indices = set(synthetic_space_indices)
    return "".join(
        char for idx, char in enumerate(text) if not (idx in indices and char == " ")
    )


def _markdown_block_to_plain_text(block: dict[str, Any]) -> str:
    """Downgrade a ``markdown`` block, preferring the build-time annotation."""
    text = getattr(block, "_plain_text", None) or ""
    if text:
        return str(text)
    raw_text = block.get("text", "")
    if not raw_text:
        return ""
    return _normalize_markdown_block_plain_text(
        _strip_synthetic_blank_line_placeholders(
            _strip_synthetic_spaces_from_plain_text(
                strip_zero_width_spaces(raw_text),
                getattr(block, "_synthetic_space_indices", None),
            ),
            getattr(block, "_synthetic_blank_line_indices", None),
        )
    )


def _blocks_to_downgrade_parts(
    blocks: list[dict[str, Any]], *, fallback: bool
) -> list[str]:
    """Shared block walker behind :func:`blocks_to_plain_text` and
    :func:`build_fallback_text_from_blocks`.

    The two public functions intentionally differ in a few policies, kept
    explicit on the ``fallback`` flag: fallback keeps table cells verbatim
    (empty cells preserve column alignment) and emits a whole table as one
    part, while the plain-text view strips zero-width spaces, drops empty
    cells, emits one part per row, and surfaces ``text`` from unknown blocks.
    """
    parts: list[str] = []

    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")

        if block_type == "markdown":
            text = _markdown_block_to_plain_text(block)
            if text.strip() if fallback else text:
                parts.append(text)
        elif block_type == "table":
            row_texts: list[str] = []
            for row in block.get("rows") or []:
                if not isinstance(row, list):
                    continue
                if fallback:
                    cell_texts = [
                        extract_plain_text_from_table_cell(cell) for cell in row
                    ]
                else:
                    cell_texts = []
                    for cell in row:
                        cell_text = extract_plain_text_from_table_cell(cell)
                        if cell_text:
                            cell_texts.append(strip_zero_width_spaces(cell_text))
                if cell_texts:
                    row_texts.append(" | ".join(cell_texts))
            if fallback:
                if row_texts:
                    parts.append("\n".join(row_texts))
            else:
                parts.extend(row_texts)
        elif block_type == "rich_text":
            text = _rich_text_block_to_plain_text(block)
            if text.strip() if fallback else text:
                parts.append(text)
        elif block_type == "header":
            text = block.get("text", {})
            if isinstance(text, dict) and text.get("text"):
                parts.append(str(text.get("text", "")))
        elif block_type == "image":
            alt_text = str(block.get("alt_text", "")).strip()
            image_url = str(block.get("image_url", "")).strip()
            image_text = alt_text or image_url
            if alt_text and image_url:
                image_text = f"{alt_text} ({image_url})"
            if image_text:
                parts.append(image_text)
        elif block_type == "divider":
            parts.append(getattr(block, "_plain_text", None) or "---")
        elif not fallback:
            text = block.get("text", "")
            if isinstance(text, dict):
                # e.g. a ``section`` block carries ``text: {type, text}``.
                text = text.get("text", "")
            if text:
                parts.append(str(text))

    return parts


def blocks_to_plain_text(blocks: list[dict[str, Any]]) -> str:
    """Build plain text representation from Slack blocks."""
    parts = _blocks_to_downgrade_parts(blocks, fallback=False)
    return "\n".join([p for p in parts if p]).strip()


def build_fallback_text_from_blocks(blocks: list[dict[str, Any]]) -> str:
    """Build Slack fallback text from block structure."""
    parts = _blocks_to_downgrade_parts(blocks, fallback=True)
    return "\n\n".join([part for part in parts if part.strip()])
