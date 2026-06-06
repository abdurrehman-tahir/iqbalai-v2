# Ticket-status automation (PR-time verifier + milestone roll-up)

A single mechanical backstop so the ROADMAP and ticket ledger never silently drift from what's actually been implemented. **Read-only / CI-only** — there is no per-commit writer hook (that approach was evaluated and shelved; status is written by the prose close-out step in WORKFLOW/CLAUDE.md, and CI verifies it at PR time).

## Files

| File | Role |
|---|---|
| `scripts/check_ticket_status.py` | **Verifier (CI).** Two checks per PR: (1) **milestone-status roll-up** — derives each milestone's status from its ticket `**Status:**` fields (all done → `done`; any done → `in-progress`; else pre-implementation → no assertion) and fails if the ROADMAP `Status` column disagrees at the done/in-progress end (runs on **every** PR, incl. docs-only — never fights the pre-impl drafting labels `blocked`/`drafted-spec`/`drafted`); (2) **referenced-tickets-done gate** — fails if any ticket whose code is touched by this PR's commits isn't `Status: done` (skips for docs-only PRs). |
| `.github/workflows/ci.ticket-status-job.snippet.yml` | The CI job, pasted into `ci.yml`. Runs on every PR; `fetch-depth: 0` so it can diff the PR range. |

> No writer: there is **no** `scripts/update_ticket_status.py`, **no** `.githooks/post-commit`, and **no** `core.hooksPath` setup. If you see those referenced anywhere, that's stale — this file is the source of truth.

## How status actually gets written

- **Per ticket:** the implementer follows the WORKFLOW/CLAUDE.md close-out step — set the ticket's `**Status:** done` (+ commit SHA) in its milestone file when it's merged. This is a prose convention, enforced after the fact by the verifier below.
- **Per milestone (ROADMAP `Status` column):** **not hand-maintained** — the roll-up in `check_ticket_status.py` derives it from ticket states and fails the PR if the column is out of sync. So you never manually edit the milestone `Status` column to `in-progress`/`done`; you fix the tickets and the roll-up validates the column.

## What CI enforces at PR time

1. The ROADMAP milestone `Status` column matches the rolled-up truth of its tickets (done/in-progress end).
2. Every ticket whose code this PR touches is marked `done` before merge (non-docs PRs).

CI cannot *write* status — it only blocks merge if the committed ledger is stale, forcing a correction. Keeping the ledger live is the close-out step's job; catching a missed one is CI's.

## Status vocabulary (ROADMAP)

`blocked` (no spec) → `drafted-spec` (flow spec only) → `drafted` (backlog tickets written, not started) → `in-progress` (some tickets done) → `done` (all tickets done). The verifier only asserts the `in-progress`/`done` end; the pre-implementation labels are drafting-side and left alone.

## Known limitations (honest)

- The roll-up asserts only the implementation end (`in-progress`/`done`); it deliberately does not police `blocked`/`drafted-spec`/`drafted`, since those are set during drafting before any ticket exists.
- The referenced-tickets-done gate keys off the `T-NNN` in commit messages / changed milestone files; a PR that touches code without naming its ticket can slip the per-ticket gate (but the roll-up still validates the milestone column). Convention: name the ticket in the commit subject (`feat(scope): … (T-NNN)`).
- It is a verifier, not a writer: it never edits files. Status is only ever written by a human/CC via the close-out step.
