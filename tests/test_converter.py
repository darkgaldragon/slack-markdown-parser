"""
Tests for slack_markdown_parser.converter
"""

import pytest
from slack_markdown_parser import (
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    add_zero_width_spaces,
    parse_markdown_table,
)


def test_add_zero_width_spaces():
    """ゼロ幅スペースの挿入テスト"""
    ZWSP = "\u200b"
    
    # 太字
    result = add_zero_width_spaces("これは**重要**です")
    assert ZWSP in result
    assert "**重要**" in result
    
    # 斜体
    result = add_zero_width_spaces("これは*参考*です")
    assert ZWSP in result
    assert "*参考*" in result
    
    # 取り消し線
    result = add_zero_width_spaces("これは~~削除~~です")
    assert ZWSP in result
    assert "~~削除~~" in result


def test_parse_markdown_table():
    """Markdownテーブルのパーステスト"""
    table_text = """
| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |
"""
    
    rows = parse_markdown_table(table_text)
    assert len(rows) == 3  # ヘッダー + 2行
    assert rows[0] == ['A', 'B']
    assert rows[1] == ['1', '2']
    assert rows[2] == ['3', '4']


def test_parse_markdown_table_with_decoration():
    """装飾付きテーブルのパーステスト"""
    table_text = """
| 項目 | 説明 |
|------|------|
| **太字** | これは**重要**です |
| *斜体* | これは*参考*です |
"""
    
    rows = parse_markdown_table(table_text)
    assert len(rows) == 3
    assert '**太字**' in rows[1][0]
    assert '**重要**' in rows[1][1]


def test_convert_markdown_to_slack_blocks_simple():
    """シンプルなMarkdownの変換テスト"""
    markdown = "これは**重要**です"
    blocks = convert_markdown_to_slack_blocks(markdown)
    
    assert len(blocks) == 1
    assert blocks[0]['type'] == 'markdown'
    assert '**重要**' in blocks[0]['text']


def test_convert_markdown_to_slack_blocks_with_table():
    """テーブル付きMarkdownの変換テスト"""
    markdown = """
# タイトル

| A | B |
|---|---|
| 1 | 2 |
"""
    
    blocks = convert_markdown_to_slack_blocks(markdown)
    
    # markdownブロックとtableブロックが含まれる
    assert len(blocks) >= 2
    
    # tableブロックが存在する
    table_blocks = [b for b in blocks if b['type'] == 'table']
    assert len(table_blocks) == 1
    
    # テーブルの内容を確認
    table = table_blocks[0]
    assert 'rows' in table
    assert len(table['rows']) == 2  # ヘッダー + 1行


def test_convert_markdown_to_slack_messages_multiple_tables():
    """複数テーブルのメッセージ分割テスト"""
    markdown = """
# タイトル

| A | B |
|---|---|
| 1 | 2 |

中間テキスト

| C | D |
|---|---|
| 3 | 4 |
"""
    
    messages = convert_markdown_to_slack_messages(markdown)
    
    # 複数のメッセージに分割される
    assert len(messages) >= 3
    
    # 各メッセージにtableブロックが1つ以下
    for blocks in messages:
        table_count = sum(1 for b in blocks if b['type'] == 'table')
        assert table_count <= 1


def test_empty_input():
    """空の入力のテスト"""
    blocks = convert_markdown_to_slack_blocks("")
    assert len(blocks) == 0


def test_only_text():
    """テーブルなしのテキストのみのテスト"""
    markdown = "これはテキストのみです。\n\n**太字**もあります。"
    blocks = convert_markdown_to_slack_blocks(markdown)
    
    # markdownブロックのみ
    assert all(b['type'] == 'markdown' for b in blocks)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
