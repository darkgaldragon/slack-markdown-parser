# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Removed internal code-review report from published docs to keep OSS documentation user-focused.
- Added `docs/README.md` as a documentation index for public references.
- Updated README code sample to use environment variable token input (`SLACK_BOT_TOKEN`).

## [2.0.0] - 2026-03-05

### Added
- Public API for production use:
  - `convert_markdown_to_slack_blocks`
  - `convert_markdown_to_slack_messages`
  - `build_fallback_text_from_blocks`
  - `blocks_to_plain_text`
  - `normalize_markdown_tables`
  - `add_zero_width_spaces_to_markdown`
  - `decode_html_entities`
  - `strip_zero_width_spaces`
- Full parser behavior spec in `docs/spec.md`.
- OSS governance docs: `SECURITY.md`, `SUPPORT.md`, `RELEASE.md`, `CODE_OF_CONDUCT.md`.
- CI pipelines for lint/test/security/package checks.

### Changed
- Distribution strategy is now PyPI-first (Layer is optional).
- Converter upgraded to normalize malformed tables and stabilize Slack rendering.
- Zero-width-space handling now preserves code fences/inline code segments.
- README and contributor docs rewritten for public OSS usage (English first + Japanese support).

### Security
- Secret scanning and dependency audit gates added to CI.
- `.gitignore` tightened for generated artifacts and credential files.

## [1.0.0] - 2025-11-25

### Added
- Initial release with markdown/table conversion.
