"""Static safety tripwire for GitHub Actions workflow changes.

This does NOT parse all of YAML, attest third-party transitive dependencies,
protect GitHub branch rules, or replace a human review. It is deliberately
small and executable with the Python standard library.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ACTION_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")
ON_DANGEROUS_RE = re.compile(r"^\s{2}(?:pull_request_target|workflow_run):\s*(?:#.*)?$")
WRITE_RE = re.compile(r"^\s+[a-zA-Z-]+:\s*write\s*(?:#.*)?$")
ON_INLINE_ELEVATED_RE = re.compile(
    r"(?m)^on:\s*(?:\[[^\]]*\b(?:pull_request_target|workflow_run)\b|"
    r"(?:pull_request_target|workflow_run)\b)"
)
JOB_PERMISSIONS_RE = re.compile(r"^\s+permissions\s*:")
CHECKOUT_RE = re.compile(r"^actions/checkout@", re.IGNORECASE)


def audit_text(text: str, name: str) -> list[str]:
    """Reject obviously unsafe permissions, events and unpinned actions."""
    problems: list[str] = []
    lines = text.splitlines()

    # This is intentionally strict for our current research-only workflows.
    if not re.search(r"(?m)^permissions:\s*$", text):
        problems.append(f"{name}: missing top-level permissions declaration")
    if not re.search(r"(?m)^  contents:\s*read\s*(?:#.*)?$", text):
        problems.append(f"{name}: missing contents: read restriction")
    if any(WRITE_RE.match(line) for line in lines):
        problems.append(f"{name}: write permission is forbidden for research CI")
    if any(ON_DANGEROUS_RE.match(line) for line in lines) or ON_INLINE_ELEVATED_RE.search(text):
        problems.append(f"{name}: dangerous elevated event trigger")
    # No job may override the top-level read-only permission set.
    # In particular, "permissions: write-all" can bypass WRITE_RE.
    if any(JOB_PERMISSIONS_RE.match(line) for line in lines):
        problems.append(f"{name}: job-level permissions override forbidden")
    refs: list[str] = []
    for n, line in enumerate(lines, start=1):
        match = ACTION_RE.match(line)
        if match is None:
            continue
        action = match.group(1)
        if action.startswith("./"):
            continue
        if "@" not in action:
            problems.append(f"{name}:{n}: action has no revision")
            continue
        target, rev = action.rsplit("@", 1)
        if not target or not SHA_RE.fullmatch(rev):
            problems.append(f"{name}:{n}: action not pinned to full immutable SHA")
        refs.append(target)
    if any(CHECKOUT_RE.match(ref + "@") for ref in refs):
        if not re.search(r"(?m)^\s+persist-credentials:\s*false\s*(?:#.*)?$", text):
            problems.append(f"{name}: checkout credentials must not persist")
    return problems


def audit_tree(root: Path) -> list[str]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir() or workflows.is_symlink():
        return ["missing/symlinked .github/workflows directory"]
    files = sorted(list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml")))
    if not files:
        return ["no GitHub Actions workflows found"]
    problems: list[str] = []
    for file in files:
        if file.is_symlink():
            problems.append(f"symlinked workflow: {file.name}")
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            problems.append(f"unreadable workflow {file.name}: {type(exc).__name__}")
            continue
        problems.extend(audit_text(text, file.name))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    problems = audit_tree(args.root)
    for problem in problems:
        print("FAIL:", problem, file=sys.stderr)
    if problems:
        return 1
    print("PASS: workflows have restricted permissions and pinned direct actions")
    print("NOT branch protection, runtime isolation or a supply-chain attestation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
