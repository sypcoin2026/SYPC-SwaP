#!/usr/bin/env python3
"""Offline upstream manifest checks (NOT a contract/security audit)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_URL = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
SOURCE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
LICENSES = {"CC0-1.0", "MIT"}


class ValidationError(ValueError):
    """The manifest or its optional local copy does not match requirements."""


def validate_manifest(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValidationError("schema must be 1")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValidationError("sources must be a non-empty list")
    seen: set[str] = set()
    seen_urls: set[str] = set()
    for i, item in enumerate(sources):
        if not isinstance(item, dict):
            raise ValidationError(f"source {i}: expected object")
        sid = item.get("id")
        if not isinstance(sid, str) or not SOURCE_ID.fullmatch(sid):
            raise ValidationError(f"source {i}: invalid id")
        if sid in seen:
            raise ValidationError(f"source {sid}: duplicate id")
        seen.add(sid)
        url = item.get("url")
        if not isinstance(url, str) or not REPO_URL.fullmatch(url):
            raise ValidationError(f"source {sid}: invalid GitHub URL")
        if url in seen_urls:
            raise ValidationError(f"source {sid}: duplicate upstream URL")
        seen_urls.add(url)
        commit = item.get("commit")
        if not isinstance(commit, str) or not GIT_SHA.fullmatch(commit):
            raise ValidationError(f"source {sid}: commit must be 40 lowercase hex chars")
        if item.get("license_declared") not in LICENSES:
            raise ValidationError(f"source {sid}: unexpected declared license")
        if item.get("imported") is not False:
            raise ValidationError(f"source {sid}: must explicitly be research-only")
    return sources


def validate_snapshot_pins(sources: list[dict[str, Any]], manifest: Any) -> int:
    """Bind each copied reference to the same upstream commit and license.

    File hash/paths are checked separately by verify_vendored.py.
    Both manifests must agree; otherwise two independent PASSes can mislead.
    """
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise ValidationError("snapshot manifest schema must be 1")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValidationError("snapshot manifest files must be nonempty")
    pins = {source["url"].removeprefix("https://github.com/"): source for source in sources}
    for i, ref in enumerate(files):
        if not isinstance(ref, dict):
            raise ValidationError(f"snapshot {i}: expected object")
        source = pins.get(ref.get("upstream")) if type(ref.get("upstream")) is str else None
        if source is None:
            raise ValidationError(f"snapshot {i}: unknown upstream")
        if ref.get("revision") != source["commit"]:
            raise ValidationError(f"snapshot {i}: revision differs from upstream pin")
        if ref.get("license_declared") != source["license_declared"]:
            raise ValidationError(f"snapshot {i}: license differs from upstream pin")
        if ref.get("executable") is not False:
            raise ValidationError(f"snapshot {i}: snapshot cannot be executable")
    return len(files)


def inspect_local_clones(sources: list[dict[str, Any]], root: Path) -> list[str]:
    """Read existing local clones only. Never clone/fetch/modify upstreams."""
    problems: list[str] = []
    for item in sources:
        repo = root / item["id"]
        if not repo.is_dir():
            problems.append(f"{item['id']}: local checkout missing at {repo}")
            continue
        try:
            sha = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, timeout=15,
            ).stdout.strip()
            status = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                check=True, capture_output=True, text=True, timeout=15,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            problems.append(f"{item['id']}: unable to inspect clone ({type(exc).__name__})")
            continue
        if sha != item["commit"]:
            problems.append(f"{item['id']}: HEAD does not match pinned commit")
        if status:
            problems.append(f"{item['id']}: checkout contains local changes")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "upstreams.lock.json")
    parser.add_argument("--local-clones", type=Path, help="read-only verification of existing directories named by source id")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        sources = validate_manifest(data)
        references = json.loads(
            (args.manifest.parent / "third_party" / "REFERENCES.json").read_text(encoding="utf-8")
        )
        reference_count = validate_snapshot_pins(sources, references)
        if args.local_clones:
            problems = inspect_local_clones(sources, args.local_clones)
            if problems:
                for problem in problems:
                    print("FAIL:", problem, file=sys.stderr)
                return 1
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: {len(sources)} upstream pins and {reference_count} snapshot records agree; "
        "metadata only, no source audit"
    )
    if not args.local_clones:
        print("No upstream code was downloaded or verified. Use --local-clones for local HEAD checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
