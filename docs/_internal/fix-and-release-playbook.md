# Maintainer Fix & Release Playbook

End-to-end workflow for landing a rendering fix and shipping a release, written
so a maintainer does not have to rediscover the repo's branch-protection rules,
CI gates, and Trusted-Publisher tagging each time.

This is maintainer-facing QA guidance, not part of the public package contract.
Keep every example placeholder-only (no real tokens, workspace URLs, channel
IDs, or permalinks).

## 0. TL;DR

```
verify (local -> Slack -> screenshot)  ->  fix + tests
  ->  local gate: pytest / ruff / black --check / build
  ->  PR to main -> CI green -> resolve ALL review threads -> squash-merge
  ->  Release PR (version bump + CHANGELOG) -> squash-merge
  ->  push annotated tag vX.Y.Z  (this PUBLISHES to PyPI + cuts the GitHub Release)
```

## 1. Verify a rendering bug empirically (do not trust the report)

Slack's `markdown` block renderer has behavior that is not obvious from reading
the parser. Always confirm against a real workspace before changing code.

1. Write a minimal Markdown sample that isolates one variable per line.
2. Send it with `scripts/post_slack_render_test.py` (see
   `slack-render-test-workflow.md` for setup and the test-bot manifest):
   - `--mode parser` — output of `convert_markdown_to_slack_payloads` (the real pipeline).
   - `--mode raw` — your text sent verbatim as one `markdown` block. Use this to
     control ZWSP placement byte-for-byte when isolating Slack's own rules.
   - `--dry-run` — print the generated payloads/blocks (and ZWSP positions)
     without posting. Always dry-run first.
3. Capture the rendered result (screenshot) and compare against a written
   prediction. A prediction that matches is your root-cause evidence.

Tip: render-relevant differences are easy to mistake for content differences.
For emphasis bugs, the deciding factors are the character *immediately inside*
the marker and the character *immediately outside* it — not which punctuation
mark it is. See "Appendix: emphasis flanking" and `docs/spec.md`.

## 2. Local gate (run before every push)

The CI `Lint` job runs **both** `ruff` and `black --check`. Running only `ruff`
locally is the most common reason a green-looking change fails CI.

```bash
python -m pytest -q
python -m ruff check .
python -m black --check .   # CI fails if this would reformat anything
python -m build
```

If `black --check` complains, run `python -m black .` and commit the reflow as a
separate "Apply black formatting" commit (no behavior change).

## 3. Fix PR to `main`

`main` is a protected branch. Push a feature branch and open a PR; you cannot
push to `main` directly.

Branch protection on `main` (verify with
`gh api repos/<owner>/<repo>/branches/main/protection`):

- **Required status check:** a single aggregate context named `test` that gates
  on the matrix jobs. If `Lint` or any `Test (Python 3.x)` fails, `test` fails
  and the PR is `BLOCKED`.
- **`required_conversation_resolution: true`** — every review thread (including
  Copilot / Codex inline comments) must be **resolved** before the PR is
  mergeable. CI can be fully green and the PR will still show
  `mergeStateStatus: BLOCKED` until threads are resolved.
- **`required_approving_review_count: 0`** — no human approval is required.
- **`enforce_admins: true`** — admins are not exempt; `--admin` does not bypass
  these rules. Resolve the threads instead.

Handling bot reviews (Copilot / Codex):

1. Read them: `gh pr view <n> --json reviews` and
   `gh api repos/<owner>/<repo>/pulls/<n>/comments`.
2. Address valid findings in code, push, and reply on the PR. Re-trigger Codex
   with a `@codex review` comment if useful.
3. Resolve each thread (no CLI command; use GraphQL):

   ```bash
   gh api graphql -f query='query { repository(owner:"<owner>", name:"<repo>") {
     pullRequest(number: <n>) { reviewThreads(first:50) {
       nodes { id isResolved path comments(first:1){nodes{author{login}}} } } } }'
   # then for each thread id:
   gh api graphql -f query='mutation { resolveReviewThread(input:{threadId:"<id>"}){ thread { isResolved } } }'
   ```

4. Confirm `gh pr view <n> --json mergeStateStatus` is `CLEAN`, then
   `gh pr merge <n> --squash --delete-branch` (squash is the repo convention;
   merge commits read `<title> (#<n>)`).

## 4. Release (publishing is tag-triggered)

`.github/workflows/publish.yml` runs on pushing a `v*` tag and **publishes to
PyPI** via Trusted Publisher, then creates the GitHub Release. A tag is a public,
irreversible publish — not just a label.

Pushing a tag alone is **not** enough and is in fact wrong: `python -m build`
reads the version from `pyproject.toml`, so a tag must point at a commit whose
version was already bumped. Otherwise you get a `vX.Y.(N+1)` tag attached to
`X.Y.N` artifacts.

Release steps (mirrors prior `Release vX.Y.Z (#NN)` commits):

1. Branch `release/vX.Y.Z` off the up-to-date `main`.
2. Bump the version in **both** places (they must match):
   - `pyproject.toml` -> `version = "X.Y.Z"`
   - `slack_markdown_parser/__init__.py` -> `__version__ = "X.Y.Z"`
3. In `CHANGELOG.md`, insert a dated section header so the accumulated
   `## [Unreleased]` entries become `## [X.Y.Z] - YYYY-MM-DD` (leave an empty
   `## [Unreleased]` above it).
4. Choose the bump with SemVer: Fixed-only -> patch; new behavior -> minor.
5. Run the local gate (section 2), commit as `Release vX.Y.Z`, open a PR to
   `main`, let CI pass, resolve any threads, squash-merge.
6. Tag the merged release commit on `main` and push the tag:

   ```bash
   git checkout main && git pull --ff-only
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

7. Watch the publish workflow:

   ```bash
   gh run watch "$(gh run list --workflow=publish.yml -L1 --json databaseId --jq '.[0].databaseId')" --exit-status
   ```

   In the log, the step `Skip publish because version already exists` shows `-`
   (skipped) for a genuinely new version, and `Publish to PyPI` shows `✓`. The
   workflow is idempotent: if the version is already on PyPI it skips the upload
   and still creates/updates the GitHub Release.

8. Confirm:
   - `gh release view vX.Y.Z` (not draft, not prerelease, latest)
   - PyPI shows `X.Y.Z` as latest.

Never publish with `twine upload`, `uv publish`, or a local PyPI token — Trusted
Publishing only.

## 5. Recurring gotchas

- Green `ruff` locally but red CI `Lint` -> you skipped `black --check`.
- All `Test (Python 3.x)` green but the `test` check and PR are red/BLOCKED ->
  it is the aggregate gate failing because another required job (usually `Lint`)
  failed, or there is an unresolved review thread.
- A tag push is a PyPI publish. Bump the version first, via a release PR.
- Keep `docs/spec.md` and `docs/spec-ja.md` in sync whenever the
  ZWSP/normalization rules change — reviewers check for this.

## Appendix: emphasis flanking (why the ZWSP rules exist)

Slack's `markdown` block follows CommonMark delimiter-run flanking. A closing
`**` only closes when it is right-flanking: if the character before it is
punctuation, the character after it must be whitespace **or ASCII punctuation**.

Observed Slack specifics (confirmed via the section-1 loop):

- A ZWSP (`U+200B`) placed just *outside* a closing marker is neither whitespace
  nor punctuation, so `**...:**​` fails the check and exposes the literal `**`.
- Slack accepts ASCII punctuation/whitespace as a flanking neighbor but **not**
  CJK punctuation (`、` / `。`), so `**70.9%→83.0%**、` is exposed regardless of
  ZWSP placement.
- CJK *content* emphasis (`本文**強調**です`) closes on its own; the last inner
  char is not punctuation.

The fix used by `wrap_match` / `_should_preserve_raw_punctuation_emphasis`:
treat chunk boundaries as safe, pad only the tight outer edge, and when a marker
is against inner punctuation insert a ZWSP *inside* the marker so it flanks via
CommonMark rule 2a regardless of what follows. ASCII-punctuation-flanked English
spans stay raw (Slack renders them). Inline code spans are exempt (no flanking
rules). Full rules: `docs/spec.md` / `docs/spec-ja.md`.
