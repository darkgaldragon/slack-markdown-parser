"""Fenced-code and inline-code-span tracking (single source of truth).

Fence state iteration, paragraph-bounded inline code span detection, and
the transforms that apply prose rewrites outside code regions."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator

from ._constants import (
    _CODE_SPAN_BLANK_LINE_PATTERN,
    FENCE_OPEN_PATTERN,
    INLINE_CODE_PLACEHOLDER_PATTERN,
    INTERNAL_MARKER_CHAR_PATTERN,
)


def _find_inline_code_span_end(text: str, start: int) -> int | None:
    """Find the end of the inline code span opened at ``start``.

    Per CommonMark, a code span closes only with a backtick run of *equal*
    length: a lone `` ` `` must not pair with the first backtick of a later
    ``` `` ``` run. Runs of a different length are skipped whole.
    """
    delimiter_end = start
    while delimiter_end < len(text) and text[delimiter_end] == "`":
        delimiter_end += 1
    delimiter_length = delimiter_end - start

    cursor = delimiter_end
    while True:
        closing = text.find("`", cursor)
        if closing == -1:
            return None
        run_end = closing
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        if run_end - closing == delimiter_length:
            return run_end
        cursor = run_end


def _iter_inline_code_spans(text: str) -> Iterator[tuple[int, int]]:
    """Yield ``(start, end)`` for each inline code span in ``text``.

    Single source of truth for the module's span model: a span closes only on
    a backtick run of the *same* length as its opener, may cross soft line
    breaks, and never crosses a blank line. This matches measured Slack
    rendering (2026-07-05): Slack pairs backticks across soft line breaks
    within a paragraph and renders the stretch as inline code, while
    backticks in different paragraphs never pair — so the blank-line bound
    keeps one stray backtick from affecting anything beyond its paragraph.
    """
    cursor = text.find("`")
    while cursor != -1:
        span_end = _find_inline_code_span_end(text, cursor)
        if span_end is None or _CODE_SPAN_BLANK_LINE_PATTERN.search(
            text, cursor, span_end
        ):
            # No same-paragraph closing run: the backticks are literal text.
            delimiter_end = cursor
            while delimiter_end < len(text) and text[delimiter_end] == "`":
                delimiter_end += 1
            cursor = text.find("`", delimiter_end)
            continue
        yield cursor, span_end
        cursor = text.find("`", span_end)


def _multiline_code_span_line_map(
    lines: list[str],
) -> tuple[list[bool], list[bool]]:
    """Per-line view of inline code spans that cross soft line breaks.

    Returns ``(interior, continuation)``: ``interior[i]`` is True when line
    ``i`` carries any part of a multi-line inline code span, and
    ``continuation[i]`` is True when such a span crosses the boundary between
    line ``i - 1`` and line ``i``. Spans are computed per non-fenced chunk —
    backticks inside a fence are literal, and a fence delimiter terminates a
    span (block structure binds before inline code, as in CommonMark) — using
    the module's paragraph-bounded span model.
    """
    interior = [False] * len(lines)
    continuation = [False] * len(lines)
    chunk_indices: list[int] = []

    def flush_chunk() -> None:
        if not chunk_indices:
            return
        offsets: list[int] = []
        position = 0
        for index in chunk_indices:
            offsets.append(position)
            position += len(lines[index]) + 1
        chunk_text = "\n".join(lines[index] for index in chunk_indices)
        for span_start, span_end in _iter_inline_code_spans(chunk_text):
            if "\n" not in chunk_text[span_start:span_end]:
                continue
            for local, line_start in enumerate(offsets):
                global_index = chunk_indices[local]
                line_end = line_start + len(lines[global_index])
                if line_start < span_end and span_start <= line_end:
                    interior[global_index] = True
                    if span_start < line_start:
                        continuation[global_index] = True
        chunk_indices.clear()

    for index, (_, is_fenced, _) in enumerate(_iter_fence_states(lines)):
        if is_fenced:
            flush_chunk()
            continue
        chunk_indices.append(index)
    flush_chunk()

    return interior, continuation


def _transform_outside_inline_code(text: str, transform: Callable[[str], str]) -> str:
    """Apply ``transform`` to text while keeping inline code spans verbatim.

    Spans follow the module's paragraph-bounded span model
    (``_iter_inline_code_spans``): rewriting a span's content would visibly
    corrupt what Slack renders as code.

    Spans are replaced with placeholder tokens (which contain no backticks or
    angle brackets) rather than split out, so the transform still sees any
    construct that *spans* a code span — e.g. an invalid angle token such as
    ``<foo `bar` baz>`` is neutralized as a whole while the span content
    itself stays verbatim. Reserved marker code points are stripped from the
    input first, so crafted input cannot collide with the placeholders.
    """
    text = INTERNAL_MARKER_CHAR_PATTERN.sub("", text)

    spans: list[str] = []
    parts: list[str] = []
    plain_start = 0

    for start, end in _iter_inline_code_spans(text):
        parts.append(text[plain_start:start])
        parts.append(f"\ufff0code{len(spans)}\ufff1")
        spans.append(text[start:end])
        plain_start = end

    parts.append(text[plain_start:])
    transformed = transform("".join(parts))

    if not spans:
        return transformed
    placeholder_map = {f"\ufff0code{idx}\ufff1": span for idx, span in enumerate(spans)}
    return INLINE_CODE_PLACEHOLDER_PATTERN.sub(
        lambda match: placeholder_map.get(match.group(0), match.group(0)),
        transformed,
    )


def _transform_outside_code_regions(text: str, transform: Callable[[str], str]) -> str:
    """Apply ``transform`` outside fenced code blocks and inline code spans.

    Code samples must reach Slack verbatim: neither Slack's ``markdown`` block
    renderer nor ``rich_text_preformatted`` interprets their content, so any
    rewrite inside a code region is visible corruption.
    """
    return "".join(
        chunk if is_fenced else _transform_outside_inline_code(chunk, transform)
        for is_fenced, chunk in _split_fenced_code_chunks(text)
    )


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


def _iter_fence_states(lines: Iterable[str]) -> Iterator[tuple[str, bool, bool]]:
    """Yield ``(line, is_fenced, is_opening)`` for each line.

    Single source of truth for fenced-code tracking across this module.
    ``is_fenced`` covers the fence delimiter lines themselves and the body of
    an unclosed trailing fence; ``is_opening`` marks the opening delimiter
    line so callers can flush per-fence state. Works with or without trailing
    newlines on the lines.
    """
    active_fence: tuple[str, int] | None = None
    for line in lines:
        if active_fence is None:
            opening_fence = _match_fence_open(line)
            if opening_fence is not None:
                active_fence = opening_fence
                yield line, True, True
                continue
            yield line, False, False
            continue
        yield line, True, False
        if _is_fence_close(line, active_fence):
            active_fence = None


def _split_fenced_code_chunks(text: str) -> list[tuple[bool, str]]:
    chunks: list[tuple[bool, str]] = []
    if not text:
        return chunks

    current: list[str] = []
    current_is_fenced = False

    for line, is_fenced, is_opening in _iter_fence_states(
        text.splitlines(keepends=True)
    ):
        if current and (is_opening or is_fenced != current_is_fenced):
            chunks.append((current_is_fenced, "".join(current)))
            current = []
        current.append(line)
        current_is_fenced = is_fenced

    if current:
        chunks.append((current_is_fenced, "".join(current)))

    return chunks
