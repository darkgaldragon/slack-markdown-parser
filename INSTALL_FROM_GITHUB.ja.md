# GitHub からインストール

次の PyPI リリース前の変更を試したい場合に使います。

## main の最新を入れる

```bash
pip install "git+https://github.com/darkgaldragon/slack-markdown-parser.git@main"
```

## タグ/コミットを指定して入れる

```bash
# タグ
pip install "git+https://github.com/darkgaldragon/slack-markdown-parser.git@v2.0.0"

# コミット
pip install "git+https://github.com/darkgaldragon/slack-markdown-parser.git@<commit-sha>"
```

## requirements.txt 記述例

```txt
slack-markdown-parser @ git+https://github.com/darkgaldragon/slack-markdown-parser.git@main
```

## 動作確認

```bash
python - <<'PY'
from slack_markdown_parser import convert_markdown_to_slack_blocks
print(convert_markdown_to_slack_blocks("**hello**"))
PY
```

## 本番運用の推奨

本番は再現性のため PyPI バージョン固定を推奨します:

```txt
slack-markdown-parser==2.0.0
```
