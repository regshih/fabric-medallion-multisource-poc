#!/usr/bin/env python3
"""Fail closed when likely credentials are present in files or Git history."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
DOCUMENTED_EXAMPLE = (ROOT / "SECURITY.md").resolve()
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".pyc"}
PATTERNS = {
    "azure-storage-key": re.compile(r"AccountKey=[A-Za-z0-9+/]{32,}={0,2}", re.I),
    "sas-signature": re.compile(r"(?:[?&;]|^)sig=[A-Za-z0-9%+/]{20,}", re.I),
    "github-token": re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b"),
    "databricks-token": re.compile(r"\bdapi[a-f0-9]{20,}\b", re.I),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\b"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "literal-secret": re.compile(
        r"(?:client[_-]?secret|password|pwd|access[_-]?token)\s*[:=]\s*[\"'][^<$%{][^\"'\r\n]{7,}[\"']",
        re.I,
    ),
    "literal-bearer": re.compile(r"Authorization\s*[:=]\s*[\"']Bearer\s+[A-Za-z0-9._~+/-]{16,}", re.I),
}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def scan_text(label: str, text: str) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(f"{label}:{line_number}: {name}")
    return findings


def working_tree_files() -> list[Path]:
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
    return [ROOT / name for name in names if name]


def scan_working_tree() -> list[str]:
    findings: list[str] = []
    for path in working_tree_files():
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.resolve() in {SELF, DOCUMENTED_EXAMPLE}:
            continue
        try:
            findings.extend(scan_text(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return findings


def scan_history() -> list[str]:
    commits = [value for value in git("rev-list", "--all").splitlines() if value]
    findings: list[str] = []
    for commit in commits:
        for name in git("ls-tree", "-r", "--name-only", commit).splitlines():
            path = ROOT / name
            if path.suffix.lower() in SKIP_SUFFIXES or name in {"tools/security_scan.py", "SECURITY.md"}:
                continue
            result = subprocess.run(
                ["git", "-C", str(ROOT), "show", f"{commit}:{name}"], capture_output=True
            )
            if result.returncode or b"\0" in result.stdout[:8192]:
                continue
            text = result.stdout.decode("utf-8", errors="replace")
            findings.extend(scan_text(f"{commit[:12]}:{name}", text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-tree", action="store_true")
    parser.add_argument("--git-history", action="store_true")
    args = parser.parse_args()
    if not args.working_tree and not args.git_history:
        parser.error("select --working-tree and/or --git-history")

    findings: list[str] = []
    if args.working_tree:
        findings.extend(scan_working_tree())
    if args.git_history:
        findings.extend(scan_history())
    if findings:
        print("SECURITY SCAN FAILED")
        print("\n".join(sorted(set(findings))))
        return 1
    print("SECURITY SCAN PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
