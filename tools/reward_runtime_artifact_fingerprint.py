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
    "reward_launcher_module": "org/ergoplatform/sypcoin/SypRewardTestnetLauncher$.class",
    "native_transaction": "org/ergoplatform/modifiers/mempool/ErgoTransaction.class",
    "native_state": "org/ergoplatform/nodeView/state/ErgoState.class",
}
MAX_CMDLINE = 262_144
MAX_CLASSPATH_ITEMS = 512
MAX_ARTIFACT_BYTES = 1_000_000_000
MAX_CLASS_BYTES = 4_194_304
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
LAUNCHER_LABELS = frozenset({"reward_launcher", "reward_launcher_module"})


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
    class_hashes = {}
    try:
        with zipfile.ZipFile(path) as archive:
            # A JAR containing duplicate class entries is not a dependable
            # fingerprint source: different readers can select different bytes.
            members = {}
            for info in archive.infolist():
                if info.filename in CLASS_FILES.values():
                    if info.filename in members:
                        raise FingerprintError("DUPLICATE_CLASS_IN_JAR")
                    members[info.filename] = info
            for label, relative in CLASS_FILES.items():
                info = members.get(relative)
                if info is None:
                    continue
                if info.file_size > MAX_CLASS_BYTES:
                    raise FingerprintError("JAR_CLASS_TOO_LARGE")
                with archive.open(info) as stream:
                    data = stream.read(MAX_CLASS_BYTES + 1)
                if len(data) != info.file_size or len(data) > MAX_CLASS_BYTES:
                    raise FingerprintError("JAR_CLASS_SIZE_MISMATCH")
                class_hashes[label] = hashlib.sha256(data).hexdigest()
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise FingerprintError("CLASSPATH_JAR_UNREADABLE") from exc
    if not class_hashes and not is_sigma:
        return None
    return {
        "type": "jar",
        "sha256": sha256_file(path),
        "class_sha256": class_hashes,
        "class_labels": sorted(class_hashes),
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
    for index, entry in enumerate(entries):
        item = fingerprint_artifact(entry)
        if item is not None:
            artifacts.append((index, item))
    launchers = [
        {"classpath_index": index, **a}
        for index, a in artifacts
        if LAUNCHER_LABELS.intersection(a.get("class_sha256", {}).keys())
    ]
    sigmas = [a["sha256"] for _, a in artifacts if a.get("is_exact_sigma607_filename")]
    # Counts only, NEVER a classpath entry, user directory or process argument.
    # Distinguish missing artifacts from more than one candidate, without
    # silently accepting the first matching classloader entry.
    dirs = sum(entry.is_dir() for entry in entries)
    jars = sum(entry.is_file() and entry.suffix.lower() == ".jar"
               for entry in entries)
    missing = sum(not entry.exists() for entry in entries)
    return {
        "pid": pid,
        "classpath_entries": len(entries),
        "classpath_directories": dirs,
        "classpath_jar_files": jars,
        "classpath_missing_entries": missing,
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
            # Previous V1 conflated 0 and >1. Publish safe counts only;
            # everything else continues to fail closed.
            print("SYPC_REWARD_SAFE_COUNTS:" + json.dumps({
                "classpath_entries": record["classpath_entries"],
                "classpath_directories": record["classpath_directories"],
                "classpath_jar_files": record["classpath_jar_files"],
                "classpath_missing_entries": record["classpath_missing_entries"],
                "launcher_candidates": len(record["launcher_artifacts"]),
                "sigma607_candidates": len(record["sigma607_sha256"]),
            }, sort_keys=True), file=sys.stderr)
            if record["launcher_artifacts"]:
                # Only positions, artifact type and cryptographic hashes.
                # Never leak paths or JVM argv; never pick the first artifact.
                details = [
                    {
                        "classpath_index": candidate["classpath_index"],
                        "type": candidate["type"],
                        "jar_sha256": candidate.get("sha256"),
                        "class_sha256": candidate.get("class_sha256", {}),
                    }
                    for candidate in record["launcher_artifacts"]
                ]
                fingerprints = {
                    tuple(sorted(item["class_sha256"].items()))
                    for item in details
                }
                print("SYPC_REWARD_LAUNCHER_CANDIDATES:" + json.dumps({
                    "entries": details,
                    "distinct_class_fingerprint_sets": len(fingerprints),
                    "first_candidate_index_is_not_verified_runtime_selection": True,
                }, sort_keys=True), file=sys.stderr)
            raise FingerprintError(
                "LAUNCHER_CODE_ARTIFACT_MISSING"
                if not record["launcher_artifacts"]
                else "MULTIPLE_LAUNCHER_CODE_ARTIFACTS"
            )
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
