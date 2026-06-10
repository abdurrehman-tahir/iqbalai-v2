#!/usr/bin/env python3
"""CI gate: every ticket referenced by this PR's commits must be `Status: done`.

Run in CI on PRs. Collects the T-NNN ids referenced by commit subjects/bodies in the
PR range (base..head), then asserts each is marked `**Status:** done` in its milestone
file. Fails (exit 1) listing any ticket that has committed work but is not yet done —
the exact stale-ledger case that breaks a fresh session's resume rule.

Range resolution (first that applies):
- $PR_BASE_SHA / $PR_HEAD_SHA env (set by the workflow), else
- merge-base of origin/staging..HEAD.

Docs-only PRs (no changes outside docs/ and .claude/) are skipped for the ticket-done
gate, but the milestone-status roll-up runs on every PR: it derives each milestone's
status from its tickets (all done -> done; any done -> in-progress; else pre-impl) and
fails if the ROADMAP Status column disagrees at the done/in-progress end. This keeps the
ROADMAP milestone dashboard an auto-verified roll-up of ticket truth, not a hand-field.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

TICKET_RE = re.compile(r"\bT-\d{3,}\b")
DONE_RE_TMPL = r"^##\s+{tid}\b.*?^\*\*Status:\*\*\s*done\b"


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout.strip()


def pr_range() -> tuple[str, str]:
    base = os.environ.get("PR_BASE_SHA")
    head = os.environ.get("PR_HEAD_SHA") or "HEAD"
    if base:
        return base, head
    mb = sh("git", "merge-base", "origin/staging", "HEAD")
    return (mb or "origin/staging"), "HEAD"


def changed_files(base: str, head: str) -> list[str]:
    out = sh("git", "diff", "--name-only", f"{base}..{head}")
    return [f for f in out.splitlines() if f.strip()]


def is_docs_only(files: list[str]) -> bool:
    if not files:
        return True
    return all(f.startswith("docs/") or f.startswith(".claude/") for f in files)


def referenced_tickets(base: str, head: str) -> set[str]:
    log = sh("git", "log", f"{base}..{head}", "--pretty=%s%n%b")
    # ignore backlog-bookkeeping commits' own subject ids? No — they reference the same
    # ticket and that's fine; we only care that the ticket ends up done.
    return set(TICKET_RE.findall(log))


def ticket_is_done(tid: str) -> bool | None:
    """True/False if found, None if ticket not in backlog."""
    import glob
    from pathlib import Path

    section = re.compile(rf"^##\s+{re.escape(tid)}\b")
    nxt = re.compile(r"^##\s+T-\d{3,}\b")
    for path in glob.glob("docs/backlog/M-*.md"):
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        start = None
        for i, ln in enumerate(lines):
            if start is None and section.match(ln):
                start = i
                continue
            if start is not None and nxt.match(ln):
                block = lines[start:i]
                return any(l.startswith("**Status:**") and "done" in l for l in block)
        if start is not None:
            block = lines[start:]
            return any(l.startswith("**Status:**") and "done" in l for l in block)
    return None


def milestone_status_rollup() -> list[str]:
    """Roll ticket truth up to the ROADMAP milestone-status column.

    For each milestone file with tickets, derive: all tickets done -> 'done';
    any (not all) done -> 'in-progress'; none done -> pre-implementation (no assertion).
    Then assert the ROADMAP row's Status column matches at the done/in-progress end.
    Returns a list of mismatch messages (empty = OK). Only asserts the impl end, so it
    never fights the pre-implementation drafting labels (blocked/drafted-spec/drafted).
    """
    import glob
    from pathlib import Path

    mismatches: list[str] = []
    roadmap = Path("docs/backlog/ROADMAP.md")
    if not roadmap.exists():
        return mismatches
    rmap = roadmap.read_text(encoding="utf-8")
    # ROADMAP row: | M-NN[x] | name | layer | tickets | duration | STATUS | demo |
    row_status = {}
    for ln in rmap.splitlines():
        if ln.startswith("| M-"):
            cells = [c.strip() for c in ln.split("|")]
            if len(cells) >= 7:
                row_status[cells[1]] = cells[6].lower()

    tsec = re.compile(r"^##\s+(T-\d{3,})\b")
    for path in sorted(glob.glob("docs/backlog/M-*.md")):
        mid = re.match(r"(M-\d{2}a?)", Path(path).name)
        if not mid:
            continue
        mid = mid.group(1)
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        states: list[bool] = []
        cur = None
        for ln in lines:
            if tsec.match(ln):
                cur = []
                states.append(False)  # placeholder; flipped below
                idx = len(states) - 1
                cur = idx
            elif cur is not None and ln.startswith("**Status:**") and "done" in ln:
                states[cur] = True
        if not states:
            continue
        expected = "done" if all(states) else ("in-progress" if any(states) else None)
        if expected is None:
            continue  # pre-implementation; don't assert against drafting labels
        actual = row_status.get(mid)
        if actual != expected:
            mismatches.append(
                f"  - {mid}: tickets imply '{expected}' but ROADMAP says '{actual}'"
            )
    return mismatches


def main() -> int:
    base, head = pr_range()
    files = changed_files(base, head)

    # Milestone-status roll-up runs on every PR (cheap; ROADMAP truth must track tickets).
    rollup = milestone_status_rollup()
    if rollup:
        print("[ticket-status-check] FAIL — ROADMAP milestone Status out of sync with ticket states:")
        print("\n".join(rollup))
        print("Fix: update the ROADMAP row Status column (done = all tickets done; in-progress = any done).")
        return 1

    if is_docs_only(files):
        print("[ticket-status-check] docs-only PR; skipping ticket-done gate (roll-up already checked).")
        return 0

    tickets = referenced_tickets(base, head)
    if not tickets:
        print("[ticket-status-check] WARNING: code changed but no T-NNN referenced in commits.")
        # Not a hard fail on its own (could be a hotfix); the commit-msg ticket rule
        # is a separate gate. Surface it and pass.
        return 0

    not_done: list[str] = []
    unknown: list[str] = []
    for tid in sorted(tickets):
        state = ticket_is_done(tid)
        if state is None:
            unknown.append(tid)
        elif not state:
            not_done.append(tid)

    if unknown:
        print(f"[ticket-status-check] referenced but not in backlog: {', '.join(unknown)}")
    if not_done:
        print("[ticket-status-check] FAIL — tickets have committed code but are not marked done:")
        for tid in not_done:
            print(f"  - {tid}")
        print("Fix: mark each done in its milestone file (the post-commit hook normally does this).")
        return 1

    print(f"[ticket-status-check] OK — all referenced tickets done: {', '.join(sorted(tickets))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
