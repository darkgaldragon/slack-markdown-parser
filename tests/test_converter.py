"""Tests for slack_markdown_parser.converter."""

from __future__ import annotations

from slack_markdown_parser import (
    add_zero_width_spaces_to_markdown,
    blocks_to_plain_text,
    build_fallback_text_from_blocks,
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    decode_html_entities,
    extract_plain_text_from_table_cell,
    normalize_markdown_tables,
)


def _first_table(blocks: list[dict]) -> dict:
    return next(block for block in blocks if block.get("type") == "table")


def test_normalize_adds_outer_pipes_and_separator() -> None:
    raw = """カテゴリ | 枠1 | 枠2 | 枠3
---|---|---|---
グループA | alpha | beta | gamma
グループB | alpha | delta | epsilon
"""

    normalized = normalize_markdown_tables(raw)
    lines = normalized.splitlines()

    assert lines[0] == "|カテゴリ|枠1|枠2|枠3|"
    assert lines[1] == "|---|---|---|---|"
    assert lines[2].startswith("|グループA")


def test_normalize_without_separator_still_generates_separator() -> None:
    raw = """カテゴリ | 枠1 | 枠2
グループA | alpha | beta
グループB | alpha | delta
"""

    normalized = normalize_markdown_tables(raw)
    lines = normalized.splitlines()

    assert lines[0] == "|カテゴリ|枠1|枠2|"
    assert lines[1] == "|---|---|---|"
    assert lines[2] == "|グループA|alpha|beta|"


def test_heading_inline_with_table_is_split() -> None:
    raw = """### 見出しつきの表 カテゴリ | 枠1 | 枠2
グループA | alpha | beta
"""

    blocks = convert_markdown_to_slack_blocks(raw)
    markdown_blocks = [b for b in blocks if b.get("type") == "markdown"]
    table_blocks = [b for b in blocks if b.get("type") == "table"]

    assert markdown_blocks
    assert table_blocks
    headers = [
        extract_plain_text_from_table_cell(cell) for cell in table_blocks[0]["rows"][0]
    ]
    assert headers == ["カテゴリ", "枠1", "枠2"]


def test_empty_table_cell_is_filled_with_dash() -> None:
    raw = """| Name | Status |
|---|---|
| UserA | |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    row = table["rows"][1]
    assert extract_plain_text_from_table_cell(row[1]) == "-"


def test_multiple_tables_are_split_into_multiple_messages() -> None:
    raw = """# Report

| A | B |
|---|---|
| 1 | 2 |

middle text

| C | D |
|---|---|
| 3 | 4 |
"""

    messages = convert_markdown_to_slack_messages(raw)
    assert len(messages) >= 3
    for message_blocks in messages:
        assert sum(1 for b in message_blocks if b.get("type") == "table") <= 1


def test_zero_width_space_not_inserted_inside_code_fence() -> None:
    text = "```\n**not bold**\n```\noutside **bold**"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "\u200b**not bold**" not in converted
    assert "**bold**\u200b" in converted


def test_blocks_to_plain_text_and_fallback_generation() -> None:
    raw = """# Title

| Name | Score |
|---|---|
| UserA | 100 |
"""

    blocks = convert_markdown_to_slack_blocks(raw)
    plain = blocks_to_plain_text(blocks)
    fallback = build_fallback_text_from_blocks(blocks)

    assert "Title" in plain
    assert "Name | Score" in plain
    assert "UserA | 100" in fallback


def test_decode_html_entities() -> None:
    assert decode_html_entities("A &gt; B &amp; C") == "A > B & C"


def test_slack_link_in_table_cell_keeps_single_cell() -> None:
    raw = """| Name | Link |
|---|---|
| Docs | <https://example.com|Example> |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    row = table["rows"][1]
    assert len(row) == 2
    assert extract_plain_text_from_table_cell(row[1]) == "<https://example.com|Example>"
