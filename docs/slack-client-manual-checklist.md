# Maintainer Slack Client Manual Checklist

Use this for quick smoke checks in Slack Desktop and mobile after parser changes.

This checklist is for maintainers and contributors validating real Slack client
rendering. It is not end-user documentation.

## How to run

1. Open the link for each case in Slack Desktop or mobile.
2. Confirm the expected visible text and formatting.
3. Mark `PASS` only if all checks below hold.

## Pass criteria

- Outer emphasis is rendered for the whole target span.
- Inline code remains monospace.
- Raw markers such as `**`, `*`, or `~~` are not visible.
- English cases do not show extra visible spaces before punctuation.
- Japanese/Chinese/Korean nested-code cases may show visible spaces around the emphasized span when needed; that is expected.

## Cases

- `manual_en`
  Expected: `Frontend (App.tsx)` is bold, `App.tsx` is code, no extra space before `:`
  Link: paste your `manual_en` permalink here

- `manual_ja`
  Expected: `フロントエンド (App.tsx)` is bold, `App.tsx` is code, visible spaces around the bold span are acceptable
  Link: paste your `manual_ja` permalink here

- `manual_zh`
  Expected: `外侧(内侧)` span is bold, inner code remains code, visible spaces around the bold span are acceptable
  Link: paste your `manual_zh` permalink here

- `manual_ko`
  Expected: `바깥(내부)강조` span is bold, inner code remains code, trailing visible space before `입니다.` is acceptable
  Link: paste your `manual_ko` permalink here

- `manual_mix_ja_en`
  Expected: `Frontend (App.tsx)` is bold inside Japanese text, `App.tsx` is code
  Link: paste your `manual_mix_ja_en` permalink here

- `manual_mix_ko_en`
  Expected: `Frontend (App.tsx)` is bold inside Korean text, `App.tsx` is code
  Link: paste your `manual_mix_ko_en` permalink here

- `manual_mix_en_ja`
  Expected: `機能A (ID-1)` is bold inside English text, `ID-1` is code, no extra visible spaces are introduced
  Link: paste your `manual_mix_en_ja` permalink here

## Recording

- `PASS`: rendering matches the expectation above
- `FAIL`: capture which marker leaked or which style was missing
- If Desktop and mobile differ, record the client and version separately
