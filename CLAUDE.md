# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

slack-markdown-parser は、LLMが生成する標準Markdownを Slack Block Kit の `markdown` / `table` ブロックに変換する Python ライブラリ。外部依存ゼロ、Python 3.10+ 対応。PyPI パッケージ名: `slack-markdown-parser`。

Slack の `markdown` renderer は 2026-03-06 以降 richer な構文を公式案内しているが、workspace / surface ごとの rollout 差が残る。見出し・水平線・raw Markdown table などの実表示は、`scripts/post_slack_render_test.py` と `docs/slack-render-test-workflow.md` を使って実機確認すること。

## Commands

```bash
# 開発環境セットアップ
pip install -e ".[dev]"

# テスト実行
pytest
pytest tests/test_converter.py::test_名前  # 単一テスト

# Lint & Format
ruff check .
black --check .
black .          # 自動フォーマット

# パッケージビルド
python -m build

# 実機 Slack render テスト
python scripts/post_slack_render_test.py --mode parser --transport raw_http --input-file docs/example.md
python scripts/post_slack_render_test.py --mode parser --transport slack_sdk --input-file docs/example.md
```

## Architecture

すべての変換ロジックは `slack_markdown_parser/converter.py` の単一ファイルに実装されている。`__init__.py` はパブリックAPIの再エクスポートのみ。

### 変換パイプライン (`convert_markdown_to_slack_blocks`)

```
入力Markdown
  → decode_html_entities()        # &gt; &amp; 等のデコード
  → normalize_markdown_tables()   # テーブル構文の修復（パイプ補完、セパレータ生成、列数統一）
  → split_markdown_into_segments()# テキスト/テーブル領域に分割
  → ブロック生成:
      テーブル領域 → markdown_table_to_slack_table() → {"type": "table", "rows": [...]}
      テキスト領域 → add_zero_width_spaces_to_markdown() → {"type": "markdown", "text": "..."}
```

`convert_markdown_to_slack_messages` はさらに `split_blocks_by_table` で「1メッセージ1テーブル」制約に分割する。

### ZWSP (Zero-Width Space) 挿入

日本語など単語間スペースのない言語で、Slackがインライン装飾（`*bold*`, `` `code` `` 等）を正しく解釈できるよう、装飾トークンの前後に U+200B を挿入する。コードフェンス内は除外。`strip_zero_width_spaces` は U+200B/U+FEFF を除去するが、ZWJ (U+200D) / ZWNJ (U+200C) は保持する。

### テーブル正規化

LLMが出力するテーブルの一般的な問題（外パイプ欠落、セパレータ行欠落、列数不一致、空セル）を修復する。セル内の `<url|text>` リンクやインラインコード内のパイプはセル区切りとして扱わない。

## Code Style

- line-length: 88 (black / ruff共通)
- ruff lint select: E, F, I, UP, B（`E501`, `UP006`, `UP035`, `UP045` は ignore）
- 型ヒント使用、簡潔な docstring
- パブリックAPIの追加・変更時は `__init__.py` の `__all__` と README の Public API セクションを同時更新

## Specification

動作仕様の詳細は `docs/spec.md`（英語）/ `docs/spec-ja.md`（日本語）に記載。

## CI/CD

- CI (`.github/workflows/ci.yml`): push to main / PR で pytest 実行
- Publish (`.github/workflows/publish.yml`): `v*` タグで PyPI trusted publishing
- バージョンは `pyproject.toml` の `project.version` と `__init__.py` の `__version__` の両方を更新する
