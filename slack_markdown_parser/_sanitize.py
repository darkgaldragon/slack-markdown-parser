"""Slack text cleanup: HTML entities, control characters, angle-bracket
tokens, and bare-URL autolink normalization."""

from __future__ import annotations

import html
import re

from ._code_regions import (
    _find_inline_code_span_end,
    _split_fenced_code_chunks,
    _transform_outside_code_regions,
)
from ._constants import (
    _CODE_SPAN_BLANK_LINE_PATTERN,
    _URL_CJK_BOUNDARY_CHARS,
    _URL_STOP_CHARS,
    _URL_TRAILING_PUNCTUATION,
    ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS,
    ANSI_ESCAPE_PATTERN,
    BARE_URL_PATTERN,
    CONTROL_CHAR_PATTERN,
    INTERNAL_MARKER_CHAR_PATTERN,
    MARKDOWN_LINK_PATTERN,
    SLACK_ANGLE_TOKEN_PATTERN,
)


def decode_html_entities(text: str) -> str:
    """Decode HTML entities in prose while leaving code regions verbatim.

    Prose entities such as ``&gt;`` are decoded for natural reading, but a
    fenced code block or inline code span showing ``&amp;`` keeps the literal
    entity: code samples are content, not markup to repair.
    """
    if not text or "&" not in text:
        return text
    return _transform_outside_code_regions(text, html.unescape)


def strip_zero_width_spaces(text: str) -> str:
    """Strip zero-width spaces from text."""
    return re.sub(r"[\u200B\uFEFF]", "", text or "")


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


def _is_allowed_slack_angle_token(token: str) -> bool:
    return any(pattern.match(token) for pattern in ALLOWED_SLACK_ANGLE_TOKEN_PATTERNS)


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
                # Same paragraph-bounded span model as
                # _transform_outside_inline_code: Slack pairs backticks across
                # soft line breaks, so a URL inside such a span must stay bare
                # — wrapping it would show a literal ``<…>`` inside the
                # rendered code span.
                if (
                    code_span_end is not None
                    and not _CODE_SPAN_BLANK_LINE_PATTERN.search(
                        chunk, cursor, code_span_end
                    )
                ):
                    parts.append(chunk[cursor:code_span_end])
                    cursor = code_span_end
                    continue
                # No same-paragraph span: skip the whole backtick run, as
                # _iter_inline_code_spans does. Restarting inside the run
                # would open a fake shorter-delimiter span and swallow a
                # later real span together with its content.
                run_end = cursor
                while run_end < len(chunk) and chunk[run_end] == "`":
                    run_end += 1
                parts.append(chunk[cursor:run_end])
                cursor = run_end
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
    """Remove control noise and neutralize invalid Slack angle tokens.

    ANSI escapes, control characters, and this module's reserved in-band
    marker code points are removed everywhere — including code regions —
    because they are never legitimate visible content. Angle-token
    neutralization rewrites visible text, so it skips fenced code blocks and
    inline code spans: a code sample containing ``<div>`` must reach Slack
    verbatim.
    """
    if not text:
        return text

    cleaned = ANSI_ESCAPE_PATTERN.sub("", text)
    cleaned = CONTROL_CHAR_PATTERN.sub("", cleaned)
    cleaned = INTERNAL_MARKER_CHAR_PATTERN.sub("", cleaned)

    def replace_invalid_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if _is_allowed_slack_angle_token(token):
            return token
        return f"＜{token[1:-1]}＞"

    def neutralize_angle_tokens(segment: str) -> str:
        return SLACK_ANGLE_TOKEN_PATTERN.sub(replace_invalid_token, segment)

    return _transform_outside_code_regions(cleaned, neutralize_angle_tokens)


def _match_slack_angle_token_end(text: str, start: int) -> int | None:
    """Return the end index (exclusive) of a valid Slack angle token at ``start``.

    Only recognized Slack tokens (links, mentions, ``<!date^…>``) protect
    their inner pipes from cell splitting. A bare ``<`` — e.g. the comparison
    in ``x < y`` — is literal text and must not open a protected region;
    a stateful "inside angle brackets" flag did exactly that, so one lone
    ``<`` swallowed every later pipe on the line into a single cell.
    """
    if start >= len(text) or text[start] != "<":
        return None
    closing = text.find(">", start + 1)
    if closing == -1:
        return None
    token = text[start : closing + 1]
    return closing + 1 if _is_allowed_slack_angle_token(token) else None
