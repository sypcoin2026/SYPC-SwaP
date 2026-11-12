"""Offline AST policy gate: SYPC Swap simulation modules must remain inert.

This is a lightweight tripwire, NOT a sandbox, proof of safety or malware scan.
Reviewers must inspect every change manually, including non-Python files.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

# No network, filesystem, subprocess, native libraries or key material in
# the experimental sypc_swap package without a separately reviewed change.
FORBIDDEN_IMPORTS = frozenset({
    "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "requests",
    "aiohttp", "websockets", "websocket", "subprocess", "os", "pathlib",
    "shutil", "tempfile", "ctypes", "importlib", "pickle", "shelve",
    "keyring", "web3", "bitcoin", "paramiko", "pexpect", "multiprocessing",
})
FORBIDDEN_CALLS = frozenset({
    "open", "exec", "eval", "compile", "input", "__import__", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir",
})


def scan_source(text: str, filename: str) -> list[str]:
    """Detect ordinary accidental boundary crossings, not arbitrary bypasses."""
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError as exc:
        return [f"{filename}:{exc.lineno}: cannot parse Python source"]
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in FORBIDDEN_IMPORTS:
                    issues.append(f"{filename}:{node.lineno}: forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if node.level or module in FORBIDDEN_IMPORTS:
                issues.append(f"{filename}:{node.lineno}: forbidden import from {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                issues.append(f"{filename}:{node.lineno}: forbidden dynamic/I-O call {node.func.id}")
    return sorted(issues)


def scan_tree(root: Path) -> list[str]:
    """Scan only our runtime package, never the unmodified upstream reference."""
    package = root / "sypc_swap"
    if not package.is_dir() or package.is_symlink():
        return [f"missing or symlinked runtime package: {package}"]
    modules = sorted(package.rglob("*.py"))
    if not modules:
        return [f"no Python sources found: {package}"]
    problems = []
    for module in modules:
        if module.is_symlink():
            problems.append(f"symlinked runtime file: {module}")
            continue
        try:
            content = module.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            problems.append(f"unreadable source {module}: {type(exc).__name__}")
            continue
        problems.extend(scan_source(content, str(module.relative_to(root))))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    issues = scan_tree(args.root)
    for issue in issues:
        print("FAIL:", issue, file=sys.stderr)
    if issues:
        return 1
    print("PASS: offline Python boundary AST tripwire (not a security audit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
