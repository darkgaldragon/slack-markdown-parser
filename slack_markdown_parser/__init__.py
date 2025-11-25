"""
Slack Markdown Parser
=====================

LLMが生成した純粋なMarkdownテキストをSlackのmarkdownブロックとtableブロックに自動変換するライブラリ

Usage:
    from slack_markdown_parser import convert_markdown_to_slack_blocks, convert_markdown_to_slack_messages
    
    # 単一メッセージに変換（テーブルが1つまで）
    blocks = convert_markdown_to_slack_blocks(markdown_text)
    
    # 複数メッセージに変換（複数テーブル対応）
    messages = convert_markdown_to_slack_messages(markdown_text)
"""

__version__ = "1.0.0"
__author__ = "darkgaldragon（ぎゃうどら）"
__license__ = "MIT"

from .converter import (
    convert_markdown_to_slack_blocks,
    convert_markdown_to_slack_messages,
    add_zero_width_spaces,
    parse_markdown_table,
    markdown_table_to_slack_table,
)

__all__ = [
    "convert_markdown_to_slack_blocks",
    "convert_markdown_to_slack_messages",
    "add_zero_width_spaces",
    "parse_markdown_table",
    "markdown_table_to_slack_table",
]
