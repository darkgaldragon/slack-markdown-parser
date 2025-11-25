# Slack Markdown Parser

LLMが生成した純粋なMarkdownテキストをSlackの`markdown`ブロックと`table`ブロックに自動変換するPythonライブラリ

## 特徴

- ✅ 標準Markdown記法をSlackで表示可能に変換
- ✅ Markdownテーブルを自動検出してSlack tableブロックに変換
- ✅ 太字、斜体、取り消し線に自動的にゼロ幅スペースを挿入
- ✅ テーブルセル内のMarkdown装飾を自動解析
- ✅ 複数テーブルがある場合は自動的にメッセージを分割
- ✅ 依存関係なし（標準ライブラリのみ使用）

## インストール

### Lambda Layerとして使用する場合

```bash
# パッケージをビルド
cd slack-markdown-parser
pip install . -t python/
zip -r slack-markdown-parser-layer.zip python/

# AWS CLIでLayerを作成
aws lambda publish-layer-version \
    --layer-name slack-markdown-parser \
    --zip-file fileb://slack-markdown-parser-layer.zip \
    --compatible-runtimes python3.8 python3.9 python3.10 python3.11
```

### ローカル開発環境にインストール

```bash
pip install slack-markdown-parser
```

または、開発版をインストール：

```bash
git clone https://github.com/darkgaldragon/slack-markdown-parser.git
cd slack-markdown-parser
pip install -e .
```

## 使い方

### 基本的な使用方法

```python
from slack_markdown_parser import convert_markdown_to_slack_blocks

markdown_text = """
# プロジェクト進捗

これは**重要**な情報です。

| タスク | ステータス |
|--------|-----------|
| **API開発** | *進行中* |
| UI設計 | ~~保留~~ → *進行中* |
"""

# Slack blocksに変換
blocks = convert_markdown_to_slack_blocks(markdown_text)

# Slack APIで送信
from slack_sdk import WebClient
client = WebClient(token="YOUR_TOKEN")
client.chat_postMessage(
    channel="C06TB295SNA",
    blocks=blocks,
    text="プロジェクト進捗"
)
```

### 複数テーブルがある場合

```python
from slack_markdown_parser import convert_markdown_to_slack_messages

markdown_text = """
# レポート

## テーブル1
| A | B |
|---|---|
| 1 | 2 |

## テーブル2
| C | D |
|---|---|
| 3 | 4 |
"""

# 複数のメッセージに自動分割
messages = convert_markdown_to_slack_messages(markdown_text)

# 各メッセージを順番に送信
for i, blocks in enumerate(messages):
    client.chat_postMessage(
        channel="C06TB295SNA",
        blocks=blocks,
        text=f"レポート - Part {i+1}"
    )
```

### Lambda関数での使用例

```python
import json
from slack_markdown_parser import convert_markdown_to_slack_messages
from slack_sdk import WebClient

def lambda_handler(event, context):
    # LLMが生成したMarkdownテキスト
    markdown_text = event.get('markdown_text', '')
    
    # Slack blocksに変換
    messages = convert_markdown_to_slack_messages(markdown_text)
    
    # Slackに送信
    client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])
    channel_id = os.environ['SLACK_CHANNEL_ID']
    
    for blocks in messages:
        client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="LLM Response"
        )
    
    return {
        'statusCode': 200,
        'body': json.dumps({'messages_sent': len(messages)})
    }
```

## API リファレンス

### `convert_markdown_to_slack_blocks(markdown_text: str) -> List[Dict[str, Any]]`

Markdownテキストを1つのSlack blocks配列に変換します。

**引数:**
- `markdown_text` (str): 変換対象のMarkdownテキスト

**戻り値:**
- `List[Dict[str, Any]]`: Slack blocks配列

**注意:**
複数のテーブルが含まれる場合、Slackの制限によりエラーになる可能性があります。その場合は `convert_markdown_to_slack_messages()` を使用してください。

### `convert_markdown_to_slack_messages(markdown_text: str) -> List[List[Dict[str, Any]]]`

Markdownテキストを複数のSlackメッセージに変換します（複数テーブル対応）。

**引数:**
- `markdown_text` (str): 変換対象のMarkdownテキスト

**戻り値:**
- `List[List[Dict[str, Any]]]`: メッセージごとに分割されたblocks配列のリスト

### `add_zero_width_spaces(text: str) -> str`

Markdownの太字、斜体、取り消し線タグの前後にゼロ幅スペースを挿入します。

### `parse_markdown_table(table_text: str) -> List[List[str]]`

Markdownテーブルをパースして2次元配列に変換します。

### `markdown_table_to_slack_table(table_text: str) -> Dict[str, Any]`

Markdownテーブルをslack tableブロックに変換します。

## 対応しているMarkdown記法

### ✅ 対応

- **見出し**: `#`, `##`, `###`, etc.
- **太字**: `**text**` (ゼロ幅スペース自動挿入)
- **斜体**: `*text*` (ゼロ幅スペース自動挿入)
- **取り消し線**: `~~text~~` (ゼロ幅スペース自動挿入)
- **コード**: `` `code` ``
- **コードブロック**: ` ```code``` `
- **リスト**: `- item` または `1. item`
- **引用**: `> text`
- **リンク**: `[text](url)`
- **水平線**: `---`, `***`, `___`
- **テーブル**: `| A | B |` (tableブロックに変換)

### ❌ 非対応

- **脚注**: `[^1]`
- **HTMLエンティティ**: `&lt;`, `&gt;`

## 制限事項

1. **1メッセージに1つのtableブロックのみ**: Slackの制限により、1メッセージに複数のテーブルを含めることはできません。`convert_markdown_to_slack_messages()` が自動的にメッセージを分割します。

2. **ゼロ幅スペースの必要性**: 太字、斜体、取り消し線を正しく表示するには、タグの前後にゼロ幅スペース（U+200B）が必要です。このライブラリは自動的に挿入します。

3. **テーブルセル内の装飾**: 太字、斜体、取り消し線、コードに対応していますが、複雑なネストは非対応です。

## ライセンス

MIT License

## 作者

darkgaldragon（ぎゃうどら）

## 貢献

プルリクエストを歓迎します！バグ報告や機能リクエストは Issues でお願いします。
