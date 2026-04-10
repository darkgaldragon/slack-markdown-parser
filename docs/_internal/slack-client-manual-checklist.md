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
- When validating richer raw Markdown rollout, note whether headings/dividers/raw tables are native-looking or flattened.
- When validating paragraph spacing, note whether blank lines look visually collapsed or visibly separated.

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

- `manual_rollout_headings`
  Expected on richer-rollout surfaces: `#`, `##`, `###`, and setext headings render with visibly different heading sizes; record any collapse to same-size text as a client/workspace difference
  Link: paste your `manual_rollout_headings` permalink here

- `manual_rollout_divider_table_tasklist`
  Expected on richer-rollout surfaces: `---` renders as a divider, task list items render as checkboxes, and raw Markdown tables render as a native table
  Link: paste your `manual_rollout_divider_table_tasklist` permalink here

- `manual_blank_lines_default`
  Expected on tested Slack Web surfaces: source blank lines create paragraph breaks but little or no extra vertical gap
  Link: paste your `manual_blank_lines_default` permalink here

- `manual_blank_lines_workaround`
  Expected when `preserve_visual_blank_lines=True`: blank lines are visibly separated without leaking placeholder characters into fallback text
  Link: paste your `manual_blank_lines_workaround` permalink here

## Recording

- `PASS`: rendering matches the expectation above
- `FAIL`: capture which marker leaked or which style was missing
- If Desktop and mobile differ, record the client and version separately
