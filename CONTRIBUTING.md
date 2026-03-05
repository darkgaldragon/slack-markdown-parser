# Contributing

Thanks for contributing to `slack-markdown-parser`.

日本語: コントリビュート歓迎です。以下の手順に沿ってください。

## Development Setup

```bash
git clone https://github.com/darkgaldragon/slack-markdown-parser.git
cd slack-markdown-parser
pip install -e ".[dev]"
```

## Local Checks

```bash
ruff check .
black --check .
pytest -q
python -m build
twine check dist/*
```

## Pull Request Rules

1. Keep changes focused and testable.
2. Add/adjust tests for behavior changes.
3. Update docs when public behavior changes.
4. Do not commit secrets, local artifacts, or generated zips.
5. Ensure CI is green before requesting review.

## Commit Guidance

- Use clear, descriptive commit messages.
- Mention behavior impact (parsing, fallback, compatibility) in PR body.

## Security

- Never commit tokens/keys/credentials.
- Run secret scans locally when possible.
- Follow [SECURITY.md](SECURITY.md) for disclosure/reporting.

## Code Style

- Python 3.10+
- Type hints where practical
- Keep parser behavior deterministic

## Questions

Open a discussion/issue via [SUPPORT.md](SUPPORT.md).
