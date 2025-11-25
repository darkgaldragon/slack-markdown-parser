# GitHubからのインストールガイド

`slack-markdown-parser`をGitHubリポジトリから直接インストールする方法

---

## 📦 インストール方法

### 方法1: pip install（最も簡単）

プライベートリポジトリからインストール：

```bash
# SSH認証を使用（推奨）
pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git

# HTTPS認証を使用
pip install git+https://github.com/darkgaldragon/slack-markdown-parser.git
```

特定のバージョンやブランチを指定：

```bash
# 特定のタグ（バージョン）
pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git@v1.0.0

# 特定のブランチ
pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git@main

# 特定のコミット
pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git@d1f1adc
```

### 方法2: requirements.txt に記述

```txt
# requirements.txt
slack-markdown-parser @ git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git
slack-sdk>=3.0.0
```

インストール：

```bash
pip install -r requirements.txt
```

### 方法3: 開発モードでインストール

ローカルで開発する場合：

```bash
# リポジトリをクローン
git clone git@github.com:darkgaldragon/slack-markdown-parser.git
cd slack-markdown-parser

# 開発モードでインストール（編集可能）
pip install -e .

# 開発用依存関係も含める
pip install -e ".[dev]"
```

---

## 🔐 プライベートリポジトリへのアクセス設定

### SSH認証の設定（推奨）

1. **SSH鍵を生成**（まだない場合）

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

2. **公開鍵をGitHubに登録**

```bash
# 公開鍵を表示
cat ~/.ssh/id_ed25519.pub

# GitHubの Settings > SSH and GPG keys > New SSH key で登録
```

3. **接続テスト**

```bash
ssh -T git@github.com
# "Hi username! You've successfully authenticated" と表示されればOK
```

### Personal Access Token（PAT）を使用

1. **GitHubでPATを生成**
   - Settings > Developer settings > Personal access tokens > Generate new token
   - `repo` スコープを選択

2. **環境変数に設定**

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

3. **インストール時に使用**

```bash
pip install git+https://${GITHUB_TOKEN}@github.com/darkgaldragon/slack-markdown-parser.git
```

---

## 🚀 各環境での使用方法

### 1. ローカル開発環境

```bash
# インストール
pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git

# 使用
python your_script.py
```

### 2. AWS Lambda

#### Lambda Layerとして使用

```bash
# 1. リポジトリをクローン
git clone git@github.com:darkgaldragon/slack-markdown-parser.git
cd slack-markdown-parser

# 2. Lambda Layerをビルド
./build_lambda_layer.sh

# 3. AWS Lambda Layerにアップロード
aws lambda publish-layer-version \
    --layer-name slack-markdown-parser \
    --zip-file fileb://slack-markdown-parser-layer.zip \
    --compatible-runtimes python3.11
```

#### デプロイパッケージに含める

```bash
# Lambda関数のディレクトリで
pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git -t .
zip -r lambda-function.zip .
```

### 3. Docker環境

```dockerfile
FROM python:3.11-slim

# SSH鍵をコピー（ビルド時のみ使用）
RUN mkdir -p /root/.ssh
COPY id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts

# インストール
RUN pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git

# SSH鍵を削除（セキュリティ）
RUN rm -rf /root/.ssh

COPY . /app
WORKDIR /app
CMD ["python", "main.py"]
```

または、マルチステージビルドを使用：

```dockerfile
# ビルドステージ
FROM python:3.11-slim AS builder
COPY --from=build-stage /root/.ssh /root/.ssh
RUN pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git -t /packages

# 実行ステージ
FROM python:3.11-slim
COPY --from=builder /packages /usr/local/lib/python3.11/site-packages
COPY . /app
WORKDIR /app
CMD ["python", "main.py"]
```

### 4. CI/CD環境（GitHub Actions）

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git
          pip install -r requirements.txt
        env:
          # SSH鍵をシークレットに登録しておく
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
      
      - name: Deploy
        run: |
          # デプロイスクリプト
```

### 5. Jupyter Notebook / Google Colab

```python
# セル1: インストール
!pip install git+https://github.com/darkgaldragon/slack-markdown-parser.git

# セル2: 使用
from slack_markdown_parser import convert_markdown_to_slack_blocks

markdown = """
# テスト
これは**重要**です
"""

blocks = convert_markdown_to_slack_blocks(markdown)
print(blocks)
```

---

## 🔄 アップデート方法

### 最新版にアップデート

```bash
pip install --upgrade git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git
```

### 特定のバージョンにアップデート

```bash
pip install --upgrade git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git@v1.1.0
```

### 現在のバージョンを確認

```bash
pip show slack-markdown-parser
```

---

## 🛠️ トラブルシューティング

### エラー: "Permission denied (publickey)"

**原因**: SSH認証が設定されていない

**解決策**:
1. SSH鍵を生成して GitHubに登録
2. または、HTTPS + Personal Access Tokenを使用

### エラー: "Repository not found"

**原因**: リポジトリへのアクセス権限がない

**解決策**:
1. リポジトリがプライベートの場合、アクセス権限を確認
2. GitHubアカウントでログインしているか確認
3. Personal Access Tokenのスコープを確認（`repo`が必要）

### エラー: "Could not find a version that satisfies the requirement"

**原因**: インストールURLが間違っている

**解決策**:
```bash
# 正しい形式
pip install git+ssh://git@github.com/darkgaldragon/slack-markdown-parser.git
```

---

## 📚 関連ドキュメント

- [README.md](README.md) - 基本的な使い方
- [QUICKSTART.md](QUICKSTART.md) - 5分で始める
- [LAMBDA_INTEGRATION_GUIDE.md](LAMBDA_INTEGRATION_GUIDE.md) - Lambda統合ガイド

---

## 🔗 リポジトリURL

**プライベートリポジトリ**: https://github.com/darkgaldragon/slack-markdown-parser

アクセスには適切な認証が必要です。
