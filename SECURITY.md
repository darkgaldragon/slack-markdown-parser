# Security Policy

## Supported Versions

- `2.x`: supported
- `1.x`: security fixes are best-effort only

## Reporting a Vulnerability

Please report vulnerabilities privately via GitHub Security Advisories.

- Preferred: `Security` tab -> `Report a vulnerability`
- If unavailable, open a private channel with repository maintainers.

Please include:
- affected version
- reproduction steps
- impact assessment
- any suggested mitigation

## Response Targets

- Initial acknowledgement: within 72 hours
- Triage/update: within 7 days
- Fix timeline: based on severity and exploitability

## Secret Handling Requirements

- Never commit API keys/tokens/private keys.
- Run secret scanning before release and in CI.
- If a secret leak is detected:
  1. stop release/publication
  2. revoke/rotate credentials immediately
  3. remove leaked content from history when required
  4. document incident and mitigation

日本語: 機密情報が混入した場合は、公開停止・失効/ローテーション・履歴修正を必須とします。
