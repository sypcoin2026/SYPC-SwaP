#!/usr/bin/env python3
"""Read-only, privacy-minimising fingerprint of a LOCAL SYPC Reward Java process.

No network, process execution, Java attach, writes, wallet or config reads.
This identifies code artifacts, NOT a matching Git commit or safe deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile

SCHEMA = "SYPC_REWARD_RUNTIME_ARTIFACT_READONLY_V1"
MAIN_CLASS = "org.ergoplatform.sypcoin.SypRewardTestnetLauncher"
SIGMA_JAR = "sigma-state_2.12-6.0.7.jar"
CLASS_FILES = {
    "reward_launcher": "org/ergoplatform/sypcoin/SypRewardTestnetLauncher.class",
    "native_transaction": "org/ergoplatform/modifiers/mempool/ErgoTransaction.class",
    "native_state": "org/ergoplatform/nodeView/state/ErgoState.class",
}
MAX_CMDLINE = 262_144
MAX_CLASSPATH_ITEMS = 512
MAX_ARTIFACT_BYTES = 1_000_000_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class FingerprintError(ValueError):
    pass


def read_cmdline(proc_pid: Path) -> list[str]:
    # Do not print, save or upload argv; it can contain secrets.
    try:
        with (proc_pid / "cmdline").open("rb") as stream:
            raw = stream.read(MAX_CMDLINE + 1)
    except (OSError, PermissionError) as exc:
        raise FingerprintError("PROCESS_CMDLINE_UNREADABLE") from exc
    if len(raw) > MAX_CMDLINE:
        raise FingerprintError("PROCESS_CMDLINE_TOO_LARGE")
    if not raw:
        return []
    return [arg.decode("utf-8", "surrogateescape") for arg in raw.split(b"\0") if arg]


def parse_explicit_classpath(argv: list[str]) -> str | None:
    if MAIN_CLASS not in argv:
        return None
    limit = argv.index(MAIN_CLASS)
    for pos in range(limit):
        if argv[pos] in ("-cp", "-classpath", "--class-path"):
            if pos + 1 < limit:
                return argv[pos + 1]
    raise FingerprintError("MATCHED_LAUNCHER_WITHOUT_EXPLICIT_CLASSPATH")


def expand_classpath(value: str, cwd: Path) -> list[Path]:
    entries = value.split(os.pathsep)
    if len(entries) > MAX_CLASSPATH_ITEMS:
        raise FingerprintError("CLASSPATH_TOO_LONG")
    result: list[Path] = []
    seen: set[str] = set()
    for part in entries:
        part = part or "."
        root = Path(part)
        if not root.is_absolute():
            root = cwd / root
        if part.endswith("/*"):
            parent = root.parent
            if not parent.is_dir():
                raise FingerprintError("CLASSPATH_WILDCARD_DIR_MISSING")
            candidates = sorted(
                x for x in parent.iterdir() if x.is_file() and x.suffix.lower() == ".jar"
            )
        else:
            candidates = [root]
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                result.append(candidate)
            if len(result) > MAX_CLASSPATH_ITEMS:
                raise FingerprintError("CLASSPATH_EXPANSION_TOO_LONG")
    return result


def sha256_file(path: Path) -> str:
    try:
        if not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise FingerprintError("ARTIFACT_MISSING_OR_OVERSIZED")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1 << 20)
                if not chunk:
                    return digest.hexdigest()
                digest.update(chunk)
    except OSError as exc:
        raise FingerprintError("ARTIFACT_UNREADABLE") from exc


def fingerprint_artifact(path: Path) -> dict | None:
    """Return hashes only; never return absolute paths or process arguments."""
    if path.is_dir():
        found = {}
        for label, relative in CLASS_FILES.items():
            file = path / relative
            if file.is_file():
                found[label] = sha256_file(file)
        if found:
            return {"type": "class_directory", "class_sha256": found}
        return None

    if not path.is_file() or path.suffix.lower() != ".jar":
        return None
    is_sigma = path.name == SIGMA_JAR
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise FingerprintError("CLASSPATH_JAR_UNREADABLE") from exc
    found = sorted(label for label, rel in CLASS_FILES.items() if rel in names)
    if not found and not is_sigma:
        return None
    return {
        "type": "jar",
        "sha256": sha256_file(path),
        "class_labels": found,
        "is_exact_sigma607_filename": is_sigma,
    }


def inspect_process(pid: int, proc_root: Path = Path("/proc")) -> dict | None:
    proc_pid = proc_root / str(pid)
    argv = read_cmdline(proc_pid)
    cp = parse_explicit_classpath(argv)
    if cp is None:
        return None
    try:
        cwd = Path(os.readlink(proc_pid / "cwd"))
    except OSError as exc:
        raise FingerprintError("PROCESS_CWD_UNREADABLE") from exc
    entries = expand_classpath(cp, cwd)
    artifacts = []
    for entry in entries:
        item = fingerprint_artifact(entry)
        if item is not None:
            artifacts.append(item)
    launchers = [a for a in artifacts if
                 ("reward_launcher" in a.get("class_labels", []) or
                  "reward_launcher" in a.get("class_sha256", {}))]
    sigmas = [a["sha256"] for a in artifacts if a.get("is_exact_sigma607_filename")]
    return {
        "pid": pid,
        "classpath_entries": len(entries),
        "launcher_artifacts": launchers,
        "sigma607_sha256": sigmas,
    }


def select_process(*, pid: int | None = None, proc_root: Path = Path("/proc")) -> dict:
    if pid is not None:
        candidates = [pid]
    else:
        candidates = sorted(int(p.name) for p in proc_root.iterdir()
                            if p.name.isdecimal() and p.is_dir())
    matches = []
    for number in candidates:
        try:
            argv = read_cmdline(proc_root / str(number))
        except FingerprintError:
            if pid is not None:
                raise
            continue  # Other users' unreadable processes: no argv is printed.
        if MAIN_CLASS not in argv:
            continue
        # Once the target is identified, every error must FAIL CLOSED.
        # Silently skipping it could hide a second, ambiguous Reward JVM.
        record = inspect_process(number, proc_root)
        if record is None:
            raise FingerprintError("LAUNCHER_DISAPPEARED_DURING_CAPTURE")
        matches.append(record)
    if len(matches) != 1:
        raise FingerprintError("EXPECTED_EXACTLY_ONE_REWARD_LAUNCHER")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, default=None,
                        help="Optional known Reward Java PID; no ps/curl/sudo needed")
    parser.add_argument("--expected-sigma-sha256", default=None)
    args = parser.parse_args()
    try:
        if args.pid is not None and args.pid <= 0:
            raise FingerprintError("INVALID_PID")
        expected = args.expected_sigma_sha256
        if expected is not None and not HEX64.fullmatch(expected):
            raise FingerprintError("INVALID_EXPECTED_SIGMA_HASH")
        record = select_process(pid=args.pid)
        if len(record["launcher_artifacts"]) != 1:
            raise FingerprintError("LAUNCHER_CODE_ARTIFACT_NOT_UNIQUE")
        if len(record["sigma607_sha256"]) != 1:
            raise FingerprintError("SIGMA607_JAR_NOT_UNIQUE")
        if expected and record["sigma607_sha256"][0] != expected:
            raise FingerprintError("SIGMA607_HASH_MISMATCH")
        print(json.dumps({
            "schema": SCHEMA,
            **record,
            "finding": "LOCAL_ARTIFACT_HASHES_ONLY",
            "git_commit_verified": False,
            "chain_or_consensus_verified": False,
            "no_node_or_wallet_interaction": True,
        }, sort_keys=True, indent=2))
        return 0
    except FingerprintError as exc:
        # Failure output consists only of fixed error codes, never command lines.
        print("SYPC_REWARD_PROVENANCE_FAIL:" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
