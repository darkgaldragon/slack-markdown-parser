# Contributing

Thanks for your interest in improving `slack-markdown-parser`.
Small fixes, bug reports, documentation updates, and tests are all welcome.
English and Japanese contributions are both welcome.

## Development setup

This project supports Python 3.10 through 3.13.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Local checks

Run these commands before opening a pull request:

```bash
python -m pytest -q
python -m ruff check .
python -m black --check .
python -m build
```

If you are changing Markdown parsing behavior, please add or update automated tests in `tests/`.

## Maintainer QA docs

The following documents are maintainer-facing QA references for validating real
Slack renderer behavior. They are not part of the public package contract and
are intentionally linked from CONTRIBUTING rather than from the main README.

Keep any examples in those docs scrubbed for the public repository:

- use placeholder-only values for tokens, channel IDs, permalinks, and workspace URLs
- never commit real `.env` contents or workspace-specific test notes
- keep exploratory notes in a private workspace, not under `docs/_internal/`

If your change depends on Slack's own renderer behavior, review these docs as
needed:

- `docs/_internal/slack-render-test-workflow.md`
- `docs/_internal/slack-client-manual-checklist.md`
- `docs/_internal/slack-render-test-app-manifest.yaml`

## Pull requests

- Keep changes focused and explain the user-facing impact.
- Add or update tests when parser behavior changes.
- Update `README.md`, `README-ja.md`, or `docs/spec*.md` when public behavior or examples change.
- Keep maintainer-only QA docs consistent with the public docs when renderer assumptions change.
- Conventional Commits are encouraged for commit messages, but not required for contributors.
- Make sure CI passes before requesting review.

## Reporting issues

Use the GitHub issue templates when possible.
Helpful reports usually include:

- A short description of the problem
- A minimal Markdown sample that reproduces it
- Expected output and actual output
- Python version and installation method
- Slack rendering details if the issue is UI-specific

## Release notes

Project maintainers keep release history in `CHANGELOG.md`.
If your pull request affects users, please include a short changelog note in the PR description.

## Maintainer releases

Package publishing is handled by GitHub Actions Trusted Publishing only.
Maintainers should create or update the changelog, create an annotated tag like
`v2.3.2`, and push the tag to GitHub.

Do not publish with `twine upload`, `uv publish`, or a local PyPI API token for
this repository. If a tag points to a version that is already present on PyPI,
the publish workflow now skips the upload and still creates the matching GitHub
Release so the repository release list stays current.
