from __future__ import annotations

from pathlib import Path

from slack_markdown_parser import (
    blocks_to_plain_text,
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_payloads,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "llm_markdown_p0_corpus.md"


def _load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_llm_markdown_p0_corpus_converts_to_payloads() -> None:
    payloads = convert_markdown_to_slack_payloads(_load_fixture())

    assert payloads
    assert len(payloads) >= 4

    table_block_count = 0
    for payload in payloads:
        assert "blocks" in payload
        assert "text" in payload
        assert "\u200b" not in payload["text"]
        assert "\ufeff" not in payload["text"]

        tables_in_payload = sum(
            1 for block in payload["blocks"] if block.get("type") == "table"
        )
        assert tables_in_payload <= 1
        table_block_count += tables_in_payload

    assert table_block_count >= 3


def test_llm_markdown_p0_corpus_plain_text_preserves_key_signals() -> None:
    blocks = convert_markdown_to_slack_blocks(_load_fixture())
    plain_text = blocks_to_plain_text(blocks)

    assert "H1 Heading" in plain_text
    assert "Setext Heading" in plain_text
    assert "Amy | OK | run-1" in plain_text
    assert "A > B & C < D" in plain_text
    assert '＜div class="note"＞hello＜/div＞' in plain_text
    assert "＜foo＞" in plain_text
