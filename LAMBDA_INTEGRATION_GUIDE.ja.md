# AWS Lambda 統合ガイド（任意）

配布の本線は PyPI です。このガイドは AWS 向けの補助手段を説明します。

## Option A（推奨）: PyPI をデプロイパッケージに直接同梱

```bash
pip install slack-markdown-parser==2.0.0 -t .
zip -r lambda_function.zip .
```

利点:
- Cloud Run / local と同じ導入フローで統一できる
- Layer のライフサイクル管理が不要

## Option B: Lambda Layer（任意）

### 1) Layer アーティファクトを作る

```bash
./build_lambda_layer.sh
```

### 2) 公開する

```bash
aws lambda publish-layer-version \
  --layer-name slack-markdown-parser \
  --description "slack-markdown-parser v2.0.0" \
  --zip-file fileb://slack-markdown-parser-layer.zip \
  --compatible-runtimes python3.10 python3.11 python3.12
```

### 3) Lambda にアタッチする

```bash
aws lambda update-function-configuration \
  --function-name YOUR_FUNCTION \
  --layers arn:aws:lambda:REGION:ACCOUNT:layer:slack-markdown-parser:VERSION
```

## 使用例

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

## 運用メモ

- Layer は AWS 固有の任意オプションです。
- 本番ではパッケージバージョン固定を推奨します。
- Cloud Run と Lambda で同一の契約テストを回し、差分を防止してください。
