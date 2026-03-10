from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from slack_markdown_parser import (
    convert_markdown_to_slack_payloads,
    strip_zero_width_spaces,
)

SLACK_API_BASE = "https://slack.com/api"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("export "):
            stripped = stripped[len("export ") :]

        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ[key] = value


def slack_api_call(method: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    api_request = request.Request(
        url=f"{SLACK_API_BASE}/{method}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with request.urlopen(api_request) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Slack API HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Slack API request failed: {exc.reason}") from exc

    if not data.get("ok"):
        raise RuntimeError(f"Slack API error for {method}: {data}")

    return data


def slack_api_get(method: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
    query = parse.urlencode(params)
    api_request = request.Request(
        url=f"{SLACK_API_BASE}/{method}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )

    try:
        with request.urlopen(api_request) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Slack API HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Slack API request failed: {exc.reason}") from exc

    if not data.get("ok"):
        raise RuntimeError(f"Slack API error for {method}: {data}")

    return data


def get_message_permalink(token: str, channel: str, ts: str) -> str | None:
    response = slack_api_get(
        "chat.getPermalink",
        token,
        {
            "channel": channel,
            "message_ts": ts,
        },
    )
    permalink = response.get("permalink")
    return permalink if isinstance(permalink, str) and permalink else None


def read_markdown(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    raise SystemExit("Provide either --text or --input-file.")


def build_raw_payload(markdown_text: str) -> list[dict[str, Any]]:
    fallback = strip_zero_width_spaces(markdown_text).strip() or "Slack render test"
    return [
        {
            "text": fallback,
            "blocks": [
                {
                    "type": "markdown",
                    "text": markdown_text,
                }
            ],
        }
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post markdown render-test messages to a Slack channel."
    )
    parser.add_argument(
        "--mode",
        choices=("parser", "raw"),
        default="parser",
        help="parser: use slack_markdown_parser, raw: send markdown block as-is.",
    )
    parser.add_argument("--text", help="Inline markdown text to post.")
    parser.add_argument("--input-file", help="Path to a markdown file to post.")
    parser.add_argument(
        "--channel",
        default=os.environ.get("SLACK_TEST_CHANNEL_ID"),
        help="Slack channel ID. Defaults to SLACK_TEST_CHANNEL_ID.",
    )
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Optional dotenv file to load before reading environment variables.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Delay between messages when one markdown input expands to many payloads.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated payloads without calling Slack.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(Path(args.dotenv))

    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    channel = (args.channel or os.environ.get("SLACK_TEST_CHANNEL_ID", "")).strip()
    markdown_text = read_markdown(args)

    if not channel:
        raise SystemExit(
            "Missing channel. Set SLACK_TEST_CHANNEL_ID or pass --channel."
        )

    if args.mode == "parser":
        payloads = convert_markdown_to_slack_payloads(markdown_text)
    else:
        payloads = build_raw_payload(markdown_text)

    if not payloads:
        raise SystemExit("No payloads were generated from the provided markdown.")

    if args.dry_run:
        print(
            json.dumps(
                {"channel": channel, "mode": args.mode, "payloads": payloads},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not token:
        raise SystemExit("Missing SLACK_BOT_TOKEN. Set it in the environment or .env.")

    for index, payload in enumerate(payloads, start=1):
        response = slack_api_call(
            "chat.postMessage",
            token,
            {
                "channel": channel,
                **payload,
            },
        )
        response_channel = response.get("channel")
        response_ts = response.get("ts")
        permalink = None
        if isinstance(response_channel, str) and isinstance(response_ts, str):
            try:
                permalink = get_message_permalink(token, response_channel, response_ts)
            except RuntimeError:
                permalink = None
        print(
            json.dumps(
                {
                    "message_index": index,
                    "channel": response_channel,
                    "ts": response_ts,
                    "mode": args.mode,
                    "permalink": permalink,
                },
                ensure_ascii=False,
            )
        )
        if index < len(payloads):
            time.sleep(max(args.sleep_seconds, 0.0))

    return 0


if __name__ == "__main__":
    sys.exit(main())
