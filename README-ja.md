# slack-markdown-parser

LLM が生成するふつうの Markdown を、Slack Block Kit（`markdown` + `table` ブロック）に変換する Python ライブラリです。

## 背景

Slack で AI BOT を動かすとき、従来は Slack 独自の `mrkdwn` 形式に変換することが多かったのですが、次の課題がありました。

- 変換の手間: LLM はふつうの Markdown を出力するため、`mrkdwn` に合わせた変換ロジックや厳しいプロンプト制御が必要になりやすい
- 装飾の崩れ: 日本語・中国語・韓国語のように単語間に空白を入れない文では、`*` や `~` などの装飾記号がうまく解釈されず、そのまま見えてしまうことがある
- テーブル非対応: `mrkdwn` には表の構文がないため、表をリストなどへ作り替える必要がある

## 設計方針

Slack Block Kit の `markdown` ブロックと `table` ブロックを使って、上の課題に対応します。

| 課題 | 解決手段 |
|---|---|
| 変換の手間 | `markdown` ブロックがふつうの Markdown を受け取れるので、LLM 出力を `mrkdwn` に書き換えずに使う |
| 装飾の崩れ | 基本はゼロ幅スペース（`U+200B`）で装飾記号の境界を補い、それでも崩れる一部の日本語・中国語・韓国語のケースだけ可視スペースを使う |
| テーブル非対応 | Markdown テーブルを見つけて `table` ブロックに変換し、LLM が作りがちな表の崩れも自動で補う |

このライブラリの目標は、CommonMark や HTML を完全再現することではなく、Slack 上で自然に読める表示を作ることです。
Slack の `markdown` ブロック自体が対応していない構文は、古い `mrkdwn` へ無理に書き換えるより、安全なプレーンテキスト表示や `table` ブロック化を優先します。

## 主な機能

- ふつうの Markdown テキストを `markdown` ブロックに変換
- Markdown テーブルを `table` ブロックに変換
- LLM が生成する表で起こりやすい崩れ（外枠パイプ不足、区切り行不足、列数不一致、空セル）を補正
- テーブルごとにメッセージを自動分割し、Slack の「1メッセージ1テーブル」制約に対応
- ANSI escape / 制御文字を除去し、不正な Slack 角括弧トークンを無害化
- フェンスドコードブロック外では、装飾記号の前後にゼロ幅スペースを入れて表示崩れを減らす
- 日本語・中国語・韓国語の詰まった文で、インラインコードを含む装飾が崩れる一部のケースでは可視スペースを補って安定化
- テーブルセル内の Markdown リンク / Slack 形式リンクを認識
- `markdown` ブロック内の空行が見えにくい環境向けに、内部空行だけを補助用の行へ置き換える `preserve_visual_blank_lines` オプションを用意
- `chat.postMessage.text` 用のプレビュー文字列を生成し、Slack 表示を安定させるために入れた補助文字はそこで自然な形に戻す
- モデル側で Markdown を厳密に制御しなくてもよいよう、Slack 送信前にできる範囲でサニタイズと表補正を行う

## 実測ベースの Slack の挙動

本ライブラリは、Slack の `markdown` / `table` ブロックが実際にどう見えるかを前提に設計しています。

Slack は 2026-03-06 に `markdown` ブロックの公式ドキュメントを更新し、見出し、水平線、タスクリスト、表、言語付きコードブロックなど、これまでより多くの Markdown 記法を案内し始めました。ただし、これらの機能は環境ごとに順番に有効化されるとも書かれています。つまり、ワークスペースやクライアントによって見え方が違う可能性があります。

現在の Slack で比較的安定して表示されるもの:

- `**bold**`, `*italic*`, `~~strike~~`, インラインコード, フェンスドコード
- bare URL, `<https://...>` 形式リンク, Markdown リンク, 参照リンク, mailto リンク
- 箇条書き, 番号付きリスト, タスクリスト, 単純な引用
- Markdown テーブルを変換した明示的な Slack `table` ブロック
- Slack 側で新しい Markdown 表示が有効な環境では、`markdown` ブロック内の見出し・水平線・表

Slack 側の制約として残るもの:

- 見出しサイズや一部の新しい Markdown 表示は、Slack アプリ・ワークスペース・有効化状況に依存する
- `markdown` ブロック内の段落区切りは、実測した Slack Web では上下の余白がほとんどなく、空行がつぶれて見えやすい
- 多段引用はフル Markdown レンダラほどきれいに出ない
- `markdown` ブロック内の生 Markdown テーブルは一部環境では表示されるが、安定性では明示的な Slack `table` ブロックの方が上
- Markdown 画像記法は `markdown` ブロック内では埋め込み画像にならない
- 数式, 生 HTML, HTML comment, `<details>`, admonition 記法, Mermaid は特別な表示にならず、テキストまたはコードとして出る
- Slack **モバイル**アプリは、`markdown` ブロック内のリスト項目に属する継続行（CommonMark で同じリスト項目に紐づくインデントされた段落）の先頭に、リストマーカーを再付加してしまう。例: `1. 見出し` の次にインデントされた継続段落を置くと、モバイルでは `1. 見出し` と `1.継続行...` のように番号が重複して表示される。Slack デスクトップ／Web は同じペイロードを正しく描画する。これはパーサー側の不具合ではなく Slack クライアントのレンダリング挙動。追跡: [issue #45](https://github.com/darkgaldragon/slack-markdown-parser/issues/45)。

このライブラリが吸収するもの:

- underscore 装飾 (`_..._`, `__...__`) を Slack 互換の asterisk 装飾へ正規化
- bare URL を Slack の `<https://...>` 形式にそろえる
- 崩れた Markdown テーブルを補って Slack `table` ブロックへ変換
- フェンスドコード内の table 風行をテーブル処理から除外
- 必要に応じて、内部空行を補助用の行に置き換えて段落の区切りを見えやすくする
- 生 HTML 風タグなど、Slack の特殊記法としては無効な `<...>` 形式を無害化

## 利用前提

- Slack Block Kit の `blocks` で `markdown` / `table` ブロックを送信できる実装が必要です。
- `text` / `mrkdwn` のみ送信できる経路では利用できません。

## インストール

```bash
pip install slack-markdown-parser
```

## 最小利用例

```python
from slack_markdown_parser import (
    convert_markdown_to_slack_payloads,
)

markdown = """
# Weekly Report

| Team | Status |
|---|---|
| API | **On track** |
| UI | *In progress* |
"""

for payload in convert_markdown_to_slack_payloads(
    markdown,
    preserve_visual_blank_lines=True,
):
    print(payload)
```

`convert_markdown_to_slack_messages` は、複数テーブルを含む入力を Slack 制約に合わせて複数メッセージへ分割します。
Slack Web の新しい `markdown` 表示で段落間の余白が極端に小さい場合は、`preserve_visual_blank_lines=True` を使うと内部空行だけを見えやすく補えます。

## 入出力イメージ

検証テキスト:

````markdown
# 週次プロダクト更新

今週は**検索速度改善**と*UI調整*を進めました。旧仕様は~~廃止予定~~です。
詳細ログIDは`run-20260305-02`です。
参考: https://example.com/changelog

- APIの**レスポンス改善**
  - *キャッシュヒット率*を改善
  - タイムアウト設定を調整
- バッチ処理の安定化
  - リトライ回数を統一
- ドキュメント更新

カテゴリ | 状況 | 担当
API | **進行中** | Team A
UI | *確認中* | Team B
QA | ~~保留~~ | Team C

> 注意: 本番反映は 3/8 10:00 JST を予定

1. リリースノート最終確認
   1. 変更点の表記統一
   2. 影響範囲の追記
2. 監視アラートしきい値調整
   1. `warning`閾値の更新
3. QA再確認

```bash
./deploy.sh production
```
````

実際のSlack BOTでの表示例（`markdown` + `table` ブロック）:

![Slack BOT rendering example](Example_ja.png)

## ライブラリの公開インターフェース

### メイン関数（公開関数）

| 関数 | 説明 |
|---|---|
| `convert_markdown_to_slack_messages(markdown_text, *, preserve_visual_blank_lines=False) → list[list[dict]]` | Markdown をテーブル分割済みのメッセージ群に変換 |
| `convert_markdown_to_slack_payloads(markdown_text, *, preserve_visual_blank_lines=False) → list[dict]` | `blocks` とプレビュー用 `text` を含む Slack 送信用データへ変換 |
| `convert_markdown_to_slack_blocks(markdown_text, *, preserve_visual_blank_lines=False) → list[dict]` | Markdown を Block Kit ブロックのリストに変換 |
| `build_fallback_text_from_blocks(blocks) → str` | `chat.postMessage.text` 用のプレビュー文字列を生成 |
| `blocks_to_plain_text(blocks) → str` | ブロックからプレーンテキストを生成 |

`preserve_visual_blank_lines=True` は、非テーブル領域の内部空行を「改行を見えやすくするための補助行」に置き換えるオプションです。
この補助行はプレビュー文字列を作るときに取り除かれるので、通知文やログは元の Markdown に近い形を保てます。
また、リスト項目の内容直後、setext 見出しの下線直前、参照リンク定義直前には補助行を入れず、Markdown の意味が変わったり一部クライアントでリスト解釈が継続したりしないようにしています。

### ユーティリティ関数（公開関数）

| 関数 | 説明 |
|---|---|
| `normalize_markdown_tables(markdown_text) → str` | テーブル記法を正規化（パイプ補完、区切り行生成、列数調整） |
| `add_zero_width_spaces_to_markdown(text) → str` | 装飾記号の前後にゼロ幅スペースを挿入（フェンスドコードブロック内は除外） |
| `decode_html_entities(text) → str` | HTML エンティティをデコード |
| `sanitize_slack_text(text) → str` | ANSI / 制御文字を除去し、不正な Slack 角括弧トークンを無害化 |
| `strip_zero_width_spaces(text) → str` | ゼロ幅スペース (U+200B) と BOM (U+FEFF) を除去（ZWJ 等の結合制御文字は保持） |

## 仕様

- 挙動仕様: [docs/spec-ja.md](docs/spec-ja.md)
- 英語仕様: [docs/spec.md](docs/spec.md)
- 非対応:
  - `mrkdwn` 文字列の生成
  - `mrkdwn` のみ送信可能なクライアント／MCP ツール

## コントリビュート

不具合報告、ドキュメント改善、コードの提案を歓迎します。
Issue / Pull Request を作成する前に [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。Slack 表示のメンテナ向け検証資料は、利用者向け README ではなく CONTRIBUTING 側から案内しています。

## 変更履歴

リリース履歴は [CHANGELOG.md](CHANGELOG.md) で管理しています。

## 連絡先

- GitHub Issue / Pull Request
- X: [@darkgaldragon](https://x.com/darkgaldragon)

## ライセンス

MIT
