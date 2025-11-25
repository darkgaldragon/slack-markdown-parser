# Contributing to slack-markdown-parser

`slack-markdown-parser`への貢献を歓迎します！

## 開発環境のセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/slack-markdown-parser.git
cd slack-markdown-parser

# 開発用の依存関係をインストール
pip install -e ".[dev]"
```

## テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジ付きで実行
pytest --cov=slack_markdown_parser --cov-report=html
```

## コーディング規約

- PEP 8に従う
- 関数とクラスにdocstringを記述
- 型ヒントを使用（Python 3.8+）

## プルリクエストの手順

1. このリポジトリをフォーク
2. 新しいブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## バグレポート

バグを見つけた場合は、以下の情報を含めてIssueを作成してください：

- Python バージョン
- `slack-markdown-parser` バージョン
- 再現手順
- 期待される動作
- 実際の動作

## 機能リクエスト

新機能の提案も歓迎します！Issueで以下を説明してください：

- 機能の説明
- ユースケース
- 実装案（あれば）

ありがとうございます！
