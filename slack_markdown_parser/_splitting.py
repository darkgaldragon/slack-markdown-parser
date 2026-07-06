"""Slack size-limit machinery: markdown block creation, expansion-item
estimation, size splitting, and per-message block packing."""

from __future__ import annotations

from typing import Any

from ._code_regions import (
    _is_fence_close,
    _iter_fence_states,
    _match_fence_open,
    _multiline_code_span_line_map,
)
from ._constants import (
    _MARKDOWN_EXPANSION_ITEMS_TARGET,
    _MARKDOWN_SPLIT_TARGET_LENGTH,
    _MESSAGE_BLOCKS_TEXT_TARGET,
    _QUOTE_MARKER_PREFIX_PATTERN,
    _TEXT_SIZE_KEYS,
    ATX_HEADING_PATTERN,
    LIST_ITEM_PATTERN,
    SLACK_MAX_BLOCKS_PER_MESSAGE,
    SLACK_MAX_EXPANSION_ITEMS_PER_MESSAGE,
    SLACK_MAX_MARKDOWN_TEXT_LENGTH,
)
from ._emphasis import _format_markdown_with_spacing_metadata
from ._fallback import _build_markdown_block_plain_text
from ._lines import _inject_visual_blank_line_placeholders, _is_thematic_break_line


class _AnnotatedSlackBlock(dict):
    """Dict-like block carrying non-serialized metadata for local helpers."""


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
    block._expansion_items = _estimate_markdown_expansion_items(formatted)
    return block


def _is_markdown_expansion_breaker_line(line: str) -> bool:
    """Return True for lines Slack expands into their own top-level block.

    ATX headings and thematic breaks each become one expansion item and end
    the surrounding content run. A setext ``===`` underline is counted too;
    that can over-count by one (heading text + underline), which only makes
    the estimate conservative.
    """
    if ATX_HEADING_PATTERN.match(line):
        return True
    if _is_thematic_break_line(line):
        return True
    stripped = line.strip()
    return bool(stripped) and set(stripped) == {"="}


def _estimate_markdown_expansion_items(text: str) -> int:
    """Estimate how many native blocks Slack expands this markdown text into.

    Model measured against a real workspace (see the constants above): each
    heading / thematic break is one item, and each maximal run of any other
    content *between* those breakers is one item — blank lines inside a run
    do not split it. Fenced lines always count as run content.
    """
    items = 0
    in_run = False
    for line, is_fenced, _ in _iter_fence_states(text.split("\n")):
        if is_fenced:
            if not in_run:
                items += 1
                in_run = True
            continue
        if not line.strip():
            continue
        if _is_markdown_expansion_breaker_line(line):
            items += 1
            in_run = False
            continue
        if not in_run:
            items += 1
            in_run = True
    return max(1, items)


def _split_text_at_blank_lines(text: str, max_length: int, max_items: int) -> list[str]:
    """Greedily pack paragraph units into pieces within both budgets.

    Units are separated by blank-line runs outside fenced code (blank lines
    inside a fence never split). The blank run at a piece boundary is dropped
    — adjacent Slack blocks already render separated — while blank runs
    packed inside a piece are kept verbatim. A piece is closed when adding
    the next unit would exceed ``max_length`` characters or ``max_items``
    estimated expansion items. A single unit over either budget is returned
    oversized; the caller splits it harder.
    """
    if (
        len(text) <= max_length
        and _estimate_markdown_expansion_items(text) <= max_items
    ):
        return [text]

    units: list[list[str]] = []
    content: list[str] = []
    blanks: list[str] = []
    for line, is_fenced, _ in _iter_fence_states(text.split("\n")):
        if not is_fenced and not line.strip():
            if content:
                blanks.append(line)
            else:
                # Leading blank lines stay attached to the first unit.
                content.append(line)
            continue
        if blanks:
            units.append(content)
            units.append(blanks)
            content, blanks = [], []
        content.append(line)
    if content:
        units.append(content)
    if blanks:
        units.append(blanks)

    pieces: list[str] = []
    current: list[str] = []
    pending_blanks: list[str] = []
    for index in range(0, len(units), 2):
        unit = units[index]
        candidate = current + (pending_blanks if current else []) + unit
        candidate_text = "\n".join(candidate)
        if current and (
            len(candidate_text) > max_length
            or _estimate_markdown_expansion_items(candidate_text) > max_items
        ):
            pieces.append("\n".join(current))
            current = list(unit)
        else:
            current = candidate
        pending_blanks = units[index + 1] if index + 1 < len(units) else []
    if current:
        pieces.append("\n".join(current))
    return pieces


def _split_line_verbatim_to_length(line: str, max_length: int) -> list[str]:
    """Hard-cut one overlong line into parts, preserving every character.

    For fenced code lines only: the prose splitter prefers a space boundary
    and drops that space — silently altering code — and its quote/list
    marker handling must not apply to a code line that merely starts with
    ``> `` or ``- ``.
    """
    return [line[i : i + max_length] for i in range(0, len(line), max_length)]


def _split_single_line_to_length(line: str, max_length: int) -> list[str]:
    """Split one overlong prose line, preferring a space boundary near the
    limit.

    A leading quote or list marker is never split off on its own (the space
    search starts after it), and a quote marker is re-applied to continuation
    parts so consecutive parts keep rendering as one quote. List continuations
    stay unmarked: as following lines they are lazy item continuations.
    """
    quote_match = _QUOTE_MARKER_PREFIX_PATTERN.match(line)
    marker_match = quote_match or LIST_ITEM_PATTERN.match(line)
    prefix_end = marker_match.end() if marker_match else 0
    continuation_prefix = quote_match.group(0) if quote_match else ""

    parts: list[str] = []
    while len(line) > max_length:
        cut = line.rfind(" ", prefix_end + 1, max_length + 1)
        if cut <= prefix_end:
            parts.append(line[:max_length])
            line = continuation_prefix + line[max_length:]
        else:
            parts.append(line[:cut])
            line = continuation_prefix + line[cut + 1 :]
        prefix_end = len(continuation_prefix)
    parts.append(line)
    return parts


def _split_lines_to_length(text: str, max_length: int, max_items: int) -> list[str]:
    """Split at line boundaries into pieces within both budgets.

    Last-resort splitter for content that exceeds a budget without blank-line
    split points (a single huge paragraph, a fence body, or a long run of
    headings). When the cut lands inside an (unclosed) fence, the continuation
    piece re-opens the fence with the original delimiter line so both pieces
    keep rendering as code.
    """
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    current_items = 0
    in_run = False
    active_fence_open: str | None = None
    lines = text.split("\n")
    _, span_continuation = _multiline_code_span_line_map(lines)
    # Keeping a span-crossing boundary glued may exceed the packing target;
    # the valve bounds that overshoot so shrink-and-retry still converges and
    # the hard block limit keeps real headroom. A span larger than the valve
    # is cut anyway (documented limitation).
    span_valve = min(max_length + 512, SLACK_MAX_MARKDOWN_TEXT_LENGTH - 256)
    # Total length of the span-connected line group starting at each line,
    # used to flush *before* a span opener when the accumulated piece would
    # otherwise push the span past the valve even though the span alone fits.
    span_group_total = [0] * len(lines)
    for index in range(len(lines) - 1, -1, -1):
        continues = index + 1 < len(lines) and span_continuation[index + 1]
        span_group_total[index] = len(lines[index]) + (
            1 + span_group_total[index + 1] if continues else 0
        )

    def flush(next_fence_prefix: str | None) -> None:
        nonlocal current, current_len, current_items, in_run
        # A piece holding nothing but the fence-open line being reopened is a
        # synthetic duplicate (the opener was consumed, the first body part
        # overflowed): emitting it would post a stray delimiter-only block.
        if current and not (
            next_fence_prefix is not None and current == [next_fence_prefix]
        ):
            pieces.append("\n".join(current))
        if next_fence_prefix:
            current = [next_fence_prefix]
            current_len = len(next_fence_prefix)
            current_items = 1
            in_run = True
        else:
            current = []
            current_len = 0
            current_items = 0
            in_run = False

    for line_index, (line, is_fenced, is_opening) in enumerate(
        _iter_fence_states(lines)
    ):
        if is_opening:
            active_fence_open = line
        elif not is_fenced:
            active_fence_open = None

        # A fence-close line never starts a new piece: flushing on it would
        # emit the close (plus reopened fence) as a stray delimiter-only
        # block. Appending it may exceed the packing target by a few
        # characters, well within the headroom to the hard limit.
        line_is_fence_close = False
        if is_fenced and not is_opening and active_fence_open is not None:
            open_spec = _match_fence_open(active_fence_open)
            line_is_fence_close = open_spec is not None and _is_fence_close(
                line, open_spec
            )

        line_is_blank = not is_fenced and not line.strip()
        line_is_breaker = (
            not is_fenced
            and not line_is_blank
            and _is_markdown_expansion_breaker_line(line)
        )

        for part_index, part in enumerate(
            [line]
            if len(line) <= max_length
            else (
                _split_line_verbatim_to_length(line, max_length)
                if is_fenced
                else _split_single_line_to_length(line, max_length)
            )
        ):
            # Word-split continuations of a breaker line render as plain
            # content, so only the first part keeps the breaker class.
            is_breaker = line_is_breaker and part_index == 0
            if line_is_blank:
                part_items = 0
            elif is_breaker:
                part_items = 1
            else:
                part_items = 0 if in_run else 1

            added = len(part) + (1 if current else 0)
            keep_span_together = (
                part_index == 0
                and span_continuation[line_index]
                and current_len + added <= span_valve
            )
            opens_fitting_span = (
                part_index == 0
                and len(line) <= max_length
                and not span_continuation[line_index]
                and line_index + 1 < len(lines)
                and span_continuation[line_index + 1]
                and span_group_total[line_index] <= span_valve
            )
            span_needs_fresh_piece = (
                opens_fitting_span
                and current_len + (1 if current else 0) + span_group_total[line_index]
                > span_valve
            )
            if (
                current
                and not line_is_fence_close
                and not keep_span_together
                and (
                    current_len + added > max_length
                    or current_items + part_items > max_items
                    or span_needs_fresh_piece
                )
            ):
                reopen = active_fence_open if active_fence_open != part else None
                flush(reopen)
                added = len(part) + (1 if current else 0)
                if line_is_blank:
                    part_items = 0
                elif is_breaker:
                    part_items = 1
                else:
                    part_items = 0 if in_run else 1
            current.append(part)
            current_len += added
            current_items += part_items
            if is_breaker:
                in_run = False
            elif not line_is_blank:
                in_run = True

    if current:
        pieces.append("\n".join(current))
    return pieces


def _markdown_block_fits_slack_limits(block: dict[str, Any]) -> bool:
    return (
        len(block["text"]) <= SLACK_MAX_MARKDOWN_TEXT_LENGTH
        and _estimate_markdown_expansion_items(block["text"])
        <= SLACK_MAX_EXPANSION_ITEMS_PER_MESSAGE
    )


def _create_markdown_blocks(
    content: str, *, preserve_visual_blank_lines: bool = False
) -> list[dict[str, Any]]:
    """Build ``markdown`` blocks that fit Slack's measured hard limits.

    The whole content is tried as a single block first. Only when the
    *formatted* text exceeds ``SLACK_MAX_MARKDOWN_TEXT_LENGTH`` or the
    estimated server-side expansion exceeds the per-message item budget is
    the raw content split — at paragraph boundaries when possible, then at
    line/word boundaries — and each piece re-checked after formatting,
    shrinking the packing budget geometrically until every block fits.
    """

    def build(piece: str) -> dict[str, Any] | None:
        return _create_markdown_block(
            piece, preserve_visual_blank_lines=preserve_visual_blank_lines
        )

    whole = build(content)
    if whole is None:
        return []
    if _markdown_block_fits_slack_limits(whole):
        return [whole]

    blocks: list[dict[str, Any]] = []
    worklist: list[tuple[str, int, int]] = [
        (content, _MARKDOWN_SPLIT_TARGET_LENGTH, _MARKDOWN_EXPANSION_ITEMS_TARGET)
    ]
    while worklist:
        piece, budget, items_budget = worklist.pop(0)
        block = build(piece)
        if block is None:
            continue
        if _markdown_block_fits_slack_limits(block):
            blocks.append(block)
            continue

        sub_pieces = _split_text_at_blank_lines(piece, budget, items_budget)
        if len(sub_pieces) == 1:
            sub_pieces = _split_lines_to_length(piece, budget, items_budget)
        if len(sub_pieces) > 1:
            worklist = [(sub, budget, items_budget) for sub in sub_pieces] + worklist
            continue
        if budget > 256 or items_budget > 8:
            # The piece fits the raw budgets but its *formatted* text overflows
            # (ZWSP/NBSP inflation or estimation drift): shrink and retry.
            worklist.insert(
                0,
                (
                    piece,
                    max(256, int(budget * 0.8)),
                    max(8, int(items_budget * 0.8)),
                ),
            )
            continue
        # A floor-budget piece cannot exceed the hard limits, so this is
        # unreachable; keep the block rather than loop forever.
        blocks.append(block)
    return blocks


def _block_expansion_weight(block: dict[str, Any]) -> int:
    """Weight of one block against Slack's per-message expansion budget.

    Slack expands ``markdown`` blocks server-side and enforces the 50-item
    limit on the expanded result, so a markdown block counts as its estimated
    expansion; every other block type posts as a single item.
    """
    if not isinstance(block, dict) or block.get("type") != "markdown":
        return 1
    annotated = getattr(block, "_expansion_items", None)
    if isinstance(annotated, int) and annotated > 0:
        return annotated
    return _estimate_markdown_expansion_items(str(block.get("text", "")))


def _block_text_size(value: Any) -> int:
    """Rough text payload of a block against the per-message total budget.

    Slack's ``msg_blocks_too_long`` check counts content across block types
    (a 11,900-char markdown block plus a 1,400-char rich_text was rejected),
    so this sums every string under content-carrying keys, recursively.
    """
    if isinstance(value, dict):
        total = 0
        for key, sub in value.items():
            if key in _TEXT_SIZE_KEYS and isinstance(sub, str):
                total += len(sub)
            else:
                total += _block_text_size(sub)
        return total
    if isinstance(value, list):
        return sum(_block_text_size(item) for item in value)
    return 0


def split_blocks_by_table(blocks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split blocks to satisfy Slack table and per-message constraints.

    A message holds at most one ``table`` block, at most
    ``SLACK_MAX_BLOCKS_PER_MESSAGE`` posted blocks, at most
    ``SLACK_MAX_EXPANSION_ITEMS_PER_MESSAGE`` estimated post-expansion items
    (headings and thematic breaks inside ``markdown`` blocks count
    individually toward that budget), and at most
    ``SLACK_MAX_MESSAGE_BLOCKS_TEXT_LENGTH`` characters of block text in
    total across block types.
    """
    messages: list[list[dict[str, Any]]] = []
    current_message: list[dict[str, Any]] = []
    current_weight = 0
    current_text_size = 0

    for block in blocks or []:
        if isinstance(block, dict) and block.get("type") == "table":
            if current_message:
                messages.append(current_message)
            messages.append([block])
            current_message = []
            current_weight = 0
            current_text_size = 0
        else:
            weight = _block_expansion_weight(block)
            text_size = _block_text_size(block)
            if current_message and (
                len(current_message) >= SLACK_MAX_BLOCKS_PER_MESSAGE
                or current_weight + weight > SLACK_MAX_EXPANSION_ITEMS_PER_MESSAGE
                or current_text_size + text_size > _MESSAGE_BLOCKS_TEXT_TARGET
            ):
                messages.append(current_message)
                current_message = []
                current_weight = 0
                current_text_size = 0
            current_message.append(block)
            current_weight += weight
            current_text_size += text_size

    if current_message:
        messages.append(current_message)

    return messages
