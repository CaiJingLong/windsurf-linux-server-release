#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def render_notes(summary: dict) -> str:
    lines = [
        f"Extracted language server binaries from Windsurf {summary['version']}.",
        "",
        f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Successful targets:",
    ]

    if summary["successful_targets"]:
        for item in summary["successful_targets"]:
            asset_list = ", ".join(item["assets"])
            suffix = f" ({item['warning']})" if "warning" in item else ""
            lines.append(f"- {item['target']}: {asset_list}{suffix}")
    else:
        lines.append("- none")

    lines.extend(["", "Failed or missing targets:"])
    if summary["failed_targets"]:
        for item in summary["failed_targets"]:
            lines.append(f"- {item['target']}: {item['reason']}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "These assets contain extracted language server binaries, not full Windsurf installers.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    Path(args.output).write_text(render_notes(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
