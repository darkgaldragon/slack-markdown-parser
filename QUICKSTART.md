# Quick Start

Get production-safe Slack Block Kit conversion in minutes.

日本語: 最短で導入する手順です。

## 1. Install

```bash
pip install slack-markdown-parser==2.*
```

## 2. Convert markdown to Slack messages

```python
from slack_markdown_parser import (
    convert_markdown_to_slack_messages,
    build_fallback_text_from_blocks,
)

markdown = """
# Notice

| Item | Value |
|---|---|
| Status | **OK** |
"""

payloads = convert_markdown_to_slack_messages(markdown)
for blocks in payloads:
    fallback = build_fallback_text_from_blocks(blocks) or "message"
    # slack_client.chat_postMessage(channel=..., text=fallback, blocks=blocks)
```

## 3. Validate quickly

```bash
python - <<'PY'
from slack_markdown_parser import convert_markdown_to_slack_messages
print(convert_markdown_to_slack_messages("|A|B|\n|---|---|\n|1|2|"))
PY
```

## Runtime Notes

- Cloud Run: install from PyPI in `requirements.txt`
- AWS Lambda: same PyPI path is recommended; Layer is optional
- Local scripts: direct import works without extra runtime dependencies

## Next

- Full docs: [README.md](README.md)
- Spec details: [docs/spec.md](docs/spec.md)
- AWS optional layer: [LAMBDA_INTEGRATION_GUIDE.md](LAMBDA_INTEGRATION_GUIDE.md)
