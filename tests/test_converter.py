"""Tests for slack_markdown_parser.converter."""

from __future__ import annotations

from slack_markdown_parser import (
    add_zero_width_spaces_to_markdown,
    blocks_to_plain_text,
    build_fallback_text_from_blocks,
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    convert_markdown_to_slack_payloads,
    decode_html_entities,
    extract_plain_text_from_table_cell,
    normalize_markdown_tables,
    sanitize_slack_text,
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


def test_inline_code_without_spaces_is_padded_with_zwsp() -> None:
    text = "詳細ログIDは`run-20260305-02`です。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "詳細ログIDは\u200b`run-20260305-02`\u200bです。" == converted


def test_bold_with_punctuation_on_only_one_side_is_wrapped_on_both_sides() -> None:
    text = (
        "GDPval は **70.9%→83.0%**、"
        "Investment Banking Modeling Tasks は **68.4%→87.3%**。"
    )
    converted = add_zero_width_spaces_to_markdown(text)

    assert (
        "GDPval は \u200b**70.9%→83.0%**\u200b、"
        "Investment Banking Modeling Tasks は \u200b**68.4%→87.3%**\u200b。"
    ) == converted


def test_bold_with_tight_boundary_on_left_is_wrapped_on_both_sides() -> None:
    text = "特に伸びが大きいのは、**実務系** と **ツール連携** ね。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert (
        "特に伸びが大きいのは、\u200b**実務系**\u200b と **ツール連携** ね。"
        == converted
    )


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


def test_sanitize_invalid_slack_angle_token() -> None:
    assert sanitize_slack_text("A <foo> B") == "A ＜foo＞ B"


def test_sanitize_keeps_valid_slack_angle_link() -> None:
    assert (
        sanitize_slack_text("Docs: <https://example.com|Example>")
        == "Docs: <https://example.com|Example>"
    )


def test_sanitize_removes_ansi_and_control_chars() -> None:
    raw = "ok\x1b[31m red\x1b[0m\x07 done"
    assert sanitize_slack_text(raw) == "ok red done"


def test_convert_blocks_applies_slack_sanitization() -> None:
    blocks = convert_markdown_to_slack_blocks("Status <draft>\x1b[31m")
    assert blocks[0]["text"] == "Status ＜draft＞"


def test_convert_blocks_neutralizes_html_like_tags() -> None:
    blocks = convert_markdown_to_slack_blocks("Plain <div>html</div> text")
    assert blocks[0]["text"] == "Plain ＜div＞html＜/div＞ text"


def test_convert_blocks_normalizes_double_underscore_bold_for_slack() -> None:
    blocks = convert_markdown_to_slack_blocks("日本語の中で__underscore太字__も使う。")
    assert blocks[0]["text"] == "日本語の中で\u200b**underscore太字**\u200bも使う。"


def test_convert_blocks_normalizes_single_underscore_italic_for_slack() -> None:
    blocks = convert_markdown_to_slack_blocks("日本語の中で_underscore italic_も使う。")
    assert blocks[0]["text"] == "日本語の中で\u200b*underscore italic*\u200bも使う。"


def test_convert_blocks_keeps_snake_case_and_escaped_underscores() -> None:
    raw = "foo_bar_baz / \\_not italic\\_"
    blocks = convert_markdown_to_slack_blocks(raw)
    assert blocks[0]["text"] == raw


def test_convert_blocks_does_not_normalize_underscores_inside_urls() -> None:
    raw = "URL: https://example.com/_private_/path"
    blocks = convert_markdown_to_slack_blocks(raw)
    assert blocks[0]["text"] == raw


def test_slack_link_in_table_cell_keeps_single_cell() -> None:
    raw = """| Name | Link |
|---|---|
| Docs | <https://example.com|Example> |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    row = table["rows"][1]
    assert len(row) == 2
    assert extract_plain_text_from_table_cell(row[1]) == "Example"


def test_markdown_link_in_table_cell_uses_link_label_for_plain_text() -> None:
    raw = """| Name | Link |
|---|---|
| Docs | [Example](https://example.com) |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    row = table["rows"][1]
    assert extract_plain_text_from_table_cell(row[1]) == "Example"


def test_table_cell_underscore_emphasis_is_normalized_before_conversion() -> None:
    raw = """| Name | Status |
|---|---|
| Chloe | _Check_ |
| Amy | __OK__ |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    italic_cell = table["rows"][1][1]["elements"][0]["elements"][0]
    bold_cell = table["rows"][2][1]["elements"][0]["elements"][0]

    assert italic_cell["text"] == "Check"
    assert italic_cell["style"] == {"italic": True}
    assert bold_cell["text"] == "OK"
    assert bold_cell["style"] == {"bold": True}


def test_table_cell_preserves_link_and_neutralizes_html_like_tags() -> None:
    raw = """| Name | Link |
|---|---|
| Docs | [Example](https://example.com) and <b>tag</b> |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    row = table["rows"][1]
    assert extract_plain_text_from_table_cell(row[1]) == "Example and ＜b＞tag＜/b＞"


def test_convert_payloads_includes_blocks_and_fallback_text() -> None:
    raw = """# Report

| Team | Status |
|---|---|
| Amy | **OK** |
"""

    payloads = convert_markdown_to_slack_payloads(raw)
    assert len(payloads) == 2
    assert payloads[0]["blocks"][0]["type"] == "markdown"
    assert "Report" in payloads[0]["text"]
    assert payloads[1]["blocks"][0]["type"] == "table"
    assert "Team | Status" in payloads[1]["text"]


def test_zwj_preserved_in_table_cell() -> None:
    raw = "| Name | Icon |\n|---|---|\n| Engineer | \U0001f468\u200d\U0001f4bb |\n"

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    cell_text = extract_plain_text_from_table_cell(table["rows"][1][1])
    assert "\u200d" in cell_text


def test_zwnj_preserved_in_table_cell() -> None:
    raw = "| Name | Word |\n|---|---|\n| Persian | \u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645 |\n"

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    cell_text = extract_plain_text_from_table_cell(table["rows"][1][1])
    assert "\u200c" in cell_text


def test_heading_with_inline_code_pipe_is_not_split() -> None:
    raw = "# Title `a|b`\n\nsome text\n"

    blocks = convert_markdown_to_slack_blocks(raw)
    assert all(b.get("type") == "markdown" for b in blocks)
    assert "Title" in blocks[0].get("text", "")


def test_escaped_pipe_in_table_cell_strips_backslash() -> None:
    raw = "| Expr | Desc |\n|---|---|\n| A \\| B | OR |\n"

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    cell_text = extract_plain_text_from_table_cell(table["rows"][1][0])
    assert cell_text == "A | B"
