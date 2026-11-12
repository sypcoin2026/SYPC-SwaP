"""Offline byte-for-byte integrity check for copied upstream source snapshots.

Checks Git blob IDs of third_party references. This is not a contract audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

HEX_SHA1 = re.compile(r"[0-9a-f]{40}\Z")


class SnapshotError(ValueError):
    """Reference manifest is malformed or a snapshot is altered."""


def verify_manifest(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise SnapshotError("manifest schema must be 1")
    entries = document.get("files")
    if not isinstance(entries, list) or not entries:
        raise SnapshotError("manifest must list at least one reference")
    seen = set()
    for i, item in enumerate(entries):
        if not isinstance(item, dict):
            raise SnapshotError(f"file {i}: expected object")
        copy_path = item.get("copy_path")
        if not isinstance(copy_path, str):
            raise SnapshotError(f"file {i}: invalid copy_path")
        pp = PurePosixPath(copy_path)
        if (not copy_path.startswith("third_party/") or pp.is_absolute()
                or len(pp.parts) < 3 or ".." in pp.parts
                or "." in copy_path.split("/") or "" in copy_path.split("/")):
            raise SnapshotError(f"file {i}: unsafe copy_path")
        if copy_path in seen:
            raise SnapshotError(f"file {i}: duplicate path")
        seen.add(copy_path)
        blob = item.get("github_blob_sha1")
        if not isinstance(blob, str) or not HEX_SHA1.fullmatch(blob):
            raise SnapshotError(f"file {i}: invalid Git blob SHA-1")
        if item.get("executable") is not False:
            raise SnapshotError(f"file {i}: not marked research-only")
        if (not isinstance(item.get("upstream"), str) or
                not item["upstream"].startswith(("ergoplatform/", "spectrum-finance/"))):
            raise SnapshotError(f"file {i}: invalid source")
        rev = item.get("revision")
        if not isinstance(rev, str) or not HEX_SHA1.fullmatch(rev):
            raise SnapshotError(f"file {i}: invalid revision")
    return entries


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def verify_copies(root: Path, entries: list[dict[str, Any]]) -> int:
    root = root.resolve()
    for item in entries:
        rel = PurePosixPath(item["copy_path"])
        current = root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise SnapshotError(f"symlink in snapshot path: {rel}")
        if not current.is_file():
            raise SnapshotError(f"missing snapshot file: {rel}")
        actual = git_blob_sha1(current.read_bytes())
        if actual != item["github_blob_sha1"]:
            raise SnapshotError(f"modified snapshot file: {rel}")
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        manifest = json.loads((args.root / "third_party" / "REFERENCES.json").read_text(encoding="utf-8"))
        total = verify_copies(args.root, verify_manifest(manifest))
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {total} reference files matched pinned Git blobs (offline, no execution)")
    print("NOT a security audit, ErgoScript validation or SYPC runtime compatibility test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
