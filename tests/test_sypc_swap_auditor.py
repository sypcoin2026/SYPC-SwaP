"""Offline adversarial regression suite for the independent auditor (no networks)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import sypc_swap_auditor as auditor

NOW = datetime(2026, 11, 13, 11, 0, tzinfo=timezone.utc)
CORE = "a" * 40
SWAP = "b" * 40
GENESIS = "c" * 64
CONTRACT = "d" * 64
HEADER = "e" * 64
ROOT = "f" * 64
RUN = "audit_run_20261113"


def policy() -> dict:
    return {
        "schema": auditor.POLICY_SCHEMA,
        "network_id": "SypPrivateV30",
        "genesis_id": GENESIS,
        "core_commit": CORE,
        "swap_commit": SWAP,
        "native_sigma_version": "6.0.7",
        "contract_sha256": CONTRACT,
    }


def run(phase="offline") -> dict:
    report = {
        "schema": auditor.RUN_SCHEMA,
        "run_id": RUN,
        "phase": phase,
        "network_id": "SypPrivateV30",
        "genesis_id": GENESIS,
        "core_commit": CORE,
        "swap_commit": SWAP,
        "native_sigma_version": "6.0.7",
        "contract_sha256": CONTRACT,
        "created_at": NOW.isoformat().replace("+00:00", "Z"),
        "checks": [],
    }
    if phase == "offline":
        report["reference_sigma_version"] = "4.0.5"
    return report


def node(role):
    return {
        "role": role, "node_id": "0" * 64 if role == "producer" else "1" * 64,
        "genesis_id": GENESIS, "full_height": 17,
        "best_full_header_id": HEADER, "state_version": HEADER,
        "state_root": ROOT, "peer_count": 1,
        "is_mining": False, "captured_at": NOW.isoformat().replace("+00:00", "Z"),
    }


class AuditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.p = policy()
        self.r = run()

    def attach(self, name, *, status="PASS", exit_code=0, body=None, phase=None):
        if body is None:
            body = "SYPC_AUDIT_CHECK_PASS:" + name + "\n"
            if self.r["phase"] in ("native", "two_node"):
                body += (
                    "SYPC_AUDIT_NATIVE_SIGMA:6.0.7\n"
                    "SYPC_AUDIT_CORE_COMMIT:" + CORE + "\n"
                    "SYPC_AUDIT_SWAP_COMMIT:" + SWAP + "\n"
                )
        filename = name + ".log"
        data = body.encode("utf-8")
        (self.folder / filename).write_bytes(data)
        self.r["checks"].append({
            "id": name, "status": status, "exit_code": exit_code,
            "artifact": filename, "sha256": hashlib.sha256(data).hexdigest(),
        })

    def complete(self):
        for check in sorted(auditor.PHASES[self.r["phase"]]):
            self.attach(check)

    def inspect(self, *, now=NOW):
        return auditor.inspect(self.p, self.r, self.folder, now=now)

    def test_offline_gate_checks_integrity_but_never_authorizes_funds(self):
        self.complete()
        result = self.inspect()
        self.assertEqual(result["status"], "PASS_EVIDENCE_INTEGRITY_ONLY")
        self.assertEqual(result["approved_native_sigma_version"], "6.0.7")
        self.assertFalse(result["native_compatibility_demonstrated"])
        self.assertFalse(result["ready_for_deployment"])
        self.assertFalse(result["ready_for_funds"])

    def test_missing_evidence_blocks(self):
        self.attach("python_regressions")
        with self.assertRaisesRegex(auditor.AuditBlocked, "Missing/blocked"):
            self.inspect()

    def test_missing_artifact_blocks(self):
        self.complete()
        (self.folder / "source_provenance.log").unlink()
        with self.assertRaisesRegex(auditor.AuditBlocked, "Missing artifact"):
            self.inspect()

    def test_fail_record_is_fail_even_if_other_checks_pass(self):
        self.complete()
        self.r["checks"][0]["status"] = "FAIL"
        with self.assertRaisesRegex(auditor.AuditError, "Failure reported"):
            self.inspect()

    def test_blocked_record_is_blocked_even_with_success_marker(self):
        self.complete()
        self.r["checks"][0]["status"] = "BLOCKED"
        with self.assertRaisesRegex(auditor.AuditBlocked, "Missing/blocked"):
            self.inspect()

    def test_contradictory_success_exit_code_fails(self):
        self.complete()
        self.r["checks"][0]["exit_code"] = 2
        with self.assertRaisesRegex(auditor.AuditError, "Contradictory PASS"):
            self.inspect()

    def test_missing_exact_success_marker_fails(self):
        self.attach("source_provenance", body="All tests passed.\n")
        with self.assertRaisesRegex(auditor.AuditError, "Contradictory PASS"):
            self.inspect()

    def test_failure_marker_overrides_claimed_pass(self):
        self.attach("source_provenance", body=(
            "SYPC_AUDIT_CHECK_PASS:source_provenance\n"
            "SYPC_AUDIT_CHECK_FAIL:source_provenance\n"))
        with self.assertRaisesRegex(auditor.AuditError, "Failure reported"):
            self.inspect()

    def test_corrupted_artifact_fails(self):
        self.complete()
        (self.folder / "python_regressions.log").write_text("modified")
        with self.assertRaisesRegex(auditor.AuditError, "hash mismatch"):
            self.inspect()

    def test_native_evidence_cannot_use_reference_sigma_version(self):
        self.r = run("native")
        self.complete()
        self.r["native_sigma_version"] = "4.0.5"
        with self.assertRaisesRegex(auditor.AuditError, "native_sigma_version"):
            self.inspect()

    def test_policy_cannot_silently_downgrade_native_version(self):
        self.p["native_sigma_version"] = "4.0.5"
        with self.assertRaisesRegex(auditor.AuditError, "6.0.7"):
            self.inspect()

    def test_native_report_claims_only_metadata_verification(self):
        self.r = run("native")
        self.complete()
        result = self.inspect()
        self.assertEqual(result["status"], "PASS_EVIDENCE_INTEGRITY_ONLY")
        self.assertFalse(result["native_compatibility_demonstrated"])
        self.assertFalse(result["ready_for_funds"])

    def test_native_rejects_old_sigma_engine_in_artifact(self):
        self.r = run("native")
        self.attach("native_contract_compile", body=(
            "SYPC_AUDIT_CHECK_PASS:native_contract_compile\n"
            "SYPC_AUDIT_NATIVE_SIGMA:4.0.5\n"
            "SYPC_AUDIT_CORE_COMMIT:" + CORE + "\n"
            "SYPC_AUDIT_SWAP_COMMIT:" + SWAP + "\n"
        ))
        with self.assertRaisesRegex(auditor.AuditError, "native engine"):
            self.inspect()

    def test_native_rejects_missing_commit_marker(self):
        self.r = run("native")
        self.attach("native_contract_compile", body=(
            "SYPC_AUDIT_CHECK_PASS:native_contract_compile\n"
            "SYPC_AUDIT_NATIVE_SIGMA:6.0.7\n"
        ))
        with self.assertRaisesRegex(auditor.AuditError, "native engine"):
            self.inspect()

    def test_offline_reference_version_is_explicitly_required(self):
        self.r.pop("reference_sigma_version")
        with self.assertRaisesRegex(auditor.AuditBlocked, "provenance"):
            self.inspect()

    def test_reference_version_does_not_substitute_native_checks(self):
        self.r = run("native")
        self.r["reference_sigma_version"] = "4.0.5"
        self.attach("source_provenance")
        with self.assertRaisesRegex(auditor.AuditError, "wrong-phase"):
            self.inspect()

    def test_wrong_chain_genesis_commit_and_contract_are_rejected(self):
        for field, altered in [
            ("network_id", "OtherNet"), ("genesis_id", "0" * 64),
            ("core_commit", "0" * 40), ("swap_commit", "0" * 40),
            ("contract_sha256", "0" * 64),
        ]:
            with self.subTest(field=field):
                snapshot = copy.deepcopy(self.r)
                self.r[field] = altered
                with self.assertRaisesRegex(auditor.AuditError, "Mismatch"):
                    self.inspect()
                self.r = snapshot

    def test_duplicate_check_and_file_are_rejected(self):
        self.complete()
        self.r["checks"].append(copy.deepcopy(self.r["checks"][0]))
        with self.assertRaisesRegex(auditor.AuditError, "Duplicate check"):
            self.inspect()
        self.r["checks"][-1]["id"] = "other"
        with self.assertRaisesRegex(auditor.AuditError, "wrong-phase"):
            self.inspect()

    def test_traversal_and_unwanted_filename_rejected(self):
        self.complete()
        for name in ("../secret.json", "/etc/passwd", "file.key", "A.log"):
            with self.subTest(name=name):
                self.r["checks"][0]["artifact"] = name
                with self.assertRaisesRegex(auditor.AuditError, "filename"):
                    self.inspect()
        self.r["checks"][0]["artifact"] = "python_regressions.log"
        self.r["checks"][1]["artifact"] = "python_regressions.log"
        with self.assertRaisesRegex(auditor.AuditError, "duplicate evidence filename"):
            self.inspect()

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires O_NOFOLLOW")
    def test_symlink_artifact_is_not_followed(self):
        self.attach("source_provenance")
        src = self.folder / "source_provenance.log"
        dst = self.folder / "real.log"
        src.rename(dst)
        src.symlink_to(dst)
        with self.assertRaises(OSError):
            self.inspect()

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
                         "requires FIFO and O_NONBLOCK")
    def test_fifo_artifact_is_rejected_without_hanging(self):
        self.complete()
        path = self.folder / "python_regressions.log"
        path.unlink()
        os.mkfifo(path)
        with self.assertRaisesRegex(auditor.AuditError, "regular file"):
            self.inspect()

    def test_oversized_artifact_is_rejected(self):
        self.complete()
        (self.folder / "python_regressions.log").write_bytes(
            b"x" * (auditor.MAX_ARTIFACT_BYTES + 1))
        with self.assertRaisesRegex(auditor.AuditError, "size limit"):
            self.inspect()

    def test_dont_trust_old_or_future_run_reports(self):
        self.complete()
        with self.assertRaisesRegex(auditor.AuditError, "stale"):
            self.inspect(now=NOW + timedelta(seconds=auditor.MAX_REPORT_AGE_SECONDS + 1))
        with self.assertRaisesRegex(auditor.AuditError, "future"):
            self.inspect(now=NOW - timedelta(seconds=1))

    def test_two_node_requires_independent_matching_tip(self):
        self.r = run("two_node")
        self.r["nodes"] = [node("producer"), node("validator")]
        self.complete()
        result = self.inspect()
        self.assertEqual(result["status"], "PASS_EVIDENCE_INTEGRITY_ONLY")
        self.assertFalse(result["ready_for_deployment"])

    def test_node_consistency_negative_cases(self):
        self.r = run("two_node")
        self.r["nodes"] = [node("producer"), node("validator")]
        for field, wrong in [
            ("node_id", "0" * 64), ("genesis_id", "a" * 64),
            ("full_height", 16), ("best_full_header_id", "b" * 64),
            ("state_version", "0" * 64), ("state_root", "1" * 64),
            ("peer_count", 2), ("is_mining", True),
        ]:
            with self.subTest(field=field):
                self.r["nodes"][1][field] = wrong
                with self.assertRaises(auditor.AuditError):
                    self.inspect()
                self.r["nodes"][1] = node("validator")

    def test_two_node_missing_observation_blocks(self):
        self.r = run("two_node")
        with self.assertRaisesRegex(auditor.AuditBlocked, "Missing independent"):
            self.inspect()

    def test_mainnet_never_approved_by_v01(self):
        self.r = run("mainnet")
        with self.assertRaisesRegex(auditor.AuditBlocked, "NOT implemented"):
            self.inspect()

    def test_invalid_json_and_duplicate_fields_are_rejected(self):
        path = self.folder / "bad.json"
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '[1,2]'):
            with self.subTest(raw=raw):
                path.write_text(raw)
                with self.assertRaises(auditor.AuditError):
                    auditor._json_file(path)

    def test_cli_reports_fail_and_blocked_without_writing_files(self):
        policy_file = self.folder / "policy.json"
        run_file = self.folder / "run.json"
        policy_file.write_text(json.dumps(self.p))
        run_file.write_text(json.dumps(self.r))
        before = set(self.folder.iterdir())
        result = auditor.review_files(policy_file, run_file, self.folder, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(set(self.folder.iterdir()), before)
        self.r["core_commit"] = "0" * 40
        run_file.write_text(json.dumps(self.r))
        result = auditor.review_files(policy_file, run_file, self.folder, now=NOW)
        self.assertEqual(result["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
