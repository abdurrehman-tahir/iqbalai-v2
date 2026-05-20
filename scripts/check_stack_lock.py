#!/usr/bin/env python3
"""
check_stack_lock.py — Enforces docs/STACK_LOCK.md Section 9 (forbidden imports).

For every Python file passed as an argument:
  1. Parse imports using ast.
  2. Check each import against the FORBIDDEN list.
  3. If a forbidden import is found, check docs/DEVIATIONS.md for an explicit
     unlock entry matching both the import path AND the file scope.
  4. If no matching deviation exists, fail with a clear error.

Exit codes:
  0  All checked files are clean.
  1  At least one violation found.
  2  Internal error (couldn't parse DEVIATIONS.md, etc.).

This script is run by pre-commit and CI. It must be kept in sync with
docs/STACK_LOCK.md Section 9.
"""
from __future__ import annotations

import ast
import fnmatch
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEVIATIONS_FILE = REPO_ROOT / "docs" / "DEVIATIONS.md"

# ---------------------------------------------------------------------------
# FORBIDDEN IMPORTS
# Keep this list in sync with docs/STACK_LOCK.md Section 9.
# Format: top-level module name → human-readable reason
# ---------------------------------------------------------------------------
FORBIDDEN: dict[str, str] = {
    # Old / legacy
    "langchain": "use langgraph + pydantic-ai (see STACK_LOCK §4.2)",
    "faiss": "use qdrant (see STACK_LOCK §3)",
    "pymilvus": "use qdrant (see STACK_LOCK §3)",
    "flask": "use fastapi (see STACK_LOCK §1)",
    "sqlite3": "use postgres (see STACK_LOCK §3)",
    "aiosqlite": "use postgres (see STACK_LOCK §3)",
    "requests": "use httpx (async) (see STACK_LOCK §1)",
    # Wrong vector stores
    "chromadb": "use qdrant (see STACK_LOCK §3)",
    "weaviate": "use qdrant (see STACK_LOCK §3)",
    "pinecone": "use qdrant (see STACK_LOCK §3)",
    "pgvector": "use qdrant (see STACK_LOCK §3)",
    # Wrong LLM clients (use the abstraction)
    "anthropic": "use app/services/llm/client.py abstraction (see STACK_LOCK §4.1)",
    "groq": "use app/services/llm/client.py abstraction (see STACK_LOCK §4.1)",
    "mistralai": "use app/services/llm/client.py abstraction (see STACK_LOCK §4.1)",
    "cohere": "use app/services/llm/client.py abstraction (see STACK_LOCK §4.1)",
    # Wrong frameworks
    "llama_index": "use langgraph + pydantic-ai (see STACK_LOCK §4.2)",
    "haystack": "use langgraph + pydantic-ai (see STACK_LOCK §4.2)",
    "crewai": "use langgraph + pydantic-ai (see STACK_LOCK §4.2)",
    "autogen": "use langgraph + pydantic-ai (see STACK_LOCK §4.2)",
    "semantic_kernel": "use langgraph + pydantic-ai (see STACK_LOCK §4.2)",
    # Wrong TTS
    "elevenlabs": "use Piper / Edge-TTS / AI4Bharat (see STACK_LOCK §4.4)",
    "TTS": "use Piper / Edge-TTS / AI4Bharat (Coqui XTTS license issue — see STACK_LOCK §4.4)",
    "melo": "MeloTTS lacks Urdu/Sindhi/Pashto (see STACK_LOCK §4.4)",
    # Wrong SR algorithms
    "sm2": "use py-fsrs (see STACK_LOCK §4.5)",
    "supermemo": "use py-fsrs (see STACK_LOCK §4.5)",
    # Wrong observability
    "datadog": "use Prometheus + Grafana + Loki (see STACK_LOCK §7)",
    "newrelic": "use Prometheus + Grafana + Loki (see STACK_LOCK §7)",
    # Wrong auth providers
    "auth0": "use Authentik (see STACK_LOCK §5)",
    "clerk": "use Authentik (see STACK_LOCK §5)",
    "supabase": "use Authentik + Postgres (see STACK_LOCK §3 and §5)",
    # Wrong build tooling
    "black": "use ruff (see STACK_LOCK §1)",
    "isort": "use ruff (see STACK_LOCK §1)",
    "flake8": "use ruff (see STACK_LOCK §1)",
}

# Optional scope-restricted forbidden imports
# Map: import → file pattern where it IS allowed (anywhere else, forbidden)
SCOPE_RESTRICTED: dict[str, list[str]] = {
    # openai SDK is allowed only inside the LLM abstraction
    "openai": ["app/services/llm/*"],
    # raw provider SDKs allowed only inside the LLM abstraction
    "anthropic": ["app/services/llm/*"],
    "groq": ["app/services/llm/*"],
    "mistralai": ["app/services/llm/*"],
    "cohere": ["app/services/llm/*"],
}


# ---------------------------------------------------------------------------
# DEVIATIONS parsing
# ---------------------------------------------------------------------------
def parse_deviations() -> list[tuple[str, str]]:
    """
    Parse docs/DEVIATIONS.md and return [(import_path, file_scope), ...].
    Looks for entries like:
        ### `langchain.text_splitter`
        ...
        - **Scope:** `app/services/ingestion/chunker.py`
    """
    if not DEVIATIONS_FILE.exists():
        return []

    text = DEVIATIONS_FILE.read_text(encoding="utf-8")
    # Pattern: ### `import.path` then later - **Scope:** `glob`
    entry_re = re.compile(
        r"^###\s+`([^`]+)`"  # the import path
        r".*?"
        r"-\s+\*\*Scope:\*\*\s+`([^`]+)`",
        re.DOTALL | re.MULTILINE,
    )
    return [(m.group(1).strip(), m.group(2).strip()) for m in entry_re.finditer(text)]


def is_deviation_unlocked(
    full_import: str, file_path: str, deviations: list[tuple[str, str]]
) -> bool:
    """Return True if (import, file) is unlocked in DEVIATIONS.md."""
    norm_file = file_path.replace("\\", "/")
    for dev_import, dev_scope in deviations:
        # Match import: exact or as a prefix (langchain.text_splitter matches langchain.text_splitter.*)
        if full_import == dev_import or full_import.startswith(dev_import + "."):
            # Match file scope as glob
            if fnmatch.fnmatch(norm_file, dev_scope):
                return True
    return False


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------
def extract_imports(source: str) -> list[tuple[str, str]]:
    """
    Return [(top_level_module, full_import_path), ...] for a source file.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Let mypy / ruff handle syntax errors; skip silently here.
        return []

    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                out.append((top, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            top = node.module.split(".")[0]
            out.append((top, node.module))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def check_file(file_path: Path, deviations: list[tuple[str, str]]) -> list[str]:
    """Return list of violation messages for one file. Empty if clean."""
    violations: list[str] = []
    try:
        rel_path = file_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return []

    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return [f"{rel_path}: could not read ({e})"]

    for top_level, full in extract_imports(source):
        # Check scope-restricted first
        if top_level in SCOPE_RESTRICTED:
            allowed_patterns = SCOPE_RESTRICTED[top_level]
            if not any(fnmatch.fnmatch(rel_path, p) for p in allowed_patterns):
                if not is_deviation_unlocked(full, rel_path, deviations):
                    violations.append(
                        f"{rel_path}: '{full}' is scope-restricted to {allowed_patterns}. "
                        f"Reason: must go through the LLM abstraction (STACK_LOCK §4.1)."
                    )
            continue

        # Check forbidden
        if top_level in FORBIDDEN:
            if not is_deviation_unlocked(full, rel_path, deviations):
                violations.append(
                    f"{rel_path}: '{full}' is FORBIDDEN. {FORBIDDEN[top_level]}"
                )

    return violations


def main(argv: list[str]) -> int:
    if not DEVIATIONS_FILE.exists():
        print(
            f"WARNING: {DEVIATIONS_FILE} not found. No deviations will be honored.",
            file=sys.stderr,
        )
        deviations: list[tuple[str, str]] = []
    else:
        try:
            deviations = parse_deviations()
        except Exception as e:
            print(f"ERROR parsing {DEVIATIONS_FILE}: {e}", file=sys.stderr)
            return 2

    targets = argv[1:] if len(argv) > 1 else []
    if not targets:
        # If invoked without args, scan all .py files in the repo
        targets = [str(p) for p in REPO_ROOT.rglob("*.py")
                   if ".venv" not in p.parts and "node_modules" not in p.parts]

    all_violations: list[str] = []
    for t in targets:
        p = Path(t).resolve()
        if not p.exists() or p.suffix != ".py":
            continue
        all_violations.extend(check_file(p, deviations))

    if all_violations:
        print("\n❌ STACK_LOCK violations found:\n", file=sys.stderr)
        for v in all_violations:
            print(f"  • {v}", file=sys.stderr)
        print(
            "\nTo resolve:\n"
            "  1. Use a library from docs/STACK_LOCK.md instead, OR\n"
            "  2. Add an approved entry to docs/DEVIATIONS.md (requires @abdurrehman approval).\n",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
