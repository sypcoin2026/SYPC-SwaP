"""Independent offline reviewer for six pinned Sigma 6.0.7 compile-only fixtures.

This checker validates text and pinned public hashes, not signatures, cost,
context, UTXO, full transactions, SYPC node acceptance or private-chain safety.
It opens no sockets, runs no commands, and changes no files.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

EXPECTED_CONTRACTS = frozenset((
    "AtomicBuy.sc", "AtomicSell.sc", "AtomicBuyRefundGuard.sc",
    "AtomicSellRefundGuard.sc", "AtomicBuySponsorRefund.sc",
    "AtomicSellSponsorRefund.sc",
))
EXPECTED_SCHEMA = "SYPC_NATIVE6_FINGERPRINT_PIN_V1"
SIGMA = "6.0.7"
MAX_LOG = 2 * 1024 * 1024
MAX_MANIFEST = 8192
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
RESULT = re.compile(
    r"SYPC_NATIVE6_COMPILE_PASS (?P<name>Atomic[A-Za-z]+\.sc) "
    r"sha256=(?P<sha>[0-9a-f]{64}) bytes=(?P<size>[1-9][0-9]*)\Z"
)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
END = "SYPC_NATIVE6_COMPILER_ONLY_SIX_CONTRACTS_PASS"
DISCLAIMER = "NOT_SYPC_CONSENSUS_NOT_FULL_TRANSACTION_NOT_SIGNATURE_VERIFICATION"


class FingerprintError(ValueError):
    """A claimed success is inconsistent with trusted local baseline."""


def _duplicate_guard(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise FingerprintError("Duplicate manifest field")
        out[key] = value
    return out


def _read_local(path: Path, max_size: int) -> bytes:
    flags = os.O_RDONLY
    for flag in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
        flags |= getattr(os, flag, 0)
    fd = os.open(path, flags)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise FingerprintError("Evidence must be regular file")
        if metadata.st_size > max_size:
            raise FingerprintError("Evidence file too large")
        # Read from the single opened descriptor with an enforced bound.
        parts = []
        size = 0
        while size <= max_size:
            data = os.read(fd, min(32768, max_size + 1 - size))
            if not data:
                break
            size += len(data)
            parts.append(data)
        if size > max_size:
            raise FingerprintError("Evidence exceeds reading budget")
        return b"".join(parts)
    finally:
        os.close(fd)


def read_manifest(path: Path) -> dict:
    raw = _read_local(path, MAX_MANIFEST)
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_duplicate_guard)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FingerprintError("Malformed manifest JSON") from exc
    if type(manifest) is not dict or set(manifest) != {
        "schema", "sigma_state", "scala_version", "network_prefix_hex",
        "scope", "contracts",
    }:
        raise FingerprintError("Manifest schema mismatch")
    if (manifest["schema"] != EXPECTED_SCHEMA
            or manifest["sigma_state"] != SIGMA
            or manifest["scala_version"] != "2.12.20"
            or manifest["network_prefix_hex"] != "30"
            or manifest["scope"] != "SYNTHETIC_COMPILE_ONLY_NOT_SYPC_CONSENSUS"):
        raise FingerprintError("Manifest is not the approved native 6.0.7 research fixture")
    contracts = manifest["contracts"]
    if type(contracts) is not dict or set(contracts) != EXPECTED_CONTRACTS:
        raise FingerprintError("Incomplete or unexpected native compiler contract list")
    for name, value in contracts.items():
        if type(value) is not dict or set(value) != {"sha256", "bytes"}:
            raise FingerprintError("Bad fingerprint record: " + name)
        if type(value["sha256"]) is not str or not HEX64.fullmatch(value["sha256"]):
            raise FingerprintError("Invalid fingerprint: " + name)
        if type(value["bytes"]) is not int or not 6 <= value["bytes"] <= 16384:
            raise FingerprintError("Invalid tree byte length: " + name)
    return manifest


def inspect(manifest: dict, log: str) -> dict:
    """Parse independent compiler output, fail on missing/extra/changed hashes."""
    if type(log) is not str or len(log) > MAX_LOG:
        raise FingerprintError("Log encoding or size invalid")
    records = {}
    end_count = 0
    note_count = 0
    for raw in log.splitlines():
        text = ANSI.sub("", raw)
        if "SYPC_NATIVE6_COMPILE_PASS " in text:
            body = text.split("SYPC_NATIVE6_COMPILE_PASS ", 1)[1]
            result = RESULT.fullmatch("SYPC_NATIVE6_COMPILE_PASS " + body)
            if result is None:
                raise FingerprintError("Malformed native compiler PASS line")
            name = result.group("name")
            if name not in EXPECTED_CONTRACTS:
                raise FingerprintError("Unexpected contract: " + name)
            if name in records:
                raise FingerprintError("Duplicate result for " + name)
            sha = result.group("sha")
            size = int(result.group("size"))
            expected = manifest["contracts"][name]
            if sha != expected["sha256"] or size != expected["bytes"]:
                raise FingerprintError("Compiler fingerprint drift: " + name)
            records[name] = (sha, size)
        if END in text and not text.lstrip().startswith("echo "):
            end_count += 1
        if DISCLAIMER in text and not text.lstrip().startswith("echo "):
            note_count += 1
        if any(token in text for token in (
            "[error]", "SYPC_NATIVE6_WRONG_RUNTIME_JAR",
            "SYPC_NATIVE6_SERIALIZATION_FAILED",
            "SYPC_NATIVE6_NONDETERMINISTIC_ERGOTREE",
            "SYPC_NATIVE6_CONTRACT_PARAMETER_NOT_BOUND",
            "SYPC_NATIVE6_MALFORMED_SCRIPT_ACCEPTED",
        )):
            raise FingerprintError("Compiler log contains explicit failure")
    if set(records) != EXPECTED_CONTRACTS:
        raise FingerprintError("Native compiler observations incomplete")
    if end_count != 1 or note_count != 1:
        raise FingerprintError("Missing or duplicated scoped compiler completion marker")
    return {
        "status": "PASS_PINNED_SIGMA607_COMPILER_ONLY",
        "sigma_version": SIGMA,
        "contracts": sorted(records),
        "count": len(records),
        "native_consensus_proven": False,
        "complete_transaction_proven": False,
        "ready_for_deployment": False,
        "ready_for_funds": False,
    }


def review(manifest_path: Path, log_path: Path) -> dict:
    try:
        manifest = read_manifest(manifest_path)
        body = _read_local(log_path, MAX_LOG).decode("utf-8")
        return inspect(manifest, body)
    except (UnicodeError, FingerprintError, OSError, ValueError) as exc:
        return {"status": "FAIL", "reason": str(exc),
                "ready_for_deployment": False, "ready_for_funds": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    result = review(args.manifest, args.log)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS_PINNED_SIGMA607_COMPILER_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
