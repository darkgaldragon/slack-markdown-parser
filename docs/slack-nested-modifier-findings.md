# Maintainer Slack Nested Modifier Findings

Observed on Slack Web in a dedicated maintainer test channel on 2026-03-09.

This note captures maintainer validation results. It is not part of the public
package API or guaranteed behavior by itself.

## Variants

- `plain`: inner content without surrounding punctuation
- `parens`: inner content wrapped in parentheses
- `quotes`: inner content wrapped in quotes

## Source fixtures

- `tests/fixtures/slack_nested_modifier_matrix.md`
- `tests/fixtures/slack_nested_modifier_matrix_parens.md`
- `tests/fixtures/slack_nested_modifier_matrix_quotes.md`
- `tests/fixtures/slack_cjk_inner_code_matrix.md`

## Note on private artifacts

The concrete Slack permalinks used during validation are intentionally omitted from the public repository. Re-run the workflow in `docs/slack-render-test-workflow.md` inside your own workspace if you want message-level links for manual verification.

## Shared result before locale-aware fallback

Before the locale-aware visible-space fallback was introduced, all three content variants produced the same high-level outcome:

- English boundaries succeeded in `raw` and `parser`
- Japanese `spaces_both` succeeded in `raw` and `parser`
- Japanese `outer_zwsp` succeeded in `raw` and `parser`
- Japanese `tight`, `space_left`, and `space_right` failed in `raw`
- `parser` improved those Japanese boundary buckets from `0/5` to `4/5`
- The remaining failures were concentrated in `inner_code`

## Focused CJK result

Fixture:

- `tests/fixtures/slack_cjk_inner_code_matrix.md`

This focused matrix contained `ja`, `zh`, and `ko`, testing only:

- inner `plain`
- inner `code`

Boundary behavior after improvement:

- `ja`, `zh`, and `ko` all still succeeded for `outer_zwsp`
- `ja`, `zh`, and `ko` all still succeeded for `spaces_both`
- raw `tight` and raw `space_left` remained fragile across all three locales
- raw `space_right` remained fragile for `ja` and `zh`, but was already stable for `ko`
- after the locale-aware fallback, `parser` reached `2/2` success in every tested bucket for `ja`, `zh`, and `ko`

Current takeaway:

- Treating Chinese like Japanese is reasonable based on current Slack Web behavior.
- Korean still differs at the raw-rendering level, but the parser can now normalize all tested Korean buckets successfully with a lighter right-side spacing rule.
- The current parser strategy for nested inline code is:
  - `ja` / `zh`: add visible spaces on whichever outer side is missing
  - `ko`: ensure a visible trailing space when needed
  - English-like boundaries: preserve the original outer formatting span
