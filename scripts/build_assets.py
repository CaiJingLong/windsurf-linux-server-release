#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


CHUNK_SIZE = 1024 * 1024


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "windsurf-release-bot/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)


def extract_archive(archive_path: Path, output_dir: Path, archive_type: str) -> None:
    if archive_type == "zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(output_dir)
        return

    if archive_type == "tar.gz":
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(output_dir)
        return

    raise ValueError(f"Unsupported archive type: {archive_type}")


def find_expected_binary(root: Path, expected_name: str) -> Path:
    matches = [path for path in root.rglob(expected_name) if path.is_file()]
    if not matches:
        raise FileNotFoundError(f"Could not find {expected_name} under {root}")
    if len(matches) > 1:
        raise RuntimeError(f"Found multiple matches for {expected_name}: {matches}")
    return matches[0]


def gzip_copy(source: Path, destination: Path) -> None:
    with source.open("rb") as src_handle, gzip.open(destination, "wb") as dst_handle:
        shutil.copyfileobj(src_handle, dst_handle)


def process_target(target: dict, dist_dir: Path, scratch_root: Path) -> tuple[list[str], str | None]:
    work_dir = scratch_root / target["target"]
    work_dir.mkdir(parents=True, exist_ok=True)

    archive_name = Path(urllib.parse.urlparse(target["source_url"]).path).name
    archive_path = work_dir / archive_name
    extracted_dir = work_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    download_file(target["source_url"], archive_path)
    extract_archive(archive_path, extracted_dir, target["archive_type"])
    binary_path = find_expected_binary(extracted_dir, target["expected_binary_name"])

    output_path = dist_dir / target["expected_binary_name"]
    shutil.copy2(binary_path, output_path)

    if not output_path.name.endswith(".exe"):
        output_path.chmod(output_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    created_assets = [output_path.name]
    gzip_path = output_path.with_name(output_path.name + ".gz")
    try:
        gzip_copy(output_path, gzip_path)
        created_assets.append(gzip_path.name)
        return created_assets, None
    except OSError as exc:
        return created_assets, f"gzip failed: {exc}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--dist-dir", required=True)
    parser.add_argument("--summary-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    dist_dir = Path(args.dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "version": manifest["version"],
        "tag": manifest["tag"],
        "release_name": manifest["release_name"],
        "successful_targets": [],
        "failed_targets": [],
    }
    required_failure = False

    with tempfile.TemporaryDirectory(prefix="windsurf-assets-") as temp_dir:
        scratch_root = Path(temp_dir)
        for target in manifest["targets"]:
            try:
                assets, warning = process_target(target, dist_dir, scratch_root)
                entry = {"target": target["target"], "assets": assets}
                if warning:
                    entry["warning"] = warning
                summary["successful_targets"].append(entry)
            except Exception as exc:  # noqa: BLE001
                summary["failed_targets"].append(
                    {
                        "target": target["target"],
                        "required": target["required"],
                        "reason": f"{target['target']}: {exc}",
                    }
                )
                if target["required"]:
                    required_failure = True

    Path(args.summary_out).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if required_failure:
        print(json.dumps(summary, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
