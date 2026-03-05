# OSS Public-Share Checklist

Use this checklist before introducing this repository on SNS, blogs, or community posts.

日本語: SNSなどで公開紹介する前に、このチェックを実施してください。

## 1. Security Hygiene

- Run local secret regex scan:
  - `rg -n --hidden --glob '!.git' --pcre2 '(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{20,}|AIza[0-9A-Za-z\-_]{35}|-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----|aws_secret_access_key\s*[:=]\s*[A-Za-z0-9/+=]{20,})' .`
- Run git-history secret scan:
  - `gitleaks git --redact --log-opts="--all"`
- Confirm no local credentials are tracked:
  - `git ls-files | rg -n '(\.env|\.pem|\.key|credentials|secrets?)'`

## 2. Repository Health

- CI is green on `main` (`lint`, `test`, `security`, `package-check`)
- No open PRs waiting for security fixes
- Branch protection is enabled on `main`:
  - force push disabled
  - deletion disabled
  - required status checks enabled

## 3. Package Publish Sanity

- Build artifacts succeed:
  - `python -m build`
  - `twine check dist/*`
- Installation smoke test succeeds:
  - `pip install slack-markdown-parser==2.*`

## 4. Docs for External Users

- README has:
  - clear What/Why
  - quick start
  - API examples
  - behavior limitations
  - support/security links
- Broken links check:
  - `rg -n 'TODO|TBD|FIXME|XXX|リンク切れ|broken' README.md docs`

## 5. Release/Announcement Notes

- Announce latest stable version tag (`v2.x.y`) rather than a local commit.
- If reporting known limitations, link to `docs/spec.md`.
- If a secret is ever found after announcement:
  1. stop promotion
  2. rotate/revoke impacted credentials
  3. remove leaked data from history
  4. publish incident note and mitigation

---

Short answer for non-technical audiences:
- "No secrets in repository/history"
- "Automated security checks enabled"
- "Installable from PyPI and reproducibly from tagged GitHub source"
