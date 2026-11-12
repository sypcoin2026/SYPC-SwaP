"""Negative and positive cases for the offline-only runtime AST tripwire."""

import tempfile
from pathlib import Path
import unittest

from tools.audit_runtime_boundary import scan_source, scan_tree


class RuntimeBoundaryTests(unittest.TestCase):
    def test_allow_pure_math_and_hash(self):
        self.assertEqual(scan_source("import hashlib\nfrom dataclasses import dataclass\n", "test.py"), [])

    def test_reject_direct_socket_import(self):
        self.assertTrue(scan_source("import socket\n", "test.py"))

    def test_reject_aliases_and_nested_imports(self):
        self.assertTrue(scan_source("import urllib.request as u\n", "test.py"))

    def test_reject_from_import(self):
        self.assertTrue(scan_source("from subprocess import Popen\n", "test.py"))

    def test_reject_dynamic_import(self):
        self.assertTrue(scan_source("module = __import__('socket')\n", "test.py"))

    def test_reject_dynamic_execution_and_file_open(self):
        for source in ("eval('1')", "exec('a=1')", "open('/tmp/secret')", "vars(object())"):
            with self.subTest(source=source):
                self.assertTrue(scan_source(source, "test.py"))

    def test_reject_malformed_python(self):
        self.assertTrue(scan_source("def f(:", "bad.py"))

    def test_missing_package_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(scan_tree(Path(tmp)))

    def test_scans_real_temp_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "sypc_swap"
            pkg.mkdir()
            (pkg / "file.py").write_text("import socket\n", encoding="utf-8")
            self.assertTrue(scan_tree(root))
            (pkg / "file.py").write_text("from dataclasses import dataclass\n", encoding="utf-8")
            self.assertEqual(scan_tree(root), [])


if __name__ == "__main__":
    unittest.main()
