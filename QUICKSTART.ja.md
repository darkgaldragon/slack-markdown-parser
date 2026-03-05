# クイックスタート

数分で本番向けの Slack Block Kit 変換を導入できます。

## 1. インストール

```bash
pip install slack-markdown-parser==2.*
```

## 2. Markdown を Slack メッセージに変換

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

## 3. すぐ確認する

```bash
python - <<'PY'
from slack_markdown_parser import convert_markdown_to_slack_messages
print(convert_markdown_to_slack_messages("|A|B|\n|---|---|\n|1|2|"))
PY
```

## 実行環境メモ

- Cloud Run: `requirements.txt` で PyPI からインストール
- AWS Lambda: 同じく PyPI 同梱推奨（Layer は任意）
- ローカルスクリプト: 追加ランタイム依存なしで import 可能

## 次に読む

- 全体ドキュメント: [README.ja.md](README.ja.md)
- 仕様詳細: [docs/spec.ja.md](docs/spec.ja.md)
- Lambda 補助手順: [LAMBDA_INTEGRATION_GUIDE.ja.md](LAMBDA_INTEGRATION_GUIDE.ja.md)
