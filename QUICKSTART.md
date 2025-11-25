# クイックスタートガイド

5分でLambdaに`slack-markdown-parser`を統合する

---

## 🚀 最速セットアップ（Lambda Layer使用）

### ステップ1: Layerをビルド（1分）

```bash
cd slack-markdown-parser
./build_lambda_layer.sh
```

✅ 出力: `slack-markdown-parser-layer.zip` (12KB)

### ステップ2: AWS Lambda Layerを作成（1分）

```bash
aws lambda publish-layer-version \
    --layer-name slack-markdown-parser \
    --zip-file fileb://slack-markdown-parser-layer.zip \
    --compatible-runtimes python3.11 \
    --region ap-northeast-1
```

📝 出力されたARNをメモ:
```
arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:1
```

### ステップ3: Lambda関数にアタッチ（30秒）

```bash
aws lambda update-function-configuration \
    --function-name your-lambda-function \
    --layers arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:1 \
    --region ap-northeast-1
```

### ステップ4: Lambda関数で使用（2分）

```python
# lambda_function.py
import json
import os
from slack_markdown_parser import convert_markdown_to_slack_messages
from slack_sdk import WebClient

def lambda_handler(event, context):
    # Markdownテキスト
    markdown = """
# 重要なお知らせ

これは**とても重要**な情報です。

| 項目 | ステータス |
|------|-----------|
| API開発 | *進行中* |
| UI設計 | ~~保留~~ → *進行中* |
"""
    
    # Slack blocksに変換
    messages = convert_markdown_to_slack_messages(markdown)
    
    # Slackに送信
    client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])
    for blocks in messages:
        client.chat_postMessage(
            channel=os.environ['SLACK_CHANNEL_ID'],
            blocks=blocks,
            text="Important Update"
        )
    
    return {'statusCode': 200}
```

### ステップ5: テスト（30秒）

```bash
aws lambda invoke \
    --function-name your-lambda-function \
    --payload '{}' \
    response.json
```

🎉 完了！Slackチャンネルでメッセージを確認してください。

---

## 📦 複数のLambda関数で使用

同じLayerを他のLambda関数にもアタッチするだけ：

```bash
# BOT 1
aws lambda update-function-configuration \
    --function-name slack-bot-1 \
    --layers arn:aws:lambda:REGION:ACCOUNT:layer:slack-markdown-parser:1

# BOT 2
aws lambda update-function-configuration \
    --function-name slack-bot-2 \
    --layers arn:aws:lambda:REGION:ACCOUNT:layer:slack-markdown-parser:1

# BOT 3
aws lambda update-function-configuration \
    --function-name slack-bot-3 \
    --layers arn:aws:lambda:REGION:ACCOUNT:layer:slack-markdown-parser:1
```

すべてのBOTで共通のライブラリが使えます！

---

## 🔄 ライブラリの更新

新しいバージョンをデプロイ：

```bash
# 1. 新しいLayerをビルド
./build_lambda_layer.sh

# 2. 新しいバージョンを公開
aws lambda publish-layer-version \
    --layer-name slack-markdown-parser \
    --zip-file fileb://slack-markdown-parser-layer.zip \
    --compatible-runtimes python3.11

# 3. Lambda関数を更新（バージョン番号を変更）
aws lambda update-function-configuration \
    --function-name your-lambda-function \
    --layers arn:aws:lambda:REGION:ACCOUNT:layer:slack-markdown-parser:2
```

---

## 💡 使用例

### 例1: LLM応答をSlackに投稿

```python
from slack_markdown_parser import convert_markdown_to_slack_messages

def lambda_handler(event, context):
    # LLMから取得したMarkdown
    llm_response = call_llm(event['prompt'])
    
    # Slack blocksに変換
    messages = convert_markdown_to_slack_messages(llm_response)
    
    # 送信
    send_to_slack(messages)
```

### 例2: レポート生成

```python
from slack_markdown_parser import convert_markdown_to_slack_blocks

def lambda_handler(event, context):
    # Markdownレポートを生成
    report = f"""
# 日次レポート

## メトリクス
- ユーザー数: **{user_count}**
- 売上: **¥{revenue:,}**

## ステータス
{generate_status_table()}
"""
    
    blocks = convert_markdown_to_slack_blocks(report)
    send_to_slack(blocks)
```

---

## 🛠️ トラブルシューティング

### インポートエラー

```python
ModuleNotFoundError: No module named 'slack_markdown_parser'
```

**解決策**: Lambda関数にLayerがアタッチされているか確認

```bash
aws lambda get-function-configuration --function-name your-function
```

### Layerが見つからない

**解決策**: Layerが正しいリージョンに作成されているか確認

```bash
aws lambda list-layers --region ap-northeast-1
```

---

## 📚 詳細ドキュメント

- [README.md](README.md) - 基本的な使い方
- [LAMBDA_INTEGRATION_GUIDE.md](LAMBDA_INTEGRATION_GUIDE.md) - 詳細な統合方法
- [完全マニュアル](slack_markdown_complete_manual.md) - Markdown記法の詳細

---

**所要時間**: 5分  
**難易度**: ⭐ (初心者向け)  
**前提条件**: AWS CLI設定済み、Slack Bot Token取得済み
