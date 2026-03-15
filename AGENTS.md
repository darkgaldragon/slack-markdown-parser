# Repository Guidelines

## Project Structure & Module Organization
`slack_markdown_parser/` contains the library code. Most behavior lives in `slack_markdown_parser/converter.py`, and `slack_markdown_parser/__init__.py` re-exports the public API. Tests live in `tests/`, currently centered in `tests/test_converter.py`. Behavior docs are in `docs/spec.md` and `docs/spec-ja.md`; user-facing package docs live in `README.md` and `README-ja.md`. Real-Slack validation helpers live in `scripts/post_slack_render_test.py` and `docs/slack-render-test-workflow.md`. Image assets are stored at the repo root (`Example_*.png`) and under `docs/images/`.

## Build, Test, and Development Commands
Set up a local environment with:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Use these checks before opening a PR:

```bash
python -m pytest -q          # run unit tests
python -m ruff check .       # lint and import order
python -m black --check .    # formatting check
python -m build              # build sdist and wheel
```

CI runs tests on Python 3.10-3.13 and builds the package on Python 3.12.

## Coding Style & Naming Conventions
Target Python 3.10+ and keep code `black`-formatted with an 88-character line length. `ruff` enforces core error, import, upgrade, and bugbear rules. Follow existing naming patterns: `snake_case` for functions, variables, and test names; `UPPER_CASE` for module constants like `ZWSP`. Keep public API updates synchronized between `converter.py` and `__init__.py`.

## Testing Guidelines
Add or update `pytest` coverage whenever parsing behavior changes, especially table normalization, ZWSP handling, fallback text, or Slack block splitting. Name tests `test_<behavior>()` and prefer small Markdown fixtures inline in the test body. If behavior changes are user-visible, update the relevant spec or README example in the same PR. When a change depends on Slack's own renderer behavior, re-run the raw-vs-parser Slack validation workflow on the target workspace because richer `markdown` rendering remains rollout-dependent.

## Commit & Pull Request Guidelines
Recent history mostly follows Conventional Commit prefixes such as `docs:`, `ci:`, and `chore:`; use that style when possible. Keep commits focused and describe the user-facing effect. PRs should include a short summary, testing results, and note whether README/spec updates were needed. When relevant, add a brief changelog note in the PR description and call out backward-compatibility or public API changes explicitly.
