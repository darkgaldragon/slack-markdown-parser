from __future__ import annotations

import argparse
import json
from pathlib import Path

ZWSP = "\u200b"

OUTER_WRAPPERS = {
    "bold": lambda text: f"**{text}**",
    "italic": lambda text: f"*{text}*",
    "strike": lambda text: f"~~{text}~~",
}

INNER_WRAPPERS = {
    "plain": lambda text: text,
    "bold": lambda text: f"**{text}**",
    "italic": lambda text: f"*{text}*",
    "strike": lambda text: f"~~{text}~~",
    "code": lambda text: f"`{text}`",
    "link": lambda text: f"[{text}](https://example.com/render-test)",
}

BOUNDARIES = [
    {
        "id": "en_tight",
        "locale": "en",
        "template": "Alpha,{outer}.",
    },
    {
        "id": "en_outer_zwsp",
        "locale": "en",
        "template": f"Alpha,{ZWSP}{{outer}}{ZWSP}.",
    },
    {
        "id": "en_spaces_both",
        "locale": "en",
        "template": "Alpha, {outer} .",
    },
    {
        "id": "ja_tight",
        "locale": "ja",
        "template": "詳細は、{outer}を確認してください。",
    },
    {
        "id": "ja_outer_zwsp",
        "locale": "ja",
        "template": f"詳細は、{ZWSP}{{outer}}{ZWSP}を確認してください。",
    },
    {
        "id": "ja_spaces_both",
        "locale": "ja",
        "template": "詳細は、 {outer} を確認してください。",
    },
    {
        "id": "ja_space_left",
        "locale": "ja",
        "template": "詳細は、 {outer}を確認してください。",
    },
    {
        "id": "ja_space_right",
        "locale": "ja",
        "template": "詳細は、{outer} を確認してください。",
    },
    {
        "id": "zh_tight",
        "locale": "zh",
        "template": "详情，{outer}请确认。",
    },
    {
        "id": "zh_outer_zwsp",
        "locale": "zh",
        "template": f"详情，{ZWSP}{{outer}}{ZWSP}请确认。",
    },
    {
        "id": "zh_spaces_both",
        "locale": "zh",
        "template": "详情， {outer} 请确认。",
    },
    {
        "id": "zh_space_left",
        "locale": "zh",
        "template": "详情， {outer}请确认。",
    },
    {
        "id": "zh_space_right",
        "locale": "zh",
        "template": "详情，{outer} 请确认。",
    },
    {
        "id": "ko_tight",
        "locale": "ko",
        "template": "설명,{outer}입니다.",
    },
    {
        "id": "ko_outer_zwsp",
        "locale": "ko",
        "template": f"설명,{ZWSP}{{outer}}{ZWSP}입니다.",
    },
    {
        "id": "ko_spaces_both",
        "locale": "ko",
        "template": "설명, {outer} 입니다.",
    },
    {
        "id": "ko_space_left",
        "locale": "ko",
        "template": "설명, {outer}입니다.",
    },
    {
        "id": "ko_space_right",
        "locale": "ko",
        "template": "설명,{outer} 입니다.",
    },
]

DEFAULT_OUTPUT = Path("tests/fixtures/slack_nested_modifier_matrix.md")

CONTENT_VARIANTS = {
    "plain": {
        "en": "Outer {inner} tail",
        "ja": "外側{inner}装飾",
        "zh": "外侧{inner}样式",
        "ko": "바깥{inner}강조",
    },
    "parens": {
        "en": "Outer ({inner}) tail",
        "ja": "外側({inner})装飾",
        "zh": "外侧({inner})样式",
        "ko": "바깥({inner})강조",
    },
    "quotes": {
        "en": 'Outer "{inner}" tail',
        "ja": "外側「{inner}」装飾",
        "zh": "外侧“{inner}”样式",
        "ko": '바깥"{inner}"강조',
    },
}

INNER_SEEDS = {
    "en": "INNER",
    "ja": "内側",
    "zh": "内侧",
    "ko": "내부",
}


def default_output_path(content_variant: str) -> Path:
    if content_variant == "plain":
        return DEFAULT_OUTPUT
    return Path(f"tests/fixtures/slack_nested_modifier_matrix_{content_variant}.md")


def _parse_csv_filter(raw_value: str | None) -> set[str] | None:
    if raw_value is None:
        return None
    values = {item.strip() for item in raw_value.split(",") if item.strip()}
    return values or None


def build_nested_content(locale: str, inner_id: str, content_variant: str) -> str:
    inner_seed = INNER_SEEDS[locale]
    template = CONTENT_VARIANTS[content_variant][locale]
    inner_markup = INNER_WRAPPERS[inner_id](inner_seed)
    return template.format(inner=inner_markup)


def build_cases(
    content_variant: str = "plain",
    locales: set[str] | None = None,
    inners: set[str] | None = None,
) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for boundary in BOUNDARIES:
        locale = boundary["locale"]
        if locales is not None and locale not in locales:
            continue
        for outer_id, outer_wrap in OUTER_WRAPPERS.items():
            for inner_id in INNER_WRAPPERS:
                if inners is not None and inner_id not in inners:
                    continue
                if inner_id == outer_id:
                    continue

                content = build_nested_content(locale, inner_id, content_variant)
                outer_markup = outer_wrap(content)
                markdown = boundary["template"].format(outer=outer_markup)
                case_id = (
                    f"{content_variant}__{boundary['id']}__outer_{outer_id}"
                    f"__inner_{inner_id}"
                )
                cases.append(
                    {
                        "case_id": case_id,
                        "content_variant": content_variant,
                        "locale": locale,
                        "boundary": boundary["id"],
                        "outer": outer_id,
                        "inner": inner_id,
                        "markdown": markdown,
                    }
                )
    return cases


def render_markdown(cases: list[dict[str, str]]) -> str:
    sections = [
        "# Nested Modifier Render Matrix",
        "",
        "Generated render-test cases for Slack markdown verification.",
        "",
        f"Total cases: {len(cases)}",
        "",
    ]
    for case in cases:
        sections.extend(
            [
                f"CASE {case['case_id']}",
                case["markdown"],
                "",
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate nested markdown modifier render-test cases."
    )
    parser.add_argument(
        "--content-variant",
        choices=tuple(CONTENT_VARIANTS),
        default="plain",
        help="Inner content shape to generate.",
    )
    parser.add_argument(
        "--locales",
        default="en,ja",
        help="Comma-separated locales to include. Default: en,ja",
    )
    parser.add_argument(
        "--inners",
        help="Optional comma-separated inner modifier ids to include.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        help="Output file path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = (
        Path(args.output) if args.output else default_output_path(args.content_variant)
    )
    locales = _parse_csv_filter(args.locales)
    inners = _parse_csv_filter(args.inners)
    cases = build_cases(args.content_variant, locales=locales, inners=inners)

    if args.format == "json":
        payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    else:
        payload = render_markdown(cases)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
