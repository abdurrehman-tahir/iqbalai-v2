#!/usr/bin/env python3
"""Modernize pre-hardened milestone backlogs (M-03..M-17) in place.

Idempotent: prepends a standard "hardened-template gates apply" banner immediately
after each file's H1 heading, skipping any file that already carries the marker.
Run from the repo root AFTER M-01a is merged. Safe to re-run.

    python scripts/modernize_milestones.py            # apply
    python scripts/modernize_milestones.py --check     # CI mode: exit 1 if any file is un-modernized

It does NOT rewrite ticket bodies or add per-ticket fields — those are added
just-in-time when each ticket is implemented. The banner makes explicit that the
CLAUDE.md + CI gates already bind every ticket here regardless of its wording.
"""
from __future__ import annotations
import glob, re, sys
from pathlib import Path

MARKER = "<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->"

BANNER = MARKER + "\n" + (
    "> **Hardened-template note (post-M-01a).** This milestone was drafted before the hardened ticket template. "
    "The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:\n"
    "> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).\n"
    "> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).\n"
    "> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).\n"
    "> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.\n"
)

# M-03 .. M-17 only (M-00/M-01 remediated by M-01a; M-01a/M-02 already on the new template;
# M-18+ are drafted-spec, not yet ticketed; M-22/M-23 handled when their IDs are reassigned).
TARGET = re.compile(r"/M-(0[3-9]|1[0-7])[^/]*\.md$")


def files() -> list[str]:
    return sorted(f for f in glob.glob("docs/backlog/M-*.md") if TARGET.search(f))


def needs(text: str) -> bool:
    return MARKER not in text


def apply_one(path: str) -> bool:
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    if not needs(t):
        return False
    lines = t.split("\n")
    # insert after the first H1 ("# ...") line; fall back to top if none
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), -1)
    at = idx + 1 if idx >= 0 else 0
    lines.insert(at, "\n" + BANNER)
    p.write_text("\n".join(lines), encoding="utf-8")
    return True


def main() -> int:
    check = "--check" in sys.argv
    fs = files()
    if not fs:
        print("modernize_milestones: no M-03..M-17 files found (run from repo root).")
        return 0
    stale = [f for f in fs if needs(Path(f).read_text(encoding="utf-8"))]
    if check:
        if stale:
            print("Un-modernized milestone files:\n  " + "\n  ".join(stale))
            return 1
        print(f"All {len(fs)} milestone files modernized.")
        return 0
    changed = [f for f in fs if apply_one(f)]
    print(f"Modernized {len(changed)}/{len(fs)} files"
          + (": " + ", ".join(Path(f).name for f in changed) if changed else " (all already current)."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
