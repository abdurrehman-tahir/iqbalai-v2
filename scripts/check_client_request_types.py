#!/usr/bin/env python3
"""
check_client_request_types.py — frontend API client request-body type gate.

Fails if any api client helper in frontend/src/lib/api types a write request body
(data/payload/body param) as an inline object literal instead of a generated OpenAPI
*Create / *Update / *Request schema (AMENDMENTS A-002, frontend-master Rule 9).

Pure text scan — no Node, no app import.

Usage:
  python scripts/check_client_request_types.py
  python scripts/check_client_request_types.py <files...>

Exit codes:
  0  No inline object-literal write-body types in the api client.
  1  Inline object literal body types found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATHS = [
    REPO_ROOT / "frontend" / "src" / "lib" / "api" / "index.ts",
    REPO_ROOT / "frontend" / "src" / "lib" / "api" / "api.ts",
]

BODY_PARAM_NAMES = ("data", "payload", "body")

_INLINE_BODY_TYPE = re.compile(
    rf"\b({'|'.join(BODY_PARAM_NAMES)})\s*:\s*\{{",
    re.MULTILINE,
)


def _line_number(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _strip_line_comment(line: str) -> str:
    pos = line.find("//")
    return line if pos == -1 else line[:pos]


def check_file(file_path: Path) -> list[str]:
    if not file_path.exists():
        return []

    try:
        rel = file_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(file_path)

    source = file_path.read_text(encoding="utf-8")
    violations: list[str] = []

    for match in _INLINE_BODY_TYPE.finditer(source):
        line = _line_number(source, match.start())
        line_text = _strip_line_comment(source.splitlines()[line - 1])
        if not line_text.strip():
            continue
        param = match.group(1)
        violations.append(
            f"{rel}:{line}: `{param}` uses an inline object literal — "
            f"use a generated *Create/*Update/*Request type from schema.d.ts."
        )

    return violations


def _iter_targets(argv: list[str]) -> list[Path]:
    if len(argv) > 1:
        return [Path(t).resolve() for t in argv[1:]]
    return [p for p in DEFAULT_PATHS if p.exists()]


def main(argv: list[str]) -> int:
    targets = _iter_targets(argv)
    if not targets:
        print("No api client files to check.", file=sys.stderr)
        return 1

    all_violations: list[str] = []
    for path in targets:
        if path.suffix in {".ts", ".tsx"}:
            all_violations.extend(check_file(path))

    if all_violations:
        print(
            "\n❌ Frontend API client request-body type violations:\n",
            file=sys.stderr,
        )
        for violation in all_violations:
            print(f"  • {violation}", file=sys.stderr)
        print(
            "\nType write request bodies from generated OpenAPI schemas "
            "(frontend-master Rule 9; AMENDMENTS A-002).",
            file=sys.stderr,
        )
        return 1
    print("✓ API client write-body params use generated schema types.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
