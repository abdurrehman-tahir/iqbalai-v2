#!/usr/bin/env python3
"""Ensure environment variables consumed by the app are documented.

The browser bundle is particularly vulnerable to missing public values: a
development fallback can otherwise ship as a broken production redirect. This
check compares ``process.env.NEXT_PUBLIC_*`` reads and required Pydantic
``Settings`` fields with keys in the repository's ``.env.example``.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)
PUBLIC_ENV_RE = re.compile(r"process\.env\.(NEXT_PUBLIC_[A-Z0-9_]+)")


def documented_keys() -> set[str]:
    return set(ENV_KEY_RE.findall((REPO_ROOT / ".env.example").read_text(encoding="utf-8")))


def frontend_public_keys() -> set[str]:
    keys: set[str] = set()
    for path in (REPO_ROOT / "frontend" / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        keys.update(PUBLIC_ENV_RE.findall(path.read_text(encoding="utf-8")))
    return keys


def required_settings_keys() -> set[str]:
    """Find Settings annotations with no default, which Pydantic requires from env."""
    tree = ast.parse((REPO_ROOT / "api" / "app" / "config.py").read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Settings":
            continue
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                if statement.value is None and statement.target.id.isupper():
                    keys.add(statement.target.id)
    return keys


def main() -> int:
    required = frontend_public_keys() | required_settings_keys()
    missing = sorted(required - documented_keys())
    if missing:
        print("Undocumented environment variables in .env.example:", file=sys.stderr)
        for key in missing:
            print(f"  - {key}", file=sys.stderr)
        return 1
    print(f"Env parity OK — documented {len(required)} consumed/required variables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
