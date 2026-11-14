"""Deterministic offline tests: no real /proc reads, node, network or wallet."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from reward_runtime_artifact_fingerprint import (  # noqa: E402
    CLASS_FILES,
    FingerprintError,
    MAIN_CLASS,
    SIGMA_JAR,
    expand_classpath,
    fingerprint_artifact,
    parse_explicit_classpath,
    select_process,
    sha256_file,
)


class FingerprintReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cwd = self.root / "java_runtime"
        self.cwd.mkdir()
        self.proc = self.root / "proc"
        self.proc.mkdir()

    def add_proc(self, pid, cmdline):
        target = self.proc / str(pid)
        target.mkdir()
        (target / "cmdline").write_bytes(b"\0".join(
            item.encode("utf-8") for item in cmdline) + b"\0"
        )
        (target / "cwd").symlink_to(self.cwd, target_is_directory=True)

    def add_classes(self):
        classes = self.cwd / "classes"
        classfile = classes / CLASS_FILES["reward_launcher"]
        classfile.parent.mkdir(parents=True, exist_ok=True)
        classfile.write_bytes(b"public-test-launcher-bytecode")
        return classes

    def add_sigma(self):
        jars = self.cwd / "lib"
        jars.mkdir(exist_ok=True)
        jar = jars / SIGMA_JAR
        with zipfile.ZipFile(jar, "w") as archive:
            archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        return jar

    def test_requires_exact_reward_main_class_and_explicit_cp(self):
        self.assertIsNone(parse_explicit_classpath(
            ["java", "-cp", "classes", "unrelated.Main"]
        ))
        self.assertEqual(parse_explicit_classpath(
            ["java", "-cp", "classes:lib/*", MAIN_CLASS, "secret=value"]
        ), "classes:lib/*")
        with self.assertRaisesRegex(FingerprintError, "EXPLICIT_CLASSPATH"):
            parse_explicit_classpath(["java", MAIN_CLASS, "secret=value"])

    def test_hashes_are_real_and_no_absolute_paths_returned(self):
        classes = self.add_classes()
        item = fingerprint_artifact(classes)
        actual = hashlib.sha256(b"public-test-launcher-bytecode").hexdigest()
        self.assertEqual(item["class_sha256"]["reward_launcher"], actual)
        self.assertEqual(item["type"], "class_directory")
        self.assertNotIn(str(self.cwd), json.dumps(item))

    def test_synthetic_proc_captures_classes_and_sigma_without_secrets(self):
        self.add_classes()
        jar = self.add_sigma()
        self.add_proc(4433, [
            "/usr/bin/java", "-Xmx1G", "-cp",
            "classes:lib/" + SIGMA_JAR, MAIN_CLASS, "secret=PRIVATE_NOT_TO_LEAK",
        ])
        item = select_process(pid=4433, proc_root=self.proc)
        self.assertEqual(item["pid"], 4433)
        self.assertEqual(item["classpath_entries"], 2)
        self.assertEqual(len(item["launcher_artifacts"]), 1)
        self.assertEqual(item["sigma607_sha256"], [sha256_file(jar)])
        snapshot = json.dumps(item, sort_keys=True)
        self.assertNotIn("PRIVATE_NOT_TO_LEAK", snapshot)
        self.assertNotIn(str(self.cwd), snapshot)
        self.assertNotIn("192.168.", snapshot)

    def test_multiple_reward_launchers_are_ambiguous(self):
        self.add_classes()
        self.add_sigma()
        argv = ["java", "-cp", "classes:lib/" + SIGMA_JAR, MAIN_CLASS]
        self.add_proc(1234, argv)
        self.add_proc(1235, argv)
        with self.assertRaisesRegex(FingerprintError, "EXACTLY_ONE"):
            select_process(proc_root=self.proc)

    def test_wildcard_expansion_only_local_jars(self):
        jar = self.add_sigma()
        self.assertEqual(
            expand_classpath("lib/*", self.cwd), [jar]
        )

    def test_classpath_expansion_bounded(self):
        with self.assertRaisesRegex(FingerprintError, "CLASSPATH_TOO_LONG"):
            expand_classpath(":".join(["x"] * 513), self.cwd)


if __name__ == "__main__":
    unittest.main()
