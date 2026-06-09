"""Core conversion utilities for Slack Block Kit output.

This module converts LLM-generated Markdown text into Slack Block Kit blocks,
with support for Slack table blocks and robust fallback text generation.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

ZWSP = "\u200b"
NBSP = "\u00a0"
VISIBLE_BOUNDARY_CHARS = {" ", "\t", "\n", "\r"}
SYNTH_SPACE_MARKER = "\u2063"
STRIP_LEFT_ZWSP_MARKER = "\ufff2"
STRIP_RIGHT_ZWSP_MARKER = "\ufff3"

ANSI_ESCAPE_PATTERN = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x1B\x07]*(?:\x07|\x1B\\))"
)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
SLACK_ANGLE_TOKEN_PATTERN = re.compile(r"<[^>\n]+>")
BARE_URL_PATTERN = re.compile(r"https?://[^\s<]+", re.IGNORECASE)
FENCE_OPEN_PATTERN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})([^\n]*)$")
STANDALONE_IMAGE_PATTERN = re.compile(
    r"^[ \t]*!\[(?P<alt>[^\]\n]*)\]\((?P<url>https?://[^\s)]+)"
    r"(?:[ \t]+(?P<title>\"[^\"\n]*\"|'[^'\n]*'))?[ \t]*\)[ \t]*$",
    re.IGNORECASE,
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\([^\)\n]+\)")
INLINE_CODE_SPAN_PATTERN = re.compile(r"(?<!`)`[^`\n]+`(?!`)", flags=re.DOTALL)
# Emphasis delimiters must satisfy CommonMark's minimal flanking requirement:
# an opening run is not followed by whitespace and a closing run is not preceded
# by whitespace. Enforcing this keeps a stray, whitespace-flanked delimiter
# (e.g. the literal ``**`` in ``閉じ ** が``) from being paired at all.
#
# For ``**`` and ``~~`` the body additionally may not contain the same delimiter
# run (``(?:(?!\*\*).)+?`` / ``(?:(?!~~).)+?``). Without this, a dangling opener
# with no valid closer of its own (``**oops ** and **70.9%→83.0%**``) would scan
# past the literal stray and steal a *later* well-formed span's closing marker,
# shifting the pairing and corrupting that span's ZWSP placement. Bounding the
# body to a single run makes the regex pair the same markers CommonMark does.
# (The single-``*`` italic body is intentionally not bounded this way: italics
# legitimately wrap ``**bold**`` and ``*`` is heavily overloaded, so it keeps the
# whitespace guard only.)
EMPHASIS_PATTERNS = (
    re.compile(r"(?<!\*)\*\*(?!\s)((?:(?!\*\*).)+?)(?<!\s)\*\*(?!\*)", flags=re.DOTALL),
    re.compile(r"(?<!\*)\*(?!\*)(?!\s)(.+?)(?<!\s)(?<!\*)\*(?!\*)", flags=re.DOTALL),
    re.compile(r"~~(?!\s)((?:(?!~~).)+?)(?<!\s)~~", flags=re.DOTALL),
)
INLINE_CODE_PLACEHOLDER_PATTERN = re.compile(r"\ufff0code\d+\ufff1")
PROTECTED_UNDERSCORE_SPAN_PATTERN = re.compile(
    r"`[^`\n]+`"
    r"|\[[^\]\n]+\]\([^\)\n]+\)"
    r"|<[^>\n]+>"
    r"|https?://[^\s<]+"
    r"|mailto:[^\s<]+",
    re.IGNORECASE,
)
REFERENCE_DEFINITION_PATTERN = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:")
SETEXT_HEADING_UNDERLINE_PATTERN = re.compile(r"^[ \t]{0,3}(?:=+|-+)\s*$")
THEMATIC_BREAK_PATTERN = re.compile(
    r"^[ \t]{0,3}(?P<char>[-_*])(?:[ \t]*\1){2,}[ \t]*$"
)
LIST_ITEM_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>\d+[.)]|[-+*])(?P<spacing>[ \t]+|$)"
)
TASK_LIST_MARKER_PATTERN = re.compile(r"^\[[ xX]\](?:[ \t]+|$)")
MARKDOWN_BACKSLASH_ESCAPE_PATTERN = re.compile(r"\\[\\`*_{}\[\]()#+\-.!>|]")
DOUBLE_UNDERSCORE_EMPHASIS_PATTERN = re.compile(
    r"(?<![\\0-9A-Za-z_])__(?=\S)(.+?\S)__(?![0-9A-Za-z_])"
)
SINGLE_UNDERSCORE_EMPHASIS_PATTERN = re.compile(
    r"(?<![\\0-9A-Za-z_])_(?!_)(?=\S)(.+?\S)_(?![0-9A-Za-z_])"
)

TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
LOOSE_TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{3,}\s*(\|\s*:?-{3,}\s*)+\|?\s*$"
)
TABLE_TOKEN_PATTERN = re.compile(
    r"\[(?P<markdown_label>[^\]\n]+)\]\((?P<markdown_url>https?://[^\s)]+)\)"
    r"|<(?P<angle_url>https?://[^>\s|]+)(?:\|(?P<angle_label>[^>\n]+))?>"
    r"|(?P<token>"
    r"(?P<code>(?P<code_delimiter>`+)(?P<code_text>[^\n]+?)(?P=code_delimiter))"
    r"|~~[^~]+~~"
    r"|\*\*[^*]+\*\*"
    r"|(?<!\*)\*[^*]+\*(?!\*)"
    r")"
)
ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS = (
    re.compile(r"^<https?://[^>\s|]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<mailto:[^>\s|]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<@[UW][A-Z0-9]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<#[CG][A-Z0-9]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<!(?:here|channel|everyone)>$"),
    re.compile(r"^<!subteam\^[A-Z0-9]+(?:\|[^>\n]+)?>$"),
    re.compile(r"^<!date\^[^>\n]+>$"),
)
SLACK_MAX_BLOCKS_PER_MESSAGE = 50


def decode_html_entities(text: str) -> str:
    """Decode HTML entities that may appear in model output."""
    if not text:
        return text
    return html.unescape(text)


def strip_zero_width_spaces(text: str) -> str:
    """Strip zero-width spaces from text."""
    return re.sub(r"[\u200B\uFEFF]", "", text or "")


class _AnnotatedSlackBlock(dict):
    """Dict-like block carrying non-serialized metadata for local helpers."""


def _is_hangul_char(char: str) -> bool:
    if not char:
        return False
    codepoint = ord(char)
    return (
        0x1100 <= codepoint <= 0x11FF
        or 0x3130 <= codepoint <= 0x318F
        or 0xAC00 <= codepoint <= 0xD7AF
    )


def _is_han_or_kana_char(char: str) -> bool:
    if not char:
        return False
    codepoint = ord(char)
    return (
        0x3040 <= codepoint <= 0x309F
        or 0x30A0 <= codepoint <= 0x30FF
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )


# Code/angle/pipe markers that never appear inside a bare URL in this library's
# prose context. (A single ``*`` and CJK letters are intentionally NOT here: a
# URL may legally contain a wildcard/query ``*`` and an IRI/IDN may contain CJK
# letters, so those must be preserved.)
_URL_STOP_CHARS = frozenset("`<>|")
# Trailing punctuation stripped from the end of a bare URL. This is exactly
# GFM's autolink-extension set (``! ? . , : * _ ~``); a closing paren is handled
# separately, with balancing. ``;`` and quotes are intentionally NOT included —
# ``;`` is URL-legal in matrix/path parameters and quotes are sub-delimiters, so
# trimming them could change the link target rather than just shedding prose.
_URL_TRAILING_PUNCTUATION = frozenset("!?.,:*_~")
# CJK and full/half-width punctuation/brackets that terminate prose, so a bare
# URL is cut here. This is an explicit set rather than the whole U+3000–U+303F
# block on purpose: letter-like CJK iteration marks (々 U+3005, 〻 U+303B),
# ditto/closure marks (〆 U+3006) and the ideographic number zero (〇 U+3007)
# are *excluded* so IRIs such as ``https://ja.wikipedia.org/wiki/人々`` survive.
_URL_CJK_BOUNDARY_CHARS = frozenset(
    "、。〃〈〉《》「」『』【】〔〕〖〗〘〙〚〛〜〝〞・…"  # CJK punctuation & brackets
    "！？，．：；（）［］｛｝＜＞｜"  # full-width punctuation & brackets
    "｡｢｣､"  # half-width CJK punctuation & brackets
)


def _is_url_boundary_char(char: str) -> bool:
    """Return True when ``char`` is a hard boundary where a bare URL must stop.

    Only unambiguous prose/markup boundaries qualify: code/angle/pipe markers
    and CJK/full-width *punctuation* (``、``/``。``/``」``/``）`` …). CJK
    *letters* (including iteration marks like ``々``) are not a boundary, so
    IRIs such as ``https://ja.wikipedia.org/wiki/人々`` survive.
    """
    return char in _URL_STOP_CHARS or char in _URL_CJK_BOUNDARY_CHARS


def _trim_bare_url(url: str) -> str:
    """Trim a greedily matched bare URL down to its real extent.

    In CJK writing a URL is usually glued directly to the following text with no
    whitespace, so the greedy ``[^\\s<]+`` match would otherwise swallow the
    trailing ``)``/``**``/``。`` and the rest of the sentence. This stops the URL
    at the first hard boundary or doubled emphasis run (``**``/``~~``) — single
    ``*`` and CJK letters are preserved — then drops GFM-style trailing
    punctuation and unbalanced closing parens, so ``https://example.com)**。``
    becomes ``https://example.com``.
    """
    for index, char in enumerate(url):
        nxt = url[index + 1] if index + 1 < len(url) else ""
        if _is_url_boundary_char(char) or (char in "*~" and nxt == char):
            url = url[:index]
            break

    while url:
        last = url[-1]
        if last == ")":
            if url.count(")") <= url.count("("):
                break
            url = url[:-1]
            continue
        if last in _URL_TRAILING_PUNCTUATION:
            url = url[:-1]
            continue
        break

    return url


def _nested_code_space_strategy(
    source: str,
    start: int,
    end: int,
    boundary_chars: set[str] | None = None,
) -> str | None:
    boundary_chars = boundary_chars or {*VISIBLE_BOUNDARY_CHARS, ZWSP}
    neighbors = []

    left_idx = start - 1
    while left_idx >= 0 and source[left_idx] in boundary_chars:
        left_idx -= 1
    if left_idx >= 0:
        neighbors.append(source[left_idx])

    right_idx = end
    while right_idx < len(source) and source[right_idx] in boundary_chars:
        right_idx += 1
    if right_idx < len(source):
        neighbors.append(source[right_idx])

    if any(_is_han_or_kana_char(char) for char in neighbors):
        return "ja_zh"
    if any(_is_hangul_char(char) for char in neighbors):
        return "ko"
    return None


def _needs_inner_code_spacing(char: str, boundary_chars: set[str]) -> bool:
    return bool(char) and char not in boundary_chars and char.isalnum()


def _normalize_markdown_block_plain_text(text: str) -> str:
    if not text:
        return text

    return re.sub(r"<(https?://[^>\s|]+)>", r"\1", text)


def _build_markdown_block_plain_text(
    text: str, synthetic_space_indices: list[int] | None = None
) -> str:
    """Build fallback/plain text for a markdown block before visual-only rewrites."""
    return _normalize_markdown_block_plain_text(
        _strip_synthetic_spaces_from_plain_text(
            strip_zero_width_spaces(text),
            synthetic_space_indices,
        )
    )


def _strip_synthetic_spaces_from_plain_text(
    text: str, synthetic_space_indices: list[int] | None = None
) -> str:
    if not text or not synthetic_space_indices:
        return text

    indices = set(synthetic_space_indices)
    return "".join(
        char for idx, char in enumerate(text) if not (idx in indices and char == " ")
    )


def _indent_width(text: str) -> int:
    width = 0
    for char in text:
        if char == " ":
            width += 1
        elif char == "\t":
            # Treat tabs conservatively for list-continuation heuristics.
            width += 4
        else:
            break
    return width


def _list_item_content_indent(match: re.Match[str]) -> int:
    spacing = match.group("spacing") or ""
    spacing_width = _indent_width(spacing) if spacing else 1
    return (
        _indent_width(match.group("indent") or "")
        + len(match.group("marker") or "")
        + spacing_width
    )


def _is_ordered_list_marker(marker: str) -> bool:
    return bool(marker) and marker[0].isdigit()


def _ordered_list_marker_number(marker: str) -> int:
    if not _is_ordered_list_marker(marker):
        return 1
    try:
        return int(marker[:-1])
    except ValueError:
        return 1


def _list_indent_level(indent: str) -> int:
    width = _indent_width(indent or "")
    if width <= 3:
        return 0
    return min(8, ((width - 4) // 4) + 1)


def _is_ambiguous_rich_list_indent(indent: str) -> bool:
    width = _indent_width(indent or "")
    return 0 < width <= 3


def _has_markdown_backslash_escape(text: str) -> bool:
    return bool(MARKDOWN_BACKSLASH_ESCAPE_PATTERN.search(text or ""))


def _is_thematic_break_line(line: str) -> bool:
    return bool(THEMATIC_BREAK_PATTERN.match(line))


def _ordered_list_marker_starts_at_one(marker: str) -> bool:
    if not _is_ordered_list_marker(marker):
        return False
    return marker[:-1] == "1"


def _starts_root_list_item(lines: list[str], marker_index: int) -> bool:
    line = lines[marker_index]
    if _is_thematic_break_line(line):
        return False
    match = LIST_ITEM_PATTERN.match(line)
    if not match or _indent_width(match.group("indent") or "") > 3:
        return False

    marker = match.group("marker") or ""
    if marker_index == 0 or not lines[marker_index - 1].strip(" \t\r"):
        return True

    if not _is_ordered_list_marker(marker):
        return True

    return _ordered_list_marker_starts_at_one(marker)


def _line_belongs_to_list_context(
    lines: list[str], *, marker_index: int, target_index: int
) -> bool:
    marker_match = LIST_ITEM_PATTERN.match(lines[marker_index])
    if not marker_match:
        return False

    list_indent_stack = [
        (
            _indent_width(marker_match.group("indent") or ""),
            _list_item_content_indent(marker_match),
        )
    ]

    for idx in range(marker_index + 1, target_index + 1):
        line = lines[idx]
        if not line.strip(" \t\r"):
            return False

        line_indent = _indent_width(line)
        nested_match = LIST_ITEM_PATTERN.match(line)
        if nested_match and not _is_thematic_break_line(line):
            marker_indent = _indent_width(nested_match.group("indent") or "")
            while list_indent_stack and marker_indent < list_indent_stack[-1][0]:
                list_indent_stack.pop()

            if not list_indent_stack:
                return False

            if marker_indent == list_indent_stack[-1][0]:
                list_indent_stack[-1] = (
                    marker_indent,
                    _list_item_content_indent(nested_match),
                )
                continue

            if marker_indent >= list_indent_stack[-1][1]:
                list_indent_stack.append(
                    (
                        marker_indent,
                        _list_item_content_indent(nested_match),
                    )
                )
                continue

            return False

        while len(list_indent_stack) > 1 and line_indent < list_indent_stack[-1][0]:
            list_indent_stack.pop()

        if line_indent >= list_indent_stack[-1][1]:
            continue

        return False

    return True


def _blank_run_follows_list_context(lines: list[str], blank_start: int) -> bool:
    previous_visible_index = blank_start - 1
    if previous_visible_index < 0 or not lines[previous_visible_index].strip(" \t\r"):
        return False

    block_start = previous_visible_index
    while block_start > 0 and lines[block_start - 1].strip(" \t\r"):
        block_start -= 1

    for marker_index in range(previous_visible_index, block_start - 1, -1):
        if not _starts_root_list_item(lines, marker_index):
            continue
        if _line_belongs_to_list_context(
            lines, marker_index=marker_index, target_index=previous_visible_index
        ):
            return True

    return False


def _inject_visual_blank_line_placeholders_in_chunk(
    text: str,
) -> tuple[str, list[int]]:
    """Replace internal blank lines with NBSP-only lines for Slack rendering."""
    if not text or "\n" not in text:
        return text, []

    lines = text.split("\n")
    rewritten: list[tuple[str, bool]] = []
    i = 0

    while i < len(lines):
        if lines[i].strip(" \t\r"):
            rewritten.append((lines[i], False))
            i += 1
            continue

        blank_start = i
        while i < len(lines) and not lines[i].strip(" \t\r"):
            i += 1

        has_visible_line_before = blank_start > 0 and bool(
            lines[blank_start - 1].strip(" \t\r")
        )
        has_visible_line_after = i < len(lines) and bool(lines[i].strip(" \t\r"))
        blank_run_follows_list_context = has_visible_line_before and (
            _blank_run_follows_list_context(lines, blank_start)
        )
        next_visible_starts_reference_definition = has_visible_line_after and bool(
            REFERENCE_DEFINITION_PATTERN.match(lines[i])
        )
        next_visible_starts_setext_heading = has_visible_line_after and i + 1 < len(
            lines
        )
        next_visible_starts_setext_heading = bool(
            next_visible_starts_setext_heading
            and lines[i].strip(" \t\r")
            and SETEXT_HEADING_UNDERLINE_PATTERN.match(lines[i + 1])
        )

        if (
            has_visible_line_before
            and has_visible_line_after
            and not blank_run_follows_list_context
            and not next_visible_starts_reference_definition
            and not next_visible_starts_setext_heading
        ):
            rewritten.extend((NBSP, True) for _ in range(i - blank_start))
        else:
            rewritten.extend((line, False) for line in lines[blank_start:i])

    rebuilt_parts: list[str] = []
    synthetic_indices: list[int] = []
    offset = 0

    for idx, (line, is_synthetic) in enumerate(rewritten):
        if idx > 0:
            rebuilt_parts.append("\n")
            offset += 1
        if is_synthetic:
            synthetic_indices.append(offset)
        rebuilt_parts.append(line)
        offset += len(line)

    return "".join(rebuilt_parts), synthetic_indices


def _inject_visual_blank_line_placeholders(text: str) -> tuple[str, list[int]]:
    """Replace internal blank lines outside fenced code blocks."""
    if not text or "\n" not in text:
        return text, []

    rebuilt_parts: list[str] = []
    synthetic_indices: list[int] = []
    offset = 0

    for is_fenced, chunk in _split_fenced_code_chunks(text):
        if is_fenced:
            rebuilt_parts.append(chunk)
            offset += len(chunk)
            continue

        rewritten_chunk, chunk_indices = (
            _inject_visual_blank_line_placeholders_in_chunk(chunk)
        )
        rebuilt_parts.append(rewritten_chunk)
        synthetic_indices.extend(offset + idx for idx in chunk_indices)
        offset += len(rewritten_chunk)

    return "".join(rebuilt_parts), synthetic_indices


def _strip_synthetic_blank_line_placeholders(
    text: str, synthetic_blank_line_indices: list[int] | None = None
) -> str:
    if not text or not synthetic_blank_line_indices:
        return text

    indices = set(synthetic_blank_line_indices)
    return "".join(
        char for idx, char in enumerate(text) if not (idx in indices and char == NBSP)
    )


def _remove_synthetic_space_markers(text: str) -> tuple[str, list[int]]:
    if not text or SYNTH_SPACE_MARKER not in text:
        return text, []

    cleaned: list[str] = []
    synthetic_indices: list[int] = []
    mark_next_space = False

    for char in text:
        if char == SYNTH_SPACE_MARKER:
            mark_next_space = True
            continue

        if mark_next_space and char == " ":
            synthetic_indices.append(len(cleaned))
        cleaned.append(char)
        mark_next_space = False

    return "".join(cleaned), synthetic_indices


def _is_allowed_slack_angle_token(token: str) -> bool:
    return any(pattern.match(token) for pattern in ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS)


def _find_inline_code_span_end(text: str, start: int) -> int | None:
    delimiter_end = start
    while delimiter_end < len(text) and text[delimiter_end] == "`":
        delimiter_end += 1

    delimiter = text[start:delimiter_end]
    closing = text.find(delimiter, delimiter_end)
    if closing == -1:
        return None
    return closing + len(delimiter)


def _is_punctuation_like(char: str, boundary_chars: set[str]) -> bool:
    return bool(char) and char not in boundary_chars and not char.isalnum()


def _should_preserve_raw_punctuation_emphasis(
    source: str,
    start: int,
    end: int,
    token_text: str,
    boundary_chars: set[str],
) -> bool:
    tight_chars = []
    before_char = source[start - 1] if start > 0 else ""
    after_char = source[end] if end < len(source) else ""

    if before_char and before_char not in boundary_chars:
        tight_chars.append(before_char)
    if after_char and after_char not in boundary_chars:
        tight_chars.append(after_char)

    if not tight_chars:
        return False
    if any(not _is_punctuation_like(char, boundary_chars) for char in tight_chars):
        return False
    # Slack only accepts ASCII punctuation (and whitespace) as a flanking
    # neighbor. A non-ASCII punctuation neighbor — e.g. the CJK comma/period
    # ``、``/``。`` — does not satisfy the right-/left-flanking rule, so the
    # token must not be preserved raw; it needs the inner-ZWSP protection in
    # ``wrap_match`` instead.
    if any(ord(char) > 127 for char in tight_chars):
        return False
    if any(_is_han_or_kana_char(char) or _is_hangul_char(char) for char in token_text):
        return False

    left_idx = start - 1
    while left_idx >= 0 and source[left_idx] in boundary_chars:
        left_idx -= 1
    if left_idx >= 0 and (
        _is_han_or_kana_char(source[left_idx]) or _is_hangul_char(source[left_idx])
    ):
        return False

    right_idx = end
    while right_idx < len(source) and source[right_idx] in boundary_chars:
        right_idx += 1
    if right_idx < len(source) and (
        _is_han_or_kana_char(source[right_idx]) or _is_hangul_char(source[right_idx])
    ):
        return False

    return True


def normalize_bare_urls_for_slack_markdown(text: str) -> str:
    """Wrap bare URLs in autolink syntax for stable Slack markdown rendering."""
    if not text:
        return text

    def wrap_chunk(chunk: str) -> str:
        parts: list[str] = []
        cursor = 0
        length = len(chunk)

        while cursor < length:
            char = chunk[cursor]

            if char == "<":
                closing = chunk.find(">", cursor + 1)
                if closing != -1:
                    token = chunk[cursor : closing + 1]
                    if _is_allowed_slack_angle_token(token):
                        parts.append(token)
                        cursor = closing + 1
                        continue

            if char == "[":
                link_match = MARKDOWN_LINK_PATTERN.match(chunk, cursor)
                if link_match:
                    parts.append(link_match.group(0))
                    cursor = link_match.end()
                    continue

            if char == "`":
                code_span_end = _find_inline_code_span_end(chunk, cursor)
                if code_span_end is not None:
                    parts.append(chunk[cursor:code_span_end])
                    cursor = code_span_end
                    continue

            url_match = BARE_URL_PATTERN.match(chunk, cursor)
            if url_match:
                url = _trim_bare_url(url_match.group(0))
                scheme = re.match(r"https?://", url, re.IGNORECASE)
                # Only autolink when something host-like survives the trim;
                # a bare ``https://`` followed straight by CJK would otherwise
                # produce an empty ``<https://>`` autolink.
                if scheme and len(url) > scheme.end():
                    parts.append(f"<{url}>")
                    cursor += len(url)
                    continue

            parts.append(char)
            cursor += 1

        return "".join(parts)

    chunks = _split_fenced_code_chunks(text)
    return "".join(
        chunk if is_fenced else wrap_chunk(chunk) for is_fenced, chunk in chunks
    )


def sanitize_slack_text(text: str) -> str:
    """Remove control noise and neutralize invalid Slack angle tokens."""
    if not text:
        return text

    cleaned = ANSI_ESCAPE_PATTERN.sub("", text)
    cleaned = CONTROL_CHAR_PATTERN.sub("", cleaned)

    def replace_invalid_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if _is_allowed_slack_angle_token(token):
            return token
        return f"＜{token[1:-1]}＞"

    return SLACK_ANGLE_TOKEN_PATTERN.sub(replace_invalid_token, cleaned)


def _match_fence_open(line: str) -> tuple[str, int] | None:
    match = FENCE_OPEN_PATTERN.match(line)
    if not match:
        return None
    marker = match.group(1)
    return marker[0], len(marker)


def _is_fence_close(line: str, fence: tuple[str, int]) -> bool:
    marker_char, marker_length = fence
    return bool(
        re.match(
            rf"^[ \t]{{0,3}}{re.escape(marker_char)}{{{marker_length},}}\s*$", line
        )
    )


def _split_fenced_code_chunks(text: str) -> list[tuple[bool, str]]:
    chunks: list[tuple[bool, str]] = []
    if not text:
        return chunks

    current: list[str] = []
    active_fence: tuple[str, int] | None = None

    for line in text.splitlines(keepends=True):
        opening_fence = _match_fence_open(line) if active_fence is None else None

        if opening_fence:
            if current:
                chunks.append((False, "".join(current)))
                current = []
            current.append(line)
            active_fence = opening_fence
            continue

        current.append(line)
        if active_fence and _is_fence_close(line, active_fence):
            chunks.append((True, "".join(current)))
            current = []
            active_fence = None

    if current:
        chunks.append((active_fence is not None, "".join(current)))

    return chunks


def _normalize_underscore_emphasis_chunk(text: str) -> str:
    protected_spans: list[str] = []

    def protect(match: re.Match[str]) -> str:
        token = f"\ufff0{len(protected_spans)}\ufff1"
        protected_spans.append(match.group(0))
        return token

    normalized = PROTECTED_UNDERSCORE_SPAN_PATTERN.sub(protect, text)
    normalized = DOUBLE_UNDERSCORE_EMPHASIS_PATTERN.sub(r"**\1**", normalized)
    normalized = SINGLE_UNDERSCORE_EMPHASIS_PATTERN.sub(r"*\1*", normalized)

    for idx, original in enumerate(protected_spans):
        normalized = normalized.replace(f"\ufff0{idx}\ufff1", original)

    return normalized


def normalize_underscore_emphasis(text: str) -> str:
    """Convert underscore emphasis into Slack-compatible asterisk emphasis."""
    if not text:
        return text

    chunks = _split_fenced_code_chunks(text)
    return "".join(
        chunk if is_fenced else _normalize_underscore_emphasis_chunk(chunk)
        for is_fenced, chunk in chunks
    )


def add_zero_width_spaces_to_markdown(text: str) -> str:
    """Stabilize markdown rendering by padding style markers with ZWSP.

    Code fences are preserved untouched.
    """
    formatted, _ = _format_markdown_with_spacing_metadata(text)
    return formatted


def _format_markdown_with_spacing_metadata(text: str) -> tuple[str, list[int]]:
    """Return formatted markdown text plus synthetic visible-space positions."""
    if not text:
        return text, []

    boundary_chars = {*VISIBLE_BOUNDARY_CHARS, ZWSP, SYNTH_SPACE_MARKER}

    def wrap_match(match: re.Match[str], source: str) -> str:
        start, end = match.start(), match.end()
        token = match.group(0)
        # The start/end of the chunk are effective boundaries: there is no
        # adjacent text to separate the marker from, so they are safe. Treating
        # them as unsafe used to append a ZWSP right after a closing marker, and
        # when the last content character was punctuation (e.g. ``**注意:**``)
        # the trailing ZWSP made Slack fail the CommonMark right-flanking check
        # and exposed the literal ``**``.
        before_safe = start == 0 or source[start - 1] in boundary_chars
        after_safe = end == len(source) or source[end] in boundary_chars
        if before_safe and after_safe:
            return token
        if _should_preserve_raw_punctuation_emphasis(
            source, start, end, token, boundary_chars
        ):
            return token

        # When an outer edge is tightly coupled to surrounding text, pad only
        # that edge so Slack can treat the decoration as a standalone span.
        # Padding a safe edge is unnecessary noise.
        prefix = "" if before_safe else ZWSP
        suffix = "" if after_safe else ZWSP

        # Emphasis markers (``*``/``**``/``~~``) obey CommonMark delimiter-run
        # flanking rules; inline code spans (``` `…` ```) do not. When an
        # emphasis marker sits directly against punctuation on its inner side
        # (``**注意:**``, ``**70%→83%**``) Slack treats the run as a delimiter
        # only when the *outer* neighbour is whitespace or ASCII punctuation; a
        # following CJK character or CJK punctuation (e.g. ``、``) — and even a
        # ZWSP placed just outside the marker — leaves the literal ``**``
        # exposed. Inserting a ZWSP just *inside* the marker makes its inner
        # neighbour a non-punctuation character, so the run flanks via rule 2a
        # regardless of what surrounds the token.
        marker_char = token[0]
        if marker_char != "`":
            marker_len = len(token) - len(token.lstrip(marker_char))
            open_marker = token[:marker_len]
            inner = token[marker_len : len(token) - marker_len]
            close_marker = token[len(token) - marker_len :]
            inner_prefix = (
                ZWSP if inner and _is_punctuation_like(inner[0], boundary_chars) else ""
            )
            inner_suffix = (
                ZWSP
                if inner and _is_punctuation_like(inner[-1], boundary_chars)
                else ""
            )
            if inner_prefix or inner_suffix:
                token = (
                    f"{open_marker}{inner_prefix}{inner}{inner_suffix}{close_marker}"
                )
                # The inner ZWSP already lets the marker flank correctly, so an
                # outer ZWSP on the same edge is redundant — and after a closing
                # marker it is precisely what would re-break rendering.
                if inner_prefix:
                    prefix = ""
                if inner_suffix:
                    suffix = ""

        return f"{prefix}{token}{suffix}"

    def wrap_nested_code_emphasis_match(
        match: re.Match[str],
        source: str,
        replacements: dict[str, dict[str, str]],
    ) -> str:
        start, end = match.start(), match.end()
        before_char = source[start - 1] if start > 0 else ""
        after_char = source[end] if end < len(source) else ""
        strategy = _nested_code_space_strategy(source, start, end, boundary_chars)
        resolved_text = INLINE_CODE_PLACEHOLDER_PATTERN.sub(
            lambda placeholder_match: replacements[placeholder_match.group(0)]["raw"],
            match.group(0),
        )
        has_ascii_word = bool(re.search(r"[A-Za-z0-9]", resolved_text))
        adjusted_text = match.group(0)

        if strategy in {"ja_zh", "ko"}:

            def add_inner_spacing(placeholder_match: re.Match[str]) -> str:
                before_inner = (
                    adjusted_text[placeholder_match.start() - 1]
                    if placeholder_match.start() > 0
                    else ""
                )
                after_inner = (
                    adjusted_text[placeholder_match.end()]
                    if placeholder_match.end() < len(adjusted_text)
                    else ""
                )
                prefix = (
                    f"{SYNTH_SPACE_MARKER} "
                    if _needs_inner_code_spacing(before_inner, boundary_chars)
                    else ""
                )
                suffix = (
                    f"{SYNTH_SPACE_MARKER} "
                    if _needs_inner_code_spacing(after_inner, boundary_chars)
                    else ""
                )
                return f"{prefix}{placeholder_match.group(0)}{suffix}"

            adjusted_text = INLINE_CODE_PLACEHOLDER_PATTERN.sub(
                add_inner_spacing, adjusted_text
            )

        if strategy == "ja_zh":
            prefix = (
                ""
                if before_char in VISIBLE_BOUNDARY_CHARS or not before_char
                else f"{SYNTH_SPACE_MARKER} "
            )
            suffix = (
                ""
                if after_char in VISIBLE_BOUNDARY_CHARS or not after_char
                else f"{SYNTH_SPACE_MARKER} "
            )
            return f"{prefix}{adjusted_text}{suffix}"
        if strategy == "ko":
            prefix = (
                ""
                if before_char in VISIBLE_BOUNDARY_CHARS or not has_ascii_word
                else f"{SYNTH_SPACE_MARKER} "
            )
            suffix = (
                ""
                if after_char in VISIBLE_BOUNDARY_CHARS or not after_char
                else f"{SYNTH_SPACE_MARKER} "
            )
            return f"{prefix}{adjusted_text}{suffix}"
        prefix = STRIP_LEFT_ZWSP_MARKER if before_char == ZWSP else ""
        suffix = STRIP_RIGHT_ZWSP_MARKER if after_char == ZWSP else ""
        return f"{prefix}{adjusted_text}{suffix}"

    def wrap_segment(segment: str) -> tuple[str, list[int]]:
        if not segment:
            return segment, []

        placeholder_map: dict[str, dict[str, str]] = {}
        protected_parts: list[str] = []
        last_end = 0

        for idx, match in enumerate(INLINE_CODE_SPAN_PATTERN.finditer(segment)):
            placeholder = f"\ufff0code{idx}\ufff1"
            protected_parts.append(segment[last_end : match.start()])
            protected_parts.append(placeholder)
            placeholder_map[placeholder] = {
                "raw": match.group(0),
                "wrapped": wrap_match(match, segment),
            }
            last_end = match.end()

        protected_parts.append(segment[last_end:])
        protected_segment = "".join(protected_parts)

        placeholders_inside_emphasis: set[str] = set()
        for pattern in EMPHASIS_PATTERNS:
            for match in pattern.finditer(protected_segment):
                placeholders_inside_emphasis.update(
                    placeholder.group(0)
                    for placeholder in INLINE_CODE_PLACEHOLDER_PATTERN.finditer(
                        match.group(0)
                    )
                )

        for placeholder in placeholders_inside_emphasis:
            placeholder_map[placeholder]["wrapped"] = placeholder_map[placeholder][
                "raw"
            ]

        for pattern in EMPHASIS_PATTERNS:
            protected_segment = pattern.sub(
                lambda m, s=protected_segment: (
                    wrap_nested_code_emphasis_match(m, s, placeholder_map)
                    if INLINE_CODE_PLACEHOLDER_PATTERN.search(m.group(0))
                    else wrap_match(m, s)
                ),
                protected_segment,
            )

        protected_segment = INLINE_CODE_PLACEHOLDER_PATTERN.sub(
            lambda placeholder_match: placeholder_map[placeholder_match.group(0)][
                "wrapped"
            ],
            protected_segment,
        )

        protected_segment = re.sub(
            f"{ZWSP}{re.escape(SYNTH_SPACE_MARKER)} ",
            f"{SYNTH_SPACE_MARKER} ",
            protected_segment,
        )
        protected_segment = re.sub(
            f"{re.escape(SYNTH_SPACE_MARKER)} {ZWSP}",
            f"{SYNTH_SPACE_MARKER} ",
            protected_segment,
        )
        protected_segment = protected_segment.replace(
            f"{ZWSP}{STRIP_LEFT_ZWSP_MARKER}", ""
        )
        protected_segment = protected_segment.replace(
            f"{STRIP_RIGHT_ZWSP_MARKER}{ZWSP}", ""
        )
        protected_segment = protected_segment.replace(STRIP_LEFT_ZWSP_MARKER, "")
        protected_segment = protected_segment.replace(STRIP_RIGHT_ZWSP_MARKER, "")
        protected_segment = re.sub(f"{ZWSP}+", ZWSP, protected_segment)
        return _remove_synthetic_space_markers(protected_segment)

    chunks = _split_fenced_code_chunks(text)
    combined_parts: list[str] = []
    combined_indices: list[int] = []
    offset = 0
    for is_fenced, chunk in chunks:
        if is_fenced:
            combined_parts.append(chunk)
            offset += len(chunk)
            continue
        formatted_chunk, synthetic_indices = wrap_segment(chunk)
        combined_parts.append(formatted_chunk)
        combined_indices.extend(offset + idx for idx in synthetic_indices)
        offset += len(formatted_chunk)

    return "".join(combined_parts), combined_indices


# Backward-compatible alias
add_zero_width_spaces = add_zero_width_spaces_to_markdown


def _split_markdown_table_cells(line: str) -> list[str]:
    """Split markdown table cells while preserving pipes inside <...|...> links."""
    working = line.strip()
    if not working:
        return []

    if working.startswith("|"):
        working = working[1:]
    if working.endswith("|"):
        working = working[:-1]

    cells: list[str] = []
    current: list[str] = []
    in_angle = False
    escaped = False
    cursor = 0

    while cursor < len(working):
        ch = working[cursor]
        if escaped:
            current.append(ch)
            escaped = False
            cursor += 1
            continue

        if ch == "\\":
            current.append(ch)
            escaped = True
            cursor += 1
            continue

        if ch == "`":
            code_span_end = _find_inline_code_span_end(working, cursor)
            if code_span_end is not None:
                current.append(working[cursor:code_span_end])
                cursor = code_span_end
                continue

        if ch == "<":
            in_angle = True
        elif ch == ">" and in_angle:
            in_angle = False

        if ch == "|" and not in_angle:
            cells.append("".join(current).strip())
            current = []
            cursor += 1
            continue

        current.append(ch)
        cursor += 1

    cells.append("".join(current).strip())
    return cells


def _count_cell_words(cell_text: str) -> int:
    tokens = [token for token in cell_text.strip().split() if token]
    return len(tokens) or 1


def _split_heading_prefix_and_first_cell(
    heading_prefix: str, reference_cell: str | None
) -> tuple[str, str] | None:
    tokens = [token for token in heading_prefix.strip().split() if token]
    if len(tokens) < 2:
        return None

    first_cell_words = _count_cell_words(reference_cell or "")
    first_cell_words = min(first_cell_words, len(tokens) - 1)
    if first_cell_words <= 0:
        return None

    heading_tokens = tokens[:-first_cell_words]
    first_cell_tokens = tokens[-first_cell_words:]
    if not heading_tokens or not first_cell_tokens:
        return None

    return " ".join(heading_tokens), " ".join(first_cell_tokens)


def _split_heading_and_table_row(
    line: str, next_line: str | None = None
) -> tuple[str, str] | None:
    """Split lines like '# Heading |a|b|' into heading and table row."""
    if "|" not in line:
        return None

    in_angle = False
    escaped = False
    first_pipe = -1
    cursor = 0
    while cursor < len(line):
        ch = line[cursor]
        if escaped:
            escaped = False
            cursor += 1
            continue
        if ch == "\\":
            escaped = True
            cursor += 1
            continue
        if ch == "`":
            code_span_end = _find_inline_code_span_end(line, cursor)
            if code_span_end is not None:
                cursor = code_span_end
                continue
        if ch == "<":
            in_angle = True
        elif ch == ">" and in_angle:
            in_angle = False
        elif ch == "|" and not in_angle:
            first_pipe = cursor
            break
        cursor += 1

    if first_pipe < 0:
        return None

    heading_part = line[:first_pipe].rstrip()
    table_part = line[first_pipe:].strip()

    if not heading_part or not heading_part.lstrip().startswith("#"):
        return None

    heading_match = re.match(r"^([ \t]{0,3}#{1,6})\s+(.+)$", heading_part)
    if not heading_match:
        return None

    heading_marker = heading_match.group(1)
    heading_body = heading_match.group(2).strip()

    if not table_part.startswith("|"):
        table_part = "|" + table_part
    if not table_part.endswith("|"):
        table_part = table_part + "|"

    explicit_cells = _split_markdown_table_cells(table_part)
    if not explicit_cells:
        return None

    reference_cell: str | None = None
    if (
        next_line
        and "|" in next_line
        and not LOOSE_TABLE_SEPARATOR_PATTERN.match(next_line.strip())
    ):
        next_working = next_line.strip()
        if not next_working.startswith("|"):
            next_working = "|" + next_working
        if not next_working.endswith("|"):
            next_working = next_working + "|"
        next_cells = _split_markdown_table_cells(next_working)
        if next_cells:
            reference_cell = next_cells[0]

    if reference_cell is None and explicit_cells:
        reference_cell = explicit_cells[0]

    split_heading = _split_heading_prefix_and_first_cell(heading_body, reference_cell)
    if not split_heading:
        return None

    heading_text_body, first_cell = split_heading
    heading_text = f"{heading_marker} {heading_text_body}"
    table_cells = [first_cell] + explicit_cells
    table_line = "|" + "|".join(table_cells) + "|"

    return heading_text, table_line


def normalize_markdown_tables(markdown_text: str) -> str:
    """Normalize markdown tables: pipe completion, separator completion, column sizing."""
    if not markdown_text:
        return markdown_text

    lines = markdown_text.splitlines()
    normalized: list[str] = []
    buffer: list[str] = []

    def is_table_block(candidates: list[str]) -> bool:
        if len(candidates) < 2:
            return False
        if any(
            LOOSE_TABLE_SEPARATOR_PATTERN.match(line.strip()) for line in candidates
        ):
            return True

        column_counts: list[int] = []
        for line in candidates:
            working = line.strip()
            if "|" not in working:
                continue
            if not working.startswith("|"):
                working = "|" + working
            if not working.endswith("|"):
                working = working + "|"
            if TABLE_SEPARATOR_PATTERN.match(working):
                continue
            column_counts.append(len(_split_markdown_table_cells(working)))

        if len(column_counts) < 2:
            return False

        min_cols, max_cols = min(column_counts), max(column_counts)
        if max_cols < 2:
            return False

        return max_cols - min_cols <= 1

    def flush_buffer() -> None:
        nonlocal buffer
        if buffer and is_table_block(buffer):
            header_line = buffer[0].strip()
            if not header_line.startswith("|"):
                header_line = "|" + header_line
            if not header_line.endswith("|"):
                header_line = header_line + "|"
            header_cells = _split_markdown_table_cells(header_line)
            column_count = max(1, len(header_cells))

            def normalize_row(raw_line: str) -> str:
                if LOOSE_TABLE_SEPARATOR_PATTERN.match(raw_line.strip()):
                    return ""
                working = raw_line.strip()
                if "|" not in working:
                    return ""
                if not working.startswith("|"):
                    working = "|" + working
                if not working.endswith("|"):
                    working = working + "|"
                cells = _split_markdown_table_cells(working)
                cells = (cells + [""] * column_count)[:column_count]
                return "|" + "|".join(cells) + "|"

            normalized.append(normalize_row(buffer[0]))
            normalized.append("|" + "|".join(["---"] * column_count) + "|")
            for line in buffer[1:]:
                row = normalize_row(line)
                if row:
                    normalized.append(row)
        else:
            normalized.extend(buffer)
        buffer = []

    active_fence: tuple[str, int] | None = None

    for idx, line in enumerate(lines):
        opening_fence = _match_fence_open(line) if active_fence is None else None
        if opening_fence:
            flush_buffer()
            normalized.append(line)
            active_fence = opening_fence
            continue

        if active_fence:
            normalized.append(line)
            if _is_fence_close(line, active_fence):
                active_fence = None
            continue

        stripped = line.strip()

        next_line = lines[idx + 1] if idx + 1 < len(lines) else None
        heading_and_table = _split_heading_and_table_row(line, next_line)
        if heading_and_table:
            flush_buffer()
            heading_text, table_line = heading_and_table
            normalized.append(heading_text)
            buffer.append(table_line)
        elif "|" in stripped:
            buffer.append(line)
        else:
            flush_buffer()
            normalized.append(line)
    flush_buffer()

    return "\n".join(normalized)


def looks_like_markdown_table(text: str) -> bool:
    """Heuristic check for markdown table candidates."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    table_like_lines = sum(
        1
        for line in lines
        if line.strip().startswith("|") and line.strip().endswith("|")
    )
    return table_like_lines >= 2


def _create_rich_text_inline_elements(
    text: str, *, empty_text: str = ""
) -> list[dict[str, Any]]:
    """Build Slack rich text inline elements from a small markdown fragment."""
    clean_text = strip_zero_width_spaces(text or "")
    clean_text = clean_text.replace("\\|", "|")
    if not clean_text.strip():
        clean_text = empty_text

    elements: list[dict[str, Any]] = []
    last_index = 0

    for match in TABLE_TOKEN_PATTERN.finditer(clean_text):
        if match.start() > last_index:
            prefix = clean_text[last_index : match.start()]
            if prefix:
                elements.append({"type": "text", "text": prefix})

        element: dict[str, Any]
        markdown_label = match.group("markdown_label")
        markdown_url = match.group("markdown_url")
        angle_url = match.group("angle_url")
        angle_label = match.group("angle_label")
        token = match.group("token") or ""

        if markdown_label and markdown_url:
            element = {"type": "link", "url": markdown_url, "text": markdown_label}
        elif angle_url:
            element = {
                "type": "link",
                "url": angle_url,
                "text": angle_label or angle_url,
            }
        else:
            style: dict[str, bool] = {}
            content = token

            if content.startswith("`") and content.endswith("`"):
                delimiter_len = len(match.group("code_delimiter") or "`")
                content = content[delimiter_len:-delimiter_len]
                style["code"] = True
            elif content.startswith("~~") and content.endswith("~~"):
                content = content[2:-2]
                style["strike"] = True
            elif content.startswith("**") and content.endswith("**"):
                content = content[2:-2]
                style["bold"] = True
            elif content.startswith("*") and content.endswith("*"):
                content = content[1:-1]
                style["italic"] = True

            # A link wrapped entirely in emphasis (``**[text](url)**``) is matched
            # by the emphasis branch above, not the link branch, so its inner
            # content is a bare ``[text](url)``. Emit a styled ``link`` element
            # rather than a literal text run, otherwise the link is dead in Slack.
            inner_link = (
                TABLE_TOKEN_PATTERN.fullmatch(content)
                if style and not style.get("code")
                else None
            )
            if inner_link is not None and inner_link.group("markdown_url"):
                element = {
                    "type": "link",
                    "url": inner_link.group("markdown_url"),
                    "text": inner_link.group("markdown_label"),
                    "style": style,
                }
            else:
                element = {"type": "text", "text": content}
                if style:
                    element["style"] = style
        elements.append(element)
        last_index = match.end()

    if last_index < len(clean_text):
        suffix = clean_text[last_index:]
        elements.append({"type": "text", "text": suffix})

    if not elements:
        elements.append({"type": "text", "text": clean_text})

    return elements


def _create_rich_text_section(text: str, *, empty_text: str = "") -> dict[str, Any]:
    return {
        "type": "rich_text_section",
        "elements": _create_rich_text_inline_elements(text, empty_text=empty_text),
    }


def _create_table_cell(text: str) -> dict[str, Any]:
    """Build Slack rich_text cell from markdown fragment."""
    return {
        "type": "rich_text",
        "elements": [_create_rich_text_section(text, empty_text="-")],
    }


def extract_plain_text_from_table_cell(cell: dict[str, Any]) -> str:
    """Extract plain text from a Slack table cell object."""
    if not isinstance(cell, dict):
        return ""

    if cell.get("type") == "rich_text":
        texts: list[str] = []
        for element in cell.get("elements", []):
            if not isinstance(element, dict):
                continue
            if element.get("type") == "rich_text_section":
                for child in element.get("elements", []):
                    if isinstance(child, dict):
                        if child.get("type") == "link":
                            texts.append(str(child.get("text") or child.get("url", "")))
                        else:
                            texts.append(child.get("text", ""))
            elif "text" in element:
                texts.append(str(element.get("text", "")))
        return "".join(texts)

    return str(cell.get("text", ""))


def markdown_table_to_slack_table(table_markdown: str) -> dict[str, Any] | None:
    """Convert markdown table text to Slack table block."""
    lines = [
        line.rstrip() for line in table_markdown.strip().splitlines() if line.strip()
    ]
    rows: list[list[dict[str, Any]]] = []
    expected_columns: int | None = None

    for line in lines:
        if TABLE_SEPARATOR_PATTERN.match(line):
            continue
        if "|" not in line:
            continue

        cells = _split_markdown_table_cells(line)
        if not cells:
            continue

        if expected_columns is None:
            expected_columns = max(1, len(cells))
        else:
            cells = (cells + [""] * expected_columns)[:expected_columns]

        rows.append(
            [_create_table_cell(cell if cell.strip() else "-") for cell in cells]
        )

    if not rows:
        return None

    return {"type": "table", "rows": rows}


# Backward-compatible alias
markdown_table_to_table_block = markdown_table_to_slack_table


def _truncate_plain_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _rich_text_inline_elements_to_plain_text(elements: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        element_type = element.get("type")
        if element_type == "link":
            texts.append(str(element.get("text") or element.get("url", "")))
        else:
            texts.append(str(element.get("text", "")))
    return "".join(texts)


def _rich_text_object_to_plain_text(element: dict[str, Any]) -> str:
    element_type = element.get("type")
    if element_type == "rich_text_section":
        return _rich_text_inline_elements_to_plain_text(element.get("elements", []))
    if element_type in {"rich_text_preformatted", "rich_text_quote"}:
        return _rich_text_inline_elements_to_plain_text(element.get("elements", []))
    if element_type == "rich_text_list":
        style = element.get("style")
        indent = max(0, int(element.get("indent") or 0))
        offset = max(0, int(element.get("offset") or 0))
        prefix = "  " * indent
        lines: list[str] = []
        for idx, child in enumerate(element.get("elements", []), start=1):
            if not isinstance(child, dict):
                continue
            child_text = _rich_text_object_to_plain_text(child).strip()
            if not child_text:
                continue
            marker = f"{offset + idx}." if style == "ordered" else "-"
            lines.append(f"{prefix}{marker} {child_text}")
        return "\n".join(lines)
    return ""


def _rich_text_block_to_plain_text(block: dict[str, Any]) -> str:
    annotated_plain_text = getattr(block, "_plain_text", None)
    if annotated_plain_text:
        return str(annotated_plain_text).strip()

    parts = [
        _rich_text_object_to_plain_text(element)
        for element in block.get("elements", [])
        if isinstance(element, dict)
    ]
    return "\n".join(part for part in parts if part).strip()


def _plain_text_from_markdown_fragment(text: str) -> str:
    return _rich_text_inline_elements_to_plain_text(
        _create_rich_text_inline_elements(text)
    ).strip()


def _create_markdown_block(
    content: str, *, preserve_visual_blank_lines: bool = False
) -> dict[str, Any] | None:
    formatted, synthetic_indices = _format_markdown_with_spacing_metadata(content)
    plain_text = _build_markdown_block_plain_text(formatted, synthetic_indices)
    synthetic_blank_line_indices: list[int] = []
    if preserve_visual_blank_lines:
        formatted, synthetic_blank_line_indices = (
            _inject_visual_blank_line_placeholders(formatted)
        )
    if not formatted.strip():
        return None

    block = _AnnotatedSlackBlock({"type": "markdown", "text": formatted})
    block._plain_text = plain_text
    block._synthetic_space_indices = synthetic_indices
    block._synthetic_blank_line_indices = synthetic_blank_line_indices
    return block


def _create_rich_text_block(
    elements: list[dict[str, Any]], *, plain_text: str | None = None
) -> dict[str, Any]:
    block = _AnnotatedSlackBlock({"type": "rich_text", "elements": elements})
    if plain_text is not None:
        block._plain_text = plain_text
    return block


def _create_image_block_from_line(line: str) -> dict[str, Any] | None:
    match = STANDALONE_IMAGE_PATTERN.match(line)
    if not match:
        return None

    image_url = match.group("url").strip()
    if not _is_http_url(image_url) or len(image_url) > 3000:
        return None

    alt_text = _plain_text_from_markdown_fragment(match.group("alt") or "")
    alt_text = _truncate_plain_text(alt_text or "Image", 2000)
    return {"type": "image", "image_url": image_url, "alt_text": alt_text}


def _is_setext_heading_underline(lines: list[str], index: int) -> bool:
    if index <= 0:
        return False
    line = lines[index].strip()
    if not line or set(line) != {"-"}:
        return False
    return bool(lines[index - 1].strip())


def _create_divider_block_from_line(
    lines: list[str], index: int
) -> dict[str, Any] | None:
    if not _is_thematic_break_line(lines[index]):
        return None
    if _is_setext_heading_underline(lines, index):
        return None
    block = _AnnotatedSlackBlock({"type": "divider"})
    block._plain_text = lines[index].strip()
    return block


def _strip_quote_marker(line: str) -> str | None:
    match = re.match(r"^[ \t]{0,3}>[ \t]?(?P<text>.*)$", line)
    if not match:
        return None
    return match.group("text")


def _quote_lines_are_simple(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            return False
        if stripped.startswith(">"):
            return False
        if LIST_ITEM_PATTERN.match(stripped):
            return False
        if _match_fence_open(stripped):
            return False
        if _has_markdown_backslash_escape(stripped):
            return False
    return True


def _consume_quote_block(
    lines: list[str], start: int
) -> tuple[dict[str, Any], int] | None:
    if _strip_quote_marker(lines[start]) is None:
        return None

    quote_lines: list[str] = []
    cursor = start
    while cursor < len(lines):
        stripped = _strip_quote_marker(lines[cursor])
        if stripped is None:
            break
        quote_lines.append(stripped)
        cursor += 1

    if not _quote_lines_are_simple(quote_lines):
        return None

    quote_text = "\n".join(quote_lines).strip()
    if not quote_text:
        return None

    block = _create_rich_text_block(
        [
            {
                "type": "rich_text_quote",
                "elements": _create_rich_text_inline_elements(quote_text),
            }
        ],
        plain_text="\n".join(lines[start:cursor]),
    )
    return block, cursor


def _parse_simple_list_item(line: str) -> dict[str, Any] | None:
    if _is_thematic_break_line(line):
        return None

    match = LIST_ITEM_PATTERN.match(line)
    if not match:
        return None

    text = line[match.end() :].rstrip()
    if TASK_LIST_MARKER_PATTERN.match(text):
        return None

    indent = match.group("indent") or ""
    if _is_ambiguous_rich_list_indent(indent):
        return None
    if _has_markdown_backslash_escape(text):
        return None

    marker = match.group("marker")
    return {
        "style": "ordered" if _is_ordered_list_marker(marker) else "bullet",
        "number": _ordered_list_marker_number(marker),
        "indent": _list_indent_level(indent),
        "text": text.strip() or " ",
    }


def _consume_list_block(
    lines: list[str], start: int
) -> tuple[dict[str, Any], int] | None:
    first_entry = _parse_simple_list_item(lines[start])
    if first_entry is None:
        return None

    first_match = LIST_ITEM_PATTERN.match(lines[start])
    first_indent = _indent_width(first_match.group("indent") if first_match else "")
    if first_indent > 3:
        return None

    if start > 0 and lines[start - 1].strip():
        return None

    entries: list[dict[str, Any]] = []
    cursor = start
    while cursor < len(lines) and lines[cursor].strip():
        entry = _parse_simple_list_item(lines[cursor])
        if entry is None:
            return None
        entries.append(entry)
        cursor += 1

    if not entries:
        return None

    lookahead = cursor
    while lookahead < len(lines) and not lines[lookahead].strip():
        lookahead += 1
    if lookahead < len(lines):
        next_line = lines[lookahead]
        if _indent_width(next_line) > 0 and _parse_simple_list_item(next_line) is None:
            return None

    rich_elements: list[dict[str, Any]] = []
    current_group: dict[str, Any] | None = None

    def flush_group() -> None:
        nonlocal current_group
        if current_group:
            rich_elements.append(current_group)
        current_group = None

    for entry in entries:
        group_key = (entry["style"], entry["indent"])
        if current_group is None or current_group["_key"] != group_key:
            flush_group()
            current_group = {
                "type": "rich_text_list",
                "style": entry["style"],
                "indent": entry["indent"],
                "elements": [],
                "_key": group_key,
            }
            if entry["style"] == "ordered" and entry["number"] > 1:
                current_group["offset"] = entry["number"] - 1

        current_group["elements"].append(_create_rich_text_section(entry["text"]))

    flush_group()
    for element in rich_elements:
        element.pop("_key", None)

    return (
        _create_rich_text_block(
            rich_elements,
            plain_text="\n".join(lines[start:cursor]),
        ),
        cursor,
    )


def _find_fence_close_index(
    lines: list[str], start: int, fence: tuple[str, int]
) -> int | None:
    cursor = start + 1
    while cursor < len(lines):
        if _is_fence_close(lines[cursor], fence):
            return cursor
        cursor += 1
    return None


def _consume_fenced_code_block(
    lines: list[str], start: int
) -> tuple[dict[str, Any], int] | None:
    open_match = FENCE_OPEN_PATTERN.match(lines[start])
    if not open_match:
        return None

    fence = _match_fence_open(lines[start])
    if fence is None:
        return None

    close_index = _find_fence_close_index(lines, start, fence)
    if close_index is None:
        return None

    info = (open_match.group(2) or "").strip()
    language = info.split()[0] if info else ""
    code_text = "\n".join(lines[start + 1 : close_index])
    preformatted: dict[str, Any] = {
        "type": "rich_text_preformatted",
        "elements": [{"type": "text", "text": code_text}],
    }
    if language and re.match(r"^[A-Za-z0-9_+.#-]+$", language):
        preformatted["language"] = language
    return (
        _create_rich_text_block(
            [preformatted],
            plain_text="\n".join(lines[start : close_index + 1]),
        ),
        close_index + 1,
    )


def _consume_rich_markdown_block(
    lines: list[str], index: int
) -> tuple[dict[str, Any], int] | None:
    if not lines[index].strip():
        return None

    consumers = (
        lambda: _consume_fenced_code_block(lines, index),
        lambda: (
            (block, index + 1)
            if (block := _create_image_block_from_line(lines[index]))
            else None
        ),
        lambda: (
            (block, index + 1)
            if (block := _create_divider_block_from_line(lines, index))
            else None
        ),
        lambda: _consume_quote_block(lines, index),
        lambda: _consume_list_block(lines, index),
    )

    for consumer in consumers:
        consumed = consumer()
        if consumed:
            return consumed
    return None


def _convert_markdown_text_segment_to_blocks(
    content: str, *, preserve_visual_blank_lines: bool = False
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    markdown_buffer: list[str] = []
    lines = content.splitlines()
    cursor = 0

    def flush_markdown_buffer() -> None:
        nonlocal markdown_buffer
        if not markdown_buffer:
            return
        while markdown_buffer and not markdown_buffer[0].strip():
            markdown_buffer.pop(0)
        while markdown_buffer and not markdown_buffer[-1].strip():
            markdown_buffer.pop()
        if not markdown_buffer:
            return
        markdown_block = _create_markdown_block(
            "\n".join(markdown_buffer),
            preserve_visual_blank_lines=preserve_visual_blank_lines,
        )
        if markdown_block:
            blocks.append(markdown_block)
        markdown_buffer = []

    while cursor < len(lines):
        fence = _match_fence_open(lines[cursor])
        if fence is not None and _find_fence_close_index(lines, cursor, fence) is None:
            markdown_buffer.extend(lines[cursor:])
            cursor = len(lines)
            break

        consumed = _consume_rich_markdown_block(lines, cursor)
        if consumed:
            flush_markdown_buffer()
            block, cursor = consumed
            blocks.append(block)
            while cursor < len(lines) and not lines[cursor].strip():
                cursor += 1
            continue

        markdown_buffer.append(lines[cursor])
        cursor += 1

    flush_markdown_buffer()
    return blocks


def split_markdown_into_segments(markdown_text: str) -> list[dict[str, str]]:
    """Split markdown into alternating text/table segments."""
    segments: list[dict[str, str]] = []
    if not markdown_text:
        return segments

    lines = markdown_text.splitlines()
    current: list[str] = []
    current_is_table: bool | None = None

    def flush() -> None:
        nonlocal current, current_is_table
        if current:
            segments.append(
                {
                    "type": "table" if current_is_table else "text",
                    "content": "\n".join(current),
                }
            )
        current = []
        current_is_table = None

    active_fence: tuple[str, int] | None = None

    for line in lines:
        stripped = line.strip()
        opening_fence = _match_fence_open(line) if active_fence is None else None
        is_fenced_line = active_fence is not None or opening_fence is not None
        is_table_line = (
            False
            if is_fenced_line
            else stripped.startswith("|") and stripped.endswith("|")
        )

        if current_is_table is None:
            current_is_table = is_table_line
            current.append(line)
        elif is_table_line == current_is_table:
            current.append(line)
        else:
            flush()
            current_is_table = is_table_line
            current.append(line)

        if opening_fence:
            active_fence = opening_fence
        elif active_fence and _is_fence_close(line, active_fence):
            active_fence = None

    flush()
    return segments


def convert_markdown_to_slack_blocks(
    markdown_text: str, *, preserve_visual_blank_lines: bool = False
) -> list[dict[str, Any]]:
    """Convert markdown text into Slack markdown/table blocks."""
    if not markdown_text:
        return []

    markdown_text = decode_html_entities(markdown_text)
    markdown_text = sanitize_slack_text(markdown_text)
    markdown_text = normalize_underscore_emphasis(markdown_text)
    markdown_text = normalize_bare_urls_for_slack_markdown(markdown_text)
    markdown_text = normalize_markdown_tables(markdown_text)
    blocks: list[dict[str, Any]] = []

    for segment in split_markdown_into_segments(markdown_text):
        content = segment.get("content", "")
        if not content.strip():
            continue

        if segment.get("type") == "table" and looks_like_markdown_table(content):
            table_block = markdown_table_to_slack_table(content)
            if table_block:
                blocks.append(table_block)
                continue

        blocks.extend(
            _convert_markdown_text_segment_to_blocks(
                content,
                preserve_visual_blank_lines=preserve_visual_blank_lines,
            )
        )

    return blocks


# Backward-compatible alias
convert_markdown_text_to_blocks = convert_markdown_to_slack_blocks


def split_blocks_by_table(blocks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split blocks to satisfy Slack table and per-message block constraints."""
    messages: list[list[dict[str, Any]]] = []
    current_message: list[dict[str, Any]] = []

    for block in blocks or []:
        if isinstance(block, dict) and block.get("type") == "table":
            if current_message:
                messages.append(current_message)
            messages.append([block])
            current_message = []
        else:
            if len(current_message) >= SLACK_MAX_BLOCKS_PER_MESSAGE:
                messages.append(current_message)
                current_message = []
            current_message.append(block)

    if current_message:
        messages.append(current_message)

    return messages


def convert_markdown_to_slack_messages(
    markdown_text: str,
    *,
    preserve_visual_blank_lines: bool = False,
) -> list[list[dict[str, Any]]]:
    """Convert markdown text into a list of Slack message block groups."""
    blocks = convert_markdown_to_slack_blocks(
        markdown_text, preserve_visual_blank_lines=preserve_visual_blank_lines
    )
    if not blocks:
        return []
    return split_blocks_by_table(blocks)


def convert_markdown_to_slack_payloads(
    markdown_text: str,
    *,
    preserve_visual_blank_lines: bool = False,
) -> list[dict[str, Any]]:
    """Convert markdown text into Slack-ready payload dicts with fallback text."""
    payloads: list[dict[str, Any]] = []
    for blocks in convert_markdown_to_slack_messages(
        markdown_text, preserve_visual_blank_lines=preserve_visual_blank_lines
    ):
        fallback_text = build_fallback_text_from_blocks(blocks).strip()
        payloads.append({"blocks": blocks, "text": fallback_text or " "})
    return payloads


def blocks_to_plain_text(blocks: list[dict[str, Any]]) -> str:
    """Build plain text representation from Slack blocks."""
    parts: list[str] = []

    for block in blocks or []:
        block_type = block.get("type") if isinstance(block, dict) else None

        if block_type == "markdown":
            text = getattr(block, "_plain_text", None) or ""
            if not text:
                raw_text = block.get("text", "")
                if raw_text:
                    text = _normalize_markdown_block_plain_text(
                        _strip_synthetic_blank_line_placeholders(
                            _strip_synthetic_spaces_from_plain_text(
                                strip_zero_width_spaces(raw_text),
                                getattr(block, "_synthetic_space_indices", None),
                            ),
                            getattr(block, "_synthetic_blank_line_indices", None),
                        )
                    )
            if text:
                parts.append(text)
        elif block_type == "table":
            rows = block.get("rows") or []
            for row in rows:
                cell_texts: list[str] = []
                if not isinstance(row, list):
                    continue
                for cell in row:
                    cell_text = extract_plain_text_from_table_cell(cell)
                    if cell_text:
                        cell_texts.append(strip_zero_width_spaces(cell_text))
                if cell_texts:
                    parts.append(" | ".join(cell_texts))
        elif block_type == "rich_text":
            text = _rich_text_block_to_plain_text(block)
            if text:
                parts.append(text)
        elif block_type == "header":
            text = block.get("text", {})
            if isinstance(text, dict) and text.get("text"):
                parts.append(str(text.get("text", "")))
        elif block_type == "image":
            alt_text = str(block.get("alt_text", "")).strip()
            image_url = str(block.get("image_url", "")).strip()
            image_text = alt_text or image_url
            if alt_text and image_url:
                image_text = f"{alt_text} ({image_url})"
            if image_text:
                parts.append(image_text)
        elif block_type == "divider":
            parts.append(getattr(block, "_plain_text", None) or "---")
        elif isinstance(block, dict):
            text = block.get("text", "")
            if text:
                parts.append(str(text))

    return "\n".join([p for p in parts if p]).strip()


def build_fallback_text_from_blocks(blocks: list[dict[str, Any]]) -> str:
    """Build Slack fallback text from block structure."""
    plain_parts: list[str] = []

    for block in blocks or []:
        if not isinstance(block, dict):
            continue

        if block.get("type") == "markdown":
            text = getattr(block, "_plain_text", None) or ""
            if not text:
                text = _normalize_markdown_block_plain_text(
                    _strip_synthetic_blank_line_placeholders(
                        _strip_synthetic_spaces_from_plain_text(
                            strip_zero_width_spaces(block.get("text", "")),
                            getattr(block, "_synthetic_space_indices", None),
                        ),
                        getattr(block, "_synthetic_blank_line_indices", None),
                    ),
                )
            if text.strip():
                plain_parts.append(text)
        elif block.get("type") == "table":
            table_lines: list[str] = []
            for row in block.get("rows", []):
                if not isinstance(row, list):
                    continue
                cells = [extract_plain_text_from_table_cell(cell) for cell in row]
                if cells:
                    table_lines.append(" | ".join(cells))
            if table_lines:
                plain_parts.append("\n".join(table_lines))
        elif block.get("type") == "rich_text":
            text = _rich_text_block_to_plain_text(block)
            if text.strip():
                plain_parts.append(text)
        elif block.get("type") == "header":
            text = block.get("text", {})
            if isinstance(text, dict) and text.get("text"):
                plain_parts.append(str(text.get("text", "")))
        elif block.get("type") == "image":
            alt_text = str(block.get("alt_text", "")).strip()
            image_url = str(block.get("image_url", "")).strip()
            image_text = alt_text or image_url
            if alt_text and image_url:
                image_text = f"{alt_text} ({image_url})"
            if image_text:
                plain_parts.append(image_text)
        elif block.get("type") == "divider":
            plain_parts.append(getattr(block, "_plain_text", None) or "---")

    return "\n\n".join([part for part in plain_parts if part.strip()])


# Backward-compatible helper retained for existing imports.
def parse_markdown_table(table_text: str) -> list[list[str]]:
    """Parse markdown table into row/cell text matrix."""
    rows: list[list[str]] = []
    for line in [line for line in table_text.strip().splitlines() if line.strip()]:
        if TABLE_SEPARATOR_PATTERN.match(line.strip()):
            continue
        if "|" not in line:
            continue
        rows.append(_split_markdown_table_cells(line))
    return rows
