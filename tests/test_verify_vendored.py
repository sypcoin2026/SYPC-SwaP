"""Synthetic tests of the offline reference snapshot verifier."""

import copy
import tempfile
import unittest
from pathlib import Path

from tools.verify_vendored import SnapshotError, git_blob_sha1, verify_copies, verify_manifest


class ReferenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.rel = "third_party/ergo-contracts/contracts/Atomic.scala"
        self.data = b"safe reference example\n"
        self.record = {
            "copy_path": self.rel,
            "github_blob_sha1": git_blob_sha1(self.data),
            "revision": "c" * 40,
            "upstream": "ergoplatform/ergo-contracts",
            "executable": False,
        }
        self.doc = {"schema": 1, "files": [self.record]}

    def test_valid_synthetic_snapshot(self):
        refs = verify_manifest(self.doc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / self.rel
            path.parent.mkdir(parents=True)
            path.write_bytes(self.data)
            self.assertEqual(verify_copies(Path(tmp), refs), 1)

    def test_license_at_repository_root_is_allowed(self):
        record = copy.deepcopy(self.record)
        record["copy_path"] = "third_party/ergo-contracts/LICENSE"
        self.assertEqual(len(verify_manifest({"schema": 1, "files": [record]})), 1)

    def test_detect_modified_bytes(self):
        refs = verify_manifest(self.doc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / self.rel
            path.parent.mkdir(parents=True)
            path.write_bytes(self.data + b"extra")
            with self.assertRaisesRegex(SnapshotError, "modified"):
                verify_copies(Path(tmp), refs)

    def test_missing_file_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SnapshotError, "missing"):
                verify_copies(Path(tmp), verify_manifest(self.doc))

    def test_reject_traversal_path(self):
        for value in ("third_party/../wallet/secrets", "/third_party/file", "third_party//oops", "third_party/a/./oops"):
            invalid = copy.deepcopy(self.doc)
            invalid["files"][0]["copy_path"] = value
            with self.subTest(value=value), self.assertRaises(SnapshotError):
                verify_manifest(invalid)

    def test_reject_bad_hash_and_duplicates(self):
        invalid = copy.deepcopy(self.doc)
        invalid["files"][0]["github_blob_sha1"] = "main"
        with self.assertRaises(SnapshotError):
            verify_manifest(invalid)
        invalid = copy.deepcopy(self.doc)
        invalid["files"].append(copy.deepcopy(self.record))
        with self.assertRaises(SnapshotError):
            verify_manifest(invalid)

    def test_reject_executable_reference(self):
        invalid = copy.deepcopy(self.doc)
        invalid["files"][0]["executable"] = True
        with self.assertRaises(SnapshotError):
            verify_manifest(invalid)


if __name__ == "__main__":
    unittest.main()
