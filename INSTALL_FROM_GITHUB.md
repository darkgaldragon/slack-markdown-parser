# Install from GitHub

Use this when you need unreleased commits before the next PyPI version.

日本語: PyPI公開前の変更を試すときの導入手順です。

## Install latest main

```bash
pip install "git+https://github.com/darkgaldragon/slack-markdown-parser.git@main"
```

## Install specific tag/commit

```bash
# tag
pip install "git+https://github.com/darkgaldragon/slack-markdown-parser.git@v2.0.0"

# commit
pip install "git+https://github.com/darkgaldragon/slack-markdown-parser.git@<commit-sha>"
```

## requirements.txt example

```txt
slack-markdown-parser @ git+https://github.com/darkgaldragon/slack-markdown-parser.git@main
```

## Verify

```bash
python - <<'PY'
from slack_markdown_parser import convert_markdown_to_slack_blocks
print(convert_markdown_to_slack_blocks("**hello**"))
PY
```

## Production recommendation

For reproducibility, prefer pinned PyPI versions in production:

```txt
slack-markdown-parser==2.0.0
```
