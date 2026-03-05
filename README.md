# slack-markdown-parser

LLM が生成した Markdown を Slack Block Kit（`markdown` + `table`）に変換する Python ライブラリです。

## インストール

```bash
pip install slack-markdown-parser==2.*
```

## 最小利用例

```python
from slack_markdown_parser import (
    convert_markdown_to_slack_messages,
    build_fallback_text_from_blocks,
)

markdown = """
# Weekly Report

| Team | Status |
|---|---|
| API | **On track** |
| UI | *In progress* |
"""

for blocks in convert_markdown_to_slack_messages(markdown):
    payload = {
        "blocks": blocks,
        "text": build_fallback_text_from_blocks(blocks) or "report",
    }
    print(payload)
```

## 公開 API

- `convert_markdown_to_slack_blocks(markdown_text: str) -> list[dict]`
- `convert_markdown_to_slack_messages(markdown_text: str) -> list[list[dict]]`
- `build_fallback_text_from_blocks(blocks: list[dict]) -> str`
- `blocks_to_plain_text(blocks: list[dict]) -> str`
- `normalize_markdown_tables(markdown_text: str) -> str`
- `add_zero_width_spaces_to_markdown(text: str) -> str`
- `decode_html_entities(text: str) -> str`
- `strip_zero_width_spaces(text: str) -> str`

## 仕様

- 挙動仕様: [docs/spec.md](docs/spec.md)

## 連絡先

- GitHub Issue / Pull Request
- X: [@darkgaldragon](https://x.com/darkgaldragon)

## ライセンス

MIT
