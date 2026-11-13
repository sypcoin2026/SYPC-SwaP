"""Adversarial tests for the pinned Sigma 6.0.7 compiler-output reviewer.

No node, wallet, shell or network access. Synthetic log content only.
"""

from pathlib import Path
import copy
import json
import os
import tempfile
import unittest

from tools import review_native6_compilation as checker

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "research" / "native6" / "fingerprints.json"


def log_lines(manifest):
    lines = []
    for name, entry in manifest["contracts"].items():
        lines.append(
            f"[info] SYPC_NATIVE6_COMPILE_PASS {name} "
            f"sha256={entry['sha256']} bytes={entry['bytes']}"
        )
    lines.extend([
        "[info] SYPC_NATIVE6_COMPILER_ONLY_SIX_CONTRACTS_PASS",
        "[info] NOT_SYPC_CONSENSUS_NOT_FULL_TRANSACTION_NOT_SIGNATURE_VERIFICATION",
    ])
    return "\n".join(lines) + "\n"


def interpreter_log():
    return "\n".join(
        ["[info] SIGMA607_INTERPRETER_PASS:valid"]
        + ["[info] SIGMA607_INTERPRETER_REJECT:" + scenario
           for scenario in sorted(checker.SELL_REJECTIONS)]
        + [
            "[info] " + checker.INTERPRETER_END,
            "[info] SIGMA607_BUY_PASS:valid",
        ]
        + ["[info] SIGMA607_BUY_REJECT:" + scenario
           for scenario in sorted(checker.BUY_REJECTIONS)]
        + [
            "[info] " + checker.BUY_INTERPRETER_END,
            "[info] " + checker.INTERPRETER_SCOPE,
        ]
    ) + "\n"


def signed_log_lines():
    return "\n".join(
        ["[info] " + checker.SIGNED_POSITIVE,
         "[info] " + checker.SIGNED_SERIALIZATION,
         "[info] " + checker.SIGNED_CONSERVATION]
        + ["[info] SIGMA607_SIGNED_REJECT:" + name
           for name in sorted(checker.SIGNED_REJECTIONS)]
        + ["[info] " + checker.SIGNED_END, "[info] " + checker.SIGNED_SCOPE]
    ) + "\n"


class Native6ReviewTests(unittest.TestCase):
    def setUp(self):
        self.manifest = checker.read_manifest(PINS)
        self.good = log_lines(self.manifest)

    def test_signed_trace_requires_evidence_from_both_inputs(self):
        result = checker.inspect_signed_transaction_log(signed_log_lines())
        self.assertEqual(result["status"], "PASS_SIGMA607_SYNTHETIC_SIGNED_TRACE_ONLY")
        self.assertEqual(result["positive_both_input_checks"], 1)
        self.assertEqual(len(result["negative_scenarios"]), 6)
        self.assertFalse(result["native_consensus_proven"])
        self.assertFalse(result["safe_cancellation_proven"])

    def test_signed_trace_missing_or_repeated_cases_fails(self):
        case = sorted(checker.SIGNED_REJECTIONS)[0]
        row = "[info] SIGMA607_SIGNED_REJECT:" + case + "\n"
        with self.assertRaisesRegex(checker.FingerprintError, "Incomplete"):
            checker.inspect_signed_transaction_log(
                signed_log_lines().replace(row, "", 1))
        with self.assertRaisesRegex(checker.FingerprintError, "duplicate"):
            checker.inspect_signed_transaction_log(signed_log_lines() + row)

    def test_signed_trace_fake_or_repeated_success_fails(self):
        with self.assertRaisesRegex(checker.FingerprintError, "Incomplete"):
            checker.inspect_signed_transaction_log(
                signed_log_lines().replace(checker.SIGNED_SERIALIZATION, "NOT_RUN"))
        with self.assertRaisesRegex(checker.FingerprintError, "Duplicate"):
            checker.inspect_signed_transaction_log(
                signed_log_lines() + checker.SIGNED_POSITIVE + "\n")

    def test_signed_trace_unrecognized_negative_fails(self):
        with self.assertRaisesRegex(checker.FingerprintError, "negative"):
            checker.inspect_signed_transaction_log(
                signed_log_lines() + "SIGMA607_SIGNED_REJECT:made-up\n")

    def test_signed_trace_explicit_runtime_failure_fails(self):
        with self.assertRaisesRegex(checker.FingerprintError, "failure"):
            checker.inspect_signed_transaction_log(
                signed_log_lines() + "[error] rejected\n")
        with self.assertRaisesRegex(checker.FingerprintError, "failure"):
            checker.inspect_signed_transaction_log(
                signed_log_lines() + "SYPC607_SIGNED_UNSAFE_TRANSACTION_ACCEPTED:attack\n")

    def test_all_three_independent_logs_are_needed(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            comp = base / "compile.log"
            smoke = base / "smoke.log"
            signed = base / "signed.log"
            comp.write_text(self.good)
            smoke.write_text(interpreter_log())
            signed.write_text(signed_log_lines())
            result = checker.review(PINS, comp, smoke, signed)
            self.assertEqual(result["status"],
                             "PASS_SIGMA607_COMPILER_SCRIPT_SIGNED_TRACES_ONLY")
            self.assertFalse(result["ready_for_funds"])
            signed.write_text("wrong")
            self.assertEqual(checker.review(PINS, comp, smoke, signed)["status"], "FAIL")
            self.assertEqual(checker.review(PINS, comp, signed_log=signed)["status"],
                             "FAIL")

    def test_interpreter_evidence_has_one_pass_and_ten_distinct_rejections(self):
        result = checker.inspect_interpreter_log(interpreter_log())
        self.assertEqual(result["status"], "PASS_SIGMA607_BUY_SELL_INTERPRETER_TRACE_ONLY")
        self.assertEqual(result["sell_positive"], 1)
        self.assertEqual(result["buy_positive"], 1)
        self.assertEqual(len(result["sell_negative_scenarios"]), 10)
        self.assertEqual(len(result["buy_negative_scenarios"]), 7)
        self.assertFalse(result["native_consensus_proven"])

    def test_interpreter_missing_or_repeated_negative_is_rejected(self):
        name = sorted(checker.SELL_REJECTIONS)[0]
        line = "[info] SIGMA607_INTERPRETER_REJECT:" + name
        with self.assertRaisesRegex(checker.FingerprintError, "Incomplete"):
            checker.inspect_interpreter_log(
                interpreter_log().replace(line + "\n", "", 1))
        with self.assertRaisesRegex(checker.FingerprintError, "duplicate"):
            checker.inspect_interpreter_log(interpreter_log() + line + "\n")

    def test_interpreter_invalid_positive_and_wrong_case_are_rejected(self):
        with self.assertRaisesRegex(checker.FingerprintError, "positive"):
            checker.inspect_interpreter_log(
                interpreter_log().replace(
                    "SIGMA607_INTERPRETER_PASS:valid",
                    "SIGMA607_INTERPRETER_PASS:maybe", 1))
        with self.assertRaisesRegex(checker.FingerprintError, "positive"):
            checker.inspect_interpreter_log(
                interpreter_log() + "SIGMA607_INTERPRETER_PASS:valid\n")
        with self.assertRaisesRegex(checker.FingerprintError, "negative"):
            checker.inspect_interpreter_log(
                interpreter_log() + "SIGMA607_INTERPRETER_REJECT:not-a-test\n")

    def test_buy_missing_or_duplicate_rejection_fails(self):
        name = sorted(checker.BUY_REJECTIONS)[0]
        marker = "[info] SIGMA607_BUY_REJECT:" + name
        with self.assertRaisesRegex(checker.FingerprintError, "Incomplete"):
            checker.inspect_interpreter_log(
                interpreter_log().replace(marker + "\n", "", 1))
        with self.assertRaisesRegex(checker.FingerprintError, "duplicate"):
            checker.inspect_interpreter_log(interpreter_log() + marker + "\n")

    def test_buy_wrong_or_duplicate_positive_fails(self):
        with self.assertRaisesRegex(checker.FingerprintError, "positive"):
            checker.inspect_interpreter_log(
                interpreter_log().replace(
                    "SIGMA607_BUY_PASS:valid", "SIGMA607_BUY_PASS:forged"))
        with self.assertRaisesRegex(checker.FingerprintError, "positive"):
            checker.inspect_interpreter_log(
                interpreter_log() + "SIGMA607_BUY_PASS:valid\n")

    def test_buy_unknown_rejection_and_explicit_failure_fails(self):
        with self.assertRaisesRegex(checker.FingerprintError, "negative"):
            checker.inspect_interpreter_log(
                interpreter_log() + "SIGMA607_BUY_REJECT:fake\n")
        with self.assertRaisesRegex(checker.FingerprintError, "failure"):
            checker.inspect_interpreter_log(
                interpreter_log() + "SYPC607_MALICIOUS_BUY_ACCEPTED:no-order-id\n")

    def test_interpreter_missing_scope_or_finish_marker_is_blocked(self):
        for marker in (checker.INTERPRETER_END, checker.BUY_INTERPRETER_END,
                       checker.INTERPRETER_SCOPE):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(checker.FingerprintError, "Incomplete"):
                    checker.inspect_interpreter_log(interpreter_log().replace(marker, ""))

    def test_interpreter_error_overrides_reported_success(self):
        with self.assertRaisesRegex(checker.FingerprintError, "failure"):
            checker.inspect_interpreter_log(
                interpreter_log() + "[error] failure\n")

    def test_two_independent_log_gates_are_required_for_combined_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compile_log = root / "compiler.log"
            interpreter = root / "interpreter.log"
            compile_log.write_text(self.good)
            interpreter.write_text(interpreter_log())
            result = checker.review(PINS, compile_log, interpreter)
            self.assertEqual(result["status"],
                             "PASS_PINNED_SIGMA607_COMPILER_AND_SCRIPT_TRACE_ONLY")
            self.assertFalse(result["ready_for_funds"])
            interpreter.write_text("wrong")
            result = checker.review(PINS, compile_log, interpreter)
            self.assertEqual(result["status"], "FAIL")

    def test_six_pinned_contracts_pass_but_never_authorize_funds(self):
        result = checker.inspect(self.manifest, self.good)
        self.assertEqual(result["status"], "PASS_PINNED_SIGMA607_COMPILER_ONLY")
        self.assertEqual(result["sigma_version"], "6.0.7")
        self.assertEqual(result["count"], 6)
        self.assertFalse(result["ready_for_funds"])
        self.assertFalse(result["native_consensus_proven"])
        self.assertFalse(result["complete_transaction_proven"])

    def test_ansi_escape_sequences_do_not_hide_actual_results(self):
        rendered = self.good.replace("[info] ", "\x1b[0J[info]\x1b[0m ")
        self.assertEqual(checker.inspect(self.manifest, rendered)["count"], 6)

    def test_empty_and_missing_contract_log_rejected(self):
        with self.assertRaisesRegex(checker.FingerprintError, "incomplete"):
            checker.inspect(self.manifest, "")
        with self.assertRaisesRegex(checker.FingerprintError, "incomplete"):
            checker.inspect(
                self.manifest,
                "\n".join(x for x in self.good.splitlines()
                          if "AtomicSellSponsorRefund.sc" not in x),
            )

    def test_changed_fingerprint_rejected(self):
        name = "AtomicSellSponsorRefund.sc"
        altered = self.good.replace(
            self.manifest["contracts"][name]["sha256"], "0" * 64
        )
        with self.assertRaisesRegex(checker.FingerprintError, "drift"):
            checker.inspect(self.manifest, altered)

    def test_wrong_byte_length_rejected(self):
        name = "AtomicBuy.sc"
        altered = self.good.replace(
            f"bytes={self.manifest['contracts'][name]['bytes']}",
            f"bytes={self.manifest['contracts'][name]['bytes'] + 1}",
            1,
        )
        with self.assertRaisesRegex(checker.FingerprintError, "drift"):
            checker.inspect(self.manifest, altered)

    def test_duplicate_pass_line_rejected(self):
        first = self.good.splitlines()[0]
        with self.assertRaisesRegex(checker.FingerprintError, "Duplicate"):
            checker.inspect(self.manifest, first + "\n" + self.good)

    def test_extra_contract_rejected(self):
        extra = "SYPC_NATIVE6_COMPILE_PASS AtomicFake.sc sha256=" + "0" * 64 + " bytes=11"
        with self.assertRaisesRegex(checker.FingerprintError, "Unexpected contract"):
            checker.inspect(self.manifest, extra + "\n" + self.good)

    def test_bad_log_format_rejected(self):
        altered = self.good.replace(" sha256=", " hash=", 1)
        with self.assertRaisesRegex(checker.FingerprintError, "Malformed"):
            checker.inspect(self.manifest, altered)

    def test_missing_completion_and_disclaimer_rejected(self):
        for marker in (checker.END, checker.DISCLAIMER):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(checker.FingerprintError, "completion marker"):
                    checker.inspect(self.manifest, self.good.replace(marker, "MISSING"))

    def test_duplicate_success_footer_rejected(self):
        with self.assertRaisesRegex(checker.FingerprintError, "completion marker"):
            checker.inspect(self.manifest, self.good + checker.END + "\n")

    def test_explicit_error_overrides_pass_lines(self):
        with self.assertRaisesRegex(checker.FingerprintError, "explicit failure"):
            checker.inspect(self.manifest, self.good + "[error] rejected\n")

    def test_bad_sigma_version_manifest_rejected(self):
        modified = copy.deepcopy(self.manifest)
        modified["sigma_state"] = "4.0.5"
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "pins.json"
            file.write_text(json.dumps(modified))
            with self.assertRaisesRegex(checker.FingerprintError, "6.0.7"):
                checker.read_manifest(file)

    def test_missing_or_extra_pin_rejected(self):
        for change in ("remove", "add"):
            modified = copy.deepcopy(self.manifest)
            if change == "remove":
                modified["contracts"].pop("AtomicBuy.sc")
            else:
                modified["contracts"]["Other.sc"] = {"sha256": "1" * 64, "bytes": 33}
            with tempfile.TemporaryDirectory() as tmp:
                file = Path(tmp) / "pins.json"
                file.write_text(json.dumps(modified))
                with self.assertRaisesRegex(checker.FingerprintError, "contract list"):
                    checker.read_manifest(file)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "pins.json"
            file.write_text('{"schema":"SYPC_NATIVE6_FINGERPRINT_PIN_V1","schema":"evil"}')
            with self.assertRaisesRegex(checker.FingerprintError, "Duplicate"):
                checker.read_manifest(file)

    def test_unknown_manifest_field_rejected(self):
        modified = copy.deepcopy(self.manifest)
        modified["unsafe_override"] = True
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "pins.json"
            file.write_text(json.dumps(modified))
            with self.assertRaisesRegex(checker.FingerprintError, "schema mismatch"):
                checker.read_manifest(file)

    def test_log_and_manifest_must_be_regular_files_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(checker.FingerprintError, "regular file"):
                checker._read_local(root, 100)
            excessive = root / "huge.log"
            excessive.write_bytes(b"x" * (checker.MAX_LOG + 1))
            with self.assertRaisesRegex(checker.FingerprintError, "too large"):
                checker._read_local(excessive, checker.MAX_LOG)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires O_NOFOLLOW")
    def test_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.log"
            real.write_text(self.good)
            alias = root / "alias.log"
            alias.symlink_to(real)
            with self.assertRaises(OSError):
                checker._read_local(alias, checker.MAX_LOG)

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
                         "requires FIFO and O_NONBLOCK")
    def test_fifo_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            fifo = Path(tmp) / "fifo.log"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(checker.FingerprintError, "regular file"):
                checker._read_local(fifo, checker.MAX_LOG)

    def test_cli_review_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "compilation.log"
            log.write_text(self.good)
            before = set(root.iterdir())
            status = checker.review(PINS, log)
            self.assertEqual(status["status"], "PASS_PINNED_SIGMA607_COMPILER_ONLY")
            self.assertEqual(before, set(root.iterdir()))
            log.write_text("broken")
            status = checker.review(PINS, log)
            self.assertEqual(status["status"], "FAIL")
            self.assertFalse(status["ready_for_deployment"])


if __name__ == "__main__":
    unittest.main()
