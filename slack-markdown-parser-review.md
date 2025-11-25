# slack-markdown-parser コードレビューレポート

## 概要

本レポートは `slack-markdown-parser` リポジトリのコード品質を検証するためのものである。
CLIエージェントによる自動検証を想定し、各問題点に対して検証方法と期待される改善を記載する。

---

## 検証対象リポジトリ構成

```
slack-markdown-parser/
├── slack_markdown_parser/
│   ├── __init__.py
│   └── converter.py
├── tests/
│   └── test_converter.py
├── setup.py
├── README.md
├── LICENSE
└── その他ドキュメント
```

---

## 問題点一覧

| ID | 問題 | 重要度 | 対象ファイル |
|----|------|--------|-------------|
| P1 | パッケージ設定が旧方式 | 中 | setup.py |
| P2 | バージョン番号の重複管理 | 低 | setup.py, __init__.py |
| P3 | 正規表現のエッジケース未対応 | 中 | converter.py |
| P4 | エラーハンドリング不足 | 高 | converter.py |
| P5 | CI/CD設定の欠如 | 中 | .github/workflows/ |
| P6 | テストカバレッジ不足 | 中 | tests/test_converter.py |

---

## P1: パッケージ設定が旧方式

### 現状

`setup.py` を使用したパッケージ設定となっている。
PEP 517/518 以降、`pyproject.toml` が標準的なパッケージ設定方式として推奨されている。

### 検証方法

```bash
# pyproject.toml の存在確認
test -f pyproject.toml && echo "EXISTS" || echo "NOT FOUND"

# setup.py の存在確認
test -f setup.py && echo "EXISTS" || echo "NOT FOUND"
```

### 期待される改善

1. `pyproject.toml` ファイルを作成
2. ビルドシステムとして `setuptools` または `hatchling` を指定
3. メタデータを `pyproject.toml` に移行
4. `setup.py` は互換性のため残すか、完全に削除するか判断

### 推奨される pyproject.toml の構成

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "slack-markdown-parser"
version = "1.0.0"
description = "Convert Markdown text to Slack blocks with table support"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.8"
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]

[project.optional-dependencies]
dev = ["pytest>=7.0.0", "pytest-cov>=4.0.0"]
```

---

## P2: バージョン番号の重複管理

### 現状

バージョン番号が以下の2箇所で定義されている:

- `setup.py`: `version='1.0.0'`
- `slack_markdown_parser/__init__.py`: `__version__ = "1.0.0"`

### 検証方法

```bash
# setup.py からバージョン抽出
grep -o "version='[^']*'" setup.py

# __init__.py からバージョン抽出
grep -o '__version__ = "[^"]*"' slack_markdown_parser/__init__.py

# 両者が一致するか確認
SETUP_VER=$(grep -o "version='[^']*'" setup.py | cut -d"'" -f2)
INIT_VER=$(grep -o '__version__ = "[^"]*"' slack_markdown_parser/__init__.py | cut -d'"' -f2)
[ "$SETUP_VER" = "$INIT_VER" ] && echo "MATCH" || echo "MISMATCH: $SETUP_VER vs $INIT_VER"
```

### 期待される改善

1. `__init__.py` の `__version__` を単一の情報源（Single Source of Truth）とする
2. `setup.py` または `pyproject.toml` から動的に読み込む

### 改善例

```python
# setup.py での動的バージョン読み込み
import re

def get_version():
    with open('slack_markdown_parser/__init__.py') as f:
        match = re.search(r'__version__ = ["\']([^"\']+)["\']', f.read())
        return match.group(1) if match else '0.0.0'

setup(
    version=get_version(),
    # ...
)
```

---

## P3: 正規表現のエッジケース未対応

### 現状

`converter.py` の装飾検出正規表現が、以下のエッジケースで誤動作する可能性がある。

### 検証方法

以下のテストケースを実行し、期待通りの結果が得られるか確認する:

```python
from slack_markdown_parser import add_zero_width_spaces, convert_markdown_to_slack_blocks

# テストケース1: ネストした装飾
test1 = "**太字の中に*斜体*がある**"
result1 = add_zero_width_spaces(test1)
print(f"Test 1: {repr(result1)}")

# テストケース2: URL内のアスタリスク
test2 = "リンク: https://example.com/*/path"
result2 = add_zero_width_spaces(test2)
print(f"Test 2: {repr(result2)}")

# テストケース3: 数式表現
test3 = "計算式: 2*3*4 = 24"
result3 = add_zero_width_spaces(test3)
print(f"Test 3: {repr(result3)}")

# テストケース4: 連続した装飾
test4 = "**太字****また太字**"
result4 = add_zero_width_spaces(test4)
print(f"Test 4: {repr(result4)}")

# テストケース5: 装飾の途中で改行
test5 = "**複数行の\n太字**"
result5 = add_zero_width_spaces(test5)
print(f"Test 5: {repr(result5)}")

# テストケース6: 空の装飾
test6 = "空の太字: ** ** 空の斜体: * *"
result6 = add_zero_width_spaces(test6)
print(f"Test 6: {repr(result6)}")
```

### 問題となる正規表現

```python
# converter.py 現在の実装
# 斜体: *text* (ただし**ではない) -> {ZWSP}*text*{ZWSP}
text = re.sub(r'(?<!\*)(\*[^*]+\*)(?!\*)', f'{ZWSP}\\1{ZWSP}', text)
```

上記の正規表現では以下の問題が発生する:
- `[^*]+` が改行を含むテキストにもマッチする
- URL内のアスタリスクを誤検出する可能性
- 数式の乗算記号を誤検出する可能性

### 期待される改善

1. より厳密な正規表現パターンの実装
2. URLやコードブロック内は変換対象から除外
3. 各エッジケースに対するテストの追加

---

## P4: エラーハンドリング不足

### 現状

`converter.py` の各関数で、不正な入力に対するエラーハンドリングが不足している。

### 検証方法

以下の異常系テストを実行:

```python
from slack_markdown_parser import (
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    parse_markdown_table,
    markdown_table_to_slack_table,
)

# テストケース1: None入力
try:
    result = convert_markdown_to_slack_blocks(None)
    print(f"None input: {result}")
except Exception as e:
    print(f"None input error: {type(e).__name__}: {e}")

# テストケース2: 非文字列入力
try:
    result = convert_markdown_to_slack_blocks(123)
    print(f"Integer input: {result}")
except Exception as e:
    print(f"Integer input error: {type(e).__name__}: {e}")

# テストケース3: 不完全なテーブル
try:
    result = parse_markdown_table("| A | B |\n|---|\n| 1 |")
    print(f"Incomplete table: {result}")
except Exception as e:
    print(f"Incomplete table error: {type(e).__name__}: {e}")

# テストケース4: 列数不一致のテーブル
try:
    result = markdown_table_to_slack_table("| A | B | C |\n|---|---|\n| 1 | 2 | 3 | 4 |")
    print(f"Mismatched columns: {result}")
except Exception as e:
    print(f"Mismatched columns error: {type(e).__name__}: {e}")

# テストケース5: 極端に大きな入力
try:
    large_input = "# Title\n" + "text " * 100000
    result = convert_markdown_to_slack_blocks(large_input)
    print(f"Large input: blocks count = {len(result)}")
except Exception as e:
    print(f"Large input error: {type(e).__name__}: {e}")

# テストケース6: 特殊文字のみ
try:
    result = convert_markdown_to_slack_blocks("🎉🎊🎁✨")
    print(f"Emoji only: {result}")
except Exception as e:
    print(f"Emoji only error: {type(e).__name__}: {e}")
```

### 期待される改善

1. 入力値のバリデーション追加
2. 適切な例外クラスの定義
3. エラーメッセージの明確化
4. ログ出力の追加（オプション）

### 改善例

```python
class SlackMarkdownParserError(Exception):
    """Base exception for slack-markdown-parser"""
    pass

class InvalidInputError(SlackMarkdownParserError):
    """Raised when input is invalid"""
    pass

class TableParseError(SlackMarkdownParserError):
    """Raised when table parsing fails"""
    pass

def convert_markdown_to_slack_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Markdownテキストを解析して、Slack blocksに変換する
    
    Raises:
        InvalidInputError: 入力がNoneまたは文字列でない場合
    """
    if markdown_text is None:
        raise InvalidInputError("Input cannot be None")
    if not isinstance(markdown_text, str):
        raise InvalidInputError(f"Input must be str, got {type(markdown_text).__name__}")
    
    # 既存の処理...
```

---

## P5: CI/CD設定の欠如

### 現状

`.github/workflows/` ディレクトリが存在せず、GitHub Actions による自動テストが設定されていない。

### 検証方法

```bash
# GitHub Actions ワークフローの存在確認
test -d .github/workflows && ls -la .github/workflows/ || echo "NOT FOUND"

# pre-commit 設定の確認
test -f .pre-commit-config.yaml && echo "EXISTS" || echo "NOT FOUND"
```

### 期待される改善

1. GitHub Actions ワークフローファイルの作成
2. 複数Pythonバージョンでのテスト実行
3. コードカバレッジの測定と報告
4. リリース時の自動パッケージ公開（オプション）

### 推奨される GitHub Actions 設定

ファイル: `.github/workflows/test.yml`

```yaml
name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"

    - name: Run tests with coverage
      run: |
        pytest --cov=slack_markdown_parser --cov-report=xml --cov-report=term

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        fail_ci_if_error: false
```

---

## P6: テストカバレッジ不足

### 現状

基本的なテストは存在するが、以下のカテゴリのテストが不足している:

- 異常系テスト（エラーケース）
- 境界値テスト
- パフォーマンステスト
- エッジケーステスト

### 検証方法

```bash
# テストカバレッジの測定
pip install pytest-cov
pytest --cov=slack_markdown_parser --cov-report=html --cov-report=term

# カバレッジレポートの確認
# htmlcov/index.html を開いて詳細を確認
```

### 現在のテストケース一覧

| テスト名 | カテゴリ | 内容 |
|---------|---------|------|
| test_add_zero_width_spaces | 正常系 | ゼロ幅スペース挿入 |
| test_parse_markdown_table | 正常系 | テーブルパース |
| test_parse_markdown_table_with_decoration | 正常系 | 装飾付きテーブル |
| test_convert_markdown_to_slack_blocks_simple | 正常系 | シンプル変換 |
| test_convert_markdown_to_slack_blocks_with_table | 正常系 | テーブル付き変換 |
| test_convert_markdown_to_slack_messages_multiple_tables | 正常系 | 複数テーブル分割 |
| test_empty_input | 境界値 | 空入力 |
| test_only_text | 正常系 | テキストのみ |

### 追加すべきテストケース

```python
# tests/test_converter.py に追加すべきテスト

import pytest
from slack_markdown_parser import (
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    add_zero_width_spaces,
    parse_markdown_table,
    markdown_table_to_slack_table,
)


class TestEdgeCases:
    """エッジケースのテスト"""
    
    def test_nested_formatting(self):
        """ネストした装飾のテスト"""
        text = "**太字の中に*斜体*がある**"
        result = add_zero_width_spaces(text)
        # 期待される動作を検証
        assert "**" in result
        assert "*" in result
    
    def test_url_with_asterisk(self):
        """URL内のアスタリスクが誤変換されないことを確認"""
        text = "リンク: https://example.com/*/path"
        result = add_zero_width_spaces(text)
        assert "https://example.com/*/path" in result
    
    def test_math_expression(self):
        """数式表現が誤変換されないことを確認"""
        text = "計算: 2*3=6"
        result = add_zero_width_spaces(text)
        # 数式は変換されるべきか検討が必要
    
    def test_consecutive_formatting(self):
        """連続した装飾のテスト"""
        text = "**太字1****太字2**"
        result = add_zero_width_spaces(text)
        assert result.count("**") == 4
    
    def test_multiline_formatting(self):
        """複数行にまたがる装飾のテスト"""
        text = "**複数行の\n太字**"
        result = add_zero_width_spaces(text)
        # 期待される動作を定義


class TestTableEdgeCases:
    """テーブル関連のエッジケーステスト"""
    
    def test_empty_table(self):
        """空のテーブル"""
        table = "| | |\n|---|---|\n| | |"
        result = parse_markdown_table(table)
        assert len(result) == 2
    
    def test_single_column_table(self):
        """1列のテーブル"""
        table = "| A |\n|---|\n| 1 |"
        result = parse_markdown_table(table)
        assert result[0] == ['A']
        assert result[1] == ['1']
    
    def test_table_with_emoji(self):
        """絵文字を含むテーブル"""
        table = "| Status | Emoji |\n|--------|-------|\n| Done | ✅ |\n| Pending | ⏳ |"
        result = parse_markdown_table(table)
        assert '✅' in result[1][1]
    
    def test_table_with_pipes_in_content(self):
        """セル内にパイプ文字を含むテーブル"""
        # エスケープされたパイプ: \|
        table = "| A | B |\n|---|---|\n| a\\|b | c |"
        result = parse_markdown_table(table)
        # 期待される動作を定義
    
    def test_mismatched_column_count(self):
        """列数が一致しないテーブル"""
        table = "| A | B | C |\n|---|---|\n| 1 | 2 |"
        result = parse_markdown_table(table)
        # エラーにするか、最小列数に合わせるか


class TestLargeInput:
    """大量データのテスト"""
    
    def test_large_markdown(self):
        """大きなMarkdownテキスト"""
        large_text = "# Title\n\n" + "This is a paragraph. " * 1000
        result = convert_markdown_to_slack_blocks(large_text)
        assert len(result) > 0
    
    def test_many_tables(self):
        """多数のテーブル"""
        table = "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        many_tables = table * 50
        result = convert_markdown_to_slack_messages(many_tables)
        assert len(result) == 50
    
    def test_large_table(self):
        """大きなテーブル（多数の行と列）"""
        header = "| " + " | ".join([f"Col{i}" for i in range(20)]) + " |"
        separator = "|" + "|".join(["---"] * 20) + "|"
        rows = "\n".join([
            "| " + " | ".join([f"R{r}C{c}" for c in range(20)]) + " |"
            for r in range(100)
        ])
        large_table = f"{header}\n{separator}\n{rows}"
        result = markdown_table_to_slack_table(large_table)
        assert len(result['rows']) == 101  # header + 100 rows


class TestSpecialCharacters:
    """特殊文字のテスト"""
    
    def test_unicode_characters(self):
        """Unicode文字"""
        text = "日本語テキスト：**重要**、*参考*、~~削除~~"
        result = add_zero_width_spaces(text)
        assert "日本語" in result
    
    def test_emoji(self):
        """絵文字"""
        text = "🎉 **祝** 🎊"
        result = add_zero_width_spaces(text)
        assert "🎉" in result
    
    def test_special_markdown_chars(self):
        """Markdownの特殊文字"""
        text = "バックスラッシュ: \\ アスタリスク: \\* チルダ: \\~"
        result = add_zero_width_spaces(text)
        # エスケープ文字の処理を検証


class TestInputValidation:
    """入力検証のテスト"""
    
    def test_none_input(self):
        """None入力"""
        # 現状: エラーになる可能性
        # 期待: 明確なエラーメッセージまたは空リスト
        with pytest.raises((TypeError, AttributeError)):
            convert_markdown_to_slack_blocks(None)
    
    def test_non_string_input(self):
        """非文字列入力"""
        with pytest.raises((TypeError, AttributeError)):
            convert_markdown_to_slack_blocks(123)
    
    def test_list_input(self):
        """リスト入力"""
        with pytest.raises((TypeError, AttributeError)):
            convert_markdown_to_slack_blocks(["markdown", "text"])
```

---

## 検証実行スクリプト

以下のスクリプトを実行することで、上記すべての問題点を一括検証できる:

```bash
#!/bin/bash
# verify_issues.sh

echo "=========================================="
echo "slack-markdown-parser Issue Verification"
echo "=========================================="

# P1: パッケージ設定
echo ""
echo "[P1] Package Configuration"
echo "--------------------------"
test -f pyproject.toml && echo "✅ pyproject.toml exists" || echo "❌ pyproject.toml NOT FOUND"
test -f setup.py && echo "⚠️  setup.py exists (legacy)" || echo "✅ setup.py not used"

# P2: バージョン管理
echo ""
echo "[P2] Version Management"
echo "-----------------------"
if [ -f setup.py ] && [ -f slack_markdown_parser/__init__.py ]; then
    SETUP_VER=$(grep -o "version='[^']*'" setup.py 2>/dev/null | cut -d"'" -f2)
    INIT_VER=$(grep -o '__version__ = "[^"]*"' slack_markdown_parser/__init__.py 2>/dev/null | cut -d'"' -f2)
    if [ "$SETUP_VER" = "$INIT_VER" ]; then
        echo "✅ Versions match: $SETUP_VER"
    else
        echo "❌ Version mismatch: setup.py=$SETUP_VER, __init__.py=$INIT_VER"
    fi
fi

# P5: CI/CD
echo ""
echo "[P5] CI/CD Configuration"
echo "------------------------"
test -d .github/workflows && echo "✅ .github/workflows exists" || echo "❌ .github/workflows NOT FOUND"
test -f .github/workflows/test.yml && echo "✅ test.yml exists" || echo "❌ test.yml NOT FOUND"

# P6: Test Coverage
echo ""
echo "[P6] Test Coverage"
echo "------------------"
if command -v pytest &> /dev/null; then
    pip install pytest-cov -q
    pytest --cov=slack_markdown_parser --cov-report=term-missing 2>/dev/null || echo "❌ Tests failed"
else
    echo "⚠️  pytest not installed"
fi

echo ""
echo "=========================================="
echo "Verification Complete"
echo "=========================================="
```

---

## 改善実施後の確認事項

各問題点を改善した後、以下を確認する:

- [ ] P1: `pip install .` でインストールが成功する
- [ ] P2: バージョン番号が単一箇所で管理されている
- [ ] P3: 追加したエッジケーステストがすべてパスする
- [ ] P4: 異常系テストで適切なエラーが発生する
- [ ] P5: GitHub Actions でテストが自動実行される
- [ ] P6: テストカバレッジが80%以上になる

---

## 参考資料

- [PEP 517 – A build-system independent format for source trees](https://peps.python.org/pep-0517/)
- [PEP 518 – Specifying Minimum Build System Requirements for Python Projects](https://peps.python.org/pep-0518/)
- [pytest documentation](https://docs.pytest.org/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Slack Block Kit Builder](https://app.slack.com/block-kit-builder)

---

**レポート作成日**: 2025-11-25  
**対象リポジトリ**: slack-markdown-parser v1.0.0
