"""Tests for slack_markdown_parser.converter."""

from __future__ import annotations

from pathlib import Path

import pytest

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
from slack_markdown_parser.converter import (
    _block_text_size,
    _estimate_markdown_expansion_items,
    normalize_bare_urls_for_slack_markdown,
)


def _first_table(blocks: list[dict]) -> dict:
    return next(block for block in blocks if block.get("type") == "table")


def test_common_markdown_blocks_convert_to_rich_block_kit_blocks() -> None:
    raw = """# Rich sample

![Generated chart](https://example.com/chart.png)

> Warning: Check the threshold

> quoted **line**

- alpha
- beta

```python
print("ok")
```
"""

    blocks = convert_markdown_to_slack_blocks(raw)

    assert [block["type"] for block in blocks] == [
        "markdown",
        "image",
        "rich_text",
        "rich_text",
        "rich_text",
        "rich_text",
    ]
    assert blocks[0]["text"] == "# Rich sample"
    assert blocks[1]["image_url"] == "https://example.com/chart.png"
    assert blocks[1]["alt_text"] == "Generated chart"
    assert blocks[2]["elements"][0]["type"] == "rich_text_quote"
    assert blocks[3]["elements"][0]["type"] == "rich_text_quote"
    assert blocks[4]["elements"][0]["type"] == "rich_text_list"
    assert blocks[5]["elements"][0]["type"] == "rich_text_preformatted"
    assert blocks[5]["elements"][0]["language"] == "python"
    assert "![Generated chart]" not in build_fallback_text_from_blocks(blocks)


def test_unclosed_fenced_code_remains_markdown_without_rich_promotions() -> None:
    raw = """```python
![Generated chart](https://example.com/chart.png)
---
- item
> quote"""

    blocks = convert_markdown_to_slack_blocks(raw)

    assert [block["type"] for block in blocks] == ["markdown"]
    assert build_fallback_text_from_blocks(blocks) == raw


def test_malformed_standalone_image_url_falls_back_to_markdown() -> None:
    raw = "![bad](http://[::1)"

    blocks = convert_markdown_to_slack_blocks(raw)

    assert [block["type"] for block in blocks] == ["markdown"]
    assert build_fallback_text_from_blocks(blocks) == raw


def test_ambiguous_two_space_nested_list_remains_markdown() -> None:
    raw = "- parent\n  - child"

    blocks = convert_markdown_to_slack_blocks(raw)

    assert [block["type"] for block in blocks] == ["markdown"]
    assert build_fallback_text_from_blocks(blocks) == raw


def test_escaped_quote_and_list_items_remain_markdown() -> None:
    quote_blocks = convert_markdown_to_slack_blocks("> \\*literal\\*")
    list_blocks = convert_markdown_to_slack_blocks("- \\*literal\\*")

    assert [block["type"] for block in quote_blocks] == ["markdown"]
    assert [block["type"] for block in list_blocks] == ["markdown"]


def test_promoted_blocks_are_split_at_slack_block_limit() -> None:
    raw = "\n\n".join(
        f"![Image {index}](https://example.com/{index}.png)" for index in range(55)
    )

    messages = convert_markdown_to_slack_messages(raw)

    assert [len(message) for message in messages] == [50, 5]
    assert all(block["type"] == "image" for message in messages for block in message)


def test_long_document_is_split_into_markdown_blocks_within_limit() -> None:
    raw = "\n\n".join(
        f"Paragraph {index} with **bold** text and `code` plus 日本語の**強調**も含む文章です。"
        for index in range(900)
    )

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) > 1
    assert all(block["type"] == "markdown" for block in blocks)
    assert all(len(block["text"]) <= 12000 for block in blocks)
    rebuilt = "\n\n".join(build_fallback_text_from_blocks([block]) for block in blocks)
    assert rebuilt == raw
    messages = convert_markdown_to_slack_messages(raw)
    for message in messages:
        assert sum(_block_text_size(block) for block in message) <= 13200


def test_document_under_markdown_length_limit_is_not_split() -> None:
    raw = "\n\n".join(f"para {index}" for index in range(50))

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) == 1


def test_single_paragraph_without_blank_lines_is_split_at_line_boundaries() -> None:
    raw = "\n".join(
        f"line {index} continues without blank separation" for index in range(600)
    )

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) > 1
    assert all(len(block["text"]) <= 12000 for block in blocks)
    rebuilt_lines = [line for block in blocks for line in block["text"].split("\n")]
    assert rebuilt_lines == raw.split("\n")


def test_single_overlong_line_is_split_at_word_boundaries() -> None:
    raw = ("word " * 5000).strip()

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) > 1
    assert all(len(block["text"]) <= 12000 for block in blocks)
    assert all(set(block["text"].split()) == {"word"} for block in blocks)


def test_cjk_line_without_spaces_is_hard_split_within_limit() -> None:
    raw = "あ" * 20000

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) > 1
    assert all(len(block["text"]) <= 12000 for block in blocks)
    assert "".join(block["text"] for block in blocks) == raw


def test_dense_emphasis_inflation_is_resplit_within_limit() -> None:
    # Raw length fits the packing target, but ZWSP insertion inflates the
    # formatted text past the hard limit, forcing the shrink-and-retry path.
    raw = ("**注:**あ " * 1400).strip()

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) > 1
    assert all(len(block["text"]) <= 12000 for block in blocks)
    # A split must never land inside an emphasis token.
    assert all(block["text"].count("**") % 2 == 0 for block in blocks)


def test_unclosed_fence_split_reopens_fence_in_continuation() -> None:
    raw = "```python\n" + "\n".join(
        f"print({index})  # long code line for splitting" for index in range(500)
    )

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) > 1
    assert all(block["type"] == "markdown" for block in blocks)
    assert all(len(block["text"]) <= 12000 for block in blocks)
    assert all(block["text"].startswith("```python") for block in blocks[1:])


def test_long_document_split_respects_preserve_visual_blank_lines() -> None:
    raw = "\n\n".join(
        f"paragraph {index} with enough text to need splitting\n\ncontinued"
        for index in range(500)
    )

    blocks = convert_markdown_to_slack_blocks(raw, preserve_visual_blank_lines=True)

    assert len(blocks) > 1
    assert all(len(block["text"]) <= 12000 for block in blocks)
    assert any("\u00a0" in block["text"] for block in blocks)


def test_expansion_item_estimate_matches_measured_slack_model() -> None:
    estimate = _estimate_markdown_expansion_items

    # Measured against a real workspace on 2026-06-11 (see converter.py):
    assert estimate("\n\n".join(f"para {i}" for i in range(60))) == 1
    assert estimate("\n".join(f"- item {i}" for i in range(60))) == 1
    assert estimate("\n\n".join(f"```\ncode {i}\n```" for i in range(52))) == 1
    assert estimate("\n\n".join(f"> quote {i}" for i in range(52))) == 1
    assert estimate("\n\n".join(f"## h{i}" for i in range(50))) == 50
    assert estimate("\n\n".join("---" for _ in range(52))) == 52
    assert estimate("\n\n".join(f"## h{i}\n\npara {i}" for i in range(26))) == 52


def test_heading_dense_document_respects_expansion_budget() -> None:
    raw = "\n\n".join(f"## 見出し{index}" for index in range(120))

    messages = convert_markdown_to_slack_messages(raw)

    assert len(messages) >= 3
    for message in messages:
        weight = sum(
            (
                _estimate_markdown_expansion_items(block["text"])
                if block["type"] == "markdown"
                else 1
            )
            for block in message
        )
        assert weight <= 50


def test_heading_paragraph_document_respects_expansion_budget() -> None:
    raw = "\n\n".join(
        f"## セクション{index}\n\n本文{index}の説明テキストです。"
        for index in range(60)
    )

    messages = convert_markdown_to_slack_messages(raw)

    assert len(messages) >= 3
    for message in messages:
        weight = sum(
            (
                _estimate_markdown_expansion_items(block["text"])
                if block["type"] == "markdown"
                else 1
            )
            for block in message
        )
        assert weight <= 50
    rebuilt = "\n\n".join(
        build_fallback_text_from_blocks(message) for message in messages
    )
    assert rebuilt == raw


def test_message_total_block_text_respects_measured_budget() -> None:
    # Measured 2026-06-11: one message's blocks may carry at most 13,200
    # characters of text in total (msg_blocks_too_long beyond that).
    raw = "巨大単一段落: " + (
        "空行を含まない長い日本語の段落です。**強調**や`コード`も混ざります。" * 400
    )

    messages = convert_markdown_to_slack_messages(raw)

    assert len(messages) >= 2
    for message in messages:
        assert sum(_block_text_size(block) for block in message) <= 13200


def test_split_blocks_by_table_packs_by_total_text_size() -> None:
    big = {"type": "markdown", "text": "A" * 11900}
    small = {"type": "markdown", "text": "B" * 1400}
    halves = [
        {"type": "markdown", "text": "C" * 6000},
        {"type": "markdown", "text": "D" * 6000},
    ]

    from slack_markdown_parser import split_blocks_by_table

    assert [len(m) for m in split_blocks_by_table([big, small])] == [1, 1]
    assert [len(m) for m in split_blocks_by_table(halves)] == [2]


def test_callout_quote_uses_supported_rich_text_quote() -> None:
    blocks = convert_markdown_to_slack_blocks(
        "> [!NOTE]\n> This is an admonition-like block."
    )

    assert len(blocks) == 1
    assert blocks[0]["type"] == "rich_text"
    assert blocks[0]["elements"][0]["type"] == "rich_text_quote"
    assert blocks[0]["elements"][0]["elements"][0]["text"] == (
        "[!NOTE]\nThis is an admonition-like block."
    )


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


def test_lone_lt_in_cell_does_not_swallow_following_pipes() -> None:
    raw = """| 条件 | 結果 |
|---|---|
| x < y | ok |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    row = [extract_plain_text_from_table_cell(cell) for cell in table["rows"][1]]
    assert row == ["x < y", "ok"]


def test_lt_threshold_cells_keep_all_columns() -> None:
    raw = """| 項目 | 目標 | 実測 |
|---|---|---|
| 応答時間 | < 100ms | 85ms |
| エラー率 | < 1% | 0.3% |
"""

    table = _first_table(convert_markdown_to_slack_blocks(raw))
    rows = [
        [extract_plain_text_from_table_cell(cell) for cell in row]
        for row in table["rows"]
    ]
    assert rows == [
        ["項目", "目標", "実測"],
        ["応答時間", "< 100ms", "85ms"],
        ["エラー率", "< 1%", "0.3%"],
    ]


def test_slack_tokens_in_cells_still_protect_inner_pipes() -> None:
    from slack_markdown_parser import parse_markdown_table

    assert parse_markdown_table(
        "| <https://example.com|click> | <!date^1234567890^{date}|fallback> |"
    ) == [["<https://example.com|click>", "<!date^1234567890^{date}|fallback>"]]


def test_heading_inline_table_splits_even_with_lone_lt_in_heading() -> None:
    raw = """### threshold < limit |A|B|
|1|2|
"""

    blocks = convert_markdown_to_slack_blocks(raw)
    table_blocks = [b for b in blocks if b.get("type") == "table"]
    assert table_blocks, "heading+table line should still split into a table"


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


def test_preserve_visual_blank_lines_injects_nbsp_lines_in_markdown_blocks() -> None:
    blocks = convert_markdown_to_slack_blocks(
        "alpha\n\nbeta", preserve_visual_blank_lines=True
    )

    assert blocks[0]["type"] == "markdown"
    assert blocks[0]["text"] == "alpha\n\u00a0\nbeta"


def test_preserve_visual_blank_lines_keeps_fallback_text_unchanged() -> None:
    payload = convert_markdown_to_slack_payloads(
        "alpha\n\nbeta", preserve_visual_blank_lines=True
    )[0]

    assert payload["blocks"][0]["text"] == "alpha\n\u00a0\nbeta"
    assert payload["text"] == "alpha\n\nbeta"


def test_preserve_visual_blank_lines_keeps_multiple_blank_lines() -> None:
    blocks = convert_markdown_to_slack_blocks(
        "alpha\n\n\nbeta", preserve_visual_blank_lines=True
    )

    assert blocks[0]["text"] == "alpha\n\u00a0\n\u00a0\nbeta"
    assert build_fallback_text_from_blocks(blocks) == "alpha\n\n\nbeta"


def test_preserve_visual_blank_lines_skips_table_blocks() -> None:
    raw = """intro

| A | B |
|---|---|
| 1 | 2 |
"""

    blocks = convert_markdown_to_slack_blocks(raw, preserve_visual_blank_lines=True)

    assert blocks[0]["type"] == "markdown"
    assert blocks[0]["text"].strip() == "intro"
    assert "\u00a0" not in blocks[0]["text"]
    assert blocks[1]["type"] == "table"


def test_preserve_visual_blank_lines_skips_fenced_code_blocks() -> None:
    blocks = convert_markdown_to_slack_blocks(
        "```python\nprint(1)\n\nprint(2)\n```\n\nAfter",
        preserve_visual_blank_lines=True,
    )

    assert blocks[0]["type"] == "rich_text"
    preformatted = blocks[0]["elements"][0]
    assert preformatted["type"] == "rich_text_preformatted"
    assert preformatted["language"] == "python"
    assert preformatted["elements"][0]["text"] == "print(1)\n\nprint(2)"
    assert blocks[1]["text"] == "After"
    assert (
        build_fallback_text_from_blocks(blocks)
        == "```python\nprint(1)\n\nprint(2)\n```\n\nAfter"
    )


def test_preserve_visual_blank_lines_skips_blank_before_setext_heading() -> None:
    blocks = convert_markdown_to_slack_blocks(
        "Intro\n\nSetext Heading\n==============\n\nBody",
        preserve_visual_blank_lines=True,
    )

    assert blocks[0]["text"] == "Intro\n\nSetext Heading\n==============\n\u00a0\nBody"


def test_preserve_visual_blank_lines_skips_blank_before_reference_definition() -> None:
    payload = convert_markdown_to_slack_payloads(
        "Reference style link: [Reference Style][ref1]\n\n"
        "[ref1]: https://example.com/reference\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert "\n\u00a0\n[ref1]:" not in payload["blocks"][0]["text"]
    assert "\n\n[ref1]: <https://example.com/reference>" in payload["blocks"][0]["text"]
    assert (
        payload["text"] == "Reference style link: [Reference Style][ref1]\n\n"
        "[ref1]: https://example.com/reference\n\nAfter"
    )


def test_preserve_visual_blank_lines_skips_blank_after_ordered_list() -> None:
    payload = convert_markdown_to_slack_payloads(
        "1. first\n2. second\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert payload["blocks"][0]["type"] == "rich_text"
    assert payload["blocks"][0]["elements"][0]["type"] == "rich_text_list"
    assert payload["blocks"][1]["text"] == "After"
    assert payload["text"] == "1. first\n2. second\n\nAfter"


def test_preserve_visual_blank_lines_skips_blank_after_ordered_list_continuation() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "1. first\n   continuation\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert payload["blocks"][0]["text"] == "1. first\n   continuation\n\nAfter"
    assert payload["text"] == "1. first\n   continuation\n\nAfter"


def test_preserve_visual_blank_lines_skips_blank_after_nested_ordered_list() -> None:
    payload = convert_markdown_to_slack_payloads(
        "1. first\n    1. nested\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert payload["blocks"][0]["type"] == "rich_text"
    assert [element["indent"] for element in payload["blocks"][0]["elements"]] == [0, 1]
    assert payload["blocks"][1]["text"] == "After"
    assert payload["text"] == "1. first\n    1. nested\n\nAfter"


def test_preserve_visual_blank_lines_skips_blank_after_unordered_list_continuation() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "- first\n  continuation\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert payload["blocks"][0]["text"] == "- first\n  continuation\n\nAfter"
    assert payload["text"] == "- first\n  continuation\n\nAfter"


def test_preserve_visual_blank_lines_skips_blank_inside_list_item_paragraph() -> None:
    payload = convert_markdown_to_slack_payloads(
        "1. first\n\n   same item paragraph",
        preserve_visual_blank_lines=True,
    )[0]

    assert payload["blocks"][0]["text"] == "1. first\n\n   same item paragraph"
    assert payload["text"] == "1. first\n\n   same item paragraph"


def test_preserve_visual_blank_lines_rewrites_blank_after_indented_non_list_marker() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "Intro\n\n    1. not-a-list\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert (
        payload["blocks"][0]["text"]
        == "Intro\n\u00a0\n    1. not-a-list\n\u00a0\nAfter"
    )
    assert payload["text"] == "Intro\n\n    1. not-a-list\n\nAfter"


def test_preserve_visual_blank_lines_rewrites_blank_after_paragraph_numbered_line_starting_at_two() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "Intro\n2. step\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert payload["blocks"][0]["text"] == "Intro\n2. step\n\u00a0\nAfter"
    assert payload["text"] == "Intro\n2. step\n\nAfter"


def test_preserve_visual_blank_lines_keeps_blank_after_paragraph_numbered_line_starting_at_one() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "Intro\n1. step\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert payload["blocks"][0]["text"] == "Intro\n1. step\n\nAfter"
    assert payload["text"] == "Intro\n1. step\n\nAfter"


def test_preserve_visual_blank_lines_keeps_blank_after_ordered_list_starting_at_two_after_blank() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "Intro\n\n2. step\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert [block["type"] for block in payload["blocks"]] == [
        "markdown",
        "rich_text",
        "markdown",
    ]
    assert payload["blocks"][1]["elements"][0]["offset"] == 1
    assert payload["text"] == "Intro\n\n2. step\n\nAfter"


def test_preserve_visual_blank_lines_still_rewrites_blank_before_ordered_list() -> None:
    payload = convert_markdown_to_slack_payloads(
        "Intro\n\n1. first\n2. second",
        preserve_visual_blank_lines=True,
    )[0]

    assert [block["type"] for block in payload["blocks"]] == ["markdown", "rich_text"]
    assert payload["text"] == "Intro\n\n1. first\n2. second"


def test_preserve_visual_blank_lines_promotes_dash_thematic_break_to_divider_block() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "Intro\n- - -\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert [block["type"] for block in payload["blocks"]] == [
        "markdown",
        "divider",
        "markdown",
    ]
    assert payload["text"] == "Intro\n\n- - -\n\nAfter"


def test_preserve_visual_blank_lines_promotes_asterisk_thematic_break_to_divider_block() -> (
    None
):
    payload = convert_markdown_to_slack_payloads(
        "Intro\n* * *\n\nAfter",
        preserve_visual_blank_lines=True,
    )[0]

    assert [block["type"] for block in payload["blocks"]] == [
        "markdown",
        "divider",
        "markdown",
    ]
    assert payload["text"] == "Intro\n\n* * *\n\nAfter"


def test_preserve_visual_blank_lines_handles_corpus_sensitive_boundaries() -> None:
    markdown_text = Path("tests/fixtures/llm_markdown_p0_corpus.md").read_text(
        encoding="utf-8"
    )

    markdown_blocks = [
        block
        for block in convert_markdown_to_slack_blocks(
            markdown_text, preserve_visual_blank_lines=True
        )
        if block.get("type") == "markdown"
    ]

    first_block_text = markdown_blocks[0]["text"]
    assert "\n\u00a0\nSetext Heading" not in first_block_text
    assert "\n\u00a0\n[ref1]:" not in first_block_text
    assert "\n\u00a0\nBare URL:" in first_block_text


def test_preserve_visual_blank_lines_keeps_fallback_text_with_synthetic_spacing() -> (
    None
):
    markdown_text = "先頭\n\n詳細は、**フロントエンド (`App.tsx`)**を確認"

    payload = convert_markdown_to_slack_payloads(
        markdown_text, preserve_visual_blank_lines=True
    )[0]

    assert payload["text"] == markdown_text
    assert build_fallback_text_from_blocks(payload["blocks"]) == markdown_text


def test_preserve_visual_blank_lines_keeps_fallback_text_with_zwsp_before_blank_line() -> (
    None
):
    markdown_text = "日本語**太字**\n\n次行"

    payload = convert_markdown_to_slack_payloads(
        markdown_text, preserve_visual_blank_lines=True
    )[0]

    assert payload["text"] == markdown_text
    assert build_fallback_text_from_blocks(payload["blocks"]) == markdown_text


def test_zero_width_space_not_inserted_inside_code_fence() -> None:
    text = "```\n**not bold**\n```\n\u672c\u6587**\u6ce8\u610f:**\u3067\u3059"
    converted = add_zero_width_spaces_to_markdown(text)

    # Fence content is preserved verbatim (no ZWSP padding inside the fence).
    assert "\u200b**not bold**" not in converted
    assert "**not bold**\u200b" not in converted
    # Text outside the fence is still processed: an inner ZWSP protects the
    # punctuation-terminated bold so Slack keeps it as a bold run.
    assert "**\u6ce8\u610f:\u200b**" in converted


def test_zero_width_space_not_inserted_inside_tilde_fence() -> None:
    text = "~~~\n**not bold**\n~~~\n\u672c\u6587**\u6ce8\u610f:**\u3067\u3059"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "\u200b**not bold**" not in converted
    assert "**not bold**\u200b" not in converted
    assert "**\u6ce8\u610f:\u200b**" in converted


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


def test_bold_ending_in_punctuation_gets_inner_zwsp_before_close() -> None:
    # A bold run ending in punctuation (``%``) directly followed by CJK
    # punctuation (``、``/``。``) is exposed by Slack unless the closing marker
    # flanks via CommonMark rule 2a. An inner ZWSP just before the closing
    # ``**`` achieves that; an outer ZWSP would itself re-break the run.
    text = (
        "GDPval は **70.9%→83.0%**、"
        "Investment Banking Modeling Tasks は **68.4%→87.3%**。"
    )
    converted = add_zero_width_spaces_to_markdown(text)

    assert (
        "GDPval は **70.9%→83.0%\u200b**、"
        "Investment Banking Modeling Tasks は **68.4%→87.3%\u200b**。"
    ) == converted


def test_bold_with_tight_boundary_on_left_is_wrapped_with_outer_zwsp() -> None:
    # A CJK-terminated bold needs no inner ZWSP; only the tight left edge is
    # padded and the safe (space) right edge is left clean.
    text = "特に伸びが大きいのは、**実務系** と **ツール連携** ね。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert "特に伸びが大きいのは、\u200b**実務系** と **ツール連携** ね。" == converted


def test_list_item_bold_ending_in_colon_at_line_end_stays_raw() -> None:
    # Reported bug: a list item whose bold ends in a colon used to receive a
    # trailing ZWSP right after the closing ``**`` (``- ...**\u200b``), which
    # broke the run on Slack. At a line/text boundary no padding is needed.
    text = "- **末尾コロン:**"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == text
    assert "\u200b" not in converted


def test_bold_ending_in_colon_before_cjk_gets_inner_zwsp() -> None:
    # Colon-terminated bold glued to a following CJK character only renders
    # when the closing marker flanks via rule 2a, so a ZWSP is inserted just
    # inside the closing ``**``.
    text = "本文**強調:**です"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == "本文\u200b**強調:\u200b**です"


def test_bold_ending_in_punctuation_before_cjk_comma_gets_inner_zwsp() -> None:
    # The GDPval/Case-1 pattern: punctuation-terminated bold directly followed
    # by a CJK comma. Slack does not accept ``、`` as a flanking neighbour, so
    # the fix relies on the inner ZWSP rather than the (useless) outer one.
    text = "**項目:**、続き"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == "**項目:\u200b**、続き"


def test_bold_ending_in_cjk_before_cjk_gets_no_inner_zwsp() -> None:
    # A CJK-terminated bold flanks via rule 2a on its own, so no ZWSP is
    # added *inside* the markers; only the legacy outer padding is applied.
    text = "本文**強調**です"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == "本文\u200b**強調**\u200bです"
    assert "調\u200b**" not in converted  # no inner ZWSP before closing marker


def test_reported_colon_bold_list_payload_has_no_exposed_markers() -> None:
    # End-to-end: a heading-hugging list (markdown path) whose items end in a
    # bold colon must not emit a ZWSP adjacent to a closing ``**``.
    markdown = "見出し\n- **カバーできてるもの:**\n- 子: **末尾コロン:**だね"
    payloads = convert_markdown_to_slack_payloads(markdown)
    block_text = payloads[0]["blocks"][0]["text"]

    # No ZWSP directly after any closing ``**`` (the failure mode).
    assert "**\u200b" not in block_text
    # The colon-before-CJK item is protected by an inner ZWSP instead.
    assert "**末尾コロン:\u200b**だね" in block_text


def test_english_bold_with_punctuation_on_right_stays_raw() -> None:
    text = "• **APIYI (apiyi.com)**: OpenAI互換"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == text


def test_english_bold_before_japanese_period_gets_inner_zwsp() -> None:
    # Slack does not accept a CJK full stop (``。``) as a flanking neighbor,
    # so an English bold ending in punctuation (``)``) right before it is no
    # longer preserved raw — an inner ZWSP protects the closing marker.
    text = "• **APIYI (apiyi.com)**。"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == "• **APIYI (apiyi.com)\u200b**。"


def test_ascii_bold_before_cjk_comma_without_kana_gets_inner_zwsp() -> None:
    # Codex review case: ASCII/numeric emphasis with no nearby Han/Kana must
    # not be preserved raw when followed by a CJK comma; the inner ZWSP keeps
    # the closing ``**`` flanking via rule 2a.
    text = "Score **70.9%→83.0%**、続き"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == "Score **70.9%→83.0%\u200b**、続き"


def test_whitespace_flanked_bold_marker_stays_literal() -> None:
    # ``** spaced **`` is not emphasis in CommonMark — the delimiters are
    # whitespace-flanked — so it must be left untouched rather than paired.
    text = "** spaced **"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == text
    assert "\u200b" not in converted


def test_stray_bold_marker_does_not_corrupt_following_bold() -> None:
    # A stray, whitespace-flanked ``**`` in the middle of a line must not be
    # paired with a later marker; the well-formed ``**bold**`` after it still
    # renders and its neighbours are left untouched.
    text = "use ** like **bold** ok"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == text


def test_unclosed_bold_marker_at_end_stays_literal() -> None:
    # A closed bold span followed by a dangling ``**`` leaves the unclosed
    # marker literal without disturbing the closed span.
    text = "**done** and **oops"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == text


def test_stray_bold_marker_does_not_break_inner_zwsp_of_other_span() -> None:
    # Regression: an unbalanced ``**`` earlier in the same block used to shift
    # marker pairing across newlines (the bold pattern is DOTALL), which flipped
    # the ZWSP of a later punctuation-terminated bold to the broken *outer*
    # position and exposed the literal ``**`` on Slack. The stray marker must
    # stay literal while the punctuation bold keeps its protective inner ZWSP.
    text = "- **手順:** ここで ** 露出\nASCII **70.9%→83.0%**、に直結"
    converted = add_zero_width_spaces_to_markdown(text)

    assert (
        converted == "- **手順:** ここで ** 露出\nASCII **70.9%→83.0%\u200b**、に直結"
    )
    # No closing marker received an outer ZWSP (the failure signature).
    assert "**\u200b" not in converted


def test_unbalanced_marker_block_keeps_other_bold_inner_zwsp() -> None:
    # End-to-end (markdown path): a stray ``**`` in one list item must not
    # corrupt the inner-ZWSP protection of a punctuation bold in a sibling item.
    markdown = "見出し\n- **手順:** ここで ** 露出\n- 値 **70.9%→83.0%**、で直結"
    payloads = convert_markdown_to_slack_payloads(markdown)
    block_text = payloads[0]["blocks"][0]["text"]

    assert "**70.9%→83.0%\u200b**、" in block_text
    assert "**\u200b" not in block_text


def test_dangling_bold_opener_does_not_steal_later_span_zwsp() -> None:
    # Codex review on #52: a dangling opener with no valid closer of its own
    # (`**: x **`) must not scan past the literal stray and steal a later
    # well-formed span's closing marker. That mis-pairing used to drop a stray
    # ZWSP just inside the dangling `**`. Bounding the bold body to a single
    # `**` run keeps the dangling opener literal and protects only the real span.
    text = "**: x ** and **y%**、"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == "**: x ** and **y%\u200b**、"
    # No ZWSP was inserted just inside the dangling opener.
    assert "**\u200b:" not in converted


def test_dangling_bold_opener_keeps_following_span_bold() -> None:
    # Same class, end to end: the second span stays an independent bold with its
    # inner ZWSP while the unclosed first marker is left literal.
    text = "**oops ** and **70.9%→83.0%**、"
    converted = add_zero_width_spaces_to_markdown(text)

    assert converted == "**oops ** and **70.9%→83.0%\u200b**、"


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


def test_sanitize_removes_internal_marker_code_points() -> None:
    raw = "a\u2063b\ufff0c\ufff1d\ufff2e\ufff3f"
    assert sanitize_slack_text(raw) == "abcdef"


def test_fenced_code_preserves_html_tags_and_entities() -> None:
    raw = 'Before\n\n```html\n<div class="x">a &amp; b</div>\n```\n'

    blocks = convert_markdown_to_slack_blocks(raw)

    preformatted = blocks[1]["elements"][0]
    assert preformatted["type"] == "rich_text_preformatted"
    assert preformatted["elements"][0]["text"] == '<div class="x">a &amp; b</div>'


def test_unclosed_fence_preserves_html_tags_and_entities() -> None:
    blocks = convert_markdown_to_slack_blocks("```\n<div> &amp;\n")

    assert blocks[0]["type"] == "markdown"
    assert "<div> &amp;" in blocks[0]["text"]


def test_inline_code_preserves_html_tags_and_entities() -> None:
    blocks = convert_markdown_to_slack_blocks(
        "A &gt; B with `<div>` and `&amp;` and <foo> tag."
    )

    assert blocks[0]["text"] == "A > B with `<div>` and `&amp;` and ＜foo＞ tag."


def test_stray_backticks_across_lines_do_not_suppress_sanitization() -> None:
    raw = "tick ` here\nProse &gt; and <foo> stay sanitized\nanother ` tick"

    blocks = convert_markdown_to_slack_blocks(raw)

    assert "Prose > and ＜foo＞ stay sanitized" in blocks[0]["text"]


def test_same_line_inline_code_still_protected_with_stray_backtick_nearby() -> None:
    raw = "stray ` tick\nuse `<div>` here"

    blocks = convert_markdown_to_slack_blocks(raw)

    assert "`<div>`" in blocks[0]["text"]


def test_lone_backtick_does_not_pair_with_longer_backtick_run() -> None:
    raw = "` not code <foo> ``<code>``"

    blocks = convert_markdown_to_slack_blocks(raw)

    assert "＜foo＞" in blocks[0]["text"]
    assert "``<code>``" in blocks[0]["text"]


def test_invalid_angle_token_spanning_inline_code_is_neutralized() -> None:
    blocks = convert_markdown_to_slack_blocks("A <foo `bar` baz> B")

    assert blocks[0]["text"] == "A ＜foo `bar` baz＞ B"


def test_placeholder_injection_does_not_crash_or_steal_spans() -> None:
    blocks = convert_markdown_to_slack_blocks("attack \ufff0code0\ufff1 here")
    assert blocks[0]["text"] == "attack code0 here"

    blocks = convert_markdown_to_slack_blocks(
        "attack \ufff0code0\ufff1 with `real` code"
    )
    assert blocks[0]["text"] == "attack code0 with `real` code"


def test_direct_zwsp_api_survives_placeholder_injection() -> None:
    formatted = add_zero_width_spaces_to_markdown("x \ufff0code0\ufff1 y `code`")

    assert "\ufff0" not in formatted
    assert "\ufff1" not in formatted
    assert "`code`" in formatted


def test_direct_underscore_api_survives_placeholder_injection() -> None:
    assert (
        normalize_underscore_emphasis("x \ufff00\ufff1 `code` _em_")
        == "x 0 `code` *em*"
    )


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


def test_bare_url_does_not_swallow_following_cjk() -> None:
    # Regression (#chloe): a scheme URL glued directly to CJK text used to be
    # matched greedily to end-of-line, dragging the closing paren, the bold
    # markers, and the rest of the sentence into one autolink. The URL must be
    # trimmed to its real extent so the surrounding markup survives.
    converted = normalize_bare_urls_for_slack_markdown(
        "**APIYI (https://apiyi.com)**。に句点を直結。"
    )

    assert converted == "**APIYI (<https://apiyi.com>)**。に句点を直結。"


def test_bare_url_trims_trailing_cjk_punctuation() -> None:
    converted = normalize_bare_urls_for_slack_markdown(
        "詳細は https://example.com。次へ"
    )

    assert converted == "詳細は <https://example.com>。次へ"


def test_bare_url_drops_unbalanced_paren_but_keeps_balanced() -> None:
    assert (
        normalize_bare_urls_for_slack_markdown("(https://example.com)")
        == "(<https://example.com>)"
    )
    assert (
        normalize_bare_urls_for_slack_markdown(
            "see https://en.wikipedia.org/wiki/Foo_(bar) ok"
        )
        == "see <https://en.wikipedia.org/wiki/Foo_(bar)> ok"
    )


def test_bare_url_stops_at_emphasis_markers() -> None:
    assert (
        normalize_bare_urls_for_slack_markdown("**https://example.com**")
        == "**<https://example.com>**"
    )


def test_scheme_url_in_bold_before_cjk_keeps_bold_closed() -> None:
    # End to end: the autolink no longer over-extends, the bold closes with an
    # inner ZWSP, and the literal ``**`` markers are not exposed on Slack.
    payload = convert_markdown_to_slack_payloads(
        "英字太字の **APIYI (https://apiyi.com)**。に句点を直結。"
    )[0]
    block_text = payload["blocks"][0]["text"]

    assert "**APIYI (<https://apiyi.com>)\u200b**。" in block_text
    # No closing marker received an outer ZWSP (the exposure signature).
    assert "**\u200b" not in block_text


def test_bare_url_preserves_cjk_iri_path() -> None:
    # Codex review on #54: CJK *letters* are legal in an IRI path / IDN host,
    # so the trim must not cut there (only CJK punctuation and emphasis runs are
    # boundaries). A Japanese Wikipedia URL must stay intact.
    assert (
        normalize_bare_urls_for_slack_markdown(
            "詳細は https://ja.wikipedia.org/wiki/日本語 を参照"
        )
        == "詳細は <https://ja.wikipedia.org/wiki/日本語> を参照"
    )
    assert (
        normalize_bare_urls_for_slack_markdown("https://日本語.example.com/path")
        == "<https://日本語.example.com/path>"
    )


def test_bare_url_preserves_single_asterisk_in_query() -> None:
    # Codex review on #54: a lone ``*`` is legal in a URL path/query (wildcards),
    # so only a doubled ``**`` emphasis run is a boundary. The link target must
    # not be truncated at the asterisk.
    assert (
        normalize_bare_urls_for_slack_markdown(
            "検索 https://example.com/search?q=a*b です"
        )
        == "検索 <https://example.com/search?q=a*b> です"
    )


def test_bare_url_preserves_cjk_iteration_mark_in_iri() -> None:
    # Codex review on #54: CJK iteration marks (`々`, `〻`) are letter-like and
    # occur in real words/IRIs (人々, 各々), so they must not be boundaries.
    assert (
        normalize_bare_urls_for_slack_markdown("https://ja.wikipedia.org/wiki/人々")
        == "<https://ja.wikipedia.org/wiki/人々>"
    )


def test_bare_url_stops_at_fullwidth_punctuation() -> None:
    # Codex review on #54: full-width CJK punctuation terminates prose just like
    # its ASCII counterpart, so the autolink must stop before it.
    assert (
        normalize_bare_urls_for_slack_markdown("詳細はhttps://example.com）次へ")
        == "詳細は<https://example.com>）次へ"
    )


def test_bare_url_keeps_url_legal_semicolon_but_trims_sentence_period() -> None:
    # Codex review on #54: `;` is URL-legal (matrix/path parameters) and must be
    # kept, while a sentence-final ASCII period is trimmed GFM-style as prose.
    assert (
        normalize_bare_urls_for_slack_markdown("見て https://example.com/p;a=1;b=2 ね")
        == "見て <https://example.com/p;a=1;b=2> ね"
    )
    assert (
        normalize_bare_urls_for_slack_markdown("See https://example.com.")
        == "See <https://example.com>."
    )


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
    assert blocks[0]["type"] == "rich_text"
    preformatted = blocks[0]["elements"][0]
    assert preformatted["type"] == "rich_text_preformatted"
    assert "a | b | c" in preformatted["elements"][0]["text"]


def test_tilde_code_fence_stays_markdown() -> None:
    raw = """~~~sql
select *
from users
where id = 1;
~~~"""

    blocks = convert_markdown_to_slack_blocks(raw)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "rich_text"
    preformatted = blocks[0]["elements"][0]
    assert preformatted["type"] == "rich_text_preformatted"
    assert preformatted["language"] == "sql"
    assert preformatted["elements"][0]["text"] == (
        "select *\nfrom users\nwhere id = 1;"
    )
    assert build_fallback_text_from_blocks(blocks) == raw


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


def _iter_inline_elements(blocks: list[dict]):
    """Yield every inline (link/text) element nested anywhere in the blocks."""
    stack = list(blocks)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("type") in {"link", "text"}:
                yield node
            stack.extend(node.get("elements", []))
        elif isinstance(node, list):
            stack.extend(node)


def _find_link(blocks: list[dict], url: str) -> dict | None:
    return next(
        (
            el
            for el in _iter_inline_elements(blocks)
            if el.get("type") == "link" and el.get("url") == url
        ),
        None,
    )


def test_bold_wrapped_link_in_list_becomes_styled_link() -> None:
    # ``**[text](url)**`` is matched by the emphasis branch, not the link branch,
    # so without the fix the whole ``[text](url)`` survived as a literal bold text
    # run and the link was dead in Slack. It should become a bold link element.
    raw = "- **[#27375](https://example.com/issues?issueNumber=27375)** closed\n"

    blocks = convert_markdown_to_slack_blocks(raw)
    link = _find_link(blocks, "https://example.com/issues?issueNumber=27375")
    assert link is not None
    assert link["text"] == "#27375"
    assert link["style"] == {"bold": True}


def test_italic_wrapped_link_in_list_becomes_styled_link() -> None:
    raw = "- *[Example](https://example.com)* trailing\n"

    blocks = convert_markdown_to_slack_blocks(raw)
    link = _find_link(blocks, "https://example.com")
    assert link is not None
    assert link["text"] == "Example"
    assert link["style"] == {"italic": True}


def test_strikethrough_wrapped_link_in_list_becomes_styled_link() -> None:
    raw = "- ~~[Example](https://example.com)~~ trailing\n"

    blocks = convert_markdown_to_slack_blocks(raw)
    link = _find_link(blocks, "https://example.com")
    assert link is not None
    assert link["style"] == {"strike": True}


def test_bare_link_in_list_still_works() -> None:
    # The emphasis fix must not disturb a plain link (no surrounding emphasis).
    raw = "- [Example](https://example.com) here\n"

    blocks = convert_markdown_to_slack_blocks(raw)
    link = _find_link(blocks, "https://example.com")
    assert link is not None
    assert "style" not in link


def test_plain_bold_without_link_stays_text() -> None:
    raw = "- **just bold text** here\n"

    blocks = convert_markdown_to_slack_blocks(raw)
    bold = next(
        el
        for el in _iter_inline_elements(blocks)
        if el.get("type") == "text" and el.get("style") == {"bold": True}
    )
    assert bold["text"] == "just bold text"


def _list_section_elements(blocks: list[dict]) -> list[dict]:
    """Return the inline elements of the first rich_text_list's first item."""
    rich = next(block for block in blocks if block.get("type") == "rich_text")
    rich_list = rich["elements"][0]
    assert rich_list["type"] == "rich_text_list"
    return rich_list["elements"][0]["elements"]


def test_channel_mention_in_list_becomes_channel_element() -> None:
    # A list is promoted to a rich_text block, where a `<#C…>` token must be a
    # structured `channel` element — otherwise Slack renders it as literal text.
    blocks = convert_markdown_to_slack_blocks("- *Channel:* <#C0B7QPVMTEH>")
    elements = _list_section_elements(blocks)

    assert {"type": "channel", "channel_id": "C0B7QPVMTEH"} in elements


def test_user_mention_in_list_becomes_user_element() -> None:
    blocks = convert_markdown_to_slack_blocks("- owner <@U123ABC>")
    elements = _list_section_elements(blocks)

    assert elements[-1] == {"type": "user", "user_id": "U123ABC"}


def test_user_group_and_broadcast_mentions_in_list() -> None:
    blocks = convert_markdown_to_slack_blocks("- ping <!subteam^S999>\n- alert <!here>")
    rich_list = next(b for b in blocks if b.get("type") == "rich_text")["elements"][0]
    first = rich_list["elements"][0]["elements"]
    second = rich_list["elements"][1]["elements"]

    assert {"type": "usergroup", "usergroup_id": "S999"} in first
    assert {"type": "broadcast", "range": "here"} in second


def test_mention_label_is_dropped_in_list() -> None:
    # `<#C…|name>` carries a display label; Slack renders the element from the
    # id, so the label is dropped rather than leaked into the output.
    blocks = convert_markdown_to_slack_blocks("1. see <#C0ENG|general> and <@W42|bob>")
    elements = _list_section_elements(blocks)

    assert {"type": "channel", "channel_id": "C0ENG"} in elements
    assert {"type": "user", "user_id": "W42"} in elements
    assert all("general" not in str(element) for element in elements)


def test_mention_in_prose_stays_in_markdown_block() -> None:
    # Prose is not promoted, so the mention rides in a `markdown` block where
    # Slack resolves it — no rich_text element is created.
    blocks = convert_markdown_to_slack_blocks("Go to <#C0B7QPVMTEH> here.")

    assert blocks[0]["type"] == "markdown"
    assert blocks[0]["text"] == "Go to <#C0B7QPVMTEH> here."


def test_list_mention_round_trips_to_live_token_in_fallback() -> None:
    # The plain-text fallback re-emits the canonical token so a downgraded
    # mrkdwn fallback still links and notifies.
    blocks = convert_markdown_to_slack_blocks("- owner <@U123ABC> in <#C0ENG>")
    fallback = build_fallback_text_from_blocks(blocks)

    assert "<@U123ABC>" in fallback
    assert "<#C0ENG>" in fallback


def test_table_cell_mention_round_trips_to_live_token_in_fallback() -> None:
    # TABLE_TOKEN_PATTERN also feeds table cells, so a mention in a cell is a
    # structured element with no "text" key. The cell plain-text extractor must
    # go through the same downgrade path as rich_text sections, or the mention
    # silently vanishes from the fallback.
    md = "| Owner | Channel |\n| --- | --- |\n| <@U123ABC> | go to <#C0ENG> |"
    blocks = convert_markdown_to_slack_blocks(md)
    table = _first_table(blocks)

    assert extract_plain_text_from_table_cell(table["rows"][1][0]) == "<@U123ABC>"
    assert extract_plain_text_from_table_cell(table["rows"][1][1]) == "go to <#C0ENG>"

    fallback = build_fallback_text_from_blocks(blocks)
    assert "<@U123ABC>" in fallback
    assert "go to <#C0ENG>" in fallback


# --- Downgrade-parity matrix -------------------------------------------------
# Every supported inline token must survive BOTH renderings of every context:
# the block structure Slack renders, and the plain-text downgrades used for
# notification fallbacks (`build_fallback_text_from_blocks`) and plain views
# (`blocks_to_plain_text`). A new inline element type that misses one of the
# downgrade paths fails here instead of silently dropping from notifications.

MENTION_TOKEN_CASES = [
    ("<@U123ABC>", {"type": "user", "user_id": "U123ABC"}),
    ("<#C0ENG>", {"type": "channel", "channel_id": "C0ENG"}),
    ("<!subteam^S999>", {"type": "usergroup", "usergroup_id": "S999"}),
    ("<!here>", {"type": "broadcast", "range": "here"}),
]


@pytest.mark.parametrize(("token", "element"), MENTION_TOKEN_CASES)
def test_mention_parity_in_prose(token: str, element: dict) -> None:
    blocks = convert_markdown_to_slack_blocks(f"see {token} now")

    assert blocks[0]["type"] == "markdown"
    assert token in blocks[0]["text"]
    assert token in build_fallback_text_from_blocks(blocks)
    assert token in blocks_to_plain_text(blocks)


@pytest.mark.parametrize(("token", "element"), MENTION_TOKEN_CASES)
def test_mention_parity_in_list_item(token: str, element: dict) -> None:
    blocks = convert_markdown_to_slack_blocks(f"- item {token} end")

    assert element in _list_section_elements(blocks)
    assert token in build_fallback_text_from_blocks(blocks)
    assert token in blocks_to_plain_text(blocks)


@pytest.mark.parametrize(("token", "element"), MENTION_TOKEN_CASES)
def test_mention_parity_in_table_cell(token: str, element: dict) -> None:
    blocks = convert_markdown_to_slack_blocks(f"| H |\n| --- |\n| x {token} y |")
    cell = _first_table(blocks)["rows"][1][0]

    assert element in cell["elements"][0]["elements"]
    assert extract_plain_text_from_table_cell(cell) == f"x {token} y"
    assert token in build_fallback_text_from_blocks(blocks)
    assert token in blocks_to_plain_text(blocks)


@pytest.mark.parametrize(
    ("markdown_link", "label", "url"),
    [
        ("[docs](https://example.com/d)", "docs", "https://example.com/d"),
        ("<https://example.com/p|portal>", "portal", "https://example.com/p"),
    ],
)
def test_link_parity_in_list_and_table_cell(
    markdown_link: str, label: str, url: str
) -> None:
    list_blocks = convert_markdown_to_slack_blocks(f"- open {markdown_link} now")
    link = next(
        e for e in _list_section_elements(list_blocks) if e.get("type") == "link"
    )
    assert link["url"] == url
    assert link["text"] == label
    assert label in build_fallback_text_from_blocks(list_blocks)

    table_blocks = convert_markdown_to_slack_blocks(
        f"| H |\n| --- |\n| open {markdown_link} now |"
    )
    cell = _first_table(table_blocks)["rows"][1][0]
    assert extract_plain_text_from_table_cell(cell) == f"open {label} now"
    assert label in build_fallback_text_from_blocks(table_blocks)
