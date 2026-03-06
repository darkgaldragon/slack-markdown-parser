# slack-markdown-parser 改善具体化メモ

このメモは、`slack-markdown-parser` を使っている 3 つの Slack BOT
(`slack-bot-chloe`, `slack-bot-amy`, `slack-bot-gal-chan`)
の実装調査を踏まえ、parser 側へ寄せるべき責務を具体的な実装項目へ落としたもの。

## 目的

- LLM が出力する標準的な Markdown を、BOT ごとの前処理や prompt 制約に依存せず、
  Slack で安定表示できるようにする
- BOT ごとに散っている Slack 向けサニタイズや fallback 組み立てを shared parser に集約する
- 「parser の弱点を system instruction で回避する」状態を減らす

## 調査結果の要点

- Chloe はほぼ shared parser に委譲済み
- Amy は送信直前の前処理を最も多く持つ
- gal は runtime の委譲は進んでいるが、旧 parser 相当の dead code が残る

特に parser に寄せる価値が高いのは次の 3 点。

1. Slack 向け前処理サニタイズ
2. table cell 内の Markdown link 対応
3. `blocks` と `fallback text` をまとめて返す高レベル API

## 優先順位

### P0: 共通サニタイズを parser に持たせる

#### 背景

Amy は BOT 側で次を実装している。

- ANSI escape 除去
- 制御文字除去
- 不正な `<...>` トークンの無害化
- `[text](url)` の `<url|text>` 化

このうち provider 固有でないものは parser 側の責務に寄せやすい。

#### 実装項目

- `slack_markdown_parser/converter.py` に Slack 向け前処理を追加する
- 公開 API として次のいずれかを追加する
  - `sanitize_slack_text(text: str) -> str`
  - `prepare_markdown_for_slack(text: str) -> str`

#### 最低限持つべき挙動

- ANSI escape を除去する
- 一般的な制御文字を除去する
- Slack で有効な angle token は維持する
  - 例: `<https://...>`, `<https://...|label>`, `<mailto:...|...>`,
    `<@U...>`, `<#C...|...>`, `<!here>`, `<!channel>`, `<!date^...>`
- 上記に該当しない `<...>` は `＜...＞` に変換して無害化する
- provider 固有トークン除去はデフォルトでは含めない
  - 例: OpenAI 内部 citation トークンは BOT 側の optional 処理として残す

#### 反映先

- `convert_markdown_to_slack_blocks()`
- `convert_markdown_to_slack_messages()`
- 今後追加する payload API

#### テスト追加

- 不正 token: `<foo>` -> `＜foo＞`
- 有効 token: `<https://example.com|Example>` は保持
- ANSI escape が除去される
- 制御文字が除去される
- ZWSP 挿入ロジックと干渉しない

#### 期待効果

- Amy の `sanitize_slack_output_text()` と
  `neutralize_invalid_slack_angle_tokens()` の大部分を削除できる
- text-only fallback 時の `invalid_blocks` 再送でも shared sanitizer を再利用できる

### P1: table cell 内の Markdown link を正式サポートする

#### 背景

現状の parser は table cell で `bold` / `italic` / `strike` / `inline code`
だけを rich_text 化している。Amy ではその不足を避けるため、
system instruction で「table cell 内の Markdown link を使うな」と制限している。

#### 実装項目

- `_create_table_cell()` で Markdown link を認識する
- 少なくとも次をサポートする
  - `[label](https://example.com)`
  - `<https://example.com|label>`
- Slack table cell の rich_text link 要素に変換する

#### 実装方針

- 第一段階では Amy の既存 regex と同等の範囲でよい
  - URL は `http://` または `https://`
  - ラベル内の複雑なネストまでは初回対応対象外
- `_split_markdown_table_cells()` の link 保護ロジックは維持する
- plain text fallback では link の可読性を落とさない

#### テスト追加

- table cell 内の Markdown link が link 要素になる
- Slack angle link を含む cell が 1 cell として維持される
- escaped pipe と link が同居しても cell split が壊れない
- 空セル `-` 補完と干渉しない

#### 期待効果

- Amy の prompt 制約
  「table cell では Markdown link 禁止」を削除できる
- 「LLM の標準 Markdown をそのまま受ける」という parser の価値が上がる

### P2: high-level payload API を追加する

#### 背景

3 BOT とも最終的には Slack 送信用に次を毎回組み立てている。

- `blocks`
- `text` fallback
- table ごとの message split

この組み立ては parser 側に寄せた方が利用者コードが薄くなる。

#### 実装項目

- 新 API を追加する
  - 例: `convert_markdown_to_slack_payloads(markdown_text: str) -> list[dict]`
- 各 payload は少なくとも次を持つ
  - `blocks`
  - `text`

#### 返り値イメージ

```python
[
    {
        "blocks": [...],
        "text": "fallback text",
    }
]
```

#### 仕様

- 1 payload あたり table block は 1 つまで
- `text` は `build_fallback_text_from_blocks()` の結果を使う
- fallback が空のときの扱いを統一する

#### テスト追加

- 複数 table を含む入力で payload が分割される
- すべての payload が `text` を持つ
- `convert_markdown_to_slack_messages()` と内容整合する

#### 期待効果

- Chloe / Amy / gal の送信直前コードをかなり薄くできる
- Slack SDK 利用側が `chat.postMessage(**payload)` に近い形で使える

### P3: fallback / utility helper を整理する

#### 背景

Chloe は fallback や thread history のために
`strip_angle_bracket_tags()` を持っている。
これは parser 本体ではないが、Slack 表示まわりの utility としては共通化余地がある。

#### 実装候補

- `strip_slack_special_tokens(text: str) -> str`
  - `<https://...|label>` -> `label` または URL
  - `<@U...>` / `<#C...|...>` の plain text 化
- `safe_slack_link(url: str, title: str) -> str`
  - citation や補足リンク整形用 helper

#### 注意

- mention を display name に解決する処理は workspace 依存なので parser 本体には入れない
- citation セクションの見た目は各 BOT 側で持つ

## 変更対象ファイル

### parser 側

- `slack_markdown_parser/converter.py`
- `slack_markdown_parser/__init__.py`
- `tests/test_converter.py`
- `docs/spec.md`
- `docs/spec-ja.md`
- `README.md`
- `README-ja.md`

### BOT 側 cleanup 候補

- `slack-bot-amy/lambda_function.py`
  - `sanitize_slack_output_text()` の縮小
  - `neutralize_invalid_slack_angle_tokens()` の削除または wrapper 化
  - `[text](url)` -> `<url|text>` 変換の削除
- `slack-bot-chloe/src/slack_bot_chloe/handlers/anthropic.py`
  - `safe_slack_link()` が shared 化されたら citation helper の一部を移管
- `slack-bot-gal-chan/lambda_function.py`
  - dead code 化している table helper を削除
  - `send_slack()` の重複前処理を shared API へ寄せる

## BOT の system instruction で緩められる項目

P0-P2 完了後、次の制約は strict requirement から guideline へ緩和できる。

- 外側パイプ必須
- separator 行必須
- 空セルは `-`
- 見出しと table を必ず改行で分離
- table cell 内の Markdown link 禁止

一方で次は prompt 側に残す。

- HTML を出さない
- Math/LaTeX を出さない
- table cell で複雑な Markdown を多用しない

## 受け入れ条件

- Amy 側の Markdown link 先行変換を削除しても表示崩れしない
- Amy 側の angle token 無害化を parser に寄せても `invalid_blocks` が増えない
- Chloe / Amy / gal の contract test を shared parser 基準で維持できる
- parser 単体で、標準 Markdown を Slack Block Kit へ送るための主要前処理が完結する

## 実装順

1. P0 を実装し、Amy の前処理を最小化する
2. P1 を実装し、table cell link の gap を埋める
3. P2 を実装し、送信 payload 組み立てを shared 化する
4. 3 BOT の prompt と runtime cleanup を行う
5. dead code を削除し、README / spec を更新する

## 次の着手候補

最初の PR は P0 のみでよい。理由は次の通り。

- Amy の独自実装を最も大きく減らせる
- table cell link 対応より変更範囲が読みやすい
- `invalid_blocks` 回避に効くため、即効性が高い

初回 PR のスコープ:

- `sanitize_slack_text()` 追加
- `convert_markdown_to_slack_blocks()` の前処理に組み込み
- sanitizer 系テスト追加
- spec / README にサニタイズ仕様を追記
