"""Offline tests; no node, network, wallet or mining involved."""

import copy
import json
import unittest
from pathlib import Path

from tools.verify_sources import (
    ValidationError, validate_manifest, validate_snapshot_pins,
)

ROOT = Path(__file__).resolve().parents[1]


class UpstreamManifestTests(unittest.TestCase):
    def setUp(self):
        self.valid = json.loads((ROOT / "upstreams.lock.json").read_text(encoding="utf-8"))

    def test_real_manifest_is_well_formed(self):
        self.assertEqual(len(validate_manifest(self.valid)), 3)

    def test_snapshot_records_match_upstream_commit_and_license(self):
        pinned = validate_manifest(self.valid)
        refs = json.loads((ROOT / "third_party" / "REFERENCES.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_snapshot_pins(pinned, refs), 8)

        stale = copy.deepcopy(refs)
        stale["files"][0]["revision"] = "d" * 40
        with self.assertRaisesRegex(ValidationError, "revision"):
            validate_snapshot_pins(pinned, stale)

        wrong_license = copy.deepcopy(refs)
        wrong_license["files"][1]["license_declared"] = "MIT"
        with self.assertRaisesRegex(ValidationError, "license"):
            validate_snapshot_pins(pinned, wrong_license)

        unrelated = copy.deepcopy(refs)
        unrelated["files"][0]["upstream"] = "other/repo"
        with self.assertRaisesRegex(ValidationError, "unknown upstream"):
            validate_snapshot_pins(pinned, unrelated)

        runnable = copy.deepcopy(refs)
        runnable["files"][0]["executable"] = True
        with self.assertRaisesRegex(ValidationError, "executable"):
            validate_snapshot_pins(pinned, runnable)

    def test_duplicate_upstream_url_must_not_override_pin(self):
        bad = copy.deepcopy(self.valid)
        bad["sources"][1]["url"] = bad["sources"][0]["url"]
        with self.assertRaisesRegex(ValidationError, "duplicate upstream URL"):
            validate_manifest(bad)

    def test_reject_weak_commit_pin(self):
        invalid = copy.deepcopy(self.valid)
        invalid["sources"][0]["commit"] = "main"
        with self.assertRaises(ValidationError):
            validate_manifest(invalid)

    def test_reject_duplicate_ids(self):
        invalid = copy.deepcopy(self.valid)
        invalid["sources"][1]["id"] = invalid["sources"][0]["id"]
        with self.assertRaises(ValidationError):
            validate_manifest(invalid)

    def test_reject_non_github_references(self):
        invalid = copy.deepcopy(self.valid)
        invalid["sources"][0]["url"] = "http://localhost/unsafe"
        with self.assertRaises(ValidationError):
            validate_manifest(invalid)

    def test_reject_unreviewed_import_flag(self):
        invalid = copy.deepcopy(self.valid)
        invalid["sources"][0]["imported"] = True
        with self.assertRaises(ValidationError):
            validate_manifest(invalid)

    def test_reject_unknown_license(self):
        invalid = copy.deepcopy(self.valid)
        invalid["sources"][1]["license_declared"] = "UNKNOWN"
        with self.assertRaises(ValidationError):
            validate_manifest(invalid)

    def test_reject_path_traversal_id(self):
        invalid = copy.deepcopy(self.valid)
        invalid["sources"][1]["id"] = "../other"
        with self.assertRaises(ValidationError):
            validate_manifest(invalid)

    def test_reject_empty_manifest(self):
        with self.assertRaises(ValidationError):
            validate_manifest({"schema": 1, "sources": []})


if __name__ == "__main__":
    unittest.main()
