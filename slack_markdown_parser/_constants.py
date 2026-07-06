"""Shared constants, regex patterns, and measured Slack hard limits."""

from __future__ import annotations

import re

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
# In-band marker code points reserved by this module's placeholder/spacing
# machinery: SYNTH_SPACE_MARKER (U+2063), the inline-code placeholder
# delimiters (U+FFF0/U+FFF1), and the ZWSP-strip markers (U+FFF2/U+FFF3).
# They have no legitimate use in chat text, and input that carries them would
# collide with internal placeholders (a stray ``\ufff0code0\ufff1`` either
# crashes restoration with KeyError or gets substituted with another span's
# content), so they are removed up front together with control characters.
INTERNAL_MARKER_CHAR_PATTERN = re.compile("[\u2063\ufff0-\ufff3]")
SLACK_ANGLE_TOKEN_PATTERN = re.compile(r"<[^>\n]+>")
BARE_URL_PATTERN = re.compile(r"https?://[^\s<]+", re.IGNORECASE)
FENCE_OPEN_PATTERN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})([^\n]*)$")
STANDALONE_IMAGE_PATTERN = re.compile(
    r"^[ \t]*!\[(?P<alt>[^\]\n]*)\]\((?P<url>https?://[^\s)]+)"
    r"(?:[ \t]+(?P<title>\"[^\"\n]*\"|'[^'\n]*'))?[ \t]*\)[ \t]*$",
    re.IGNORECASE,
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\([^\)\n]+\)")
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
#
# Every body additionally may not cross a blank line (``(?!\n[ \t\r]*\n)``,
# CRLF included): CommonMark emphasis never spans paragraphs, so a stray
# ``*``/``**``/``~~`` in one paragraph must not pair with a stray marker in a
# later paragraph and get ZWSP-padded as though it were one span.
EMPHASIS_PATTERNS = (
    re.compile(
        r"(?<!\*)\*\*(?!\s)((?:(?!\*\*|\n[ \t\r]*\n).)+?)(?<!\s)\*\*(?!\*)",
        flags=re.DOTALL,
    ),
    re.compile(
        r"(?<!\*)\*(?!\*)(?!\s)((?:(?!\n[ \t\r]*\n).)+?)(?<!\s)(?<!\*)\*(?!\*)",
        flags=re.DOTALL,
    ),
    re.compile(r"~~(?!\s)((?:(?!~~|\n[ \t\r]*\n).)+?)(?<!\s)~~", flags=re.DOTALL),
)
INLINE_CODE_PLACEHOLDER_PATTERN = re.compile(r"\ufff0code\d+\ufff1")
# A blank line ends the paragraph, and with it any possible code span: Slack
# pairs backticks across soft line breaks but never across paragraphs. The
# ``\r`` in the class keeps CRLF blank lines (``\r\n\r\n``) recognized too.
_CODE_SPAN_BLANK_LINE_PATTERN = re.compile(r"\n[ \t\r]*\n")
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
    # Slack mention tokens: user (<@U…>/<@W…>), channel (<#C…>/<#G…>), user
    # group (<!subteam^S…>), and broadcast (<!here>/<!channel>/<!everyone>).
    # An optional ``|label`` is the human-readable display the author saw; the
    # rich_text element is rendered by Slack from the id, so the label is dropped.
    r"|<(?P<mention>@[UW][A-Z0-9]+|#[CG][A-Z0-9]+|!subteam\^[A-Z0-9]+"
    r"|!(?:here|channel|everyone))(?:\|[^>\n]+)?>"
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
# Verified against a real Slack workspace (2026-06-11): a ``markdown`` block's
# ``text`` accepts exactly 12,000 characters, while 12,001 fails the whole
# chat.postMessage call with ``msg_too_long``. The top-level fallback ``text``
# field is not subject to this limit (40,001 characters was accepted).
SLACK_MAX_MARKDOWN_TEXT_LENGTH = 12000
# Raw-content packing target used when an oversized markdown segment is split.
# Formatting inflates text (ZWSP padding, NBSP blank-line placeholders), so
# pieces are packed below the hard limit; the block builder re-splits any
# piece whose *formatted* text still exceeds the hard limit.
_MARKDOWN_SPLIT_TARGET_LENGTH = 11500
# Slack expands a ``markdown`` block server-side into native blocks and then
# enforces "no more than 50 items" on the expanded result *per message*.
# Measured against a real workspace (2026-06-11): each heading and each
# thematic break becomes its own item (50 headings accepted, 51 rejected;
# 30 headings in each of two blocks rejected), while paragraphs, lists,
# quotes, and fenced code merge into one item per run between those breakers
# (60 blank-separated paragraphs and 52 fences were accepted).
SLACK_MAX_EXPANSION_ITEMS_PER_MESSAGE = 50
# Per-block packing target, leaving headroom for estimation error.
_MARKDOWN_EXPANSION_ITEMS_TARGET = 45
# Third measured hard limit (2026-06-11): the text carried by one message's
# blocks *in total* — across block types; rich_text content counts too — may
# not exceed 13,200 characters (= 1.1 × the single-block limit). 13,201
# fails the whole call with ``msg_blocks_too_long``.
SLACK_MAX_MESSAGE_BLOCKS_TEXT_LENGTH = 13200
# Packing target, leaving headroom for structural fields the size proxy may
# not count exactly.
_MESSAGE_BLOCKS_TEXT_TARGET = 12800
ATX_HEADING_PATTERN = re.compile(r"^[ \t]{0,3}#{1,6}(?:[ \t]|$)")


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


_QUOTE_MARKER_PREFIX_PATTERN = re.compile(r"^[ \t]{0,3}>[ \t]?")


_TEXT_SIZE_KEYS = frozenset({"text", "url", "alt_text", "image_url"})
