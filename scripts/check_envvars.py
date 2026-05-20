#!/usr/bin/env python3
"""
check_envvars.py — Reject hardcoded URLs, API keys, and connection strings.

Catches the most common "I forgot to use an env var" mistakes:
  - HTTP(S) URLs hardcoded in code (with allowlist for safe examples)
  - Postgres / Redis / Qdrant / NATS connection strings in code
  - Long suspicious-looking strings that resemble API keys (entropy heuristic)
  - os.environ.get with substantial fallback defaults

Allowlisted:
  - localhost / 127.0.0.1 / 0.0.0.0 (dev only)
  - example.com, example.org
  - schema URIs (xmlns, JSON schema)
  - Anything in test files (tests/**, conftest.py)
  - Lines marked with: # noqa: envvars

Self-skip:
  - The enforcement scripts in scripts/check_*.py contain pattern definitions
    and docstring examples by necessity, so they are skipped entirely.

Exit codes:
  0  Clean.
  1  Violations found.
"""
from __future__ import annotations

import math
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Allowlisted hosts that are NEVER flagged
ALLOWLISTED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "example.com",
    "example.org",
    "schema.org",
    "www.w3.org",
    "xmlns.com",
    "json-schema.org",
}

# Paths skipped entirely
SKIP_PATH_PARTS = {".venv", "node_modules", "tests", "test", ".git"}

# Specific files skipped (enforcement scripts contain their own patterns)
SKIP_FILES = {
    "scripts/check_envvars.py",
    "scripts/check_stack_lock.py",
    "scripts/check_imports.py",
}

# Per-line escape hatch
NOQA_MARKER = re.compile(r"#\s*noqa:\s*envvars\b", re.IGNORECASE)

URL_RE = re.compile(r"https?://([a-zA-Z0-9.\-_]+)(?::\d+)?(/[^\s\"'`]*)?")
CONN_STR_RE = re.compile(
    r"(postgresql|postgres|redis|qdrant|nats|mongodb|mysql|amqp)://"
    r"[^\s\"'`]+",
    re.IGNORECASE,
)
# Heuristic API key pattern: long alphanumeric strings inside quotes
KEY_LIKE_RE = re.compile(
    r"""['"]([A-Za-z0-9_\-]{32,})['"]""",
)

# Patterns that look like env-var fallbacks with suspicious defaults
ENVVAR_DEFAULT_RE = re.compile(
    r"""os\.environ\.get\(\s*['"][A-Z_]+['"]\s*,\s*['"]([^'"]{8,})['"]\s*\)""",
)


def shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string. High entropy = likely a key/token."""
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def is_likely_key(s: str) -> bool:
    """Heuristic: high entropy + mixed alphanumeric + long = likely a key."""
    if len(s) < 32:
        return False
    if not re.search(r"[A-Z]", s) or not re.search(r"[a-z]", s) or not re.search(r"\d", s):
        return False
    return shannon_entropy(s) > 3.5


def check_file(file_path: Path) -> list[str]:
    try:
        rel = file_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        # File is outside the repo (e.g., direct invocation with absolute path) — skip it.
        return []
    violations: list[str] = []

    if any(part in SKIP_PATH_PARTS for part in file_path.parts):
        return []

    # Self-skip the enforcement scripts (they contain pattern definitions)
    if rel in SKIP_FILES:
        return []

    # Only check Python and TypeScript/JavaScript files
    if file_path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
        return []

    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    for lineno, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Per-line escape hatch
        if NOQA_MARKER.search(line):
            continue

        # URL check
        for m in URL_RE.finditer(line):
            host = m.group(1)
            if host in ALLOWLISTED_HOSTS:
                continue
            # Suppress if it's clearly in a docstring URL reference (heuristic)
            if line.lstrip().startswith(('"""', "'''")):
                continue
            violations.append(
                f"{rel}:{lineno}: hardcoded URL 'https://{host}...'. Read from env var instead."
            )

        # Connection string check
        for m in CONN_STR_RE.finditer(line):
            violations.append(
                f"{rel}:{lineno}: hardcoded connection string '{m.group(0)[:40]}...'. "
                f"Read from env var instead."
            )

        # API key heuristic
        for m in KEY_LIKE_RE.finditer(line):
            candidate = m.group(1)
            if is_likely_key(candidate):
                violations.append(
                    f"{rel}:{lineno}: suspicious high-entropy string (possible API key). "
                    f"Read from env var instead. (prefix: {candidate[:8]}...)"
                )

        # Env var with substantial default
        for m in ENVVAR_DEFAULT_RE.finditer(line):
            default = m.group(1)
            # Allow short defaults like "info", "debug", "1", numeric strings
            if len(default) > 16 or "://" in default or "=" in default:
                violations.append(
                    f"{rel}:{lineno}: os.environ.get() has suspicious default '{default[:30]}...'. "
                    f"Use a safe placeholder or empty string, not real values."
                )

    return violations


def main(argv: list[str]) -> int:
    targets = argv[1:] if len(argv) > 1 else []
    if not targets:
        exts = (".py", ".ts", ".tsx", ".js", ".jsx")
        targets = [
            str(p)
            for p in REPO_ROOT.rglob("*")
            if p.suffix in exts
            and not any(part in SKIP_PATH_PARTS for part in p.parts)
        ]

    all_violations: list[str] = []
    for t in targets:
        p = Path(t).resolve()
        if not p.exists():
            continue
        all_violations.extend(check_file(p))

    if all_violations:
        print("\n❌ Hardcoded secret/URL violations:\n", file=sys.stderr)
        for v in all_violations:
            print(f"  • {v}", file=sys.stderr)
        print(
            "\nTo resolve: read these values from environment variables. "
            "See docs/ENV_VARS.md (when created) for naming conventions.\n",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
