# リリースガイド

## バージョニング

本プロジェクトは SemVer に従います。
- MAJOR: 破壊的変更（挙動/API互換性なし）
- MINOR: 後方互換ありの機能追加
- PATCH: 後方互換ありの不具合修正

## リリース前チェックリスト

1. `ruff check .`
2. `black --check .`
3. `pytest -q`
4. `python -m build`
5. `twine check dist/*`
6. 秘密情報スキャン（作業ツリー + 全履歴）
7. 依存監査（`pip-audit`）
8. changelog 更新

## PyPI 公開（Trusted Publishing）

1. タグ作成: `vX.Y.Z`
2. タグを GitHub に push
3. GitHub Actions `publish-pypi.yml` が OIDC で公開
4. Workflow が PyPI attestations（署名付き provenance）を生成
5. Workflow が GitHub Release（自動リリースノート + artifact）を作成

## ロールバック

- 問題があれば、修正版の次パッチ（`X.Y.(Z+1)`）を速やかに公開。
- 公開済みバージョン削除は避け、上書きではなく修正版で前進する。

## リリース後

- クリーン環境でインストール確認:
  - `pip install slack-markdown-parser==X.Y.Z`
- 固定 Markdown フィクスチャでスモークテスト。
