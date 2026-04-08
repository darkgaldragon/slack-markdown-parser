# Maintainer Slack Markdown Rollout Observations

Observed on Slack Web in a dedicated maintainer test channel on 2026-04-08.

This note captures maintainer validation results for Slack's richer `markdown`
block rollout. It is not part of the public package API or a guarantee that
all workspaces and clients behave the same way.

## Official references

- Slack `markdown` block docs:
  [https://docs.slack.dev/reference/block-kit/blocks/markdown-block/](https://docs.slack.dev/reference/block-kit/blocks/markdown-block/)
- Slack richer rich-text rollout changelog:
  [https://docs.slack.dev/changelog/2026/03/06/block-kit-rich-text](https://docs.slack.dev/changelog/2026/03/06/block-kit-rich-text)

Slack's docs and changelog started documenting richer raw Markdown support on
2026-03-06, including headers, dividers, task lists, tables, and richer code
formatting. The docs also explicitly say the rollout is progressive.

## Test setup

- Workspace: dedicated maintainer workspace
- Channel: dedicated render-test channel
- App: `smp-render-test-bot`
- Surface: Slack Web
- Browser validation: Playwright CLI against an existing logged-in Chrome profile
- Posting modes compared:
  - raw `markdown` block over raw HTTP
  - parser-generated payload over raw HTTP
  - parser-generated payload over `slack_sdk`

## Confirmed observations

### Transport path parity

The same `markdown` payload produced materially identical rendering across:

- raw HTTP posting
- parser-generated payload over raw HTTP
- parser-generated payload over `slack_sdk`

For the cases validated here, richer Markdown rendering was Slack-owned rather
than transport-owned.

### Heading rendering

Raw `markdown` blocks produced native header elements on the tested Slack Web
surface:

- `#` and setext `=` rendered as `H1`
- `##` and setext `-` rendered as `H2`
- `###` rendered as `H3`
- `####` rendered as `H4`
- `#####` and `######` collapsed to the same `H4`-level styling

This differed from the contemporaneous Slack docs note that all header levels
render at the same size.

Observed classes and computed styles on the tested surface:

- `H1` -> `p-header_block p-header_block--level_1`, `font-size: 28px`, `font-weight: 900`
- `H2` -> `p-header_block p-header_block--level_2`, `font-size: 22px`, `font-weight: 900`
- `H3` -> `p-header_block p-header_block--level_3`, `font-size: 18px`, `font-weight: 900`
- `H4` -> `p-header_block p-header_block--level_4`, `font-size: 15px`, `font-weight: 700`

### Divider, task list, and raw Markdown table rendering

The following raw Markdown constructs rendered natively inside `markdown`
blocks on the tested surface:

- `---` -> divider block
- `- [ ]` / `- [x]` -> checklist rendering
- raw pipe-table Markdown -> native table DOM

Observed DOM hints on the tested surface:

- divider -> `div.p-divider_block`
- task list -> `ul.p-rich_text_list__check`
- raw table -> native `table` element rendered by Slack's richer markdown surface

Even with that richer support, the parser should still keep explicit Slack
`table` blocks as the stable output path because:

- Slack enforces one `table` block per message
- rollout differences remain possible
- explicit `table` blocks make fallback text and tests easier to control

### Blank-line behavior

Blank lines were not fully ignored, but they also did not create visible
paragraph spacing in the tested Slack Web client.

Observed DOM behavior:

- paragraph breaks became separate `div.p-rich_text_section` nodes
- those paragraph sections had `margin-top: 0` and `margin-bottom: 0`
- single line breaks inside one paragraph became `<br>`

Observed structural consequence:

- `A`
- blank line
- `B`

did not become one flat line, but it also did not receive extra paragraph
margin. Slack preserved structure while dropping the expected visual whitespace.

Practical effect:

- source Markdown paragraphs remained structurally separate
- visual spacing between paragraphs was still very tight
- ordinary blank lines therefore looked collapsed to end users

## Parser implications

These observations motivated the optional
`preserve_visual_blank_lines=True` parser workaround:

- only non-table Markdown segments are affected
- only internal blank-only lines are rewritten
- the parser inserts synthetic NBSP-only spacer lines for Slack rendering
- fallback plain text removes those synthetic placeholders again

This keeps the workaround explicitly opt-in because it is a Slack-specific
presentation fix rather than a universal Markdown rule.

## Maintainer guidance

- Re-run these checks in the exact workspace and client you care about before
  changing public claims about Slack rendering.
- Do not assume Slack docs are pixel-accurate for your target client; verify
  the rendered DOM and screenshots when the distinction matters.
- Treat richer raw Markdown support as Slack-owned behavior, not parser-owned
  behavior.
- Keep public docs focused on what the parser guarantees, and keep detailed
  renderer observations in maintainer-facing docs such as this one.
