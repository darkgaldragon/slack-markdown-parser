# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and the project follows Semantic Versioning.

## [Unreleased]

### Added

- Added a contributor guide, issue templates, and a pull request template.
- Added the `py.typed` marker and packaging rules for docs and tests in source distributions.
- Added an automated LLM-style Markdown corpus fixture and smoke tests.

### Changed

- CI now runs the test suite on Python 3.10, 3.11, 3.12, and 3.13.
- `.gitignore` no longer ignores the entire `tests/` directory, so new tests and sample fixtures can be tracked.
- Clarified the documented conversion pipeline and Slack-oriented behavior in both specs.

### Fixed

- Normalized underscore emphasis (`_..._`, `__...__`) into Slack-compatible asterisk emphasis while preserving snake_case, escaped underscores, URLs, code spans, and links.

## [2.2.0] - 2026-03-07

### Added

- Added public regression coverage for LLM-like Markdown corpus inputs.

### Changed

- Refreshed the English and Japanese behavior specs to reflect the current conversion pipeline and Slack compatibility rules.

### Fixed

- Converted underscore emphasis into Slack-compatible asterisk emphasis in both markdown blocks and table cells without touching protected spans such as code, links, or bare URLs.

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
