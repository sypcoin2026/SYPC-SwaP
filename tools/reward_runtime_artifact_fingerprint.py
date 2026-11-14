#!/usr/bin/env python3
"""Read-only inventory and byte comparison for a local Reward classpath."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

SCHEMA = "SYPC_REWARD_RUNTIME_ARTIFACT_READONLY_V2"
MANIFEST_SCHEMA = "SYPC_REWARD_BUILD_MANIFEST_V1"
MAIN_CLASS = "org.ergoplatform.sypcoin.SypRewardTestnetLauncher"
SIGMA_JAR = "sigma-state_2.12-6.0.7.jar"
SIGMA_SHA256 = "390bc91cb6201c26ae5309fd25c96f3e427343ed9b75968a2db96f365ca7d31b"
LAUNCHER = MAIN_CLASS.replace(".", "/")
SYPC = "org/ergoplatform/sypcoin/"
CLASS_FILES = {
    "reward_launcher": LAUNCHER + ".class",
    "reward_launcher_module": LAUNCHER + "$.class",
    "reward_launcher_session": LAUNCHER + "$Session.class",
    "reward_launcher_session_module": LAUNCHER + "$Session$.class",
    "native_transaction": "org/ergoplatform/modifiers/mempool/ErgoTransaction.class",
    "native_state": "org/ergoplatform/nodeView/state/ErgoState.class",
    "utxo_state": "org/ergoplatform/nodeView/state/UtxoState.class",
    "native_interpreter": "org/ergoplatform/wallet/interpreter/ErgoInterpreter.class",
    "sigma_tree": "sigma/ast/ErgoTree.class",
    "sigma_tree_serializer": "sigma/serialization/ErgoTreeSerializer.class",
    "sigma_interpreter": "sigmastate/interpreter/Interpreter.class",
    "headers_processor": "org/ergoplatform/nodeView/history/storage/modifierprocessors/HeadersProcessor.class",
    "reward_maturity": SYPC + "SypRewardMaturity$.class",
    "native_admission": SYPC + "SypV30NativeAdmission$.class",
    "native_emission": SYPC + "SypV31NativeEmission$.class",
}
for label, name in (
    ("node_app", "org/ergoplatform/ErgoApp"),
    ("network_controller", "scorex/core/network/NetworkController"),
    ("reward_config", SYPC + "SypRewardTestnetConfig"),
    ("consensus_permit", SYPC + "SypV41PrivateConsensusPermit"),
    ("native_profile", SYPC + "SypV30NativeProfile"),
):
    CLASS_FILES[label] = name + ".class"
    CLASS_FILES[label + "_module"] = name + "$.class"

CLASS_LABELS = {path: label for label, path in CLASS_FILES.items()}
LAUNCHER_LABELS = frozenset(label for label in CLASS_FILES if label.startswith("reward_launcher"))
ENTRY_POINT_LABELS = frozenset({"reward_launcher", "reward_launcher_module"})
SIGMA_LABELS = frozenset(label for label in CLASS_FILES if label.startswith("sigma_"))
CORE_PACKAGES = ("org/ergoplatform/", "scorex/core/", "sigma/", "sigmastate/")
RUNTIME_FILES = ("bin/java", "lib/server/libjvm.so", "lib/modules", "release")
MAX_CMDLINE = 256 * 1024
MAX_ENVIRON = 1024 * 1024
MAX_CLASSPATH_ITEMS = 512
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_CLASS_BYTES = 4 * 1024 * 1024
MAX_DIRECTORY_ITEMS = 25_000
MAX_DIRECTORY_DEPTH = 32
MAX_DIRECTORY_BYTES = 512 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
CP_OPTIONS = ("-cp", "-classpath", "--class-path")
MODULE_OPTIONS_WITH_VALUE = {
    "-p", "--module-path", "--upgrade-module-path", "--patch-module",
    "--add-modules", "--limit-modules", "--add-reads", "--add-exports", "--add-opens",
}
LOADER_PROPERTIES = (
    "-Djava.system.class.loader", "-Djava.class.path", "-Djava.ext.dirs",
    "-Djava.endorsed.dirs", "-Djava.home", "-Djava.library.path",
    "-Djdk.module.", "-Djdk.util.jar.", "-Dsun.boot.",
)
JAVA_ENV_OPTIONS = {
    b"JAVA_TOOL_OPTIONS", b"JDK_JAVA_OPTIONS", b"_JAVA_OPTIONS",
    b"LD_PRELOAD", b"LD_AUDIT", b"LD_LIBRARY_PATH",
}


class FingerprintError(ValueError):
    pass


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise FingerprintError("INVALID_ARGUMENTS")


def read_bounded(path: Path, limit: int, code: str) -> bytes:
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise FingerprintError("EVIDENCE_UNREADABLE")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise FingerprintError(code)
    return data


def read_cmdline(proc_pid: Path) -> list[str]:
    raw = read_bounded(proc_pid / "cmdline", MAX_CMDLINE, "PROCESS_CMDLINE_TOO_LARGE")
    if raw and not raw.endswith(b"\0"):
        raise FingerprintError("PROCESS_CMDLINE_INCOMPLETE")
    return [os.fsdecode(arg) for arg in raw[:-1].split(b"\0")] if raw else []


def parse_explicit_classpath(argv: list[str]) -> str | None:
    if not argv or Path(argv[0]).name != "java":
        return None
    cp = None
    ambiguous = False
    options = iter(argv[1:])
    for arg in options:
        if arg in CP_OPTIONS or arg.startswith("--class-path="):
            value = next(options, None) if arg in CP_OPTIONS else arg.split("=", 1)[1]
            ambiguous |= cp is not None
            cp = value
        elif arg == MAIN_CLASS:
            if ambiguous:
                raise FingerprintError("UNSUPPORTED_JAVA_LAUNCH_OPTIONS")
            if not cp:
                raise FingerprintError("MATCHED_LAUNCHER_WITHOUT_EXPLICIT_CLASSPATH")
            return cp
        elif arg in ("-jar", "-m", "--module", "--") or arg.startswith("--module="):
            return None
        elif arg in MODULE_OPTIONS_WITH_VALUE:
            next(options, None)
            ambiguous = True
        elif not arg.startswith(("-", "@")):
            return None
        elif not (
            (arg.startswith("-D") and not arg.startswith(LOADER_PROPERTIES))
            or re.fullmatch(r"-Xm[sx]\d+[kKmMgG]?", arg)
            or arg == "-Xshare:off"
            or re.fullmatch(r"-Xlog:class\+load=info(?::file=[^:]+)?", arg)
        ):
            # A JVM flag outside the supported launch form can change code lookup.
            ambiguous = True
    return None


def expand_classpath(value: str, cwd: Path | None) -> list[Path]:
    entries = value.split(os.pathsep)
    if len(entries) > MAX_CLASSPATH_ITEMS:
        raise FingerprintError("CLASSPATH_TOO_LONG")
    if any("*" in entry for entry in entries):
        raise FingerprintError("CLASSPATH_WILDCARD_UNSUPPORTED")
    paths = list(map(Path, entries))
    if cwd is None:
        if any(not path.is_absolute() for path in paths):
            raise FingerprintError("MANIFEST_REQUIRES_ABSOLUTE_CLASSPATH")
        return paths
    return [cwd / path for path in paths]


def stamp(info: os.stat_result) -> tuple:
    return (
        info.st_dev, info.st_ino, info.st_mode, info.st_size,
        info.st_mtime_ns, info.st_ctime_ns,
    )


@contextmanager
def regular_file(path: Path, limit: int, size_code: str):
    # NONBLOCK keeps replacement with a FIFO from blocking the inventory.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise FingerprintError(size_code)
        yield stream, before.st_size
        if stamp(before) != stamp(os.fstat(stream.fileno())) or stamp(before) != stamp(path.stat()):
            raise FingerprintError("ARTIFACT_CHANGED_DURING_CAPTURE")


def hash_stream(stream, limit: int, size_code: str) -> str:
    digest = hashlib.sha256()
    remaining = limit
    while chunk := stream.read(min(remaining + 1, 1 << 20)):
        remaining -= len(chunk)
        if remaining < 0:
            raise FingerprintError(size_code)
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path, limit: int = MAX_ARTIFACT_BYTES) -> str:
    with regular_file(path, limit, "ARTIFACT_MISSING_OR_OVERSIZED") as (stream, length):
        return hash_stream(stream, length, "ARTIFACT_CHANGED_DURING_CAPTURE")


def class_directory_digest(path: Path) -> tuple[str, set[str], dict[str, str]]:
    """Hash directories and regular files in sorted relative pathname order."""
    digest = hashlib.sha256()
    remaining_items = MAX_DIRECTORY_ITEMS
    remaining_bytes = MAX_DIRECTORY_BYTES
    code = set()
    classes = {}

    def visit(directory: Path, depth: int):
        nonlocal remaining_items, remaining_bytes
        if depth > MAX_DIRECTORY_DEPTH:
            raise FingerprintError("CLASSPATH_DIRECTORY_TOO_DEEP")
        before = stamp(directory.lstat())
        children = []
        for child in directory.iterdir():
            remaining_items -= 1
            if remaining_items < 0:
                raise FingerprintError("CLASSPATH_DIRECTORY_TOO_LARGE")
            children.append(child)
        for child in sorted(children, key=lambda file: os.fsencode(file.name)):
            info = child.lstat()
            name = os.fsencode(child.relative_to(path))
            if stat.S_ISDIR(info.st_mode):
                digest.update(b"D" + name + b"\0")
                visit(child, depth + 1)
            elif stat.S_ISREG(info.st_mode):
                if info.st_size > remaining_bytes:
                    raise FingerprintError("CLASSPATH_DIRECTORY_TOO_LARGE")
                relative = child.relative_to(path).as_posix()
                label = CLASS_LABELS.get(relative)
                limit = MAX_CLASS_BYTES if label else MAX_ARTIFACT_BYTES
                file_digest = sha256_file(child, min(remaining_bytes, limit))
                remaining_bytes -= info.st_size
                digest.update(b"F" + name + b"\0" + bytes.fromhex(file_digest))
                if label:
                    classes[label] = file_digest
                if relative.endswith(".class") and relative.startswith(CORE_PACKAGES):
                    code.add(relative)
            else:
                raise FingerprintError("MANIFEST_UNSUPPORTED_DIRECTORY_MEMBER")
            if stamp(info) != stamp(child.lstat()):
                raise FingerprintError("ARTIFACT_CHANGED_DURING_CAPTURE")
        if before != stamp(directory.lstat()):
            raise FingerprintError("ARTIFACT_CHANGED_DURING_CAPTURE")

    visit(path, 0)
    return digest.hexdigest(), code, classes


def read_jar_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_CLASS_BYTES:
        raise FingerprintError("JAR_MEMBER_TOO_LARGE")
    with archive.open(info) as stream:
        data = stream.read(MAX_CLASS_BYTES + 1)
    if len(data) != info.file_size:
        raise FingerprintError("JAR_MEMBER_SIZE_MISMATCH")
    return data


def jar_classes(archive: zipfile.ZipFile, jar_name: str, *, full: bool) -> tuple[dict, set[str]]:
    manifest = "META-INF/MANIFEST.MF"
    jar_index = "META-INF/INDEX.LIST"
    if len(archive.infolist()) > 100_000:
        raise FingerprintError("CLASSPATH_JAR_TOO_MANY_ENTRIES")
    members = {}
    code = set()
    for info in archive.infolist():
        name = info.filename
        if name.startswith("META-INF/versions/"):
            logical = name.split("/", 3)[-1]
            if logical in CLASS_LABELS or (full and logical.endswith(".class")
                                            and logical.startswith(CORE_PACKAGES)):
                raise FingerprintError("VERSIONED_CORE_CLASS_IN_JAR")
        if full and name.endswith(".class"):
            if name in code:
                raise FingerprintError("DUPLICATE_CLASS_IN_JAR")
            code.add(name)
        if name in CLASS_LABELS or name in (manifest, jar_index):
            if name in members:
                raise FingerprintError("DUPLICATE_CLASS_IN_JAR" if name in CLASS_LABELS
                                       else "DUPLICATE_JAR_METADATA")
            members[name] = info
    if manifest in members:
        lines = read_jar_member(archive, members[manifest]).splitlines()
        if any(line.lower().startswith(b"class-path:") for line in lines):
            raise FingerprintError("JAR_MANIFEST_CLASSPATH_UNSUPPORTED")
    if jar_index in members:
        index = read_jar_member(archive, members[jar_index]).splitlines()
        jar = os.fsencode(jar_name)
        if (index[:3] != [b"JarIndex-Version: 1.0", b"", jar]
                or any(line.endswith(b".jar") for line in index[3:])):
            raise FingerprintError("JAR_INDEX_CLASSPATH_UNSUPPORTED")
    classes = {
        CLASS_LABELS[name]: hashlib.sha256(read_jar_member(archive, member)).hexdigest()
        for name, member in members.items() if name in CLASS_LABELS
    }
    return classes, {name for name in code if name.startswith(CORE_PACKAGES)}


def class_file(directory: Path, relative: str) -> Path:
    for part in relative.split("/"):
        directory = directory / part
        if stat.S_ISLNK(directory.lstat().st_mode):
            raise FingerprintError("CLASSPATH_CLASS_SYMLINK_UNSUPPORTED")
    return directory


def fingerprint_directory(path: Path, *, full: bool) -> dict:
    if full:
        digest, code, classes = class_directory_digest(path)
        return {"type": "class_directory", "class_sha256": classes,
                "sha256": digest, "core_classes": code}
    classes = {}
    for label, relative in CLASS_FILES.items():
        try:
            classes[label] = sha256_file(class_file(path, relative), MAX_CLASS_BYTES)
        except FileNotFoundError:
            continue
    return {"type": "class_directory", "class_sha256": classes}


def fingerprint_artifact(path: Path, *, full: bool = False) -> dict:
    try:
        before = path.stat()
    except FileNotFoundError:
        return {"type": "missing", "class_sha256": {}}
    resolved = path.resolve(strict=True)
    if full and resolved != path:
        raise FingerprintError("MANIFEST_REQUIRES_CANONICAL_CLASSPATH")
    if stat.S_ISDIR(before.st_mode):
        item = fingerprint_directory(resolved, full=full)
    elif stat.S_ISREG(before.st_mode) and path.suffix.lower() == ".jar":
        is_sigma = path.name == SIGMA_JAR
        with regular_file(resolved, MAX_ARTIFACT_BYTES, "JAR_TOO_LARGE") as (stream, length):
            try:
                with zipfile.ZipFile(stream) as archive:
                    classes, code = jar_classes(archive, path.name, full=full)
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                raise FingerprintError("CLASSPATH_JAR_UNREADABLE") from exc
            item = {"type": "jar", "class_sha256": classes, "is_sigma": is_sigma}
            if full:
                item["core_classes"] = code
            if full or is_sigma or LAUNCHER_LABELS.intersection(classes):
                stream.seek(0)
                item["sha256"] = hash_stream(stream, length, "ARTIFACT_CHANGED_DURING_CAPTURE")
    else:
        raise FingerprintError("CLASSPATH_ENTRY_UNSUPPORTED")
    if resolved != path.resolve(strict=True) or stamp(before) != stamp(path.stat()):
        raise FingerprintError("ARTIFACT_CHANGED_DURING_CAPTURE")
    return item


def snapshot(proc_pid: Path, argv: list[str]) -> tuple:
    raw = read_bounded(proc_pid / "stat", 4096, "PROCESS_STAT_TOO_LARGE")
    fields = raw.rsplit(b")", 1)[-1].split()
    if len(fields) < 20 or not fields[19].isdigit():
        raise FingerprintError("INVALID_PROCESS_START_TIME")
    if read_cmdline(proc_pid) != argv:
        raise FingerprintError("PROCESS_CHANGED_DURING_CAPTURE")
    return (
        proc_pid.stat().st_ino, fields[19],
        inode(proc_pid / "root"), inode(proc_pid / "ns/mnt"),
        stamp((proc_pid / "exe").stat()), inode(proc_pid / "cwd"),
    )


def inode(path: Path) -> tuple[int, int]:
    info = path.stat()
    return info.st_dev, info.st_ino


def select_process(*, pid: int | None = None, proc_root: Path = Path("/proc")) -> tuple:
    candidates = (proc_root / str(pid),) if pid is not None else proc_root.iterdir()
    matches = []
    for proc_pid in candidates:
        if not proc_pid.name.isascii() or not proc_pid.name.isdecimal():
            continue
        try:
            if read_bounded(proc_pid / "comm", 64, "PROCESS_COMM_TOO_LARGE").strip() != b"java":
                continue
            argv = read_cmdline(proc_pid)
        except FileNotFoundError:
            if pid is not None:
                raise FingerprintError("PROCESS_DISAPPEARED") from None
            continue
        cp = parse_explicit_classpath(argv)
        if cp is not None:
            matches.append((proc_pid, cp, argv))
    if len(matches) != 1:
        raise FingerprintError("EXPECTED_EXACTLY_ONE_REWARD_LAUNCHER")
    return matches[0]


def capture_classpath(entries: list[Path], *, full: bool) -> list[dict]:
    return [
        {"classpath_index": index, **fingerprint_artifact(path, full=full)}
        for index, path in enumerate(entries)
    ]


def java_runtime(java: Path) -> dict:
    executable = java.resolve(strict=True)
    if executable.name != "java" or executable.parent.name != "bin":
        raise FingerprintError("PROCESS_EXECUTABLE_UNSUPPORTED")
    runtime = {part: sha256_file(executable.parent.parent / part, 256 * 1024 * 1024)
               for part in RUNTIME_FILES}
    release = read_bounded(executable.parent.parent / "release", 16_384, "INVALID_JAVA_RELEASE")
    if not re.search(rb'^JAVA_VERSION="11(?:\.[0-9]+)*"\r?$', release, re.MULTILINE):
        raise FingerprintError("UNSUPPORTED_JAVA_VERSION")
    if hashlib.sha256(release).hexdigest() != runtime["release"]:
        raise FingerprintError("ARTIFACT_CHANGED_DURING_CAPTURE")
    return runtime


def inspect_process(*, pid: int | None = None, proc_root: Path = Path("/proc"),
                    full: bool = False) -> tuple[list[dict], dict | None]:
    proc_pid, cp, argv = select_process(pid=pid, proc_root=proc_root)
    before = snapshot(proc_pid, argv)
    if before[2] != inode(proc_root / "self/root"):
        raise FingerprintError("PROCESS_ROOT_MISMATCH")
    if before[3] != inode(proc_root / "self/ns/mnt"):
        raise FingerprintError("PROCESS_MOUNT_NAMESPACE_MISMATCH")
    executable = Path(os.readlink(proc_pid / "exe"))
    if executable.name != "java" or stamp(executable.stat()) != before[4]:
        raise FingerprintError("PROCESS_EXECUTABLE_UNSUPPORTED")
    environ = read_bounded(proc_pid / "environ", MAX_ENVIRON, "PROCESS_ENVIRON_TOO_LARGE")
    if any(name in JAVA_ENV_OPTIONS and value
           for name, _, value in (env.partition(b"=") for env in environ.split(b"\0"))):
        raise FingerprintError("UNSUPPORTED_JAVA_LAUNCH_ENVIRONMENT")
    cwd = None if full else Path(os.readlink(proc_pid / "cwd"))
    entries = capture_classpath(expand_classpath(cp, cwd), full=full)
    runtime = java_runtime(executable) if full else None
    if before != snapshot(proc_pid, argv) or environ != read_bounded(
            proc_pid / "environ", MAX_ENVIRON, "PROCESS_ENVIRON_TOO_LARGE"):
        raise FingerprintError("PROCESS_CHANGED_DURING_CAPTURE")
    return entries, runtime


def summarize(entries: list[dict]) -> dict:
    locations = {label: [] for label in CLASS_FILES}
    for record in entries:
        for label, digest in record["class_sha256"].items():
            locations[label].append({"classpath_index": record["classpath_index"], "sha256": digest})
    launchers = [
        {
            "classpath_index": item["classpath_index"], "type": item["type"],
            "jar_sha256": item.get("sha256") if item["type"] == "jar" else None,
            "class_sha256": {k: v for k, v in item["class_sha256"].items() if k in LAUNCHER_LABELS},
        }
        for item in entries if LAUNCHER_LABELS.intersection(item["class_sha256"])
    ]
    counts = {
        "classpath_entries": len(entries),
        "classpath_directories": sum(e["type"] == "class_directory" for e in entries),
        "classpath_jar_files": sum(e["type"] == "jar" for e in entries),
        "classpath_missing_entries": sum(e["type"] == "missing" for e in entries),
        "launcher_candidates": len(launchers),
        "sigma607_candidates": sum(e.get("is_sigma", False) for e in entries),
    }
    return {
        "counts": counts, "launcher_artifacts": launchers, "tracked_classes": locations,
        "distinct_launcher_fingerprints": len({
            tuple(sorted(item["class_sha256"].items())) for item in launchers
        }),
        "sigma607_sha256": [item["sha256"] for item in entries if item.get("is_sigma")],
        "sigma607_indices": [item["classpath_index"] for item in entries if item.get("is_sigma")],
    }


def require_consistent(summary: dict, expected_sigma: str, *, full: bool):
    counts = summary["counts"]
    if counts["classpath_missing_entries"]:
        raise FingerprintError("CLASSPATH_ENTRY_MISSING")
    if counts["launcher_candidates"] > 1:
        raise FingerprintError("MULTIPLE_LAUNCHER_CODE_ARTIFACTS")
    classes = summary["tracked_classes"]
    required = CLASS_FILES if full else ENTRY_POINT_LABELS
    if any(not classes[label] for label in required):
        raise FingerprintError("REQUIRED_CLASS_MISSING")
    if any(len(locations) > 1 for locations in classes.values()):
        raise FingerprintError("DUPLICATE_TRACKED_CLASS")
    if counts["sigma607_candidates"] != 1:
        raise FingerprintError("SIGMA607_JAR_NOT_UNIQUE")
    if summary["sigma607_sha256"][0] != expected_sigma:
        raise FingerprintError("SIGMA607_HASH_MISMATCH")
    sigma_index = summary["sigma607_indices"][0]
    if any(locations and locations[0]["classpath_index"] != sigma_index
           for label, locations in classes.items() if label in SIGMA_LABELS):
        raise FingerprintError("SIGMA_CLASS_OUTSIDE_PINNED_JAR")


def make_manifest(entries: list[dict], runtime: dict, commit: str) -> dict:
    classes = set()
    for record in entries:
        if classes.intersection(record["core_classes"]):
            raise FingerprintError("DUPLICATE_CORE_CLASS")
        classes.update(record["core_classes"])
    return {
        "schema": MANIFEST_SCHEMA, "core_commit": commit, "java_runtime": runtime,
        "entries": [{"type": item["type"], "sha256": item["sha256"]} for item in entries],
    }


def read_manifest(path: Path, expected_hash: str) -> dict:
    with regular_file(path, MAX_ENVIRON, "INVALID_MANIFEST_SIZE") as (stream, length):
        data = stream.read(length + 1)
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise FingerprintError("MANIFEST_HASH_MISMATCH")
    try:
        manifest = json.loads(data)
    except (ValueError, RecursionError) as exc:
        raise FingerprintError("INVALID_MANIFEST") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise FingerprintError("INVALID_MANIFEST")
    commit = manifest.get("core_commit")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise FingerprintError("INVALID_MANIFEST_COMMIT")
    return manifest


def main() -> int:
    parser = PrivateArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, help="Known local Reward Java PID")
    parser.add_argument("--expected-sigma-sha256", default=SIGMA_SHA256)
    parser.add_argument("--manifest", type=Path, help="Manifest from an independently verified build")
    parser.add_argument("--expected-manifest-sha256", help="Trusted SHA-256 of the manifest bytes")
    parser.add_argument("--build-classpath-file", type=Path,
                        help="Read an isolated build's explicit classpath and emit a manifest")
    parser.add_argument("--build-java", type=Path, help="Java executable used by the isolated build")
    parser.add_argument("--core-commit", help="Git commit recorded by the build producing the manifest")
    try:
        args = parser.parse_args()
        if args.pid is not None and args.pid <= 0:
            raise FingerprintError("INVALID_PID")
        if not HEX64.fullmatch(args.expected_sigma_sha256):
            raise FingerprintError("INVALID_EXPECTED_SIGMA_HASH")
        expected_manifest = None
        if args.manifest or args.expected_manifest_sha256:
            if not args.manifest or not HEX64.fullmatch(args.expected_manifest_sha256 or ""):
                raise FingerprintError("REQUIRE_TRUSTED_MANIFEST_HASH")
            expected_manifest = read_manifest(args.manifest, args.expected_manifest_sha256)
        full = bool(args.build_classpath_file or expected_manifest)
        if args.build_classpath_file:
            if (args.pid is not None or expected_manifest or args.build_java is None
                    or not COMMIT.fullmatch(args.core_commit or "")):
                raise FingerprintError("INVALID_MANIFEST_BUILD_ARGUMENTS")
            raw = read_bounded(args.build_classpath_file, MAX_CMDLINE, "CLASSPATH_TOO_LONG")
            entries = capture_classpath(expand_classpath(os.fsdecode(raw.rstrip(b"\n")), None),
                                        full=True)
            runtime = java_runtime(args.build_java)
        else:
            if args.core_commit is not None or args.build_java is not None:
                raise FingerprintError("INVALID_MANIFEST_BUILD_ARGUMENTS")
            entries, runtime = inspect_process(pid=args.pid, full=full)

        summary = summarize(entries)
        try:
            require_consistent(summary, args.expected_sigma_sha256, full=full)
        except FingerprintError:
            print("SYPC_REWARD_SAFE_COUNTS:" + json.dumps(summary["counts"], sort_keys=True),
                  file=sys.stderr)
            print("SYPC_REWARD_DISK_EVIDENCE:" + json.dumps(summary, sort_keys=True),
                  file=sys.stderr)
            raise

        if args.build_classpath_file:
            result = make_manifest(entries, runtime, args.core_commit)
        else:
            if expected_manifest:
                actual = make_manifest(entries, runtime, expected_manifest["core_commit"])
                if actual != expected_manifest:
                    raise FingerprintError("CLASSPATH_OR_JAVA_MANIFEST_MISMATCH")
            result = {
                "schema": SCHEMA, **summary,
                "artifact_manifest_match": expected_manifest is not None,
                "manifest_source_commit": expected_manifest["core_commit"] if expected_manifest else None,
                "git_commit_verified": False,
                "runtime_class_loading_verified": False,
                "chain_or_consensus_verified": False,
            }
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except FingerprintError as exc:
        code = str(exc)
    except (OSError, ValueError, OverflowError, RecursionError):
        code = "EVIDENCE_UNREADABLE"
    print("SYPC_REWARD_PROVENANCE_FAIL:" + code, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
