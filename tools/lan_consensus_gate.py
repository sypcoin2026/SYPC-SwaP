#!/usr/bin/env python3
"""Read-only local-node consistency gate for the private SYPC laboratory.

This tool NEVER sends transactions, signs, mines, accesses a wallet, starts
nodes or changes firewalls. The only network requests are fixed GETs to
127.0.0.1, with proxies and redirects disabled. It cannot prove network
isolation, genesis identity, consensus correctness or DEX compatibility.
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
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

SCHEMA = "SYPC_PRIVATE_LAN_READONLY_V2"
BASE_URL = "http://127.0.0.1:9053"
MAX_JSON_BYTES = 262_144
MAX_CAPTURE_AGE_SECONDS = 900
MAX_CAPTURE_SKEW_SECONDS = 300
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class GateError(ValueError):
    """Fail closed when an observation is malformed or inconsistent."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise GateError("Local node attempted an HTTP redirect; refusing")


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise GateError("Duplicate JSON key")
        obj[key] = value
    return obj


def _parse_json(data: bytes):
    if not isinstance(data, bytes) or len(data) > MAX_JSON_BYTES:
        raise GateError("Unexpected or excessive JSON response")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError("Invalid UTF-8 JSON") from exc


def _get_local_json(endpoint: str):
    # Endpoints are a closed allowlist, NOT an arbitrary URL supplied by a user.
    if endpoint not in ("/info", "/peers/connected"):
        raise GateError("Prohibited REST endpoint")
    opener = build_opener(ProxyHandler({}), NoRedirects())
    req = Request(BASE_URL + endpoint, headers={"Accept": "application/json"}, method="GET")
    with opener.open(req, timeout=3.0) as response:
        if response.geturl() != req.full_url or response.status != 200:
            raise GateError("Unexpected REST response")
        body = response.read(MAX_JSON_BYTES + 1)
    return _parse_json(body)


def _hash64(value, label):
    if type(value) is not str or HEX64.fullmatch(value) is None:
        raise GateError(label + ": expected lowercase 64-character hex")
    return value


def _nonnegative_int(value, label):
    if type(value) is not int or value < 0 or value > (1 << 31) - 1:
        raise GateError(label + ": invalid nonnegative integer")
    return value


def capture(role: str, now=None) -> dict:
    """Get only public consensus metadata from the LOCAL node's read-only API."""
    if role not in ("producer", "validator"):
        raise GateError("Unknown role")
    info = _get_local_json("/info")
    peers = _get_local_json("/peers/connected")
    if not isinstance(info, dict) or not isinstance(peers, list):
        raise GateError("Unexpected node API response shape")

    height = _nonnegative_int(info.get("fullHeight"), "fullHeight")
    genesis = _hash64(info.get("genesisBlockId"), "genesisBlockId")
    header = _hash64(info.get("bestFullHeaderId"), "bestFullHeaderId")
    state_version = _hash64(info.get("stateVersion"), "stateVersion")
    root = _hash64(info.get("stateRoot"), "stateRoot")
    # The reported full-block tip must actually have been applied to state.
    if state_version != header:
        raise GateError("State version does not match the applied full-block tip")
    reported = info.get("isMining")
    if type(reported) is not bool:
        raise GateError("isMining must be a reported boolean")
    if role == "validator" and reported is True:
        raise GateError("Validator reports mining enabled; review its configuration")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise GateError("Clock must be timezone-aware")
    return {
        "schema": SCHEMA,
        "role": role,
        "captured_at_utc": now.astimezone(timezone.utc).isoformat(),
        "fullHeight": height,
        "genesisBlockId": genesis,
        "bestFullHeaderId": header,
        "stateVersion": state_version,
        "stateRoot": root,
        "connected_peers": len(peers),
        "reported_is_mining": reported,
    }


def _validated_snapshot(value, now):
    if not isinstance(value, dict) or set(value) != {
        "schema", "role", "captured_at_utc", "fullHeight",
        "genesisBlockId", "bestFullHeaderId", "stateVersion", "stateRoot",
        "connected_peers",
        "reported_is_mining",
    }:
        raise GateError("Unsupported snapshot structure")
    if value["schema"] != SCHEMA or value["role"] not in ("producer", "validator"):
        raise GateError("Unsupported schema or role")
    _nonnegative_int(value["fullHeight"], "fullHeight")
    _nonnegative_int(value["connected_peers"], "connected_peers")
    _hash64(value["genesisBlockId"], "genesisBlockId")
    _hash64(value["bestFullHeaderId"], "bestFullHeaderId")
    _hash64(value["stateVersion"], "stateVersion")
    _hash64(value["stateRoot"], "stateRoot")
    if value["stateVersion"] != value["bestFullHeaderId"]:
        raise GateError("State version differs from the validated full-block tip")
    reported = value["reported_is_mining"]
    if type(reported) is not bool:
        raise GateError("Missing or invalid mining status")
    if value["role"] == "validator" and reported is True:
        raise GateError("Validator reports mining enabled")
    try:
        timestamp = datetime.fromisoformat(value["captured_at_utc"])
        if timestamp.tzinfo is None:
            raise ValueError("naive timestamp")
    except (TypeError, ValueError) as exc:
        raise GateError("Invalid snapshot timestamp") from exc
    if not 0 <= (now - timestamp).total_seconds() <= MAX_CAPTURE_AGE_SECONDS:
        raise GateError("Snapshot is stale or has a future timestamp")
    return timestamp


def compare(producer: dict, validator: dict, *, expected_genesis_id: str, now=None) -> dict:
    """Check two FRESH node observations against an independently pinned genesis.

    The expected ID must come from an owner's reviewed SYPC genesis manifest,
    NOT either peer's response; this remains a metadata check, not proof of PoW.
    """
    _hash64(expected_genesis_id, "expected_genesis_id")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise GateError("Clock must be timezone-aware")
    a_time = _validated_snapshot(producer, now)
    b_time = _validated_snapshot(validator, now)
    if producer["role"] != "producer" or validator["role"] != "validator":
        raise GateError("Wrong node roles")
    if producer["genesisBlockId"] != expected_genesis_id or validator["genesisBlockId"] != expected_genesis_id:
        raise GateError("Reported genesisBlockId does not match independently pinned genesis")
    if abs((a_time - b_time).total_seconds()) > MAX_CAPTURE_SKEW_SECONDS:
        raise GateError("Snapshots not collected close enough in time")
    # This private laboratory has exactly two nodes; more than one peer per
    # node is unexpected and must be investigated before running a DEX.
    # Peer count still does NOT attest the identity or actual IP of the peer.
    if producer["connected_peers"] != 1 or validator["connected_peers"] != 1:
        raise GateError("Expected exactly one private LAN peer per node")
    if producer["fullHeight"] < 1:
        raise GateError("No full blocks validated")
    for key in ("genesisBlockId", "fullHeight", "bestFullHeaderId",
                "stateVersion", "stateRoot"):
        if producer[key] != validator[key]:
            raise GateError("Node consensus observations differ: " + key)
    return {
        "status": "PASS_READONLY_TIP_CONSISTENCY_ONLY",
        "fullHeight": producer["fullHeight"],
        "genesisBlockId": producer["genesisBlockId"],
        "bestFullHeaderId": producer["bestFullHeaderId"],
        "stateVersion": producer["stateVersion"],
        "stateRoot": producer["stateRoot"],
        "requires_separate_genesis_firewall_and_tx_validation": True,
    }


def _write_private_new_file(path, value: dict):
    dest = Path(path)
    serialized = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(dest, flags, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(serialized)
    return hashlib.sha256(serialized).hexdigest()


def _read_snapshot(path):
    # Open once and bound bytes even if a file changes between stat and read.
    # On Linux, O_NOFOLLOW refuses symlinks; never read a device or FIFO.
    flags = os.O_RDONLY
    # Without O_NONBLOCK, opening a named pipe can hang BEFORE fstat runs.
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(Path(path), flags)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise GateError("Snapshot must be a regular file")
        if metadata.st_size > MAX_JSON_BYTES:
            raise GateError("Snapshot exceeds maximum size")
        return _parse_json(os.read(fd, MAX_JSON_BYTES + 1))
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="SYPC private testnet read-only gate")
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture", help="GET /info and /peers/connected on localhost only")
    cap.add_argument("--role", choices=("producer", "validator"), required=True)
    cap.add_argument("--out", required=True, help="New local JSON file (0600)")
    cmp = sub.add_parser("compare", help="Compare two locally captured JSON files")
    cmp.add_argument("--producer", required=True)
    cmp.add_argument("--validator", required=True)
    cmp.add_argument("--expected-genesis-id", required=True,
                     help="64-char hex genesis ID pinned from owner-reviewed manifest")
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            result = capture(args.role)
            digest = _write_private_new_file(args.out, result)
            print("CAPTURED_READONLY; SHA256=" + digest)
        else:
            result = compare(
                _read_snapshot(args.producer), _read_snapshot(args.validator),
                expected_genesis_id=args.expected_genesis_id,
            )
            print(json.dumps(result, sort_keys=True))
    except (GateError, OSError, RuntimeError, ValueError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
