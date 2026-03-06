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
For exploratory checks, you can also use `tests/test_markdown_edge_cases.md` as a manual sample input.

## Pull requests

- Keep changes focused and explain the user-facing impact.
- Add or update tests when parser behavior changes.
- Update `README.md`, `README-ja.md`, or `docs/spec*.md` when public behavior or examples change.
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
