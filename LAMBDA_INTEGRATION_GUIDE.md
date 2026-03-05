# AWS Lambda Integration Guide (Optional)

Primary distribution is PyPI. This guide describes AWS-specific options.

日本語: 本線はPyPI配布です。LayerはAWS向けの補助手段です。

## Option A (recommended): install from PyPI into deployment package

```bash
pip install slack-markdown-parser==2.0.0 -t .
zip -r lambda_function.zip .
```

Pros:
- same install flow as Cloud Run/local
- no layer lifecycle management

## Option B: Lambda Layer (optional)

### 1) Build layer artifact

```bash
./build_lambda_layer.sh
```

### 2) Publish

```bash
aws lambda publish-layer-version \
  --layer-name slack-markdown-parser \
  --description "slack-markdown-parser v2.0.0" \
  --zip-file fileb://slack-markdown-parser-layer.zip \
  --compatible-runtimes python3.10 python3.11 python3.12
```

### 3) Attach to Lambda

```bash
aws lambda update-function-configuration \
  --function-name YOUR_FUNCTION \
  --layers arn:aws:lambda:REGION:ACCOUNT:layer:slack-markdown-parser:VERSION
```

## Usage Example

```python
from slack_markdown_parser import (
    convert_markdown_to_slack_messages,
    build_fallback_text_from_blocks,
)

payloads = convert_markdown_to_slack_messages(markdown_text)
for blocks in payloads:
    fallback = build_fallback_text_from_blocks(blocks) or "message"
    slack_client.chat_postMessage(channel=channel, text=fallback, blocks=blocks)
```

## Operational Notes

- Layer is optional and AWS-specific.
- Keep package version pinned in production.
- Run the same contract tests across Cloud Run and Lambda to avoid drift.
