# slack-markdown-parser（日本語版）

LLM が生成した Markdown テキストを Slack Block Kit（`markdown` + `table`）に変換する Python ライブラリです。

英語版: [README.md](README.md)

## 何を解決するか（What / Why）

Slack の本番表示には次の制約があります。
- 1メッセージに `table` ブロックは1つまで
- 空セルがあると `invalid_blocks` になりやすい
- 太字/斜体/取り消し線の周辺でレンダリングが不安定になりうる

本ライブラリはこの差分を吸収し、Cloud Run / AWS Lambda / ローカルで同一挙動を提供します。

## 対応範囲

- Python: `3.10+`
- 実行環境: Cloud Run / AWS Lambda / ローカル
- 出力: Slack Block Kit（`markdown` / `table`）
- 非対応: `mrkdwn` 文字列生成モード

## インストール

### PyPI（推奨）

```bash
pip install slack-markdown-parser==2.*
```

### GitHub から

```bash
pip install git+https://github.com/darkgaldragon/slack-markdown-parser.git@v2.0.0
```

再現性のため、`@main` ではなくタグ（`@v2.0.0`）またはコミットSHA固定を推奨します。

### 開発用インストール

```bash
git clone https://github.com/darkgaldragon/slack-markdown-parser.git
cd slack-markdown-parser
pip install -e ".[dev]"
```

## クイックスタート（3分）

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
    raise RuntimeError("SLACK_BOT_TOKEN を設定してください。")
client = WebClient(token=token)

for blocks in convert_markdown_to_slack_messages(markdown):
    client.chat_postMessage(
        channel="C123456",
        blocks=blocks,
        text=build_fallback_text_from_blocks(blocks) or "report",
    )
```

## 公開API

### `convert_markdown_to_slack_blocks(markdown_text: str) -> list[dict]`
Markdown を1つの block 配列に変換。

### `convert_markdown_to_slack_messages(markdown_text: str) -> list[list[dict]]`
複数メッセージ配列に変換（テーブル制約に応じて分割）。

### `build_fallback_text_from_blocks(blocks: list[dict]) -> str`
`chat.postMessage.text` 用の fallback 文字列を生成。

### `blocks_to_plain_text(blocks: list[dict]) -> str`
Block配列を可読なプレーンテキストに平坦化。

### `normalize_markdown_tables(markdown_text: str) -> str`
テーブルのパイプ・セパレータ・列幅を正規化。

### `add_zero_width_spaces_to_markdown(text: str) -> str`
Markdown装飾の安定表示のために ZWSP を挿入（コード領域除外）。

### `decode_html_entities(text: str) -> str`
`&gt;` などのHTMLエンティティをデコード。

### `strip_zero_width_spaces(text: str) -> str`
挿入済み ZWSP を除去。

## API利用例

### 単一テーブル -> 1メッセージ

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

### 複数テーブル -> 自動分割

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
# table 制約を満たすよう自動分割される
```

### fallback 生成

```python
from slack_markdown_parser import (
    build_fallback_text_from_blocks,
    convert_markdown_to_slack_blocks,
)

blocks = convert_markdown_to_slack_blocks("# Title\n\n| Name | Score |\n|---|---|\n| Amy | 100 |")
fallback = build_fallback_text_from_blocks(blocks)
```

## 挙動仕様（要約）

対応:
- 見出し、リスト、引用、コードフェンス、インラインコード
- Markdown テーブル -> Slack `table` ブロック
- テーブルセル内装飾: 太字/斜体/取り消し線/コード

自動保護:
- テーブル正規化（外枠パイプ、セパレータ、列揃え）
- 空セルを `-` で補完
- 1メッセージ1テーブル分割
- 装飾記号周辺の安定化（ZWSP）

制約:
- テーブルセル内の複雑ネストMarkdownは簡略化される
- `mrkdwn` 出力モードは提供しない

詳細は [docs/spec.ja.md](docs/spec.ja.md) を参照してください。

## 既存BOTからの移行

既存の整形ヘルパーをこのパッケージ呼び出しに置き換えます。

### 置き換え前

```python
# lambda_function.py / handlers/slack.py にローカル実装
messages = convert_markdown_to_slack_messages(text)
for blocks in messages:
    fallback = blocks_to_plain_text(blocks)
```

### 置き換え後

```python
from slack_markdown_parser import (
    convert_markdown_to_slack_messages,
    blocks_to_plain_text,
)

messages = convert_markdown_to_slack_messages(text)
for blocks in messages:
    fallback = blocks_to_plain_text(blocks)
```

推奨手順:
1. `requirements.txt` に依存追加
2. 呼び出し箇所を置換
3. 固定入力の契約テストを追加
4. サービス間で block JSON の一致を確認

## 任意: AWS Lambda Layer

配布本線は PyPI です。Layer は AWS 向けの補助オプションです。

- [LAMBDA_INTEGRATION_GUIDE.ja.md](LAMBDA_INTEGRATION_GUIDE.ja.md)

## セキュリティと運用

- セキュリティポリシー: [SECURITY.ja.md](SECURITY.ja.md)
- リリース手順: [RELEASE.ja.md](RELEASE.ja.md)
- 貢献ガイド: [CONTRIBUTING.ja.md](CONTRIBUTING.ja.md)
- サポート窓口: [SUPPORT.ja.md](SUPPORT.ja.md)
- メンテナー告知/連絡先（X）: [`@darkgaldragon`](https://x.com/darkgaldragon)
- OSS公開前チェック: [docs/OSS_RELEASE_CHECKLIST.ja.md](docs/OSS_RELEASE_CHECKLIST.ja.md)

## ライセンス

MIT
