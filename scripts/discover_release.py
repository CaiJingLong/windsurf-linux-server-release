#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path


RELEASES_URL = "https://windsurf.com/editor/releases"

CANONICAL_TARGETS = [
    {
        "target": "linux-x64",
        "display_name": "Linux x64 (.tar.gz)",
        "archive_type": "tar.gz",
        "expected_binary_name": "language_server_linux_x64",
        "required": True,
    },
    {
        "target": "macos-arm",
        "display_name": "macOS for Apple Silicon (Archive, .zip)",
        "archive_type": "zip",
        "expected_binary_name": "language_server_macos_arm",
        "required": False,
    },
    {
        "target": "macos-x64",
        "display_name": "macOS for Intel (Archive, .zip)",
        "archive_type": "zip",
        "expected_binary_name": "language_server_macos_x64",
        "required": False,
    },
    {
        "target": "windows-arm",
        "display_name": "Windows arm64 (Archive, .zip)",
        "archive_type": "zip",
        "expected_binary_name": "language_server_windows_arm.exe",
        "required": False,
    },
    {
        "target": "windows-x64",
        "display_name": "Windows x64 (Archive, .zip)",
        "archive_type": "zip",
        "expected_binary_name": "language_server_windows_x64.exe",
        "required": False,
    },
]


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "windsurf-release-bot/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def extract_escaped_json_array(html: str, field_name: str) -> list[dict]:
    marker = f'{field_name}\\":'
    start = html.find(marker)
    if start == -1:
        raise ValueError(f"Could not find field {field_name!r} in Windsurf releases HTML.")

    array_start = html.find("[", start)
    if array_start == -1:
        raise ValueError(f"Could not find array start for field {field_name!r}.")

    depth = 0
    in_string = False
    escaped = False

    for index in range(array_start, len(html)):
        char = html[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                raw = html[array_start : index + 1]
                decoded = raw.encode("utf-8").decode("unicode_escape")
                return json.loads(decoded)

    raise ValueError(f"Could not find the closing bracket for field {field_name!r}.")


def build_manifest(stable_releases: list[dict]) -> dict:
    if not stable_releases:
        raise ValueError("The stableReleases array is empty.")

    latest = stable_releases[0]
    version = latest["version"]

    all_entries: list[dict] = []
    for platform_name in ("MacOS", "Windows", "Linux"):
        all_entries.extend(latest.get(platform_name, []))

    by_display_name = {entry["displayName"]: entry for entry in all_entries}
    targets = []
    for canonical_target in CANONICAL_TARGETS:
        entry = by_display_name.get(canonical_target["display_name"])
        if entry is None:
            raise ValueError(
                f"Could not find canonical download entry {canonical_target['display_name']!r} for version {version}."
            )
        targets.append(
            {
                "target": canonical_target["target"],
                "display_name": canonical_target["display_name"],
                "source_url": entry["url"],
                "archive_type": canonical_target["archive_type"],
                "required": canonical_target["required"],
                "expected_binary_name": canonical_target["expected_binary_name"],
            }
        )

    return {
        "version": version,
        "tag": f"v{version}",
        "release_name": f"Windsurf {version}",
        "targets": targets,
    }


def write_github_output(manifest: dict) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return

    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"version={manifest['version']}\n")
        handle.write(f"tag={manifest['tag']}\n")
        handle.write(f"release_name={manifest['release_name']}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=RELEASES_URL)
    parser.add_argument("--manifest-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html = fetch_html(args.url)
    stable_releases = extract_escaped_json_array(html, "stableReleases")
    manifest = build_manifest(stable_releases)

    manifest_path = Path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_github_output(manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
