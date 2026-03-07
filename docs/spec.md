# Parser Behavior Specification

This document defines the conversion behavior of `slack-markdown-parser`.

## Input

- A UTF-8 Markdown string
- Malformed tables, HTML entities, and mixed plain text are accepted

## Output

- Slack Block Kit blocks (`markdown` / `table`)
- When the input contains multiple tables, a list of messages that satisfies the "one table per message" rule

## Conversion pipeline

Processing order in `convert_markdown_to_slack_blocks`:

1. HTML entity decode: restore entities such as `&gt;` and `&amp;`
2. Slack text sanitize: remove ANSI/control noise and neutralize invalid Slack angle-bracket tokens
3. Underscore emphasis normalization: canonicalize `_..._` / `__...__` into `*...*` / `**...**` where Slack needs compatibility, while preserving snake_case-like identifiers and protected spans such as code, links, angle tokens, and bare URLs
4. Table normalization: repair malformed table syntax according to the rules below
5. Segment split: divide the text into table regions (consecutive lines containing `|`) and non-table regions
6. Block generation:
   - Table regions: parse inline cell styling and generate a `table` block. If conversion fails, such as when there are fewer than two candidate lines or the parse result is empty, fall back to a `markdown` block.
   - Non-table regions: add ZWSP where needed and generate a `markdown` block

`convert_markdown_to_slack_messages` then splits the resulting block list to satisfy the "one table per message" constraint.
`convert_markdown_to_slack_payloads` returns the same split blocks plus fallback `text` values ready for `chat.postMessage`.

## Slack text sanitize rules

Behavior of `sanitize_slack_text`:

- Remove ANSI escape sequences
- Remove general control characters except line breaks and tabs already preserved by the regex
- Keep valid Slack angle-bracket tokens such as links, mentions, channels, special mentions, subteam mentions, and `<!date^...>`
- Replace unsupported angle-bracket tokens such as `<foo>` with full-width brackets (`＜foo＞`) so Slack does not interpret them as malformed special syntax
- This includes raw HTML-like tags such as `<div>` or `<span>`, which are neutralized instead of being passed through as Slack special syntax

## Underscore emphasis normalization rules

Behavior of underscore emphasis normalization:

- Convert `__text__` to `**text**` when the underscores behave like emphasis markers
- Convert `_text_` to `*text*` when the underscores behave like emphasis markers
- Do not convert underscore runs that are attached to ASCII word characters, so identifiers such as `foo_bar_baz` stay unchanged
- Do not convert escaped forms such as `\_not italic\_`
- Do not convert inside protected spans: fenced code, inline code, Markdown links, angle-bracket tokens, and bare URLs

## Table normalization rules

LLMs often emit tables with omitted outer pipes, missing separator rows, or inconsistent column counts. Passing those directly to Slack `table` blocks can trigger `invalid_blocks`, so `normalize_markdown_tables` repairs them first.

### Table candidate detection

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

### Preserving literal pipes inside cells

- Treat pipes inside Slack links such as `<url|text>` as literal content, not as cell separators
- Treat pipes inside inline code `` `...` `` as literal content, not as cell separators
- Treat escaped pipes `\|` as literal content and remove the backslash in the final displayed text

## Table cell styling

Inside table cells, the following inline styles are recognized and converted into Slack `rich_text` styling:

| Syntax | Style |
|---|---|
| `__text__` | normalized to bold |
| `**text**` | bold |
| `_text_` | normalized to italic |
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

## ZWSP insertion rules

Behavior of `add_zero_width_spaces_to_markdown`:

### Purpose

In languages such as Japanese that do not use spaces between words, formatting markers can attach directly to surrounding characters and break Slack rendering. This library inserts zero-width spaces instead of visible spaces so Slack gets clearer formatting boundaries without changing the visible layout.

### Target patterns

For each formatting token below, if either adjacent side is not a space, tab, newline, or existing ZWSP, or if the token touches the start or end of a line, the whole token is wrapped in ZWSP (`U+200B`) so Slack recognizes it as a standalone formatting boundary:

- `` `code` ``: inline code
- `**bold**`: bold
- `*italic*`: italic
- `~~strike~~`: strikethrough

### Excluded regions

- Fenced code blocks (`` ``` ... ``` ``) are never modified
- Inline code (`` `...` ``) is not excluded; it is part of the target set above

## ZWSP removal rules

`strip_zero_width_spaces` is called when generating table cells and fallback text so that control characters inserted by this library do not leak into plain output.

### Removed characters

| Code point | Name | Reason |
|---|---|---|
| `U+200B` | ZWSP (zero-width space) | Inserted by this library for formatting stability |
| `U+FEFF` | BOM (byte order mark) | Unwanted encoding artifact |

### Preserved characters

| Code point | Name | Reason |
|---|---|---|
| `U+200C` | ZWNJ (zero-width non-joiner) | Used for word-shape control in languages such as Persian and Hindi |
| `U+200D` | ZWJ (zero-width joiner) | Required for joined emoji and other grapheme composition |

## Fallback text

`build_fallback_text_from_blocks` generates preview text for `chat.postMessage.text` as follows:

- `markdown` blocks: text with ZWSP removed
- `table` blocks: join each row's cell text with ` | `
- Join block outputs with blank lines between them

For table-cell links, fallback text uses the link label if present, otherwise the URL.

## Determinism

For the same input, the library always returns the same output regardless of environment.

## Non-goals

- Generating Slack `mrkdwn` strings
- Reconstructing a full Markdown AST
- Matching HTML rendering behavior
