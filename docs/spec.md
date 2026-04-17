# Parser Behavior Specification

This document describes how `slack-markdown-parser` converts Markdown into Slack blocks.

## Input

- A UTF-8 Markdown string
- Broken tables, HTML entities, and mixed plain text are accepted

## Output

- Slack Block Kit blocks (`markdown` / `table`)
- When the input contains multiple tables, a list of messages that satisfies the "one table per message" rule

## Design target

This parser does not try to reproduce full CommonMark, HTML, or rich-document rendering.
Its goal is to produce Slack messages that read naturally when delivered through Slack Block Kit `markdown` and `table` blocks.

When exact Markdown fidelity conflicts with Slack readability, readable Slack output takes priority.

## Conversion steps

`convert_markdown_to_slack_blocks` processes text in this order:

1. Decode HTML entities such as `&gt;` and `&amp;`
2. Clean Slack text by removing ANSI/control noise and neutralizing invalid Slack angle-bracket tokens
3. Normalize underscore emphasis by converting `_..._` / `__...__` into Slack-friendly `*...*` / `**...**`
4. Normalize bare URLs by wrapping them in Slack-friendly `<https://...>` form
5. Repair malformed tables using the rules below
6. Split the text into table regions and non-table regions
7. Build blocks for each region:
   - Table regions: parse inline cell styling and generate a `table` block. If conversion fails, such as when there are fewer than two candidate lines or the parse result is empty, fall back to a `markdown` block.
   - Non-table regions: add zero-width spaces where needed and generate a `markdown` block.
   - If `preserve_visual_blank_lines=True`, replace internal blank lines in non-table regions with lines that contain only a non-breaking space before emitting the `markdown` block.

`convert_markdown_to_slack_messages` then splits the resulting block list to satisfy the "one table per message" rule.
`convert_markdown_to_slack_payloads` returns the same split blocks plus preview `text` values ready for `chat.postMessage`.

## How Slack behaved in testing

The behaviors below are based on practical validation against real Slack clients using the generated Block Kit request data.

### Things Slack currently renders well

- Asterisk emphasis: `*italic*`, `**bold**`
- Strikethrough: `~~strike~~`
- Inline code and fenced code blocks
- Bare URLs, `<https://...>` style links, Markdown links, reference-style links, and mailto links
- Bullet lists, ordered lists, task lists, and simple one-level blockquotes
- Slack `table` blocks

Slack published updated `markdown` block documentation and a changelog entry on March 6, 2026. In the Slack Web workspace validated for this project on April 8, 2026, raw `markdown` blocks rendered:

- ATX and setext headings
- `---` as a divider
- task lists
- raw Markdown tables

Slack still controls when those newer features appear and how they look, so treat them as workspace- and client-dependent until you verify them in your own environment.

### Things still limited by Slack itself

- Exact heading sizes and some newer raw Markdown features still depend on the Slack app, workspace, and release state
- Paragraph breaks inside `markdown` blocks currently receive little or no extra vertical spacing in tested Slack Web clients, so blank lines can look visually collapsed
- Nested blockquotes are weaker than in full Markdown renderers
- Raw Markdown tables inside `markdown` blocks now work in some newer Slack environments, but explicit Slack `table` blocks remain the reliable option
- Markdown image syntax does not become an embedded image inside `markdown` blocks
- Math, raw HTML, HTML comments, `<details>`, admonition syntax, and Mermaid do not receive special rich rendering

### Things this parser corrects or stabilizes

- `_..._` and `__...__` are normalized into Slack-friendly `*...*` and `**...**`
- Bare URLs are wrapped into Slack-friendly `<https://...>` form before `markdown` block delivery
- Malformed Markdown tables are repaired before `table` block generation
- Table-like rows inside fenced code blocks are kept out of table parsing
- Internal blank lines can optionally be rewritten into placeholder lines so Slack keeps visible paragraph separation
- Unsupported Slack angle-bracket tokens such as `<foo>` or raw HTML-like tags are neutralized

## Slack text cleanup rules

Behavior of `sanitize_slack_text`:

- Remove ANSI escape sequences
- Remove general control characters except line breaks and tabs already preserved by the regex
- Keep valid Slack angle-bracket tokens such as links, mentions, channels, special mentions, subteam mentions, and `<!date^...>`
- Replace unsupported angle-bracket tokens such as `<foo>` with full-width brackets (`＜foo＞`) so Slack does not interpret them as malformed special syntax
- This also applies to raw HTML-like tags such as `<div>` or `<span>`

## Underscore emphasis normalization rules

Behavior of `normalize_underscore_emphasis`:

- Convert `_text_` into `*text*`
- Convert `__text__` into `**text**`
- Only convert emphasis-style underscores that are not embedded inside ASCII alphanumeric identifiers
- Preserve identifiers such as `snake_case`
- Preserve escaped forms such as `\_escaped\_`
- Preserve underscores inside bare URLs, Markdown links, Slack `<...>` forms, and inline code
- Preserve underscores inside fenced code blocks (both `` ``` `` and `~~~`)

## Table normalization rules

LLMs often emit tables with omitted outer pipes, missing separator rows, or inconsistent column counts. Passing those directly to Slack `table` blocks can trigger `invalid_blocks`, so `normalize_markdown_tables` repairs them first.

### Detecting table candidates

- Buffer consecutive lines that contain `|`
- Treat the buffered region as a table when either of the following is true:
  - It contains a separator row such as `|---|---|`
  - It has at least two data rows, the column counts match or differ by at most one, and the maximum column count is at least two

### Normalization behavior

- Add missing outer pipes so lines become `|...|`
- If the separator row is missing, generate one immediately after the header row
- Match each row to the header width by filling missing cells with empty cells and truncating extra cells
- Replace empty cells with `-` when generating the Slack `table` block
- Split `# Heading |a|b|`-style lines into a heading line and a table row. Pipes inside inline code in the heading are ignored for this detection.
- When a heading and a header row collapse into one line, such as `### Heading ... Header A | Header B`, use the next row shape as a hint to keep the first header cell as a multi-word phrase when possible.
- Ignore lines inside fenced code blocks (both `` ``` `` and `~~~`) when collecting table candidates.

### Preserving literal pipes inside cells

- Treat pipes inside Slack links such as `<url|text>` as literal content, not as cell separators
- Treat pipes inside inline code `` `...` `` as literal content, not as cell separators
- Treat escaped pipes `\|` as literal content and remove the backslash in the final displayed text

## Table cell styling

Inside table cells, the following inline styles are recognized and converted into Slack `rich_text` styling:

| Syntax | Style |
|---|---|
| `**text**` | bold |
| `*text*` | italic |
| `~~text~~` | strike |
| `` `text` `` | code |

Nested combinations of these styles are preserved as plain text.

The following link syntaxes are also recognized inside table cells:

| Syntax | Output |
|---|---|
| `[label](https://example.com)` | Slack rich-text link |
| `<https://example.com|label>` | Slack rich-text link |
| `<https://example.com>` | Slack rich-text link |

## Zero-width space insertion rules

Behavior of `add_zero_width_spaces_to_markdown`:

### Purpose

In languages such as Japanese, Chinese, and Korean that do not usually put spaces between words, formatting markers can attach directly to surrounding characters and break Slack rendering. This library mainly inserts zero-width spaces so Slack gets clearer formatting boundaries without changing the visible layout. For some nested inline-code emphasis cases in dense Japanese, Chinese, or Korean text, it falls back to visible spaces because current Slack rendering is more reliable with explicit spacing.

### Target patterns

For each formatting token below, if either adjacent side is not a space, tab, newline, or existing zero-width space, or if the token touches the start or end of a line, the whole token is normally wrapped in a zero-width space (`U+200B`) so Slack recognizes it as a standalone formatting boundary:

- `` `code` ``: inline code
- `**bold**`: bold
- `*italic*`: italic
- `~~strike~~`: strikethrough

Exception:

- If the token body is English-like text and the only tight neighbors are punctuation characters, the raw token is preserved. This avoids over-correcting spans such as `**APIYI (apiyi.com)**:` that Slack already renders correctly without extra zero-width spaces.

### Excluded regions

- Fenced code blocks (both `` ``` ... ``` `` and `~~~ ... ~~~`) are never modified
- Inline code (`` `...` ``) is not excluded; it is part of the target set above
- Inline code nested inside `**bold**`, `*italic*`, or `~~strike~~` is left untouched
- For English-like boundaries around those nested combinations, the outer formatting span is preserved as-is
- For dense Japanese and Chinese boundaries, visible spaces are inserted on the missing outer side or sides around the outer formatting span
- For dense Korean boundaries, a visible trailing space is inserted when needed, while right-space cases are otherwise preserved because Slack already renders them more reliably

## Zero-width space removal rules

`strip_zero_width_spaces` is called when generating table cells and preview text so that control characters inserted by this library do not leak into plain output.

### Removed characters

| Code point | Name | Reason |
|---|---|---|
| `U+200B` | zero-width space | Inserted by this library for formatting stability |
| `U+FEFF` | BOM (byte order mark) | Unwanted encoding artifact |

### Preserved characters

| Code point | Name | Reason |
|---|---|---|
| `U+200C` | ZWNJ (zero-width non-joiner) | Used for word-shape control in languages such as Persian and Hindi |
| `U+200D` | ZWJ (zero-width joiner) | Required for joined emoji and other grapheme composition |

## Optional blank-line visibility workaround

When `preserve_visual_blank_lines=True` is passed to the main conversion APIs,
the parser rewrites internal blank-only lines in non-table Markdown segments
into lines that contain only a non-breaking space before emitting Slack `markdown`
blocks.

This workaround is intentionally narrow:

- Only blank lines between visible lines are rewritten
- Leading and trailing blank runs are left untouched
- Table segments are not modified by this option
- Blank runs immediately after list items are left untouched
- Blank runs immediately before setext-heading underlines are left untouched
- Blank runs immediately before reference-link definitions are left untouched
- Preview text and `blocks_to_plain_text` remove those placeholder markers again, preserving the original blank lines in plain-text output

## Preview text

`build_fallback_text_from_blocks` generates preview text for `chat.postMessage.text` as follows:

- `markdown` blocks: text with zero-width spaces removed
- Parser-inserted visible spaces used only to stabilize nested inline-code emphasis are normalized back out when building plain preview text
- `table` blocks: join each row's cell text with ` | `
- Join block outputs with blank lines between them

For table-cell links, preview text uses the link label if present, otherwise the URL.

## Determinism

For the same input, the library always returns the same output regardless of environment.

## Non-goals

- Generating Slack `mrkdwn` strings
- Reconstructing a full Markdown AST
- Matching HTML rendering behavior
- Recreating rich rendering for constructs Slack does not natively support in `markdown` blocks
