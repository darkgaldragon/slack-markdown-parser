# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and the project follows Semantic Versioning.

## [Unreleased]

### Fixed

- Stopped bare-URL autolinking from greedily swallowing trailing text. `normalize_bare_urls_for_slack_markdown` matched `https?://[^\s<]+`, so a scheme URL glued directly to following CJK text (e.g. `(https://example.com)**。に句点を直結。`) — common in Japanese, which puts no space after a URL — captured the closing paren, the `**` markers, the CJK punctuation, and the rest of the sentence into one `<…>` autolink, over-extending the link and exposing the literal `**`. The matched URL is now trimmed GFM-style: it stops at CJK letters/punctuation and emphasis/code/angle markers (`*`, `` ` ``, `<`, `>`, `|`), and trailing punctuation (`. , ; : ! ?` and an unbalanced `)`) is dropped while balanced parentheses are kept.

## [2.4.2] - 2026-05-29

### Fixed

- Stopped an unbalanced emphasis delimiter from corrupting unrelated, well-formed spans in the same block. The bold/italic/strikethrough patterns are matched with `re.DOTALL`, so a single stray `**` (for example a whitespace-flanked literal `**` in `閉じ ** が`, or an unclosed marker) shifted marker pairing across the whole block and flipped the protective ZWSP of nearby punctuation-terminated bold to the broken *outer* position, re-exposing the literal markers on Slack. `EMPHASIS_PATTERNS` now enforces CommonMark's minimal flanking requirement — an opening run is not followed by whitespace and a closing run is not preceded by whitespace — so a non-flanking stray marker stays literal and no longer disturbs its neighbours.
- Bounded the `**` and `~~` emphasis bodies to a single delimiter run so a dangling opener with no valid closer of its own (for example `**oops **` or `**: x **` before a later `**…%**`) can no longer scan past the literal stray and steal a following well-formed span's closing marker, which had misplaced that span's protective ZWSP. The single-`*` italic body is intentionally left unbounded because italics legitimately wrap `**bold**`.

## [2.4.1] - 2026-05-29

### Fixed

- Stopped punctuation-terminated emphasis from leaking its literal markers (`**`, `*`, `~~`) in `markdown` blocks. A ZWSP placed just outside a closing marker broke Slack's CommonMark right-flanking check whenever the last inner character was punctuation (e.g. `- **項目:**` at a line end, or `**70.9%→83.0%**、` before CJK punctuation), exposing the raw markers. Chunk boundaries are now treated as safe so no stray ZWSP is appended at line/text ends, and when a marker sits against inner punctuation a ZWSP is inserted just inside it so the run flanks via rule 2a regardless of the following character — including before CJK text and CJK punctuation that Slack does not accept as a flanking neighbor.
- Stopped preserving English-like punctuation-flanked emphasis raw when its tight neighbor is non-ASCII punctuation (e.g. `**APIYI (apiyi.com)**。` or `Score **70.9%→83.0%**、`). Slack only accepts ASCII punctuation/whitespace as a flanking neighbor, so these now receive the inner ZWSP protection instead of being emitted unchanged.

## [2.4.0] - 2026-05-14

### Added

- Added automatic richer Block Kit output for unambiguous standalone Markdown constructs, including image blocks, dividers, fenced code, simple quotes, and simple lists, while leaving Markdown headings in `markdown` blocks so Slack can preserve heading levels.

### Documentation

- Documented the Slack mobile `markdown` block limitation where list-item continuation lines are re-prefixed with the list marker, and linked the tracking issue so users can check upstream status instead of expecting a parser-side workaround.

## [2.3.2] - 2026-04-17

### Fixed

- Stopped `preserve_visual_blank_lines` from keeping ordered-list context open after list items, including continued items, nested lists, and ordered-list paragraph interruption edge cases.
- Avoided false-positive list-context detection for indented non-list lines and thematic breaks, so visible blank-line preservation no longer regresses on inputs like `    1. not-a-list` or `- - -`.

## [2.3.1] - 2026-04-10

### Fixed

- Stopped `preserve_visual_blank_lines` from inserting visual-only blank-line placeholders inside fenced code blocks.
- Kept fallback plain text stable when visual blank-line placeholders are enabled alongside parser-added spacing markers around emphasis or inline code.

## [2.3.0] - 2026-04-10

### Changed

- Documented Slack's March 6, 2026 richer `markdown` block rollout as rollout-dependent in the README and behavior specs, so headers and raw Markdown tables are no longer described as universally stable.
- Updated maintainer docs with the April 8, 2026 Slack Web rollout observations, including native headers/dividers/task lists/raw Markdown tables and the current blank-line spacing limitation.
- Extended `scripts/post_slack_render_test.py` with `--transport raw_http|slack_sdk` to compare Web API posting paths while keeping the same markdown payload generation.
- Split public docs from maintainer QA docs in README / CONTRIBUTING and labeled render-check workflow notes as maintainer-facing rather than end-user package docs.
- Further reduced README-to-QA coupling by moving maintainer QA doc links behind CONTRIBUTING so the main README stays focused on the public package surface.

### Added

- Added an opt-in `preserve_visual_blank_lines` argument to the main conversion APIs so parser callers can compensate for Slack's currently tight paragraph spacing inside `markdown` blocks without changing fallback plain text.

## [2.2.5] - 2026-03-14

### Fixed

- Preserved raw English-like emphasis when it only touches surrounding punctuation, avoiding unnecessary ZWSP around cases such as `**APIYI (apiyi.com)**:` that Slack already renders correctly on its own.

## [2.2.4] - 2026-03-11

### Changed

- Published a follow-up release so the packaged artifacts match the merged 2.2.3 source changes exactly.

### Fixed

- Preserved multi-backtick inline-code spans when splitting table cells and heading-plus-table lines, so pipes inside code spans no longer break parsing.
- Extended Slack table rich-text cell conversion to keep multi-backtick code spans intact in rendered table cells.
- Reduced fallback text generation overhead by removing the redundant second plain-text pass during payload assembly.
- Simplified nested modifier formatting internals so placeholder handling scales more predictably on long messages.

## [2.2.3] - 2026-03-11

### Changed

- Reduced fallback text generation overhead by removing the redundant second plain-text pass during payload assembly.
- Simplified nested modifier formatting internals so placeholder handling scales more predictably on long messages.

### Fixed

- Preserved multi-backtick inline-code spans when splitting table cells and heading-plus-table lines, so pipes inside code spans no longer break parsing.
- Extended Slack table rich-text cell conversion to keep multi-backtick code spans intact in rendered table cells.

## [2.2.2] - 2026-03-10

### Added

- Added Slack render-test tooling, generated regression fixtures, and maintainer docs for validating real Slack client rendering across Web, desktop, and mobile.

### Changed

- Refreshed the README and behavior spec to distinguish Slack renderer limitations from parser-owned normalization and repair behavior.
- Clarified locale-aware formatting behavior and added public examples for the Slack render-test workflow.

### Fixed

- Stabilized nested inline-code emphasis rendering across English, Japanese, Chinese, and Korean contexts, including existing-ZWSP boundaries and CJK italic/strike cases.
- Preserved user-authored spacing in fallback text while removing parser-inserted rendering-only padding.
- Wrapped bare URLs into Slack-friendly autolink form before sending `markdown` blocks so adjacent lines no longer collapse into malformed angle-link text.

## [2.2.1] - 2026-03-07

### Changed

- Normalized underscore emphasis (`_..._`, `__...__`) into Slack-compatible asterisk emphasis before table parsing.
- Excluded fenced code blocks from table normalization and segment splitting so table-like rows inside code fences stay in `markdown` blocks.
- Extended fenced-code preservation to tilde fences (`~~~ ... ~~~`) when inserting ZWSP.
- Improved heading-plus-table rescue so inputs like `### Heading ... Header A | Header B` preserve multi-word first header cells more naturally.

## [2.0.2] - 2026-03-06

### Changed

- Improved public API wording and refreshed the English and Japanese README files.
- Clarified project scope for `mrkdwn`-only clients and fallback text behavior.
- Refined validation samples and screenshots in the documentation.

### Fixed

- Improved ZWSP padding around punctuation-adjacent Markdown.
- Expanded parser edge-case handling and related documentation.

## [2.0.1] - 2026-03-05

### Added

- Added initial GitHub Actions coverage for tests and package builds.
- Added OSS-facing documentation and a real rendering example in the README.

### Changed

- Trimmed the repository to the core distributable package and refreshed maintainer contact details.
- Updated GitHub Actions dependencies to newer major versions.

### Fixed

- Added ZWSP padding for inline code markers when adjacent to surrounding text.

## [2.0.0] - 2026-03-05

### Added

- Published the packaged OSS release of `slack-markdown-parser`.
- Added packaging metadata, documentation, and review/reference materials for the open-source release.
