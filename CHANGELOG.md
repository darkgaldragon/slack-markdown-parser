# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and the project follows Semantic Versioning.

## [Unreleased]

### Changed

- Documented Slack's March 6, 2026 richer `markdown` block rollout as rollout-dependent in the README and behavior specs, so headers and raw Markdown tables are no longer described as universally stable.
- Extended `scripts/post_slack_render_test.py` with `--transport raw_http|slack_sdk` to compare Web API posting paths while keeping the same markdown payload generation.

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
