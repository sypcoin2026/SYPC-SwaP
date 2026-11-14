"""Offline tests using synthetic proc, classpath entries, and JDK files."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reward_runtime_artifact_fingerprint as audit  # noqa: E402


class FingerprintReadOnlyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cwd = self.root / "private-cwd"
        self.cwd.mkdir()
        self.proc = self.root / "proc"
        self.proc.mkdir()
        process_root = self.root / "mount-root"
        process_root.mkdir()
        self.mount_ns = self.root / "mount-namespace"
        self.mount_ns.touch()
        self.make_proc_view(self.proc / "self", process_root, self.mount_ns)
        self.process_root = process_root
        self.jdk = self.root / "private-jdk"
        for name in audit.RUNTIME_FILES:
            path = self.jdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'JAVA_VERSION="11.0.33"\n' if name == "release" else name.encode())
        self.java = self.jdk / "bin/java"

    @staticmethod
    def make_proc_view(entry, root, mount):
        entry.mkdir()
        (entry / "ns").mkdir()
        (entry / "ns/mnt").symlink_to(mount)
        (entry / "root").symlink_to(root)

    def add_proc(self, pid, argv, *, comm=b"java", environ=b""):
        target = self.proc / str(pid)
        self.make_proc_view(target, self.process_root, self.mount_ns)
        (target / "comm").write_bytes(comm + b"\n")
        (target / "stat").write_text(f"{pid} (test ) java) " + " ".join(["S"] + ["0"] * 18 + ["100"]))
        (target / "cmdline").write_bytes(b"\0".join(map(os.fsencode, argv)) + b"\0")
        (target / "environ").write_bytes(environ)
        (target / "cwd").symlink_to(self.cwd)
        (target / "exe").symlink_to(self.java)
        return target

    def add_class(self, directory, label, data=None):
        path = self.cwd / directory / audit.CLASS_FILES[label]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if data is not None else label.encode())
        return path

    def add_classes(self, *, full=False):
        labels = set(audit.CLASS_FILES) - audit.SIGMA_LABELS if full else {
            "reward_launcher", "reward_launcher_module",
        }
        return {label: self.add_class("classes", label) for label in labels}

    def add_sigma(self, *, delta=None):
        jar = self.cwd / audit.SIGMA_JAR
        with zipfile.ZipFile(jar, "w") as archive:
            archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
            for label in sorted(audit.SIGMA_LABELS):
                archive.writestr(audit.CLASS_FILES[label], label.encode())
            if delta:
                archive.writestr("resource.dat", delta)
        return jar

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        inspect = lambda **kwargs: self.inspect_fixture(**kwargs)
        with patch.object(sys, "argv", ["audit", *map(str, args)]), \
                patch.object(audit, "inspect_process", side_effect=inspect), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = audit.main()
        output = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(str(self.root), output)
        self.assertNotIn("PRIVATE_TEST", output)
        return rc, stdout.getvalue(), stderr.getvalue()

    inspect_real = staticmethod(audit.inspect_process)

    def inspect_fixture(self, **kwargs):
        return self.inspect_real(proc_root=self.proc, **kwargs)

    def test_exact_java_entry_point(self):
        parse = audit.parse_explicit_classpath
        for argv in (
            ["python", "-c", audit.MAIN_CLASS],
            ["java", "-cp", "foo", "Other.Main", audit.MAIN_CLASS],
            ["java", "-cp", "foo", "-jar", "irrelevant.jar", audit.MAIN_CLASS],
            ["java", "-m", "other/module.Main", audit.MAIN_CLASS],
        ):
            self.assertIsNone(parse(argv))
        self.assertEqual(parse(["/usr/bin/java", "-Xmx1G", "--class-path=classes",
                                audit.MAIN_CLASS, "secret=PRIVATE_TEST"]), "classes")
        with self.assertRaisesRegex(audit.FingerprintError, "EXPLICIT_CLASSPATH"):
            parse(["java", audit.MAIN_CLASS])

    def test_hidden_code_lookup_flags_fail_closed(self):
        for flags in (
            ["-javaagent:PRIVATE_TEST"], ["@PRIVATE_TEST"], ["-Djava.system.class.loader=PRIVATE_TEST"],
            ["--patch-module=java.base=PRIVATE_TEST"], ["-Djava.class.path=PRIVATE_TEST"],
            ["--module-path", "PRIVATE_TEST"],
            ["-Xbootclasspath/a:PRIVATE_TEST"], ["-XX:VMOptionsFile=PRIVATE_TEST"],
            ["-cp", "second"], ["-Djava.home=PRIVATE_TEST"],
        ):
            with self.subTest(flags=flags), self.assertRaisesRegex(
                audit.FingerprintError, "UNSUPPORTED_JAVA_LAUNCH_OPTIONS"
            ):
                audit.parse_explicit_classpath(["java", "-cp", "first", *flags, audit.MAIN_CLASS])

    def test_order_keeps_repeated_entries_and_empty_segments(self):
        entries = audit.expand_classpath(":classes:classes", self.cwd)
        self.assertEqual(entries, [self.cwd, self.cwd / "classes", self.cwd / "classes"])
        with self.assertRaisesRegex(audit.FingerprintError, "WILDCARD_UNSUPPORTED"):
            audit.expand_classpath("lib/*", self.cwd)
        with self.assertRaisesRegex(audit.FingerprintError, "CLASSPATH_TOO_LONG"):
            audit.expand_classpath(":".join(["x"] * 513), self.cwd)
        with self.assertRaisesRegex(audit.FingerprintError, "ABSOLUTE_CLASSPATH"):
            audit.expand_classpath("classes", None)

    def test_capture_auto_and_explicit_pid_with_paths_redacted(self):
        layout = self.add_classes()
        sigma = self.add_sigma()
        self.add_proc(43, ["java", "-cp", f"classes:{sigma.name}", audit.MAIN_CLASS, "PRIVATE_TEST"])
        self.add_proc(44, ["java", "-cp", "other", "Other.Main", audit.MAIN_CLASS])
        self.add_proc(45, ["python3", "-c", audit.MAIN_CLASS], comm=b"python3")
        for cmd in ([], ["--pid", 43]):
            rc, stdout, stderr = self.run_cli(*cmd, "--expected-sigma-sha256", audit.sha256_file(sigma))
            self.assertEqual((rc, stderr), (0, ""))
            data = json.loads(stdout)
            self.assertEqual(data["counts"]["classpath_entries"], 2)
            digest = hashlib.sha256(layout["reward_launcher"].read_bytes()).hexdigest()
            self.assertEqual(data["tracked_classes"]["reward_launcher"], [
                {"classpath_index": 0, "sha256": digest},
            ])
            self.assertFalse(data["git_commit_verified"])
            self.assertFalse(data["runtime_class_loading_verified"])

    def test_multiple_reward_candidates_rejected_before_artifact_scan(self):
        argv = ["java", "-cp", "classes", audit.MAIN_CLASS]
        self.add_proc(43, argv)
        self.add_proc(44, argv)
        with patch.object(audit, "fingerprint_artifact", side_effect=AssertionError("no classpath scan")):
            rc, stdout, stderr = self.run_cli()
        self.assertEqual((rc, stdout), (2, ""))
        self.assertIn("EXPECTED_EXACTLY_ONE_REWARD_LAUNCHER", stderr)

    def test_pid_reuse_is_rejected(self):
        target = self.add_proc(43, ["java", "-cp", "classes", audit.MAIN_CLASS])
        self.add_classes()
        capture = audit.capture_classpath

        def replacement(*args, **kwargs):
            value = capture(*args, **kwargs)
            stat = target / "stat"
            stat.write_text(stat.read_text().removesuffix("100") + "200")
            return value

        with patch.object(audit, "capture_classpath", side_effect=replacement):
            rc, _, stderr = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("PROCESS_CHANGED_DURING_CAPTURE", stderr)

    def test_untrusted_process_mounts_or_launcher_environment(self):
        process = self.add_proc(43, ["java", "-cp", "classes", audit.MAIN_CLASS],
                                environ=b"JAVA_TOOL_OPTIONS=-javaagent:PRIVATE_TEST\0")
        rc, _, stderr = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("UNSUPPORTED_JAVA_LAUNCH_ENVIRONMENT", stderr)
        (process / "ns/mnt").unlink()
        (process / "ns/mnt").symlink_to(self.java)
        rc, _, stderr = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("PROCESS_MOUNT_NAMESPACE_MISMATCH", stderr)
        (process / "root").unlink()
        (process / "root").symlink_to(self.cwd)
        rc, _, stderr = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("PROCESS_ROOT_MISMATCH", stderr)

    def test_duplicate_classes_fail_with_directory_and_jar_evidence(self):
        classes = self.add_classes()
        jar = self.cwd / "dup.jar"
        self.add_sigma()
        with zipfile.ZipFile(jar, "w") as archive:
            archive.write(classes["reward_launcher"], audit.CLASS_FILES["reward_launcher"])
        self.add_proc(43, ["java", "-cp", f"classes:dup.jar:{audit.SIGMA_JAR}", audit.MAIN_CLASS])
        rc, stdout, stderr = self.run_cli()
        self.assertEqual((rc, stdout), (2, ""))
        self.assertIn("MULTIPLE_LAUNCHER_CODE_ARTIFACTS", stderr)
        evidence = json.loads(stderr.splitlines()[1].split(":", 1)[1])
        self.assertEqual([r["classpath_index"] for r in evidence["launcher_artifacts"]], [0, 1])
        hashes = [r["class_sha256"]["reward_launcher"] for r in evidence["launcher_artifacts"]]
        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(evidence["launcher_artifacts"][1]["jar_sha256"], audit.sha256_file(jar))

    def test_missing_module_or_classpath_entry_fails(self):
        self.add_class("classes", "reward_launcher_module")
        self.add_sigma()
        process = self.add_proc(43, ["java", "-cp", f"classes:absent:{audit.SIGMA_JAR}", audit.MAIN_CLASS])
        rc, _, err = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("CLASSPATH_ENTRY_MISSING", err)
        (process / "cmdline").write_bytes((f"java\0-cp\0classes:{audit.SIGMA_JAR}\0" +
                                           audit.MAIN_CLASS + "\0").encode())
        rc, _, err = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("REQUIRED_CLASS_MISSING", err)

    def test_shadowed_core_and_wrong_sigma_fail(self):
        self.add_classes()
        self.add_class("classes", "native_transaction", b"first")
        second = self.add_class("second", "native_transaction", b"second")
        self.add_sigma()
        self.add_proc(43, ["java", "-cp", f"classes:second:{audit.SIGMA_JAR}", audit.MAIN_CLASS])
        rc, _, err = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("DUPLICATE_TRACKED_CLASS", err)
        second.unlink()
        rc, _, err = self.run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("SIGMA607_HASH_MISMATCH", err)

    def test_zip_redirects_duplicate_members_and_versioned_class_rejected(self):
        member = audit.CLASS_FILES["reward_launcher"]
        cases = (
            ([("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\nClass-Path: PRIVATE_TEST\r\n")],
             "JAR_MANIFEST_CLASSPATH_UNSUPPORTED"),
            ([("META-INF/INDEX.LIST", "JarIndex-Version: 1.0\n\nother.jar\norg/example\n")],
             "JAR_INDEX_CLASSPATH_UNSUPPORTED"),
            ([(member, "1"), (member, "2")], "DUPLICATE_CLASS_IN_JAR"),
            ([(f"META-INF/versions/11/{member}", "1")], "VERSIONED_CORE_CLASS_IN_JAR"),
        )
        for files, reason in cases:
            jar = self.cwd / "test.jar"
            with self.subTest(reason=reason), warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(jar, "w") as archive:
                    for name, data in files:
                        archive.writestr(name, data)
                with self.assertRaisesRegex(audit.FingerprintError, reason):
                    audit.fingerprint_artifact(jar)

    def test_class_cannot_be_a_fifo_or_symlink(self):
        member = self.add_class("classes", "reward_launcher")
        member.unlink()
        os.mkfifo(member)
        with self.assertRaisesRegex(audit.FingerprintError, "ARTIFACT_MISSING_OR_OVERSIZED"):
            audit.fingerprint_artifact(self.cwd / "classes")
        member.unlink()
        member.symlink_to(self.java)
        with self.assertRaisesRegex(audit.FingerprintError, "CLASSPATH_CLASS_SYMLINK_UNSUPPORTED"):
            audit.fingerprint_artifact(self.cwd / "classes")

    def test_invalid_arguments_and_unreadable_jar_stay_redacted(self):
        rc, stdout, err = self.run_cli("--PRIVATE_TEST", self.root)
        self.assertEqual((rc, stdout, err), (2, "", "SYPC_REWARD_PROVENANCE_FAIL:INVALID_ARGUMENTS\n"))
        jar = self.cwd / "PRIVATE_TEST.jar"
        jar.write_bytes(b"malformed")
        self.add_proc(43, ["java", "-cp", jar.name, audit.MAIN_CLASS])
        rc, stdout, err = self.run_cli()
        self.assertEqual((rc, stdout), (2, ""))
        self.assertIn("CLASSPATH_JAR_UNREADABLE", err)

    def manifest_fixture(self):
        self.add_classes(full=True)
        sigma = self.add_sigma()
        empty = self.cwd / "extra"
        empty.mkdir()
        cp = os.pathsep.join(map(str, [self.cwd / "classes", sigma, empty]))
        cpfile = self.root / "build-cp"
        cpfile.write_text(cp + "\n")
        sigma_hash = audit.sha256_file(sigma)
        rc, output, err = self.run_cli("--build-classpath-file", cpfile, "--build-java", self.java,
                                       "--core-commit", "a" * 40, "--expected-sigma-sha256", sigma_hash)
        self.assertEqual((rc, err), (0, ""))
        manifest = self.root / "manifest.json"
        manifest.write_text(output)
        self.add_proc(43, ["java", "-cp", cp, audit.MAIN_CLASS])
        verify = ["--manifest", manifest, "--expected-manifest-sha256", audit.sha256_file(manifest),
                  "--expected-sigma-sha256", sigma_hash]
        return empty, cp, cpfile, verify

    def test_pinned_manifest_validates_order_resources_and_java(self):
        extra, cp, _, verify = self.manifest_fixture()
        rc, stdout, err = self.run_cli(*verify)
        self.assertEqual((rc, err), (0, ""))
        result = json.loads(stdout)
        self.assertTrue(result["artifact_manifest_match"])
        self.assertFalse(result["git_commit_verified"])
        self.assertFalse(result["runtime_class_loading_verified"])
        self.assertEqual(result["manifest_source_commit"], "a" * 40)
        resource = extra / "resource.conf"
        resource.write_text("test-only")
        rc, _, err = self.run_cli(*verify)
        self.assertEqual(rc, 2)
        self.assertIn("CLASSPATH_OR_JAVA_MANIFEST_MISMATCH", err)
        resource.unlink()
        modules = self.jdk / "lib/modules"
        modules.write_bytes(b"changed jdk")
        rc, _, err = self.run_cli(*verify)
        self.assertEqual(rc, 2)
        self.assertIn("CLASSPATH_OR_JAVA_MANIFEST_MISMATCH", err)
        modules.write_bytes(b"lib/modules")
        target = self.proc / "43/cmdline"
        reordered = os.pathsep.join(reversed(cp.split(os.pathsep)))
        target.write_bytes(b"\0".join(map(os.fsencode, ["java", "-cp", reordered, audit.MAIN_CLASS, ""])))
        rc, _, err = self.run_cli(*verify)
        self.assertEqual(rc, 2)
        self.assertIn("CLASSPATH_OR_JAVA_MANIFEST_MISMATCH", err)

    def test_manifest_rejects_unpinned_metadata_and_duplicate_untracked_core(self):
        extra, _, cpfile, verify = self.manifest_fixture()
        manifest = verify[1]
        data = json.loads(manifest.read_text())
        data["core_commit"] = "b" * 40
        manifest.write_text(json.dumps(data))
        rc, _, err = self.run_cli(*verify)
        self.assertEqual(rc, 2)
        self.assertIn("MANIFEST_HASH_MISMATCH", err)
        for directory in (self.cwd / "classes", extra):
            f = directory / "org/ergoplatform/UntrackedConsensus.class"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"untracked class")
        rc, _, err = self.run_cli("--build-classpath-file", cpfile, "--build-java", self.java,
                                  "--core-commit", "a" * 40, *verify[-2:])
        self.assertEqual(rc, 2)
        self.assertIn("DUPLICATE_CORE_CLASS", err)

    def test_full_check_rejects_top_level_symlink(self):
        classes = self.add_classes()
        self.assertTrue(classes)
        link = self.cwd / "PRIVATE_TEST"
        link.symlink_to(self.cwd / "classes")
        self.assertIn("reward_launcher", audit.fingerprint_artifact(link)["class_sha256"])
        with self.assertRaisesRegex(audit.FingerprintError, "CANONICAL_CLASSPATH"):
            audit.fingerprint_artifact(link, full=True)

    def test_manifest_rejects_non_java11_runtime(self):
        _, _, _, verify = self.manifest_fixture()
        (self.jdk / "release").write_bytes(b'JAVA_VERSION="17.0.1"\n')
        rc, _, err = self.run_cli(*verify)
        self.assertEqual(rc, 2)
        self.assertIn("UNSUPPORTED_JAVA_VERSION", err)


if __name__ == "__main__":
    unittest.main()
