#!/usr/bin/env python3
"""CI gate: env vars read in code must be documented in `.env.example`.

Closes AUDIT_LOG [env-fallback] — the class of bug where code reads an env var
behind a silent dev-default (e.g. `NEXT_PUBLIC_AUTHENTIK_URL ?? "localhost:9000"`)
that is never listed in `.env.example`, so a deploy that forgets to set it ships a
broken default (testers bounced to a dev port; wrong EMBEDDING_PROVIDER; etc.).

Two parities are enforced (matching the ci.yml `env-example-parity` job contract):

1. FRONTEND — every `process.env.NEXT_PUBLIC_*` read under `frontend/src/` has a
   documented key in `.env.example`. (Client-exposed vars are the highest-risk:
   they are baked into the build, so a wrong default is shipped to the browser.)

2. BACKEND — every *required* Pydantic `Settings` field (one with NO default, i.e.
   the deploy MUST provide it) has a documented key in `.env.example`. Fields that
   carry an in-code default are intentionally optional and are not required to be
   listed; this check exists so a newly-added mandatory field can never merge
   without an ops-visible entry.

Pure standard library (ast + re) so it runs on the bare setup-python interpreter
with nothing to install (CI invariant 1 has nothing to sync). Paths resolve from
the repo root (the script's parent's parent), so the working directory is
irrelevant. Exits 1 listing every miss; exits 0 when both parities hold.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
CONFIG_PY = REPO_ROOT / "api" / "app" / "config.py"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

# `process.env.NEXT_PUBLIC_FOO` and `process.env["NEXT_PUBLIC_FOO"]` forms.
NEXT_PUBLIC_RE = re.compile(r"""process\.env(?:\.|\[["'])(NEXT_PUBLIC_[A-Z0-9_]+)""")
# A documented key: `KEY=...` at line start (ignore leading spaces), not a comment.
ENV_KEY_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=")


def documented_keys() -> set[str]:
    if not ENV_EXAMPLE.exists():
        return set()
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        m = ENV_KEY_RE.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def frontend_next_public_reads() -> set[str]:
    """Every NEXT_PUBLIC_* env var read under frontend/src/."""
    if not FRONTEND_SRC.is_dir():
        return set()
    found: set[str] = set()
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".mjs"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        found.update(NEXT_PUBLIC_RE.findall(text))
    return found


def _field_is_required(value: ast.expr | None) -> bool:
    """A Pydantic v2 field is REQUIRED when it has no usable default.

    - `NAME: T` (no assignment)                         -> required
    - `NAME: T = Field(...)`  (Ellipsis, no default)    -> required
    - `NAME: T = Field(default=..)` / `Field(default_factory=..)` -> optional
    - `NAME: T = <any literal/other>`                   -> optional
    """
    if value is None:
        return True
    if isinstance(value, ast.Call) and _is_field_call(value.func):
        # Field(...) positional Ellipsis means required.
        if any(isinstance(a, ast.Constant) and a.value is Ellipsis for a in value.args):
            return True
        has_default = any(
            kw.arg in {"default", "default_factory"} for kw in value.keywords
        )
        # Bare Field() with no default/positional is also required.
        positional_default = bool(value.args)
        return not (has_default or positional_default)
    # A bare Ellipsis default (`NAME: T = ...`) is required too.
    if isinstance(value, ast.Constant) and value.value is Ellipsis:
        return True
    return False


def _is_field_call(func: ast.expr) -> bool:
    return (isinstance(func, ast.Name) and func.id == "Field") or (
        isinstance(func, ast.Attribute) and func.attr == "Field"
    )


def required_settings_fields() -> set[str]:
    """Names of REQUIRED fields on the `Settings` class in api/app/config.py."""
    if not CONFIG_PY.exists():
        return set()
    tree = ast.parse(CONFIG_PY.read_text(encoding="utf-8"))
    required: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "Settings"):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            name = stmt.target.id
            if name.startswith("_") or name == "model_config":
                continue
            if _field_is_required(stmt.value):
                required.add(name)
    return required


def main() -> int:
    docs = documented_keys()
    problems: list[str] = []

    fe_missing = sorted(v for v in frontend_next_public_reads() if v not in docs)
    for var in fe_missing:
        problems.append(f"  - FRONTEND: {var} is read in frontend/src but not in .env.example")

    be_missing = sorted(v for v in required_settings_fields() if v not in docs)
    for var in be_missing:
        problems.append(
            f"  - BACKEND: required Settings field {var} has no key in .env.example"
        )

    if problems:
        print("[env-parity] FAIL — env vars read in code but undocumented in .env.example:")
        print("\n".join(problems))
        print("Fix: add each key (with a safe example value + comment) to .env.example.")
        return 1

    print("[env-parity] OK — all frontend NEXT_PUBLIC_* reads + required Settings fields documented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
