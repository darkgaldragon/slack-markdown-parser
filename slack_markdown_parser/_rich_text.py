"""rich_text inline element construction (links, code, emphasis, mentions)
and their plain-text downgrades."""

from __future__ import annotations

from typing import Any

from ._constants import TABLE_TOKEN_PATTERN
from ._sanitize import strip_zero_width_spaces


def _slack_mention_element(mention: str) -> dict[str, Any]:
    """Map a Slack mention token body to its rich_text element.

    ``mention`` is the token interior without the angle brackets or ``|label``
    (e.g. ``@U123``, ``#C123``, ``!subteam^S123``, ``!here``). Slack renders
    these from the id alone, so no display text is carried.
    """
    sigil, body = mention[0], mention[1:]
    if sigil == "@":
        return {"type": "user", "user_id": body}
    if sigil == "#":
        return {"type": "channel", "channel_id": body}
    if body.startswith("subteam^"):
        return {"type": "usergroup", "usergroup_id": body[len("subteam^") :]}
    return {"type": "broadcast", "range": body}


def _slack_mention_element_to_token(element: dict[str, Any]) -> str:
    """Inverse of :func:`_slack_mention_element` for plain-text fallbacks.

    Emitting the canonical ``<#C…>`` / ``<@U…>`` token (rather than an empty
    string) keeps the mention live when a rich_text block is downgraded to a
    mrkdwn fallback, so it still links and notifies.
    """
    element_type = element.get("type")
    if element_type == "user":
        return f"<@{element.get('user_id', '')}>"
    if element_type == "channel":
        return f"<#{element.get('channel_id', '')}>"
    if element_type == "usergroup":
        return f"<!subteam^{element.get('usergroup_id', '')}>"
    return f"<!{element.get('range', '')}>"


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
        mention = match.group("mention")
        token = match.group("token") or ""

        if markdown_label and markdown_url:
            element = {"type": "link", "url": markdown_url, "text": markdown_label}
        elif angle_url:
            element = {
                "type": "link",
                "url": angle_url,
                "text": angle_label or angle_url,
            }
        elif mention:
            element = _slack_mention_element(mention)
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


def _rich_text_inline_elements_to_plain_text(elements: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        element_type = element.get("type")
        if element_type == "link":
            texts.append(str(element.get("text") or element.get("url", "")))
        elif element_type in {"user", "channel", "usergroup", "broadcast"}:
            texts.append(_slack_mention_element_to_token(element))
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
