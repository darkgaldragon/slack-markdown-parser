"""
Markdown to Slack Blocks Converter
===================================

Markdownテキストを解析してSlack blocksに変換する機能を提供
"""

import re
from typing import List, Dict, Any

# ゼロ幅スペース（U+200B）
ZWSP = "\u200b"


def add_zero_width_spaces(text: str) -> str:
    """
    Markdownの太字、斜体、取り消し線タグの前後にゼロ幅スペースを挿入する
    
    Args:
        text: 変換対象のMarkdownテキスト
    
    Returns:
        ゼロ幅スペースが挿入されたテキスト
    
    Example:
        >>> add_zero_width_spaces("これは**重要**です")
        'これは​**重要**​です'  # ​ はゼロ幅スペース
    """
    # 太字: **text** -> {ZWSP}**text**{ZWSP}
    text = re.sub(r'(\*\*[^*]+\*\*)', f'{ZWSP}\\1{ZWSP}', text)
    
    # 斜体: *text* (ただし**ではない) -> {ZWSP}*text*{ZWSP}
    text = re.sub(r'(?<!\*)(\*[^*]+\*)(?!\*)', f'{ZWSP}\\1{ZWSP}', text)
    
    # 取り消し線: ~~text~~ -> {ZWSP}~~text~~{ZWSP}
    text = re.sub(r'(~~[^~]+~~)', f'{ZWSP}\\1{ZWSP}', text)
    
    # 連続したゼロ幅スペースを1つにまとめる
    text = re.sub(f'{ZWSP}+', ZWSP, text)
    
    return text


def parse_markdown_table(table_text: str) -> List[List[str]]:
    """
    Markdownテーブルをパースして2次元配列に変換する
    
    Args:
        table_text: Markdownテーブルのテキスト
    
    Returns:
        2次元配列（行×列）
    
    Example:
        >>> table = '''
        ... | A | B |
        ... |---|---|
        ... | 1 | 2 |
        ... '''
        >>> parse_markdown_table(table)
        [['A', 'B'], ['1', '2']]
    """
    lines = table_text.strip().split('\n')
    rows = []
    
    for line in lines:
        # セパレーター行（|-----|-----| など）をスキップ
        if re.match(r'^\s*\|[\s\-:|]+\|\s*$', line):
            continue
        
        # セルを分割（先頭と末尾の | を除去）
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if cells:
            rows.append(cells)
    
    return rows


def _parse_simple_text(text: str) -> List[Dict[str, Any]]:
    """装飾なしテキストを要素リストに変換"""
    if not text:
        return []
    return [{"type": "text", "text": text}]


def _create_table_cell(text: str) -> Dict[str, Any]:
    """
    テーブルセルのrich_text構造を作成する
    Markdown装飾（太字、斜体、取り消し線、コード）を解析して適用する
    
    Args:
        text: セルのテキスト（Markdown装飾を含む可能性あり）
    
    Returns:
        Slack rich_text構造
    """
    elements = []
    
    # パターン定義
    code_pattern = r'`([^`]+)`'
    strike_pattern = r'~~([^~]+)~~'
    bold_pattern = r'\*\*([^*]+)\*\*'
    italic_pattern = r'\*([^*]+)\*'
    
    # テキストを分割して処理
    remaining = text
    while remaining:
        # コードを最優先で検出
        code_match = re.search(code_pattern, remaining)
        if code_match:
            before = remaining[:code_match.start()]
            if before:
                elements.extend(_parse_simple_text(before))
            
            elements.append({
                "type": "text",
                "text": code_match.group(1),
                "style": {"code": True}
            })
            
            remaining = remaining[code_match.end():]
            continue
        
        # 取り消し線を検出
        strike_match = re.search(strike_pattern, remaining)
        if strike_match:
            before = remaining[:strike_match.start()]
            if before:
                elements.extend(_parse_simple_text(before))
            
            elements.append({
                "type": "text",
                "text": strike_match.group(1),
                "style": {"strike": True}
            })
            
            remaining = remaining[strike_match.end():]
            continue
        
        # 太字を検出
        bold_match = re.search(bold_pattern, remaining)
        if bold_match:
            before = remaining[:bold_match.start()]
            if before:
                elements.extend(_parse_simple_text(before))
            
            elements.append({
                "type": "text",
                "text": bold_match.group(1),
                "style": {"bold": True}
            })
            
            remaining = remaining[bold_match.end():]
            continue
        
        # 斜体を検出
        italic_match = re.search(italic_pattern, remaining)
        if italic_match:
            before = remaining[:italic_match.start()]
            if before:
                elements.extend(_parse_simple_text(before))
            
            elements.append({
                "type": "text",
                "text": italic_match.group(1),
                "style": {"italic": True}
            })
            
            remaining = remaining[italic_match.end():]
            continue
        
        # 装飾なしのテキスト
        elements.append({
            "type": "text",
            "text": remaining
        })
        break
    
    return {
        "type": "rich_text",
        "elements": [
            {
                "type": "rich_text_section",
                "elements": elements
            }
        ]
    }


def markdown_table_to_slack_table(table_text: str) -> Dict[str, Any]:
    """
    Markdownテーブルをslack tableブロックに変換する
    
    Args:
        table_text: Markdownテーブルのテキスト
    
    Returns:
        Slack tableブロック
    
    Example:
        >>> table = '''
        ... | 項目 | 説明 |
        ... |------|------|
        ... | **API** | REST API |
        ... '''
        >>> block = markdown_table_to_slack_table(table)
        >>> block['type']
        'table'
    """
    rows_data = parse_markdown_table(table_text)
    
    slack_rows = []
    for row in rows_data:
        slack_row = [_create_table_cell(cell) for cell in row]
        slack_rows.append(slack_row)
    
    return {
        "type": "table",
        "rows": slack_rows
    }


def convert_markdown_to_slack_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Markdownテキストを解析して、Slack blocksに変換する
    - テーブルはtableブロックに変換
    - その他のテキストはmarkdownブロックに変換（ゼロ幅スペース挿入）
    
    Args:
        markdown_text: 変換対象のMarkdownテキスト
    
    Returns:
        Slack blocks配列
    
    Note:
        複数のテーブルが含まれる場合、1メッセージに1テーブルの制限により
        エラーになる可能性があります。その場合は convert_markdown_to_slack_messages() を使用してください。
    
    Example:
        >>> markdown = "これは**重要**です\\n\\n| A | B |\\n|---|---|\\n| 1 | 2 |"
        >>> blocks = convert_markdown_to_slack_blocks(markdown)
        >>> len(blocks)
        2
        >>> blocks[0]['type']
        'markdown'
        >>> blocks[1]['type']
        'table'
    """
    blocks = []
    
    # テーブルパターンを検出（複数行の | で始まる行）
    table_pattern = r'(\|.+\|[\r\n]+(?:\|.+\|[\r\n]*)+)'
    
    parts = re.split(table_pattern, markdown_text)
    
    for part in parts:
        if not part.strip():
            continue
        
        # テーブルかどうか判定
        if re.match(r'^\|.+\|', part.strip()):
            # テーブルブロックに変換
            table_block = markdown_table_to_slack_table(part)
            blocks.append(table_block)
        else:
            # 通常のMarkdownテキスト（ゼロ幅スペース挿入）
            processed_text = add_zero_width_spaces(part)
            blocks.append({
                "type": "markdown",
                "text": processed_text
            })
    
    return blocks


def _split_blocks_by_table(blocks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    blocksを複数のメッセージに分割する（1メッセージに1テーブルの制限対応）
    
    Args:
        blocks: Slack blocks配列
    
    Returns:
        メッセージごとに分割されたblocks配列のリスト
    """
    messages = []
    current_message = []
    
    for block in blocks:
        if block["type"] == "table":
            # テーブルが見つかった場合
            if current_message:
                # 既存のメッセージがあれば保存
                messages.append(current_message)
            # テーブル単独で1メッセージ
            messages.append([block])
            current_message = []
        else:
            # 通常のブロックは現在のメッセージに追加
            current_message.append(block)
    
    # 最後のメッセージを保存
    if current_message:
        messages.append(current_message)
    
    return messages


def convert_markdown_to_slack_messages(markdown_text: str) -> List[List[Dict[str, Any]]]:
    """
    Markdownテキストを複数のSlackメッセージに変換する（複数テーブル対応）
    
    Args:
        markdown_text: 変換対象のMarkdownテキスト
    
    Returns:
        メッセージごとに分割されたblocks配列のリスト
    
    Note:
        Slackの制限により、1メッセージに1つのtableブロックしか含められません。
        この関数は自動的にメッセージを分割します。
    
    Example:
        >>> markdown = '''
        ... # タイトル
        ... 
        ... | A | B |
        ... |---|---|
        ... | 1 | 2 |
        ... 
        ... 中間テキスト
        ... 
        ... | C | D |
        ... |---|---|
        ... | 3 | 4 |
        ... '''
        >>> messages = convert_markdown_to_slack_messages(markdown)
        >>> len(messages)  # 5つのメッセージに分割される
        5
    """
    blocks = convert_markdown_to_slack_blocks(markdown_text)
    return _split_blocks_by_table(blocks)
