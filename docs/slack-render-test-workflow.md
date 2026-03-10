# Slack Render Test Workflow

This repository includes a minimal local workflow for validating how Slack
actually renders generated Block Kit `markdown` and `table` output.

## Files

- `docs/slack-render-test-app-manifest.yaml`
  - Minimal Slack App manifest for a test-only bot
- `.env.example`
  - Example local environment variables
- `scripts/post_slack_render_test.py`
  - Local CLI for posting test messages to Slack

## Local environment

Expected local-only environment variables:

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_TEST_CHANNEL_ID=CXXXXXXXX
```

`SLACK_BOT_TOKEN` is loaded from `.env` by default when using the script.

## Test channel

- Workspace: your Slack workspace
- Channel: your dedicated render-test channel
- Channel ID: e.g. `CXXXXXXXX`

The bot must already be installed and invited to the channel.

## Commands

Post a raw Slack `markdown` block without parser processing:

```bash
python scripts/post_slack_render_test.py \
  --mode raw \
  --text 'from **bold**.'
```

Post using `slack_markdown_parser`:

```bash
python scripts/post_slack_render_test.py \
  --mode parser \
  --text 'from **bold**.'
```

Preview generated payloads without calling Slack:

```bash
python scripts/post_slack_render_test.py \
  --mode parser \
  --text 'from **bold**.' \
  --dry-run
```

Post a markdown file:

```bash
python scripts/post_slack_render_test.py \
  --mode parser \
  --input-file tests/fixtures/llm_markdown_p0_corpus.md
```

Generate nested modifier matrix fixtures:

```bash
python scripts/generate_nested_modifier_matrix.py --content-variant plain
python scripts/generate_nested_modifier_matrix.py --content-variant parens
python scripts/generate_nested_modifier_matrix.py --content-variant quotes
```

Generate focused CJK nested-code fixtures:

```bash
python scripts/generate_nested_modifier_matrix.py \
  --content-variant plain \
  --locales ja,zh,ko \
  --inners plain,code \
  --output tests/fixtures/slack_cjk_inner_code_matrix.md
```

## Output

Each posted message prints JSON like:

```json
{
  "message_index": 1,
  "channel": "CXXXXXXXX",
  "ts": "1773051865.764719",
  "mode": "parser",
  "permalink": "https://your-workspace.slack.com/archives/CXXXXXXXX/p1234567890123456"
}
```

Use the `permalink` to open the exact message in Slack and verify rendering in the
web UI or via Playwright.

## Recommended comparison flow

1. Post the same markdown once with `--mode raw`.
2. Post the same markdown once with `--mode parser`.
3. Open both permalinks in Slack.
4. Compare visible rendering, especially for:
   - bold/italic/strike recognition
   - punctuation boundaries
   - Japanese vs English surrounding text
   - fallback text behavior when relevant

For desktop/mobile spot checks, use:

- `docs/slack-client-manual-checklist.md`
