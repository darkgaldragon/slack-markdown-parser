# Release Guide

## Versioning

This project follows SemVer:
- MAJOR: behavior/API breaking change
- MINOR: backward-compatible feature
- PATCH: backward-compatible fixes

## Pre-release Checklist

1. `ruff check .`
2. `black --check .`
3. `pytest -q`
4. `python -m build`
5. `twine check dist/*`
6. secret scan (working tree + full git history)
7. dependency audit (`pip-audit`)
8. changelog updated

## Publish to PyPI (Trusted Publishing)

1. Create tag: `vX.Y.Z`
2. Push tag to GitHub
3. GitHub Action `publish-pypi.yml` publishes via OIDC
4. The workflow generates PyPI attestations (signed provenance)
5. The workflow creates a GitHub Release with auto-generated notes and built artifacts

## Rollback

- If release is broken, publish next patch quickly (`X.Y.(Z+1)`) with fix.
- Avoid deleting published versions; use superseding patch release.

## Post-release

- Validate install in clean env:
  - `pip install slack-markdown-parser==X.Y.Z`
- Smoke-test with fixed markdown fixtures.
