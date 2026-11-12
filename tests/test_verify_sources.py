"""Offline tests; no node, network, wallet or mining involved."""

import copy
import json
import unittest
from pathlib import Path

from tools.verify_sources import ValidationError, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


class UpstreamManifestTests(unittest.TestCase):
    def setUp(self):
        self.valid = json.loads((ROOT / "upstreams.lock.json").read_text(encoding="utf-8"))

    def test_real_manifest_is_well_formed(self):
        self.assertEqual(len(validate_manifest(self.valid)), 3)

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
