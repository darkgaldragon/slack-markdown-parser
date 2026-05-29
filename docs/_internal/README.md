# Internal Maintainer Docs

This directory keeps only the maintainer documents that are still useful to
contributors in the public repository.

The rule is simple:

- Keep reproducible checklists and workflows here.
- Keep generic setup assets here when they are required by those workflows.
- Keep all examples placeholder-only so the public repository never exposes real tokens, workspace URLs, channel IDs, or permalinks.
- Do not keep exploratory notes, ambiguous observations, or project-specific
  planning memos here.

If a note is not something another maintainer can reliably rerun or follow, it
belongs in a private workspace rather than in the public repository.

Current contents:

- `fix-and-release-playbook.md` — end-to-end flow: verify a rendering bug, land the fix, and cut a release (branch protection, CI gates, Trusted-Publisher tagging)
- `slack-render-test-workflow.md`
- `slack-client-manual-checklist.md`
- `slack-render-test-app-manifest.yaml`
