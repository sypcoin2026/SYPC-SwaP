"""SYPC Swap Auditor v0.1: independent, OFFLINE, fail-closed evidence gate.

No network, no signing, no wallets, no mining, no shell, no database writes.
Verifies evidence consistency and SHA256 of local artifacts, NOT provenance
authenticity, native consensus, token ownership or financial safety.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

POLICY_SCHEMA = "SYPC_SWAP_AUDITOR_POLICY_V1"
RUN_SCHEMA = "SYPC_SWAP_AUDITOR_RUN_V1"
NATIVE_SIGMA_VERSION = "6.0.7"
REFERENCE_SIGMA_VERSION = "4.0.5"
MAX_JSON_BYTES = 262_144
MAX_ARTIFACT_BYTES = 1_048_576
MAX_REPORT_AGE_SECONDS = 900
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{7,63}\Z")
FILENAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}\.(?:txt|log|json)\Z")

# Each check must have its OWN local artifact, a SHA256 and a success marker.
# These are *evidence types*, not permission to sign/broadcast or deploy.
PHASES = {
    "offline": frozenset((
        "source_provenance", "python_regressions", "sigma_reference_regressions",
    )),
    "native": frozenset((
        "native_contract_compile", "native_positive_transaction",
        "native_negative_transactions", "native_cancel_liveness",
        "native_fee_and_asset_conservation",
    )),
    "two_node": frozenset((
        "producer_validates", "validator_validates",
        "independent_state_consistency", "reorg_and_restart",
    )),
}


class AuditError(ValueError):
    """Inconsistent, corrupt or actively failing evidence (FAIL)."""


class AuditBlocked(ValueError):
    """Missing evidence; the step must not advance (BLOCKED)."""


def _nonempty_string(value: object, label: str, max_length: int = 100) -> str:
    if type(value) is not str or not 1 <= len(value) <= max_length:
        raise AuditError(f"{label}: expected nonempty string")
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in value):
        raise AuditError(f"{label}: only visible ASCII allowed")
    return value


def _hex(value: object, length: int, label: str) -> str:
    if type(value) is not str or re.fullmatch(
        r"[0-9a-f]{" + str(length) + r"}", value
    ) is None:
        raise AuditError(f"{label}: expected {length}-character lowercase hex")
    return value


def _time(value: object, label: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise AuditError(f"{label}: expected UTC ISO 8601 timestamp with Z")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AuditError(f"{label}: invalid timestamp") from exc
    return result


def _json_no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise AuditError("Duplicate JSON field")
        obj[key] = value
    return obj


def _read_regular(path: Path, limit: int) -> bytes:
    flags = os.O_RDONLY
    for option in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
        flags |= getattr(os, option, 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise AuditError("Evidence must be a regular file")
        if info.st_size > limit:
            raise AuditError("Evidence exceeds size limit")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise AuditError("Evidence exceeds size limit")
        return data
    finally:
        os.close(fd)


def _json_file(path: Path) -> dict:
    try:
        data = _read_regular(path, MAX_JSON_BYTES)
        doc = json.loads(data.decode("utf-8"),
                         object_pairs_hook=_json_no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             AuditError("Non-finite JSON constant")
                         ))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("Invalid UTF-8 JSON") from exc
    if type(doc) is not dict:
        raise AuditError("JSON root must be an object")
    return doc


def _policy(data: dict) -> dict:
    required = {"schema", "network_id", "genesis_id", "core_commit",
                "swap_commit", "native_sigma_version", "contract_sha256"}
    if set(data) != required or data["schema"] != POLICY_SCHEMA:
        raise AuditError("Invalid policy schema or extra fields")
    _nonempty_string(data["network_id"], "network_id", 64)
    for field, length in (("genesis_id", 64), ("core_commit", 40),
                          ("swap_commit", 40), ("contract_sha256", 64)):
        _hex(data[field], length, field)
    if data["native_sigma_version"] != NATIVE_SIGMA_VERSION:
        raise AuditError("Policy does not pin approved SYPC Core Sigma 6.0.7")
    return data


def _node_consistency(nodes: object, expected_genesis: str,
                      reported_at: datetime) -> None:
    if type(nodes) is not list or len(nodes) != 2:
        raise AuditBlocked("Missing independent producer/validator observations")
    rows = {}
    for entry in nodes:
        required = {"role", "node_id", "genesis_id", "full_height",
                    "best_full_header_id", "state_version", "state_root",
                    "peer_count", "is_mining", "captured_at"}
        if type(entry) is not dict or set(entry) != required:
            raise AuditError("Invalid node observation fields")
        role = entry["role"]
        if role not in ("producer", "validator") or role in rows:
            raise AuditError("Duplicate or unknown node role")
        _hex(entry["node_id"], 64, "node_id")
        _hex(entry["genesis_id"], 64, "node_genesis")
        for key in ("best_full_header_id", "state_version", "state_root"):
            _hex(entry[key], 64, key)
        if type(entry["full_height"]) is not int or entry["full_height"] < 1:
            raise AuditError("Invalid full block height")
        if type(entry["peer_count"]) is not int or entry["peer_count"] != 1:
            raise AuditError("Unexpected private node peer count")
        if type(entry["is_mining"]) is not bool:
            raise AuditError("Invalid node mining status")
        if role == "validator" and entry["is_mining"]:
            raise AuditError("Validator must never mine")
        if entry["genesis_id"] != expected_genesis:
            raise AuditError("Node reports the wrong genesis")
        if entry["state_version"] != entry["best_full_header_id"]:
            raise AuditError("State not applied to reported full block tip")
        captured = _time(entry["captured_at"], "captured_at")
        age = (reported_at - captured).total_seconds()
        if not 0 <= age <= MAX_REPORT_AGE_SECONDS:
            raise AuditError("Node observation is stale or from the future")
        rows[role] = entry
    a, b = rows["producer"], rows["validator"]
    if a["node_id"] == b["node_id"]:
        raise AuditError("Nodes are not independently identified")
    for key in ("full_height", "best_full_header_id", "state_version",
                "state_root"):
        if a[key] != b[key]:
            raise AuditError(f"Producer and validator differ on {key}")


def inspect(policy: dict, report: dict, evidence_dir: Path,
            *, now: datetime | None = None) -> dict:
    """Validate evidence metadata; PASS is NEVER a deployment permission.

    Artifacts are local and untrusted; SHA256 is only an integrity checksum.
    There is no evidence-signature or on-chain proof verifier in v0.1.
    """
    p = _policy(policy)
    if type(report) is not dict or report.get("schema") != RUN_SCHEMA:
        raise AuditError("Unknown audit run schema")
    required = {"schema", "run_id", "phase", "network_id", "genesis_id",
                "core_commit", "swap_commit", "native_sigma_version",
                "contract_sha256", "created_at", "checks"}
    if set(report) - (required | {"reference_sigma_version", "nodes"}):
        raise AuditError("Unknown audit run fields")
    if not required.issubset(report):
        raise AuditBlocked("Audit run metadata is incomplete")
    if not RUN_ID.fullmatch(_nonempty_string(report["run_id"], "run_id", 64)):
        raise AuditError("Invalid run_id")
    phase = report["phase"]
    if phase == "mainnet":
        raise AuditBlocked("Mainnet verification NOT implemented in auditor v0.1")
    if type(phase) is not str or phase not in PHASES:
        raise AuditError("Unknown audit phase")
    for field in ("network_id", "genesis_id", "core_commit", "swap_commit",
                  "native_sigma_version", "contract_sha256"):
        if report[field] != p[field]:
            raise AuditError(f"Mismatch against approved policy: {field}")
    # Reference 4.0.5 is allowed ONLY as historical research evidence.
    reference = report.get("reference_sigma_version")
    if reference is not None and reference != REFERENCE_SIGMA_VERSION:
        raise AuditError("Unexpected historical reference Sigma version")
    if phase == "offline" and reference != REFERENCE_SIGMA_VERSION:
        raise AuditBlocked("Offline research Sigma provenance not declared")
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None:
        raise AuditError("Current clock has no timezone")
    at = _time(report["created_at"], "created_at")
    age = (now - at).total_seconds()
    if not 0 <= age <= MAX_REPORT_AGE_SECONDS:
        raise AuditError("Audit run stale or dated in future")
    if phase == "two_node":
        _node_consistency(report.get("nodes"), p["genesis_id"], at)
    if type(report["checks"]) is not list or len(report["checks"]) > 32:
        raise AuditError("Invalid check collection")
    checked = set()
    paths = set()
    failed = []
    for row in report["checks"]:
        if type(row) is not dict or set(row) != {
            "id", "status", "exit_code", "artifact", "sha256",
        }:
            raise AuditError("Invalid check entry fields")
        check = row["id"]
        if type(check) is not str or check not in PHASES[phase]:
            raise AuditError("Unknown or wrong-phase check")
        if check in checked:
            raise AuditError("Duplicate check ID")
        checked.add(check)
        if row["status"] not in ("PASS", "FAIL", "BLOCKED"):
            raise AuditError("Unknown result status")
        if type(row["exit_code"]) is not int or row["exit_code"] < 0:
            raise AuditError("Invalid process exit code")
        path = row["artifact"]
        if type(path) is not str or not FILENAME.fullmatch(path) or path in paths:
            raise AuditError("Unsafe or duplicate evidence filename")
        paths.add(path)
        _hex(row["sha256"], 64, "artifact_sha256")
        try:
            data = _read_regular(Path(evidence_dir) / path, MAX_ARTIFACT_BYTES)
        except FileNotFoundError as exc:
            raise AuditBlocked(f"Missing artifact for {check}") from exc
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise AuditError(f"Artifact hash mismatch for {check}")
        try:
            content = data.decode("utf-8")
        except UnicodeError as exc:
            raise AuditError(f"Invalid artifact encoding for {check}") from exc
        lines = set(content.splitlines())
        if phase in ("native", "two_node") and row["status"] == "PASS":
            # Reporter must declare the exact native engine, not historical
            # Sigma 4.0.5. These are UNAUTHENTICATED assertions in v0.1.
            required_markers = {
                f"SYPC_AUDIT_NATIVE_SIGMA:{NATIVE_SIGMA_VERSION}",
                f"SYPC_AUDIT_CORE_COMMIT:{p['core_commit']}",
                f"SYPC_AUDIT_SWAP_COMMIT:{p['swap_commit']}",
            }
            if not required_markers.issubset(lines):
                raise AuditError(f"Missing native engine/commit markers for {check}")
        if f"SYPC_AUDIT_CHECK_FAIL:{check}" in lines:
            failed.append(check)
        elif row["status"] == "PASS":
            if row["exit_code"] != 0 or (
                f"SYPC_AUDIT_CHECK_PASS:{check}" not in lines
            ):
                raise AuditError(f"Contradictory PASS evidence for {check}")
        elif row["status"] == "FAIL":
            failed.append(check)
        # BLOCKED remains BLOCKED, even with a PASS marker in its artifact.
    if failed:
        raise AuditError("Failure reported for " + ", ".join(sorted(failed)))
    missing = PHASES[phase] - checked
    blocked = [r["id"] for r in report["checks"] if r["status"] == "BLOCKED"]
    if missing or blocked:
        raise AuditBlocked("Missing/blocked evidence: " + ", ".join(sorted(
            missing | set(blocked)
        )))
    return {
        "status": "PASS_EVIDENCE_INTEGRITY_ONLY",
        "phase": phase,
        "run_id": report["run_id"],
        "validated_checks": sorted(checked),
        "approved_native_sigma_version": NATIVE_SIGMA_VERSION,
        "native_compatibility_demonstrated": False,
        "ready_for_funds": False,
        "ready_for_deployment": False,
        "note": "Checksums and reported test outcomes are NOT authenticated consensus proofs.",
    }


def review_files(policy_path: Path, run_path: Path, evidence_dir: Path,
                 *, now: datetime | None = None) -> dict:
    try:
        policy, run = _json_file(policy_path), _json_file(run_path)
        return inspect(policy, run, evidence_dir, now=now)
    except AuditBlocked as exc:
        return {"status": "BLOCKED", "reason": str(exc), "ready_for_funds": False,
                "ready_for_deployment": False}
    except (AuditError, OSError, ValueError) as exc:
        return {"status": "FAIL", "reason": str(exc), "ready_for_funds": False,
                "ready_for_deployment": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    verdict = review_files(args.policy, args.run, args.evidence_dir)
    print(json.dumps(verdict, sort_keys=True))
    return {"PASS_EVIDENCE_INTEGRITY_ONLY": 0, "FAIL": 2, "BLOCKED": 3}[verdict["status"]]


if __name__ == "__main__":
    sys.exit(main())
