# Lambda統合ガイド

複数のLambda関数から`slack-markdown-parser`を共通利用する方法

---

## 📋 目次

1. [概要](#概要)
2. [方法1: Lambda Layer（推奨）](#方法1-lambda-layer推奨)
3. [方法2: 各Lambdaにデプロイ](#方法2-各lambdaにデプロイ)
4. [方法3: PyPI公開](#方法3-pypi公開)
5. [方法4: AWS CodeArtifact](#方法4-aws-codeartifact)
6. [使用例](#使用例)

---

## 概要

`slack-markdown-parser`は標準ライブラリのみを使用しているため、依存関係の管理が不要で、Lambda環境に簡単に統合できます。

### 推奨方法の比較

| 方法 | メリット | デメリット | 推奨度 |
|------|---------|-----------|--------|
| Lambda Layer | 一度デプロイすれば全Lambda共通利用可能 | Layer管理が必要 | ⭐⭐⭐⭐⭐ |
| 各Lambdaにデプロイ | シンプル | 更新時に全Lambda再デプロイ必要 | ⭐⭐⭐ |
| PyPI公開 | pip installで簡単 | 公開リポジトリ必要 | ⭐⭐⭐⭐ |
| CodeArtifact | プライベート管理可能 | AWS追加コスト | ⭐⭐⭐⭐ |

---

## 方法1: Lambda Layer（推奨）

### 特徴

- ✅ 一度デプロイすれば複数のLambda関数で共通利用可能
- ✅ Lambda関数のデプロイパッケージサイズを削減
- ✅ ライブラリの更新が容易（Layerのみ更新）
- ✅ バージョン管理が可能

### 手順

#### 1. Lambda Layerをビルド

```bash
cd slack-markdown-parser
./build_lambda_layer.sh
```

出力: `slack-markdown-parser-layer.zip` (約12KB)

#### 2. AWS Lambda Layerを作成

**AWS CLI使用:**

```bash
aws lambda publish-layer-version \
    --layer-name slack-markdown-parser \
    --description "Slack Markdown Parser v1.0.0" \
    --zip-file fileb://slack-markdown-parser-layer.zip \
    --compatible-runtimes python3.8 python3.9 python3.10 python3.11 \
    --region ap-northeast-1
```

**出力例:**

```json
{
    "LayerArn": "arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser",
    "LayerVersionArn": "arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:1",
    "Version": 1
}
```

**AWS Console使用:**

1. Lambda コンソールを開く
2. 左メニューから「レイヤー」を選択
3. 「レイヤーの作成」をクリック
4. 名前: `slack-markdown-parser`
5. ZIPファイルをアップロード: `slack-markdown-parser-layer.zip`
6. 互換性のあるランタイム: Python 3.8, 3.9, 3.10, 3.11 を選択
7. 「作成」をクリック

#### 3. Lambda関数にLayerをアタッチ

**AWS CLI使用:**

```bash
aws lambda update-function-configuration \
    --function-name your-lambda-function-name \
    --layers arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:1 \
    --region ap-northeast-1
```

**AWS Console使用:**

1. Lambda関数を開く
2. 「レイヤー」セクションまでスクロール
3. 「レイヤーの追加」をクリック
4. 「カスタムレイヤー」を選択
5. `slack-markdown-parser` を選択
6. バージョンを選択
7. 「追加」をクリック

#### 4. Lambda関数で使用

```python
# Lambda関数のコード (lambda_function.py)
import json
import os
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
    
    for i, blocks in enumerate(messages):
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Message {i+1}"
        )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'messages_sent': len(messages)
        })
    }
```

#### 5. 複数のLambda関数で使用

同じLayerを複数のLambda関数にアタッチするだけで、すべての関数で使用可能になります。

```bash
# Lambda関数1
aws lambda update-function-configuration \
    --function-name slack-bot-1 \
    --layers arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:1

# Lambda関数2
aws lambda update-function-configuration \
    --function-name slack-bot-2 \
    --layers arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:1

# Lambda関数3
aws lambda update-function-configuration \
    --function-name slack-bot-3 \
    --layers arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:1
```

#### 6. ライブラリの更新

ライブラリを更新する場合：

1. 新しいバージョンをビルド
2. 新しいLayerバージョンを公開
3. Lambda関数のLayer参照を更新

```bash
# 新しいLayerバージョンを公開
aws lambda publish-layer-version \
    --layer-name slack-markdown-parser \
    --description "Slack Markdown Parser v1.1.0" \
    --zip-file fileb://slack-markdown-parser-layer.zip \
    --compatible-runtimes python3.8 python3.9 python3.10 python3.11

# Lambda関数を更新（バージョン2に）
aws lambda update-function-configuration \
    --function-name your-lambda-function-name \
    --layers arn:aws:lambda:ap-northeast-1:123456789012:layer:slack-markdown-parser:2
```

---

## 方法2: 各Lambdaにデプロイ

### 特徴

- ✅ シンプルで理解しやすい
- ✅ Layer管理不要
- ❌ 各Lambda関数のデプロイパッケージサイズが増加
- ❌ 更新時に全Lambda関数を再デプロイ必要

### 手順

#### 1. デプロイパッケージに含める

```bash
# Lambda関数のディレクトリに移動
cd your-lambda-function/

# ライブラリをインストール
pip install /path/to/slack-markdown-parser -t .

# デプロイパッケージを作成
zip -r lambda-function.zip .

# Lambdaにデプロイ
aws lambda update-function-code \
    --function-name your-lambda-function-name \
    --zip-file fileb://lambda-function.zip
```

#### 2. SAM/Serverless Frameworkを使用する場合

**SAM template.yaml:**

```yaml
Resources:
  YourFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      Environment:
        Variables:
          SLACK_BOT_TOKEN: !Ref SlackBotToken
      
# requirements.txt に追加
# slack-markdown-parser @ file:///path/to/slack-markdown-parser
```

**Serverless Framework serverless.yml:**

```yaml
functions:
  yourFunction:
    handler: lambda_function.lambda_handler
    runtime: python3.11
    environment:
      SLACK_BOT_TOKEN: ${env:SLACK_BOT_TOKEN}

plugins:
  - serverless-python-requirements

custom:
  pythonRequirements:
    dockerizePip: true
```

---

## 方法3: PyPI公開

### 特徴

- ✅ `pip install`で簡単にインストール可能
- ✅ バージョン管理が容易
- ❌ 公開リポジトリが必要（プライベート利用には不向き）

### 手順

#### 1. PyPIアカウントを作成

https://pypi.org/account/register/

#### 2. パッケージをビルド

```bash
cd slack-markdown-parser

# ビルドツールをインストール
pip install build twine

# パッケージをビルド
python -m build
```

#### 3. PyPIにアップロード

```bash
# TestPyPIにアップロード（テスト用）
python -m twine upload --repository testpypi dist/*

# PyPIにアップロード（本番）
python -m twine upload dist/*
```

#### 4. Lambda関数で使用

```bash
# requirements.txt
slack-markdown-parser==1.0.0
slack-sdk
```

```bash
# インストール
pip install -r requirements.txt -t .
```

---

## 方法4: AWS CodeArtifact

### 特徴

- ✅ プライベートなPythonパッケージリポジトリ
- ✅ 組織内で安全に共有可能
- ✅ バージョン管理とアクセス制御
- ❌ AWS追加コスト（$0.05/GB保存、$0.05/GB転送）

### 手順

#### 1. CodeArtifactリポジトリを作成

```bash
# ドメインを作成
aws codeartifact create-domain \
    --domain my-company \
    --region ap-northeast-1

# リポジトリを作成
aws codeartifact create-repository \
    --domain my-company \
    --repository python-packages \
    --region ap-northeast-1
```

#### 2. パッケージをアップロード

```bash
# 認証情報を取得
aws codeartifact login \
    --tool pip \
    --domain my-company \
    --repository python-packages \
    --region ap-northeast-1

# パッケージをビルド
cd slack-markdown-parser
python -m build

# アップロード
aws codeartifact publish \
    --domain my-company \
    --repository python-packages \
    --format pypi \
    --package slack-markdown-parser \
    --package-version 1.0.0 \
    --asset-content dist/slack_markdown_parser-1.0.0-py3-none-any.whl
```

#### 3. Lambda関数で使用

Lambda関数のビルド時にCodeArtifactから取得：

```bash
# 認証
aws codeartifact login \
    --tool pip \
    --domain my-company \
    --repository python-packages

# インストール
pip install slack-markdown-parser -t .
```

---

## 使用例

### 例1: シンプルなSlack Bot

```python
import json
import os
from slack_markdown_parser import convert_markdown_to_slack_blocks
from slack_sdk import WebClient

def lambda_handler(event, context):
    markdown = event['body']
    blocks = convert_markdown_to_slack_blocks(markdown)
    
    client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])
    client.chat_postMessage(
        channel=os.environ['SLACK_CHANNEL_ID'],
        blocks=blocks,
        text="New message"
    )
    
    return {'statusCode': 200}
```

### 例2: LLM応答をSlackに投稿

```python
import json
import os
import boto3
from slack_markdown_parser import convert_markdown_to_slack_messages
from slack_sdk import WebClient

def lambda_handler(event, context):
    # Bedrockを呼び出し
    bedrock = boto3.client('bedrock-runtime')
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'messages': [{'role': 'user', 'content': event['prompt']}],
            'max_tokens': 4096
        })
    )
    
    # LLM応答を取得
    result = json.loads(response['body'].read())
    markdown_text = result['content'][0]['text']
    
    # Markdownをblocks に変換
    messages = convert_markdown_to_slack_messages(markdown_text)
    
    # Slackに投稿
    client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])
    for blocks in messages:
        client.chat_postMessage(
            channel=os.environ['SLACK_CHANNEL_ID'],
            blocks=blocks,
            text="LLM Response"
        )
    
    return {'statusCode': 200, 'body': json.dumps({'messages': len(messages)})}
```

### 例3: 複数のBOTで共通利用

**BOT 1: レポート生成BOT**

```python
from slack_markdown_parser import convert_markdown_to_slack_messages

def lambda_handler(event, context):
    report = generate_report()  # Markdownレポートを生成
    messages = convert_markdown_to_slack_messages(report)
    send_to_slack(messages)
```

**BOT 2: 通知BOT**

```python
from slack_markdown_parser import convert_markdown_to_slack_blocks

def lambda_handler(event, context):
    notification = format_notification(event)  # Markdown通知を生成
    blocks = convert_markdown_to_slack_blocks(notification)
    send_to_slack(blocks)
```

**BOT 3: Q&A BOT**

```python
from slack_markdown_parser import convert_markdown_to_slack_messages

def lambda_handler(event, context):
    answer = get_llm_answer(event['question'])  # LLMからMarkdown回答を取得
    messages = convert_markdown_to_slack_messages(answer)
    send_to_slack(messages)
```

すべてのBOTで同じLambda Layerを使用できます。

---

## トラブルシューティング

### Q: Lambda Layerが認識されない

**A:** Layerのディレクトリ構造を確認してください。`python/`ディレクトリ内にパッケージが配置されている必要があります。

```
slack-markdown-parser-layer.zip
└── python/
    └── slack_markdown_parser/
        ├── __init__.py
        └── converter.py
```

### Q: インポートエラーが発生する

**A:** Lambda関数のランタイムとLayerの互換性を確認してください。Python 3.8以上が必要です。

### Q: Layerのサイズ制限

**A:** Lambda Layerの最大サイズは250MB（解凍後）です。`slack-markdown-parser`は約12KBなので問題ありません。

---

## まとめ

### 推奨フロー

1. **開発環境**: ローカルで`slack-markdown-parser`をインストールして開発
2. **テスト**: Lambda関数をローカルでテスト
3. **デプロイ**: Lambda Layerをビルドして公開
4. **運用**: 複数のLambda関数で同じLayerを使用

### メリット

- ✅ コードの重複を排除
- ✅ ライブラリの更新が容易
- ✅ デプロイパッケージサイズを削減
- ✅ 一貫性のあるMarkdown変換

---

**作成日**: 2025年11月25日  
**バージョン**: 1.0  
**対象**: AWS Lambda (Python 3.8+)
