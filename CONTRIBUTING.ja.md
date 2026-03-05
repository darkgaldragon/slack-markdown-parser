# コントリビュートガイド

`slack-markdown-parser` への貢献ありがとうございます。

## 開発環境セットアップ

```bash
git clone https://github.com/darkgaldragon/slack-markdown-parser.git
cd slack-markdown-parser
pip install -e ".[dev]"
```

## ローカルチェック

```bash
ruff check .
black --check .
pytest -q
python -m build
twine check dist/*
```

## Pull Request ルール

1. 変更は小さく、目的を明確にする。
2. 挙動変更時はテストを追加/更新する。
3. 公開挙動が変わる場合はドキュメントを更新する。
4. 秘密情報、ローカル生成物、生成zipをコミットしない。
5. レビュー依頼前にCIをグリーンにする。

## コミット方針

- 内容が分かるコミットメッセージを使う。
- PR本文に「挙動への影響（パース/fallback/互換性）」を記載する。

## セキュリティ

- トークン/鍵/資格情報をコミットしない。
- 可能ならローカルでもシークレットスキャンを実行する。
- 開示/報告は [SECURITY.md](SECURITY.md) に従う。

## コードスタイル

- Python 3.10+
- 実用的な範囲で型ヒントを付与
- パーサー挙動は決定的（deterministic）に保つ

## 質問先

[SUPPORT.md](SUPPORT.md) を参照してください。
