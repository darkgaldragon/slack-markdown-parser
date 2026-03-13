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
    normalize_underscore_emphasis,
    sanitize_slack_text,
)
from slack_markdown_parser.converter import normalize_bare_urls_for_slack_markdown


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


def test_heading_inline_table_preserves_multiword_first_header_cell() -> None:
    raw = """### Heading inline table Header A | Header B
value A | value B
"""

    blocks = convert_markdown_to_slack_blocks(raw)
    assert blocks[0]["type"] == "markdown"
    assert blocks[0]["text"] == "### Heading inline table"

    table = _first_table(blocks)
    headers = [extract_plain_text_from_table_cell(cell) for cell in table["rows"][0]]
    assert headers == ["Header A", "Header B"]


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


def test_zero_width_space_not_inserted_inside_tilde_fence() -> None:
    text = "~~~\n**not bold**\n~~~\noutside **bold**"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "\u200b**not bold**" not in converted
    assert "**bold**\u200b" in converted


def test_inline_code_without_spaces_is_padded_with_zwsp() -> None:
    text = "詳細ログIDは`run-20260305-02`です。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "詳細ログIDは\u200b`run-20260305-02`\u200bです。" == converted


def test_inline_code_inside_bold_with_english_punctuation_wraps_only_outer_bold() -> (
    None
):
    text = "1. **Frontend (`App.tsx`)**: The quick brown fox jumps over the lazy dog."
    converted = add_zero_width_spaces_to_markdown(text)

    assert text == converted


def test_inline_code_inside_bold_with_japanese_spacing_does_not_get_inner_zwsp() -> (
    None
):
    text = "詳細は **フロントエンド (`App.tsx`)** を確認してください。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "詳細は **フロントエンド (`App.tsx`)** を確認してください。" == converted


def test_inline_code_inside_bold_with_tight_japanese_boundaries_is_left_as_raw() -> (
    None
):
    text = "詳細は、**フロントエンド (`App.tsx`)**を確認してください。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "詳細は、 **フロントエンド (`App.tsx`)** を確認してください。" == converted


def test_inline_code_inside_bold_with_left_space_only_in_japanese_gets_right_space() -> (
    None
):
    text = "詳細は、 **フロントエンド (`App.tsx`)**を確認してください。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "詳細は、 **フロントエンド (`App.tsx`)** を確認してください。" == converted


def test_inline_code_inside_bold_with_right_space_only_in_japanese_gets_left_space() -> (
    None
):
    text = "詳細は、**フロントエンド (`App.tsx`)** を確認してください。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "詳細は、 **フロントエンド (`App.tsx`)** を確認してください。" == converted


def test_inline_code_inside_bold_with_tight_chinese_boundaries_gets_visible_spaces() -> (
    None
):
    text = "详情，**外侧(`内侧`)样式**请确认。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "详情， **外侧(`内侧`)样式** 请确认。" == converted


def test_inline_code_inside_bold_with_tight_korean_boundaries_gets_right_space_only() -> (
    None
):
    text = "설명,**바깥(`내부`)강조**입니다."
    converted = add_zero_width_spaces_to_markdown(text)

    assert "설명,**바깥(`내부`)강조** 입니다." == converted


def test_inline_code_inside_bold_with_right_space_in_korean_is_preserved() -> None:
    text = "설명,**바깥(`내부`)강조** 입니다."
    converted = add_zero_width_spaces_to_markdown(text)

    assert text == converted


def test_fallback_text_normalizes_synthetic_spaces_for_japanese_nested_code() -> None:
    text = "詳細は、**フロントエンド (`App.tsx`)**を確認してください。"
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert (
        payload["blocks"][0]["text"]
        == "詳細は、 **フロントエンド (`App.tsx`)** を確認してください。"
    )
    assert payload["text"] == text


def test_plain_text_normalizes_synthetic_spaces_for_chinese_nested_code() -> None:
    text = "详情，**外侧(`内侧`)样式**请确认。"
    blocks = convert_markdown_to_slack_blocks(text)

    assert blocks_to_plain_text(blocks) == text
    assert build_fallback_text_from_blocks(blocks) == text


def test_fallback_text_normalizes_synthetic_spaces_for_korean_nested_code() -> None:
    text = "설명,**바깥(`내부`)강조**입니다."
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert payload["blocks"][0]["text"] == "설명,**바깥(`내부`)강조** 입니다."
    assert payload["text"] == text


def test_mixed_language_japanese_context_normalizes_fallback_text() -> None:
    text = "詳細は**Frontend (`App.tsx`)**を確認してください。"
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert (
        payload["blocks"][0]["text"]
        == "詳細は **Frontend (`App.tsx`)** を確認してください。"
    )
    assert payload["text"] == text


def test_mixed_language_english_context_keeps_original_spacing() -> None:
    text = "Please check **機能A (`ID-1`)** now."
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert payload["blocks"][0]["text"] == text
    assert payload["text"] == text


def test_mixed_language_korean_context_adds_visible_spaces_around_english_nested_code() -> (
    None
):
    text = "설명은**Frontend (`App.tsx`)**입니다."
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert payload["blocks"][0]["text"] == "설명은 **Frontend (`App.tsx`)** 입니다."
    assert payload["text"] == text


def test_fallback_preserves_user_authored_spaces_around_nested_code_emphasis() -> None:
    text = "詳細は **フロント (`App`)** を確認"
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert payload["blocks"][0]["text"] == text
    assert payload["text"] == text


def test_fallback_preserves_user_authored_trailing_space_around_korean_nested_code() -> (
    None
):
    text = "설명, **바깥(`내부`)강조** 입니다."
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert payload["blocks"][0]["text"] == text
    assert payload["text"] == text


def test_existing_zwsp_boundaries_are_upgraded_for_nested_code_emphasis() -> None:
    text = "詳細は、\u200b**フロント(`App`)**\u200bを確認"
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert payload["blocks"][0]["text"] == "詳細は、 **フロント(`App`)** を確認"
    assert payload["text"] == "詳細は、**フロント(`App`)**を確認"


def test_existing_zwsp_boundaries_are_removed_for_english_nested_code_emphasis() -> (
    None
):
    text = "Detail: \u200b**Frontend(`App`)**\u200b check."
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert payload["blocks"][0]["text"] == "Detail: **Frontend(`App`)** check."
    assert payload["text"] == "Detail: **Frontend(`App`)** check."


def test_japanese_nested_code_inside_italic_gets_internal_spacing() -> None:
    text = "詳細は、*外側`内側`装飾*を確認してください。"
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert (
        payload["blocks"][0]["text"]
        == "詳細は、 *外側 `内側` 装飾* を確認してください。"
    )
    assert payload["text"] == text


def test_japanese_nested_code_inside_strike_gets_internal_spacing() -> None:
    text = "詳細は、~~外側`内側`装飾~~を確認してください。"
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert (
        payload["blocks"][0]["text"]
        == "詳細は、 ~~外側 `内側` 装飾~~ を確認してください。"
    )
    assert payload["text"] == text


def test_nested_code_next_to_parentheses_does_not_gain_internal_spacing() -> None:
    text = "詳細は、**外側(`内側`)装飾**を確認してください。"
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert (
        payload["blocks"][0]["text"]
        == "詳細は、 **外側(`内側`)装飾** を確認してください。"
    )
    assert payload["text"] == text


def test_bold_markers_inside_inline_code_are_not_rewritten() -> None:
    text = "コードは`**literal**`です。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "コードは\u200b`**literal**`\u200bです。" == converted


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


def test_english_bold_with_punctuation_on_right_stays_raw() -> None:
    text = "• **APIYI (apiyi.com)**: OpenAI互換"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == text


def test_english_bold_with_japanese_period_stays_raw() -> None:
    text = "• **APIYI (apiyi.com)**。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == text


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


def test_normalize_underscore_emphasis_converts_cjk_adjacent_markup() -> None:
    converted = normalize_underscore_emphasis(
        "日本語の中で__underscore太字__も使う。日本語の中で_underscore italic_も使う。"
    )

    assert "**underscore太字**" in converted
    assert "*underscore italic*" in converted
    assert "__underscore太字__" not in converted
    assert "_underscore italic_" not in converted


def test_normalize_underscore_emphasis_preserves_identifiers_and_escaped_markup() -> (
    None
):
    converted = normalize_underscore_emphasis(
        r"snake_case はそのまま。\_not bold\_ もそのまま。"
    )

    assert "snake_case" in converted
    assert r"\_not bold\_" in converted


def test_normalize_underscore_emphasis_preserves_urls_and_angle_tokens() -> None:
    converted = normalize_underscore_emphasis(
        "URL https://example.com/a_b と <https://example.com/a_b|A_B>"
    )

    assert "https://example.com/a_b" in converted
    assert "<https://example.com/a_b|A_B>" in converted


def test_normalize_bare_urls_wraps_plain_http_links() -> None:
    converted = normalize_bare_urls_for_slack_markdown(
        "Bare URL: https://example.com/path_(demo)?a=1&b=2#frag"
    )

    assert converted == "Bare URL: <https://example.com/path_(demo)?a=1&b=2#frag>"


def test_normalize_bare_urls_preserves_markdown_links_and_code_spans() -> None:
    converted = normalize_bare_urls_for_slack_markdown(
        "Docs: [Example](https://example.com/docs) and `https://example.com/code`"
    )

    assert "[Example](https://example.com/docs)" in converted
    assert "`https://example.com/code`" in converted


def test_fallback_unwraps_inserted_bare_url_autolinks() -> None:
    text = (
        "Bare URL: https://example.com/path_(demo)?a=1&b=2#frag\n"
        "Markdown link: [Example Docs](https://example.com/docs)"
    )
    payload = convert_markdown_to_slack_payloads(text)[0]

    assert (
        payload["blocks"][0]["text"]
        == "Bare URL: <https://example.com/path_(demo)?a=1&b=2#frag>\n"
        "Markdown link: [Example Docs](https://example.com/docs)"
    )
    assert payload["text"] == text


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


def test_underscore_emphasis_is_normalized_inside_table_cells() -> None:
    raw = """| Name | Status |
|---|---|
| Amy | __OK__ |
| Chloe | _Check_ |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    ok_cell = table["rows"][1][1]["elements"][0]["elements"][0]
    check_cell = table["rows"][2][1]["elements"][0]["elements"][0]

    assert ok_cell["text"] == "OK"
    assert ok_cell["style"] == {"bold": True}
    assert check_cell["text"] == "Check"
    assert check_cell["style"] == {"italic": True}


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


def test_heading_with_multi_backtick_inline_code_pipe_is_not_split() -> None:
    raw = "# Title ``a|b``\n\nsome text\n"

    blocks = convert_markdown_to_slack_blocks(raw)
    assert len(blocks) == 1
    assert all(b.get("type") == "markdown" for b in blocks)
    assert blocks[0]["text"] == raw.strip()


def test_code_fence_with_table_like_rows_stays_markdown() -> None:
    raw = """```
a | b | c
--- | --- | ---
inside code fence, not a table
```"""

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "markdown"
    assert "a | b | c" in blocks[0]["text"]


def test_tilde_code_fence_stays_markdown() -> None:
    raw = """~~~sql
select *
from users
where id = 1;
~~~"""

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "markdown"
    assert blocks[0]["text"] == raw


def test_escaped_pipe_in_table_cell_strips_backslash() -> None:
    raw = "| Expr | Desc |\n|---|---|\n| A \\| B | OR |\n"

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    cell_text = extract_plain_text_from_table_cell(table["rows"][1][0])
    assert cell_text == "A | B"


def test_multi_backtick_code_span_keeps_pipe_inside_table_cell() -> None:
    raw = "| A | B |\n|---|---|\n| left | ``x|y`` |\n"

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    code_cell = table["rows"][1][1]["elements"][0]["elements"][0]

    assert extract_plain_text_from_table_cell(table["rows"][1][1]) == "x|y"
    assert code_cell["text"] == "x|y"
    assert code_cell["style"] == {"code": True}
