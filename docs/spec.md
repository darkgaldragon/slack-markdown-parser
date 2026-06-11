# Parser Behavior Specification

This document describes how `slack-markdown-parser` converts Markdown into Slack blocks.

## Input

- A UTF-8 Markdown string
- Broken tables, HTML entities, and mixed plain text are accepted

## Output

- Slack Block Kit blocks (`markdown`, `table`, `rich_text`, `image`, and `divider`)
- When the input contains multiple tables, many promoted blocks, or long content, a list of messages that satisfies the "one table per message" rule, Slack's per-message block-count limit, and the measured size limits described in "Markdown block size splitting"

## Design target

This parser does not try to reproduce full CommonMark, HTML, or rich-document rendering.
Its goal is to produce Slack messages that read naturally when delivered through Slack Block Kit blocks.

When exact Markdown fidelity conflicts with Slack readability, readable Slack output takes priority.

## Conversion steps

`convert_markdown_to_slack_blocks` processes text in this order:

1. Decode HTML entities such as `&gt;` and `&amp;` in prose, leaving fenced code blocks and inline code spans verbatim
2. Clean Slack text: remove ANSI/control noise and this library's reserved internal marker code points everywhere, and neutralize invalid Slack angle-bracket tokens outside fenced code blocks and inline code spans
3. Normalize underscore emphasis by converting `_..._` / `__...__` into Slack-friendly `*...*` / `**...**`
4. Normalize bare URLs by wrapping them in Slack-friendly `<https://...>` form
5. Repair malformed tables using the rules below
6. Split the text into table regions and non-table regions
7. Build blocks for each region:
   - Table regions: parse inline cell styling and generate a `table` block. If conversion fails, such as when there are fewer than two candidate lines or the parse result is empty, fall back to a `markdown` block.
   - Non-table regions: first promote safe standalone Markdown constructs into richer Block Kit blocks, then add zero-width spaces where needed and generate `markdown` blocks for the remaining text.
   - If `preserve_visual_blank_lines=True`, replace internal blank lines in remaining `markdown` blocks with lines that contain only a non-breaking space before emitting the `markdown` block.
   - A remaining region whose formatted text would exceed Slack's 12,000-character `markdown` block limit is split into multiple `markdown` blocks using the rules in "Markdown block length splitting" below.

`convert_markdown_to_slack_messages` then splits the resulting block list to satisfy the "one table per message" rule, Slack's per-message block-count limit, and the per-message expansion-item and total-text budgets described in "Markdown block size splitting".
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
- Native richer blocks generated from unambiguous standalone Markdown constructs

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
- Bare URLs are wrapped into Slack-friendly `<https://...>` form before `markdown` block delivery. The URL is trimmed to its real extent first (GFM-style): it stops at a doubled emphasis run (`**`/`~~`), at code/angle/pipe markers (`` ` ``, `<`, `>`, `|`), and at CJK / full-width punctuation (`、` `。` `」` `）` `！` …); trailing punctuation (GFM's autolink set `! ? . , : * _ ~`, and an unbalanced `)`) is excluded — `;` and quotes are kept because they are URL-legal. A lone `*` (URL wildcards/queries) and CJK *letters* — including iteration marks like `々` (IRIs / Unicode IDN hosts such as `https://ja.wikipedia.org/wiki/人々`) — are preserved. This keeps a scheme URL glued directly to following CJK text — common in Japanese, where no space separates them — from greedily swallowing the rest of the line (including a closing `**`) into the autolink.
- Malformed Markdown tables are repaired before `table` block generation
- Unambiguous standalone Markdown constructs are promoted into native Slack blocks:
  - standalone image syntax `![alt](https://...)` to `image`
  - thematic-break lines to `divider`
  - fenced code blocks to `rich_text_preformatted`
  - simple one-level quotes to `rich_text_quote`
  - simple bullet and ordered lists to `rich_text_list`
    - Lists are promoted only when the list starts at the beginning of the text region or after a blank line, each non-blank line in the run is a list item, the list does not use ambiguous 1-3-space nested indentation, the item text does not rely on Markdown backslash escapes, and the run is not followed by an indented continuation paragraph.
    - Slack mention tokens inside a promoted list item are converted to their structured `rich_text` elements — `<@U…>`/`<@W…>` to `user`, `<#C…>`/`<#G…>` to `channel`, `<!subteam^S…>` to `usergroup`, and `<!here>`/`<!channel>`/`<!everyone>` to `broadcast` — since a `rich_text` block does not resolve a raw token. An optional `|label` display suffix is dropped (Slack renders the element from the id).
- Table-like rows inside fenced code blocks are kept out of table parsing
- Internal blank lines can optionally be rewritten into placeholder lines so Slack keeps visible paragraph separation
- Unsupported Slack angle-bracket tokens such as `<foo>` or raw HTML-like tags are neutralized in prose, while fenced code blocks and inline code spans keep them verbatim

## Slack text cleanup rules

Behavior of `sanitize_slack_text`:

- Remove ANSI escape sequences
- Remove general control characters except line breaks and tabs already preserved by the regex
- Remove this library's reserved internal marker code points (`U+2063`, `U+FFF0`–`U+FFF3`) so input cannot collide with the internal placeholder machinery
- Keep valid Slack angle-bracket tokens such as links, mentions, channels, special mentions, subteam mentions, and `<!date^...>`
- Replace unsupported angle-bracket tokens such as `<foo>` with full-width brackets (`＜foo＞`) so Slack does not interpret them as malformed special syntax
- This also applies to raw HTML-like tags such as `<div>` or `<span>`
- Angle-token neutralization applies only outside fenced code blocks and inline code spans, so code samples such as `` `<div>` `` reach Slack verbatim; ANSI/control/marker removal applies everywhere because those characters are never legitimate content
- For this purpose an inline code span is recognized within a single line only, and it closes only on a backtick run of the same length as the opener. A stray unpaired backtick therefore stays literal and cannot suppress sanitization of later lines, and an invalid angle token that spans a code span (`<foo `bar` baz>`) is still neutralized as a whole while the span content stays verbatim

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
- Only valid Slack angle tokens (links, mentions, `<!date^...>`) open a pipe-protected region; a bare `<` — such as the comparison in `x < y` or a threshold like `< 100ms` — stays literal and does not swallow later cell separators

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

The library inserts zero-width spaces (`U+200B`) only where they are needed to keep Slack's formatting boundaries intact, without changing the visible layout, for each formatting token below:

- `` `code` ``: inline code
- `**bold**`: bold
- `*italic*`: italic
- `~~strike~~`: strikethrough

Rules:

- The start and end of a chunk (a line/text boundary, or the edge of a fenced code block) are treated as safe; no zero-width space is added there.
- When an outer edge is tight against surrounding non-boundary text, only that edge is padded with a zero-width space. The safe (boundary) edge is left clean.
- When an emphasis marker (`**`, `*`, `~~`) sits directly against punctuation on its inner side (for example `**注意:**` or `**70.9%→83.0%**`), a zero-width space is inserted just *inside* the marker. This makes the marker's inner neighbor a non-punctuation character, so Slack's CommonMark right-/left-flanking check succeeds regardless of what surrounds the token — including before CJK text and CJK punctuation (`、` / `。`), which Slack does not accept as a flanking neighbor. Inline code spans are exempt from this rule because they do not obey flanking rules.
- Emphasis delimiters are recognized only when they satisfy CommonMark's minimal flanking rule: an opening run is not immediately followed by whitespace, and a closing run is not immediately preceded by whitespace. A stray, whitespace-flanked marker (for example the literal `**` in `閉じ ** が`), or an otherwise unbalanced marker, is left untouched. This prevents one dangling marker from shifting the pairing of nearby well-formed spans and misplacing their zero-width spaces.

Exception:

- If the token body is English-like text and its only tight neighbors are **ASCII** punctuation characters, the raw token is preserved. This avoids over-correcting spans such as `**APIYI (apiyi.com)**:` that Slack already renders correctly without extra zero-width spaces. A non-ASCII punctuation neighbor such as `、` or `。` is not preserved — it is protected by the inner zero-width space described above.

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

## Markdown block size splitting

Three Slack-side hard limits were measured against a real workspace on 2026-06-11:

- A `markdown` block's `text` accepts exactly 12,000 characters; 12,001 fails the whole `chat.postMessage` call with `msg_too_long`.
- Slack expands `markdown` blocks server-side into native blocks and enforces "no more than 50 items" on the expanded result per message (`invalid_blocks`). Each heading and each thematic break becomes its own item (50 headings were accepted, 51 rejected; 30 headings in each of two blocks were rejected together), while paragraphs, lists, quotes, and fenced code merge into one item per contiguous run between those breakers (60 blank-separated paragraphs and 52 fences were accepted). Blank lines alone do not split a run.
- One message's blocks may carry at most 13,200 characters of text in total — exactly 1.1 × the single-block limit; 13,201 fails with `msg_blocks_too_long`. The total counts content across block types (a 11,900-character `markdown` block plus a 1,400-character `rich_text` was rejected).

Long or heading-dense non-table regions are therefore split before delivery:

- The whole region is tried as a single block first; splitting happens only when the formatted text exceeds the character limit or the estimated expansion exceeds the per-message item budget
- Raw content is packed toward targets below the hard limits (11,500 characters, 45 estimated items), because zero-width-space insertion and placeholder lines inflate the formatted text and the item estimate is intentionally conservative
- Split points prefer paragraph boundaries (blank-line runs outside fenced code); the blank run at a chosen boundary is dropped, since adjacent Slack blocks already render visually separated
- A single paragraph longer than the budget is split at line boundaries, and a single overlong line at word boundaries, with a hard cut when no space exists (for example dense CJK text)
- When a cut lands inside an unclosed fenced code block, the continuation block re-opens the fence with the original delimiter line so both halves keep rendering as code
- Each piece is re-checked after formatting; when it still exceeds a hard limit, the packing budgets shrink and the piece is split again
- `convert_markdown_to_slack_messages` additionally packs blocks into messages so that the summed expansion estimate stays within the 50-item budget (non-`markdown` blocks count as one item each) and the summed block text stays within the 13,200-character per-message total
- The top-level fallback `text` field is not subject to the character limit (Slack truncates it instead of rejecting), so preview text is left whole

## Optional blank-line visibility workaround

When `preserve_visual_blank_lines=True` is passed to the main conversion APIs,
the parser rewrites internal blank-only lines in non-table Markdown segments
into lines that contain only a non-breaking space before emitting Slack `markdown`
blocks.

This workaround is intentionally narrow:

- Only blank lines between visible lines are rewritten
- Leading and trailing blank runs are left untouched
- Table segments are not modified by this option
- Blank runs immediately after list-item content are left untouched
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
