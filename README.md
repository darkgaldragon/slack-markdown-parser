# slack-markdown-parser

Convert LLM-generated Markdown into Slack Block Kit messages (`markdown` + `table` blocks).

日本語: LLMのMarkdown出力をSlack向けBlock Kit (`markdown` / `table`) に安全変換するPythonライブラリです。
Japanese docs: [README.ja.md](README.ja.md)

## What / Why

Slack rendering is strict in production:
- only one `table` block per message
- empty table cells can trigger `invalid_blocks`
- markdown decorations can become unstable without zero-width-space padding

This package standardizes those edge cases into one reusable converter so Cloud Run, AWS Lambda, and local workers can use the same behavior.

日本語: Slack固有の制約（1メッセージ1テーブル、空セル、装飾崩れ）を吸収して共通化します。

## Compatibility

- Python: `3.10+`
- Runtime: Cloud Run / AWS Lambda / local scripts
- Output: **Slack Block Kit only** (`markdown` and `table` blocks)
- Not included: `mrkdwn` string generator

## Installation

### PyPI (recommended)

```bash
pip install slack-markdown-parser==2.*
```

### From GitHub

```bash
pip install git+https://github.com/darkgaldragon/slack-markdown-parser.git@v2.0.0
```

For reproducibility, prefer a tag (`@v2.0.0`) or commit SHA over `@main`.

### Dev install

```bash
git clone https://github.com/darkgaldragon/slack-markdown-parser.git
cd slack-markdown-parser
pip install -e ".[dev]"
```

## Quick Start (3 minutes)

```python
import os

from slack_markdown_parser import (
    convert_markdown_to_slack_messages,
    build_fallback_text_from_blocks,
)
from slack_sdk import WebClient

markdown = """
# Weekly Report

| Team | Status |
|---|---|
| API | **On track** |
| UI | *In progress* |
"""

token = os.getenv("SLACK_BOT_TOKEN")
if not token:
    raise RuntimeError("Set SLACK_BOT_TOKEN before running this example.")
client = WebClient(token=token)

for blocks in convert_markdown_to_slack_messages(markdown):
    client.chat_postMessage(
        channel="C123456",
        blocks=blocks,
        text=build_fallback_text_from_blocks(blocks) or "report",
    )
```

## API

### `convert_markdown_to_slack_blocks(markdown_text: str) -> list[dict]`
Convert markdown text into one block array.

### `convert_markdown_to_slack_messages(markdown_text: str) -> list[list[dict]]`
Convert markdown text into multiple message payloads (automatically split for table constraints).

### `build_fallback_text_from_blocks(blocks: list[dict]) -> str`
Build plain fallback text from blocks (recommended for `chat_postMessage.text`).

### `blocks_to_plain_text(blocks: list[dict]) -> str`
Flatten block contents into readable plain text.

### `normalize_markdown_tables(markdown_text: str) -> str`
Normalize table pipes/separators and column width before conversion.

### `add_zero_width_spaces_to_markdown(text: str) -> str`
Insert zero-width-space around markdown decorations while preserving code sections.

### `decode_html_entities(text: str) -> str`
Decode entities like `&gt;` before parsing.

### `strip_zero_width_spaces(text: str) -> str`
Remove inserted ZWSP characters for fallback/plain output.

## API Examples

### Single table -> one message payload

```python
from slack_markdown_parser import convert_markdown_to_slack_messages

md = """
| Name | Score |
|---|---|
| Amy | 100 |
"""

messages = convert_markdown_to_slack_messages(md)
assert len(messages) == 1
assert messages[0][0]["type"] == "table"
```

### Multiple tables -> split messages (one table per message)

```python
from slack_markdown_parser import convert_markdown_to_slack_messages

md = """
# Report
| A | B |
|---|---|
| 1 | 2 |

text between tables

| C | D |
|---|---|
| 3 | 4 |
"""

messages = convert_markdown_to_slack_messages(md)
# table messages are automatically split to satisfy Slack constraints
```

### Build fallback text from blocks

```python
from slack_markdown_parser import (
    build_fallback_text_from_blocks,
    convert_markdown_to_slack_blocks,
)

blocks = convert_markdown_to_slack_blocks("# Title\n\n| Name | Score |\n|---|---|\n| Amy | 100 |")
fallback = build_fallback_text_from_blocks(blocks)
```

## Behavior Spec (summary)

Supported:
- headings, lists, quotes, code fences, inline code
- markdown tables -> Slack `table` blocks
- style in table cells: bold/italic/strike/code

Automatic safeguards:
- table normalization (outer pipes, separator row, column alignment)
- empty table cell replacement with `-`
- one-table-per-message split
- stable markdown decoration padding

Limitations:
- complex nested markdown in table cells is simplified
- `mrkdwn` output mode is intentionally not provided

See full details in [docs/spec.md](docs/spec.md).

Additional public docs index: [docs/README.md](docs/README.md).

## Migration Guide (existing bots)

If your bot currently has local formatting helpers, replace them with this package.

### Before

```python
# local implementations in lambda_function.py / handlers/slack.py
messages = convert_markdown_to_slack_messages(text)
for blocks in messages:
    fallback = blocks_to_plain_text(blocks)
```

### After

```python
from slack_markdown_parser import (
    convert_markdown_to_slack_messages,
    blocks_to_plain_text,
)

messages = convert_markdown_to_slack_messages(text)
for blocks in messages:
    fallback = blocks_to_plain_text(blocks)
```

Recommended rollout:
1. add dependency in `requirements.txt`
2. replace call sites
3. add contract tests with fixed markdown inputs
4. compare produced block JSON across services

## Optional: AWS Lambda Layer

PyPI is the primary distribution. Layer is optional for AWS-only setups.

See [LAMBDA_INTEGRATION_GUIDE.md](LAMBDA_INTEGRATION_GUIDE.md).

## Security and Operations

- Security policy: [SECURITY.md](SECURITY.md)
- Release process: [RELEASE.md](RELEASE.md)
- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Support channels: [SUPPORT.md](SUPPORT.md)
- Maintainer updates/contact on X: [`@darkgaldragon`](https://x.com/darkgaldragon)
- Public-share checklist (GitHub beginners): [docs/OSS_RELEASE_CHECKLIST.md](docs/OSS_RELEASE_CHECKLIST.md)

## License

MIT
