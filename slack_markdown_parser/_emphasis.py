"""Emphasis stabilization: underscore-emphasis normalization and the
zero-width-space / visible-space engine for CJK-safe Slack rendering."""

from __future__ import annotations

import re

from ._code_regions import (
    _iter_inline_code_spans,
    _split_fenced_code_chunks,
    _transform_outside_inline_code,
)
from ._constants import (
    DOUBLE_UNDERSCORE_EMPHASIS_PATTERN,
    EMPHASIS_PATTERNS,
    INLINE_CODE_PLACEHOLDER_PATTERN,
    INTERNAL_MARKER_CHAR_PATTERN,
    PROTECTED_UNDERSCORE_SPAN_PATTERN,
    SINGLE_UNDERSCORE_EMPHASIS_PATTERN,
    STRIP_LEFT_ZWSP_MARKER,
    STRIP_RIGHT_ZWSP_MARKER,
    SYNTH_SPACE_MARKER,
    VISIBLE_BOUNDARY_CHARS,
    ZWSP,
)


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


def _normalize_underscore_emphasis_chunk(text: str) -> str:
    # Inline code spans are paragraph-bounded (the module's span model) and
    # must stay verbatim: Slack renders them as code, where a rewritten
    # ``_value_`` is visible corruption. The single-line backtick alternative
    # in PROTECTED_UNDERSCORE_SPAN_PATTERN cannot cover a span that crosses a
    # soft line break, so the shared span walker protects those first (it
    # also strips the reserved marker code points).
    return _transform_outside_inline_code(text, _normalize_underscore_emphasis_prose)


def _normalize_underscore_emphasis_prose(text: str) -> str:
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

    # Defense in depth for direct calls that bypass sanitize_slack_text: input
    # carrying our reserved marker code points would collide with the inline
    # placeholder machinery below.
    text = INTERNAL_MARKER_CHAR_PATTERN.sub("", text)

    boundary_chars = {*VISIBLE_BOUNDARY_CHARS, ZWSP, SYNTH_SPACE_MARKER}

    def wrap_match(match: re.Match[str], source: str) -> str:
        return wrap_span(source, match.start(), match.end())

    def wrap_span(source: str, start: int, end: int) -> str:
        token = source[start:end]
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

        def resolve_placeholder_raw(placeholder_match: re.Match[str]) -> str:
            # Unknown placeholder-shaped sequences pass through unchanged
            # (belt-and-braces against in-band collisions; the markers are
            # already stripped at every entry point).
            entry = replacements.get(placeholder_match.group(0))
            return entry["raw"] if entry else placeholder_match.group(0)

        resolved_text = INLINE_CODE_PLACEHOLDER_PATTERN.sub(
            resolve_placeholder_raw, match.group(0)
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

        for idx, (span_start, span_end) in enumerate(_iter_inline_code_spans(segment)):
            placeholder = f"\ufff0code{idx}\ufff1"
            protected_parts.append(segment[last_end:span_start])
            protected_parts.append(placeholder)
            placeholder_map[placeholder] = {
                "raw": segment[span_start:span_end],
                "wrapped": wrap_span(segment, span_start, span_end),
            }
            last_end = span_end

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

        def restore_placeholder(placeholder_match: re.Match[str]) -> str:
            entry = placeholder_map.get(placeholder_match.group(0))
            return entry["wrapped"] if entry else placeholder_match.group(0)

        protected_segment = INLINE_CODE_PLACEHOLDER_PATTERN.sub(
            restore_placeholder, protected_segment
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
