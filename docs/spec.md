# Parser Behavior Specification

This document defines deterministic behavior for `slack-markdown-parser` v2.x.

## Input

- UTF-8 markdown string
- May contain malformed tables, HTML entities, and mixed plain text

## Output

- Slack Block Kit blocks (`markdown` / `table`)
- For multi-table input: message groups with max one table per message

## Conversion Pipeline

1. Decode HTML entities (`&gt;`, `&amp;`, ...)
2. Normalize markdown tables
3. Segment markdown into table and non-table regions
4. Convert table segments to Slack `table` blocks
5. Convert text segments to Slack `markdown` blocks
6. Add zero-width-space around markdown decorators (outside code)
7. Split blocks by table constraint

## Table Normalization Rules

- Requires at least 2 candidate rows to be recognized as table block
- Header/rows are pipe-completed (`|...|`) if needed
- Separator row is generated when missing
- Row columns are padded/truncated to header width
- Empty cell values become `-`
- Heading+table single line (`# H |a|b|`) is split into heading + table row

## Table Cell Styling

Within table cells, parser recognizes:
- `**bold**`
- `*italic*`
- `~~strike~~`
- `` `code` ``

Unsupported nested/complex syntax is preserved as plain text.

## Markdown Decoration Stability

`add_zero_width_spaces_to_markdown` inserts ZWSP around decoration markers for stable Slack rendering.

Exclusions:
- fenced code blocks
- inline code segments

## Fallback Text

`build_fallback_text_from_blocks` reconstructs readable plain text:
- markdown blocks => text (ZWSP stripped)
- table blocks => rows joined by ` | `

## Determinism

Given identical input, output blocks must be stable across environments.

## Non-goals

- `mrkdwn` output generation
- full markdown AST fidelity
- HTML rendering semantics
