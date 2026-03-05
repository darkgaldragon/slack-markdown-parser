# 変更履歴

このファイルには、このプロジェクトの主な変更点を記録します。

## [Unreleased]

### 変更
- 公開ドキュメントを利用者向けに整理するため、内部コードレビュー用レポートを公開対象から除外。
- 公開ドキュメントの索引として `docs/README.md` を追加。
- README のコードサンプルを、環境変数トークン入力（`SLACK_BOT_TOKEN`）方式に更新。

## [2.0.0] - 2026-03-05

### 追加
- 本番利用向けの公開APIを追加:
  - `convert_markdown_to_slack_blocks`
  - `convert_markdown_to_slack_messages`
  - `build_fallback_text_from_blocks`
  - `blocks_to_plain_text`
  - `normalize_markdown_tables`
  - `add_zero_width_spaces_to_markdown`
  - `decode_html_entities`
  - `strip_zero_width_spaces`
- パーサー挙動仕様書 `docs/spec.md` を追加。
- OSS運用ドキュメントを追加: `SECURITY.md`, `SUPPORT.md`, `RELEASE.md`, `CODE_OF_CONDUCT.md`。
- CIパイプライン（lint/test/security/package checks）を追加。

### 変更
- 配布方針を PyPI 本線（Layer は任意）に変更。
- 不正形テーブルの正規化や Slack レンダリング安定化を含むコンバータ改善。
- ゼロ幅スペース処理を改善し、コードフェンス/インラインコードを保護。
- README とコントリビュート関連ドキュメントを OSS 公開向けに再構成。

### セキュリティ
- CI に秘密情報スキャンと依存監査ゲートを追加。
- `.gitignore` を見直し、生成物と認証情報ファイルを確実に除外。

## [1.0.0] - 2025-11-25

### 追加
- Markdown/table 変換機能を備えた初回リリース。
