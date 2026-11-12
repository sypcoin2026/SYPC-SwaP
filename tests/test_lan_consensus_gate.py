"""Offline tests: no node, no wallet, no sockets, no mining, no Internet."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import lan_consensus_gate as gate

NOW = datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)
HEADER = "a" * 64
ROOT = "b" * 64
GENESIS = "c" * 64


def snapshot(role="producer", **changes):
    value = {
        "schema": gate.SCHEMA,
        "role": role,
        "captured_at_utc": (NOW - timedelta(seconds=15)).isoformat(),
        "fullHeight": 377,
        "genesisBlockId": GENESIS,
        "bestFullHeaderId": HEADER,
        "stateVersion": HEADER,
        "stateRoot": ROOT,
        "connected_peers": 1,
        "reported_is_mining": False,
    }
    value.update(changes)
    return value


def pinned_compare(producer, validator, *, now=None):
    return gate.compare(
        producer, validator, expected_genesis_id=GENESIS, now=now,
    )


class LanReadonlyGateTests(unittest.TestCase):
    def test_reject_unpinned_or_different_expected_genesis(self):
        with self.assertRaises(TypeError):
            gate.compare(snapshot(), snapshot("validator"), now=NOW)
        for invalid in ("d" * 64, "INVALID", None, True):
            with self.subTest(invalid=invalid), self.assertRaises(gate.GateError):
                gate.compare(snapshot(), snapshot("validator"),
                             expected_genesis_id=invalid, now=NOW)

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
                         "requires FIFO and O_NONBLOCK")
    def test_fifo_snapshot_is_rejected_without_waiting_for_a_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            fifo = Path(folder) / "untrusted-fifo"
            os.mkfifo(fifo)
            # This would block indefinitely in O_RDONLY without O_NONBLOCK.
            with self.assertRaisesRegex(gate.GateError, "regular file"):
                gate._read_snapshot(fifo)


    def test_equal_full_tip_and_state_is_readonly_pass(self):
        result = pinned_compare(snapshot(), snapshot("validator"), now=NOW)
        self.assertEqual(result["status"], "PASS_READONLY_TIP_CONSISTENCY_ONLY")
        self.assertEqual(result["fullHeight"], 377)
        self.assertTrue(result["requires_separate_genesis_firewall_and_tx_validation"])

    def test_mismatched_genesis_is_rejected(self):
        with self.assertRaisesRegex(gate.GateError, "genesisBlockId"):
            pinned_compare(snapshot(), snapshot("validator", genesisBlockId="d" * 64), now=NOW)

    def test_mismatched_full_height_is_rejected(self):
        with self.assertRaisesRegex(gate.GateError, "fullHeight"):
            pinned_compare(snapshot(), snapshot("validator", fullHeight=376), now=NOW)

    def test_mismatched_header_is_rejected(self):
        # Both nodes may be internally consistent but disagree with each other.
        with self.assertRaisesRegex(gate.GateError, "bestFullHeaderId"):
            pinned_compare(snapshot(), snapshot(
                "validator", bestFullHeaderId="c" * 64, stateVersion="c" * 64,
            ), now=NOW)

    def test_state_version_lag_blocks_a_false_pass(self):
        # Two nodes with the same apparent full tip but stale state are unsafe.
        with self.assertRaisesRegex(gate.GateError, "State version"):
            pinned_compare(snapshot(stateVersion="d" * 64),
                         snapshot("validator", stateVersion="d" * 64), now=NOW)

    def test_mismatched_state_root_is_rejected(self):
        with self.assertRaisesRegex(gate.GateError, "stateRoot"):
            pinned_compare(snapshot(), snapshot("validator", stateRoot="c" * 64), now=NOW)

    def test_unexpected_private_peer_counts_are_rejected(self):
        for count in (0, 2, 3):
            with self.subTest(count=count), self.assertRaisesRegex(
                gate.GateError, "exactly one private LAN peer"
            ):
                pinned_compare(snapshot(connected_peers=count), snapshot("validator"), now=NOW)

    def test_no_validated_block_is_rejected(self):
        with self.assertRaisesRegex(gate.GateError, "No full blocks"):
            pinned_compare(snapshot(fullHeight=0), snapshot("validator", fullHeight=0), now=NOW)

    def test_validator_mining_enabled_is_rejected(self):
        with self.assertRaisesRegex(gate.GateError, "mining"):
            pinned_compare(snapshot(), snapshot("validator", reported_is_mining=True), now=NOW)

    def test_stale_future_and_out_of_sync_snapshots_are_rejected(self):
        stale = (NOW - timedelta(minutes=16)).isoformat()
        future = (NOW + timedelta(seconds=1)).isoformat()
        far = (NOW - timedelta(minutes=7)).isoformat()
        for timestamp in (stale, future):
            with self.subTest(timestamp=timestamp), self.assertRaises(gate.GateError):
                pinned_compare(snapshot(), snapshot("validator", captured_at_utc=timestamp), now=NOW)
        with self.assertRaisesRegex(gate.GateError, "close enough"):
            pinned_compare(snapshot(), snapshot("validator", captured_at_utc=far), now=NOW)

    def test_role_schema_and_invalid_identifiers_rejected(self):
        cases = [
            (snapshot(role="validator"), snapshot("validator")),
            (snapshot(schema="WRONG"), snapshot("validator")),
            (snapshot(), snapshot("validator", stateRoot="0x" + ROOT)),
            (snapshot(), snapshot("validator", bestFullHeaderId="A" * 64)),
            (snapshot(), snapshot("validator", stateVersion="A" * 64)),
            (snapshot(), snapshot("validator", fullHeight=True)),
            (snapshot(), snapshot("validator", connected_peers=-1)),
            (snapshot(), snapshot("validator", reported_is_mining="false")),
            (snapshot(), snapshot("validator", unexpected=1)),
        ]
        for producer, validator in cases:
            with self.subTest(producer=producer, validator=validator):
                with self.assertRaises(gate.GateError):
                    pinned_compare(producer, validator, now=NOW)

    def test_timestamp_with_no_timezone_rejected(self):
        with self.assertRaisesRegex(gate.GateError, "timestamp"):
            pinned_compare(snapshot(), snapshot("validator", captured_at_utc="2026-11-12T20:00:00"), now=NOW)

    def test_capture_reads_only_local_info_and_peers(self):
        info = {
            "fullHeight": 377, "genesisBlockId": GENESIS,
            "bestFullHeaderId": HEADER, "stateVersion": HEADER, "stateRoot": ROOT,
            "isMining": False,
        }
        calls = []
        def fake_get(path):
            calls.append(path)
            return info if path == "/info" else [{"placeholder": "test-peer"}]
        with patch.object(gate, "_get_local_json", side_effect=fake_get):
            s = gate.capture("validator", now=NOW)
        self.assertEqual(calls, ["/info", "/peers/connected"])
        self.assertEqual(s["connected_peers"], 1)
        self.assertEqual(s["fullHeight"], 377)
        self.assertEqual(s["genesisBlockId"], GENESIS)
        self.assertEqual(s["stateVersion"], HEADER)
        self.assertNotIn("placeholder", json.dumps(s))

    def test_capture_rejects_enabled_validator_mining(self):
        with patch.object(gate, "_get_local_json", side_effect=[
            {"fullHeight": 377, "genesisBlockId": GENESIS,
             "bestFullHeaderId": HEADER, "stateVersion": HEADER, "stateRoot": ROOT, "isMining": True},
            [],
        ]):
            with self.assertRaises(gate.GateError):
                gate.capture("validator", now=NOW)

    def test_mining_status_must_be_explicit_and_boolean(self):
        for unknown in (None, "false", 0, 1):
            with self.subTest(value=unknown):
                with self.assertRaisesRegex(gate.GateError, "mining status"):
                    pinned_compare(snapshot(), snapshot(
                        "validator", reported_is_mining=unknown,
                    ), now=NOW)
                info = {
                    "fullHeight": 377, "genesisBlockId": GENESIS,
                    "bestFullHeaderId": HEADER, "stateVersion": HEADER,
                    "stateRoot": ROOT, "isMining": unknown,
                }
                with patch.object(gate, "_get_local_json", side_effect=[info, []]):
                    with self.assertRaisesRegex(gate.GateError, "isMining"):
                        gate.capture("validator", now=NOW)

    def test_capture_rejects_unapplied_full_tip(self):
        with patch.object(gate, "_get_local_json", side_effect=[
            {"fullHeight": 377, "genesisBlockId": GENESIS,
             "bestFullHeaderId": HEADER, "stateVersion": "d" * 64,
             "stateRoot": ROOT, "isMining": False},
            [{"name": "peer"}],
        ]):
            with self.assertRaisesRegex(gate.GateError, "State version"):
                gate.capture("producer", now=NOW)

    def test_capture_rejects_malformed_node_metadata(self):
        with patch.object(gate, "_get_local_json", side_effect=[
            {"fullHeight": 377, "bestFullHeaderId": HEADER}, [],
        ]):
            with self.assertRaises(gate.GateError):
                gate.capture("producer", now=NOW)

    def test_rest_endpoint_allowlist_blocks_wallet_calls(self):
        with self.assertRaisesRegex(gate.GateError, "Prohibited REST endpoint"):
            gate._get_local_json("/wallet/balances")
        with self.assertRaisesRegex(gate.GateError, "redirect"):
            gate.NoRedirects().redirect_request(None, None, 302, "", {}, "https://example.com")

    def test_duplicate_json_keys_and_excessive_response_rejected(self):
        for body in (b'{"a":1,"a":2}', b"{" + b"x" * (gate.MAX_JSON_BYTES + 1) + b"}",
                     b"not-json", b"\xff"):
            with self.subTest(length=len(body)), self.assertRaises(gate.GateError):
                gate._parse_json(body)

    def test_reject_nonregular_and_oversized_snapshot_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with self.assertRaisesRegex(gate.GateError, "regular file"):
                gate._read_snapshot(folder)
            huge = folder / "huge.json"
            huge.write_bytes(b"x" * (gate.MAX_JSON_BYTES + 2))
            with self.assertRaisesRegex(gate.GateError, "maximum size"):
                gate._read_snapshot(huge)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires O_NOFOLLOW")
    def test_snapshot_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            target = folder / "real.json"
            gate._write_private_new_file(target, snapshot())
            link = folder / "link.json"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                gate._read_snapshot(link)

    def test_snapshot_is_written_once_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            digest = gate._write_private_new_file(path, snapshot())
            self.assertEqual(len(digest), 64)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(gate._read_snapshot(path)["fullHeight"], 377)
            with self.assertRaises(FileExistsError):
                gate._write_private_new_file(path, snapshot())


if __name__ == "__main__":
    unittest.main()
