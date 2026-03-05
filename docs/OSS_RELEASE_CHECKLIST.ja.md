# OSS公開前チェックリスト（日本語版）

SNS・ブログ・コミュニティ投稿で紹介する前に、以下を確認してください。

## 1. セキュリティ衛生

- ローカル正規表現スキャンを実行:
  - `rg -n --hidden --glob '!.git' --pcre2 '(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{20,}|AIza[0-9A-Za-z\-_]{35}|-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----|aws_secret_access_key\s*[:=]\s*[A-Za-z0-9/+=]{20,})' .`
- Git履歴スキャンを実行:
  - `gitleaks git --redact --log-opts="--all"`
- 認証情報ファイルが追跡されていないことを確認:
  - `git ls-files | rg -n '(\.env|\.pem|\.key|credentials|secrets?)'`

## 2. リポジトリ健全性

- `main` の CI がグリーン（`lint`, `test`, `security`, `package-check`）
- セキュリティ修正待ちの open PR がない
- `main` のブランチ保護が有効
  - force push 禁止
  - branch 削除禁止
  - required status checks 有効

## 3. パッケージ公開健全性

- ビルド成果物が成功:
  - `python -m build`
  - `twine check dist/*`
- インストールのスモークテスト成功:
  - `pip install slack-markdown-parser==2.*`

## 4. 外部向けドキュメント

- README に次が揃っている:
  - What/Why
  - クイックスタート
  - API例
  - 制約/非対応
  - support/security 導線
- リンク切れ/未整備語の確認:
  - `rg -n 'TODO|TBD|FIXME|XXX|リンク切れ|broken' README.md docs`

## 5. 公開・告知時の注意

- 告知は安定タグ（`v2.x.y`）基準で行い、ローカルコミット参照を避ける
- 既知制約の説明時は `docs/spec.ja.md` へ誘導
- もし公開後に秘密情報漏えいを検知したら:
  1. 告知・公開活動を停止
  2. 影響資格情報を失効/ローテーション
  3. 履歴から漏えい情報を除去
  4. インシデント内容と再発防止を公表

---

非技術者向けの短い説明テンプレ:
- 「リポジトリと履歴に秘密情報はありません」
- 「自動セキュリティチェックを有効化しています」
- 「PyPIとタグ固定GitHubソースの両方で再現可能に導入できます」
