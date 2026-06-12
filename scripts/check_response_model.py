#!/usr/bin/env python3
"""
check_response_model.py — FastAPI route contract gate (T-225).

Enforces the CLAUDE.md API rule: every FastAPI route MUST declare both
`response_model=` and `operation_id=` on its decorator. Without `response_model`
the OpenAPI advertises a bare object and the generated frontend client (A-002)
loses its typed `data` shape; without a stable `operation_id` the generated
client method names churn on every refactor.

This is an AST check (no app import, no DB) so it runs fast in pre-commit and CI.
It inspects only decorators in a function's decorator list, so non-route calls
like `client.get(...)` are never flagged.

Usage:
  python scripts/check_response_model.py            # scan api/app
  python scripts/check_response_model.py <files...>  # scan specific files

Exit codes:
  0  All routes declare response_model + operation_id.
  1  Violations found.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "api" / "app"

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
REQUIRED_KWARGS = ("response_model", "operation_id")


def _is_route_decorator(decorator: ast.expr) -> bool:
    """True if the decorator is a `<router>.<http_method>(...)` call."""
    return (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr in HTTP_METHODS
    )


def check_file(file_path: Path) -> list[str]:
    try:
        rel = file_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(file_path)

    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not _is_route_decorator(decorator):
                continue
            assert isinstance(decorator, ast.Call)  # narrowed by _is_route_decorator
            kwargs = {kw.arg for kw in decorator.keywords if kw.arg is not None}
            missing = [k for k in REQUIRED_KWARGS if k not in kwargs]
            if missing:
                method = decorator.func.attr  # type: ignore[attr-defined]
                violations.append(
                    f"{rel}:{decorator.lineno}: route "
                    f"`{method.upper()}` on `{node.name}` is missing "
                    f"{', '.join(missing)}."
                )
    return violations


def _iter_targets(argv: list[str]) -> list[Path]:
    if len(argv) > 1:
        return [Path(t).resolve() for t in argv[1:]]
    return [
        p
        for p in DEFAULT_ROOT.rglob("*.py")
        if ".venv" not in p.parts and "__pycache__" not in p.parts
    ]


def main(argv: list[str]) -> int:
    all_violations: list[str] = []
    for p in _iter_targets(argv):
        if p.exists() and p.suffix == ".py":
            all_violations.extend(check_file(p))

    if all_violations:
        print("\n❌ FastAPI route contract violations (T-225):\n", file=sys.stderr)
        for v in all_violations:
            print(f"  • {v}", file=sys.stderr)
        print(
            "\nEvery route must declare response_model= and operation_id=.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
