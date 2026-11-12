"""Tests for conservative CI workflow lint; source-only, no subprocess."""

import tempfile
import unittest
from pathlib import Path

from tools.audit_ci_workflows import audit_text, audit_tree

SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"

def valid_workflow():
    return (
        "name: Offline Test\n"
        "on:\n"
        "  push:\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-24.04\n"
        "    steps:\n"
        f"      - uses: actions/checkout@{SHA}\n"
        "        with:\n"
        "          persist-credentials: false\n"
    )


class WorkflowSafetyTests(unittest.TestCase):
    def test_valid_workflow(self):
        self.assertEqual(audit_text(valid_workflow(), "fixture.yml"), [])

    def test_unpinned_action_rejected(self):
        candidate = valid_workflow().replace("@" + SHA, "@v4")
        self.assertTrue(any("not pinned" in x for x in audit_text(candidate, "bad.yml")))

    def test_missing_action_revision_rejected(self):
        candidate = valid_workflow().replace("@" + SHA, "")
        self.assertTrue(any("no revision" in x for x in audit_text(candidate, "bad.yml")))

    def test_forbidden_write_permissions(self):
        candidate = valid_workflow().replace("  contents: read", "  contents: read\n  actions: write")
        self.assertTrue(any("write" in x for x in audit_text(candidate, "bad.yml")))

    def test_missing_global_read_scope_rejected(self):
        candidate = valid_workflow().replace("  contents: read\n", "")
        self.assertTrue(any("contents: read" in x for x in audit_text(candidate, "bad.yml")))

    def test_missing_permissions_rejected(self):
        candidate = valid_workflow().replace("permissions:\n", "")
        self.assertTrue(any("top-level" in x for x in audit_text(candidate, "bad.yml")))

    def test_elevated_trigger_rejected(self):
        for trigger in ("pull_request_target", "workflow_run"):
            candidate = valid_workflow().replace("  push:", f"  {trigger}:")
            with self.subTest(trigger=trigger):
                self.assertTrue(any("elevated" in x for x in audit_text(candidate, "bad.yml")))

    def test_inline_elevated_triggers_rejected(self):
        for trigger in ("on: [push, pull_request_target]", "on: workflow_run",
                        "on: [workflow_run, push]"):
            candidate = valid_workflow().replace("on:\\n  push:", trigger)
            with self.subTest(trigger=trigger):
                self.assertTrue(any(
                    "elevated" in x for x in audit_text(candidate, "bad.yml")
                ))

    def test_job_level_permissions_overrides_are_rejected(self):
        for override in ("write-all", "read-all"):
            candidate = valid_workflow().replace(
                "    runs-on: ubuntu-24.04",
                "    permissions: " + override + "\\n    runs-on: ubuntu-24.04",
            )
            with self.subTest(value=override):
                self.assertTrue(any(
                    "job-level permissions" in x
                    for x in audit_text(candidate, "bad.yml")
                ))

    def test_checkout_persisted_credentials_rejected(self):
        candidate = valid_workflow().replace("persist-credentials: false", "persist-credentials: true")
        self.assertTrue(any("persist" in x for x in audit_text(candidate, "bad.yml")))

    def test_current_workflows_pass(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit_tree(root), [])

    def test_missing_directory_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(audit_tree(Path(directory)))

    def test_workflow_non_sha_other_action_rejected(self):
        candidate = valid_workflow() + "      - uses: actions/setup-python@v5\n"
        self.assertTrue(any("not pinned" in x for x in audit_text(candidate, "bad.yml")))


if __name__ == "__main__":
    unittest.main()
