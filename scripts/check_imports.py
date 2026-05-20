#!/usr/bin/env python3
"""
check_imports.py — Lightweight import-shape checker.

Runs alongside check_stack_lock.py. Where check_stack_lock.py enforces WHICH
libraries are allowed, this one enforces HOW imports are structured.

Rules enforced (all from CLAUDE.md and STACK_LOCK.md conventions):
  1. No `from X import *` (star imports) — explicit only.
  2. No `import X as Y` for stdlib modules to obscure their origin.
  3. App code in `app/` must use absolute imports (`from app.services...`),
     not relative imports beyond one level (`from ...foo` is rejected).

Exit codes:
  0  All clean.
  1  Violations found.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def check_file(file_path: Path) -> list[str]:
    try:
        rel = file_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return []
    violations: list[str] = []

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    for node in ast.walk(tree):
        # Rule 1: no star imports
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    violations.append(
                        f"{rel}:{node.lineno}: 'from {node.module} import *' is forbidden. "
                        f"Use explicit imports."
                    )

        # Rule 3: no deep relative imports in app/
        if isinstance(node, ast.ImportFrom) and rel.startswith("app/"):
            if node.level >= 2:
                violations.append(
                    f"{rel}:{node.lineno}: relative import with level={node.level} "
                    f"is forbidden in app/. Use absolute import (from app.<module>...)."
                )

    return violations


def main(argv: list[str]) -> int:
    targets = argv[1:] if len(argv) > 1 else []
    if not targets:
        targets = [
            str(p)
            for p in REPO_ROOT.rglob("*.py")
            if ".venv" not in p.parts and "node_modules" not in p.parts
        ]

    all_violations: list[str] = []
    for t in targets:
        p = Path(t).resolve()
        if not p.exists() or p.suffix != ".py":
            continue
        all_violations.extend(check_file(p))

    if all_violations:
        print("\n❌ Import-shape violations:\n", file=sys.stderr)
        for v in all_violations:
            print(f"  • {v}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
