# Slack Markdown & Table Block 完全マニュアル

LLMが生成した純粋なMarkdownテキストをSlackで正しく表示するための完全ガイド

---

## 📋 目次

1. [概要](#概要)
2. [markdownブロックの仕様](#markdownブロックの仕様)
3. [tableブロックの仕様](#tableブロックの仕様)
4. [自動変換ロジック](#自動変換ロジック)
5. [実装例](#実装例)
6. [制限事項と注意点](#制限事項と注意点)

---

## 概要

Slackの新しい`markdown`ブロックと`table`ブロックを使用することで、標準的なMarkdown記法をSlack上で表現できます。

### 主要な発見

- **markdownブロック**: 標準Markdown記法を使用可能だが、太字・斜体・取り消し線には**ゼロ幅スペース（U+200B）**が必要
- **tableブロック**: Markdownテーブルを表構造で表示可能、セル内でrich_text装飾が使用可能
- **制限**: 1メッセージに1つのtableブロックのみ許可

---

## markdownブロックの仕様

### ✅ 対応している記法

#### 基本的な文字修飾（ゼロ幅スペース必須）

| 記法 | Markdown | 正しい書き方 | 間違った書き方 |
|------|----------|------------|--------------|
| 太字 | `**text**` | `これは{ZWSP}**重要**{ZWSP}です` | `これは**重要**です` |
| 斜体 | `*text*` | `これは{ZWSP}*参考*{ZWSP}です` | `これは*参考*です` |
| 取り消し線 | `~~text~~` | `これは{ZWSP}~~削除~~{ZWSP}です` | `これは~~削除~~です` |

**重要**: `{ZWSP}` は `\u200b`（ゼロ幅スペース）を表します。

#### その他の記法（スペース不要）

- **見出し**: `#`, `##`, `###`, `####`, `#####`, `######`
- **リスト**: 
  - 箇条書き: `- item` または `* item`
  - 番号付き: `1. item`
  - ネスト対応（インデントで表現）
- **タスクリスト**: `- [ ]` と `- [x]`
- **引用**: `> text`（複数行対応、書式適用可能）
- **インラインコード**: `` `code` ``
- **コードブロック**: ` ```language\ncode\n``` `（言語指定によるハイライトは非対応）
- **リンク**: `[text](url)`
- **水平線**: `---`, `***`, `___`
- **絵文字**: `:emoji_name:`

### ❌ 非対応の記法

- **テーブル**: Markdownテーブル記法は表示されない（tableブロックを使用）
- **脚注**: `[^1]` 形式の脚注
- **HTMLエンティティ**: `&lt;`, `&gt;` など

### ⚠️ 制限付き対応

- **ネストした書式**: 2階層までは可能、3つ以上の複雑な組み合わせは非対応

---

## tableブロックの仕様

### 基本構造

```json
{
  "type": "table",
  "rows": [
    [
      {
        "type": "rich_text",
        "elements": [
          {
            "type": "rich_text_section",
            "elements": [
              {
                "type": "text",
                "text": "セルの内容",
                "style": {
                  "bold": true,
                  "italic": true,
                  "code": true,
                  "strike": true
                }
              }
            ]
          }
        ]
      }
    ]
  ]
}
```

### ✅ 対応している機能

#### セル全体の装飾

| 装飾 | style属性 | 説明 |
|------|-----------|----- |
| 太字 | `"bold": true` | テキストを太字にする |
| 斜体 | `"italic": true` | テキストを斜体にする |
| コード | `"code": true` | テキストをコードスタイルで表示 |
| 取り消し線 | `"strike": true` | テキストに取り消し線を適用 |

#### セル内の一部の文字のみ装飾

セル内で一部の文字だけに装飾を適用する場合は、`elements`配列に複数のテキスト要素を含めます。

**Markdown入力例**:
```markdown
| 項目 | 説明 |
|------|------|
| API | これは**重要**な項目です |
```

**変換後JSON構造**:
```json
{
  "type": "rich_text",
  "elements": [
    {
      "type": "rich_text_section",
      "elements": [
        {
          "type": "text",
          "text": "これは"
        },
        {
          "type": "text",
          "text": "重要",
          "style": {"bold": true}
        },
        {
          "type": "text",
          "text": "な項目です"
        }
      ]
    }
  ]
}
```

**表示結果**: 「これは**重要**な項目です」→ 「これは重要な項目です」（「重要」のみ太字）

**複数の装飾を混在させる例**:
```markdown
| ステータス |
|---------|
| ~~保留~~ → *進行中* |
```

この場合、`elements`には3つの要素が含まれます：
1. 「保留」（取り消し線）
2. 「 → 」（装飾なし）
3. 「進行中」（斜体）

#### 組み合わせ

複数のスタイルを同時に適用可能：

```json
{
  "type": "text",
  "text": "太字+取り消し線",
  "style": {
    "bold": true,
    "strike": true
  }
}
```

#### サイズ制限

- **最大行数**: 20行以上でもテスト成功（実用上の制限は不明）
- **最大列数**: 10列以上でもテスト成功（実用上の制限は不明）
- **長文**: セル内で自動的に折り返される
- **複数行**: 改行（`\n`）を含むテキストも表示可能

### ❌ 非対応の機能

- **セルの結合**: colspan/rowspanは非対応
- **整列指定**: Markdownの`:---:`などの整列指定は無視される
- **背景色・文字色**: カスタムカラーは非対応

### ⚠️ 重要な制限

**1メッセージに1つのtableブロックのみ許可**

複数のテーブルを送信する場合は、メッセージを分割する必要があります。

エラー例：
```json
{
  "ok": false,
  "error": "invalid_blocks",
  "errors": ["only_one_table_allowed"]
}
```

---

## 自動変換ロジック

### 処理フロー

```
Markdownテキスト
    ↓
1. テーブル検出（正規表現: `\|.+\|` で始まる複数行）
    ↓
2. テキスト分割（テーブル部分とそれ以外）
    ↓
3. 各部分を変換
   - テーブル → tableブロック
   - その他 → markdownブロック（ゼロ幅スペース挿入）
    ↓
4. メッセージ分割（1メッセージに1テーブル）
    ↓
複数のSlackメッセージ
```

### ゼロ幅スペース挿入ロジック

```python
ZWSP = "\u200b"

def add_zero_width_spaces(text: str) -> str:
    # 太字: **text** -> {ZWSP}**text**{ZWSP}
    text = re.sub(r'(\*\*[^*]+\*\*)', f'{ZWSP}\\1{ZWSP}', text)
    
    # 斜体: *text* -> {ZWSP}*text*{ZWSP}
    text = re.sub(r'(?<!\*)(\*[^*]+\*)(?!\*)', f'{ZWSP}\\1{ZWSP}', text)
    
    # 取り消し線: ~~text~~ -> {ZWSP}~~text~~{ZWSP}
    text = re.sub(r'(~~[^~]+~~)', f'{ZWSP}\\1{ZWSP}', text)
    
    # 連続したゼロ幅スペースを1つにまとめる
    text = re.sub(f'{ZWSP}+', ZWSP, text)
    
    return text
```

### セル内の一部装飾の実装例

**入力**: `"これは**重要**な項目です"`

**処理フロー**:
1. 正規表現で`**重要**`を検出
2. 前後のテキストを分割
3. 各部分を個別の`text`要素として生成

```python
def create_table_cell(text: str) -> Dict[str, Any]:
    elements = []
    remaining = text
    
    # 太字パターンを検出
    bold_pattern = r'\*\*([^*]+)\*\*'
    bold_match = re.search(bold_pattern, remaining)
    
    if bold_match:
        # 太字の前のテキスト
        before = remaining[:bold_match.start()]
        if before:
            elements.append({"type": "text", "text": before})
        
        # 太字部分
        elements.append({
            "type": "text",
            "text": bold_match.group(1),
            "style": {"bold": True}
        })
        
        # 太字の後のテキスト
        after = remaining[bold_match.end():]
        if after:
            elements.append({"type": "text", "text": after})
    else:
        # 装飾なし
        elements.append({"type": "text", "text": text})
    
    return {
        "type": "rich_text",
        "elements": [{"type": "rich_text_section", "elements": elements}]
    }
```

### Markdownテーブル検出ロジック

```python
# テーブルパターン（複数行の | で始まる行）
table_pattern = r'(\|.+\|[\r\n]+(?:\|.+\|[\r\n]*)+)'

# テキストを分割
parts = re.split(table_pattern, markdown_text)

for part in parts:
    if re.match(r'^\|.+\|', part.strip()):
        # テーブルとして処理
        table_block = markdown_table_to_slack_table(part)
    else:
        # 通常のMarkdownとして処理
        markdown_block = create_markdown_block(part)
```

### テーブルセル内のMarkdown解析

```python
def create_table_cell(text: str) -> Dict[str, Any]:
    # 優先順位: コード > 取り消し線 > 太字 > 斜体
    
    # 1. コード: `text`
    if code_match := re.search(r'`([^`]+)`', text):
        return {"style": {"code": True}, "text": code_match.group(1)}
    
    # 2. 取り消し線: ~~text~~
    if strike_match := re.search(r'~~([^~]+)~~', text):
        return {"style": {"strike": True}, "text": strike_match.group(1)}
    
    # 3. 太字: **text**
    if bold_match := re.search(r'\*\*([^*]+)\*\*', text):
        return {"style": {"bold": True}, "text": bold_match.group(1)}
    
    # 4. 斜体: *text*
    if italic_match := re.search(r'\*([^*]+)\*', text):
        return {"style": {"italic": True}, "text": italic_match.group(1)}
    
    # 装飾なし
    return {"text": text}
```

### メッセージ分割ロジック

```python
def split_blocks_by_table(blocks: List[Dict]) -> List[List[Dict]]:
    messages = []
    current_message = []
    
    for block in blocks:
        if block["type"] == "table":
            # 既存のメッセージを保存
            if current_message:
                messages.append(current_message)
            # テーブル単独で1メッセージ
            messages.append([block])
            current_message = []
        else:
            current_message.append(block)
    
    # 最後のメッセージを保存
    if current_message:
        messages.append(current_message)
    
    return messages
```

---

## 実装例

### Python + Slack Bolt

```python
from slack_sdk import WebClient
from markdown_converter_final import convert_markdown_to_slack_messages

# Slack WebClientの初期化
client = WebClient(token="YOUR_SLACK_BOT_TOKEN")
CHANNEL_ID = "C06TB295SNA"

# LLMが生成したMarkdownテキスト
markdown_text = """
# プロジェクト進捗報告

## タスク一覧

| タスク | 担当者 | ステータス |
|--------|--------|------------|
| **API開発** | 太郎 | *進行中* |
| **UI設計** | 花子 | ~~保留~~ → *進行中* |
| `テスト` | 次郎 | **完了** |

次回ミーティングは**来週月曜日**です。
"""

# Markdownを複数のSlackメッセージに変換
messages = convert_markdown_to_slack_messages(markdown_text)

# 各メッセージを順番に送信
for i, blocks in enumerate(messages):
    response = client.chat_postMessage(
        channel=CHANNEL_ID,
        blocks=blocks,
        text=f"メッセージ {i+1}"  # フォールバックテキスト
    )
    print(f"メッセージ {i+1} 送信完了: {response['ts']}")
```

### リクエスト構造

#### markdownブロックのリクエスト

```json
{
  "channel": "C06TB295SNA",
  "blocks": [
    {
      "type": "markdown",
      "text": "これは\u200b**重要**\u200bな情報です。"
    }
  ],
  "text": "重要な情報があります。"
}
```

#### tableブロックのリクエスト

```json
{
  "channel": "C06TB295SNA",
  "blocks": [
    {
      "type": "table",
      "rows": [
        [
          {
            "type": "rich_text",
            "elements": [
              {
                "type": "rich_text_section",
                "elements": [
                  {
                    "type": "text",
                    "text": "項目",
                    "style": {"bold": true}
                  }
                ]
              }
            ]
          },
          {
            "type": "rich_text",
            "elements": [
              {
                "type": "rich_text_section",
                "elements": [
                  {
                    "type": "text",
                    "text": "説明"
                  }
                ]
              }
            ]
          }
        ]
      ]
    }
  ],
  "text": "テーブルがあります。"
}
```

---

## 制限事項と注意点

### 1. ゼロ幅スペースの必要性

**問題**: 通常の半角スペースを使用すると、表示上もスペースが残る

```markdown
これは **太字** です。  # スペースが見える
```

**解決**: ゼロ幅スペース（`\u200b`）を使用

```python
ZWSP = "\u200b"
text = f"これは{ZWSP}**太字**{ZWSP}です。"  # スペースが見えない
```

### 2. テーブル数の制限

**問題**: 1メッセージに複数のtableブロックを含めるとエラー

```json
{
  "error": "invalid_blocks",
  "errors": ["only_one_table_allowed"]
}
```

**解決**: メッセージを分割して送信

### 3. Markdownテーブルの非対応

**問題**: markdownブロックではMarkdownテーブルが表として表示されない

**解決**: テーブルを検出してtableブロックに変換

### 4. セパレーター行の処理

**問題**: Markdownテーブルのセパレーター行（`|-----|-----|`）も行として認識される

**解決**: 正規表現で除外

```python
if re.match(r'^\s*\|[\s\-:|]+\|\s*$', line):
    continue  # セパレーター行をスキップ
```

### 5. 装飾の優先順位

テーブルセル内で複数の装飾が競合する場合の優先順位：

1. コード（`` `text` ``）
2. 取り消し線（`~~text~~`）
3. 太字（`**text**`）
4. 斜体（`*text*`）

### 6. エッジケース

- **空のセル**: 空文字列として処理
- **パイプ文字**: セル内の `|` はエスケープ不要（テーブル構造が正しければ問題なし）
- **改行**: セル内の `\n` は改行として表示される

---

## まとめ

### ベストプラクティス

1. **太字、斜体、取り消し線には必ずゼロ幅スペース（`\u200b`）を前後に挿入**
2. **Markdownテーブルを検出してtableブロックに変換**
3. **複数テーブルがある場合はメッセージを分割**
4. **テーブルセル内のMarkdown装飾を自動解析**
5. **セパレーター行を除外**

### 対応表

| 機能 | markdownブロック | tableブロック |
|------|-----------------|--------------|
| 見出し | ✅ | ❌ |
| 太字 | ✅（ZWSP必須） | ✅ |
| 斜体 | ✅（ZWSP必須） | ✅ |
| 取り消し線 | ✅（ZWSP必須） | ✅ |
| コード | ✅ | ✅ |
| リスト | ✅ | ❌ |
| 引用 | ✅ | ❌ |
| リンク | ✅ | ❌ |
| テーブル | ❌ | ✅ |
| 絵文字 | ✅ | ✅ |

---

## 参考資料

- [Slack Block Kit - Markdown Block](https://docs.slack.dev/reference/block-kit/blocks/markdown-block/)
- [Slack Block Kit - Table Block](https://api.slack.com/reference/block-kit/blocks#table)
- [Slack Web API - chat.postMessage](https://api.slack.com/methods/chat.postMessage)

---

**作成日**: 2025年11月25日  
**バージョン**: 1.0  
**検証環境**: Slack Web API, Python 3.11, slack-sdk
