# Drafting and next steps — start here

This directory is how the project keeps moving without an architect. It was set up in the final architect session on 2026-10-13. From here on, the team owns everything: drafting milestones, building them, reviewing and merging.

## The cycle

1. **Open a session and type `Continue.`** The always-on rules (resume rule in `.claude/CLAUDE.md`) read `docs/backlog/ROADMAP.md` and pick the first row not marked `done`. **The roadmap's row order is the build order.**
2. **If that milestone already has a backlog file with tickets**, the session implements its next ticket, as before (ticket-loader first).
3. **If it has no backlog file** (status `drafted-spec`), or it is a placeholder row (`Deferred work`, `Rollout N`), the session switches to **drafting mode** and follows `PLAYBOOK.md`. It drafts that one milestone, opens a docs-only PR, and stops. Nothing gets built in that session.
4. **Merge the drafting PR.** Then a new session implements the milestone in a separate PR.
5. Repeat.

## What comes next (as of handover)

M-22 → M-23 → M-16 → M-17 → M-18a → M-18b → M-18c → M-18d → M-19 → M-20a → M-20b → M-21a → M-21b → Deferred work → Rollout 1 → Rollout 2 → Rollout 3 → Rollout 4

- **M-16 and M-17** already have tickets. Build them as they are.
- **M-22 and M-23** are largely built already. Their drafting step checks the code first and drafts only what is missing.

## Files here

| File | What it is |
|---|---|
| `PLAYBOOK.md` | Drafting mode, step by step |
| `PROMPTS.md` | What to type to the coding agent |
| `HANDOVER.md` | Decisions from the last architect session, and what is still open |
| `DEFERRED_REGISTER.md` | Created later, by the first "Deferred work" run |

## The rules that matter most

- **Draft and build in separate PRs.** Merge the draft first.
- **Number tickets at draft time:** the next number after the highest `T-NNN` that exists. Never reserve ranges in advance.
- **Name every ticket ID in the commit that implements it.** The CI ledger only sees tickets named in commit messages.
- **Anything scoped out of a ticket gets a `BLOCKED-HOOK:` line.** Drafting finds deferred work only through those markers.
- **Milestone file names are `M-NN` or `M-NN` plus one letter** (for example `M-18b`). The CI ledger maps files to roadmap rows by that name.
- **The second coding tool (Cursor) gets its rules from `.claude/`.** After anyone edits `.claude/`, run `python scripts/sync_cursor.py`, commit `.cursor/` too, then reload Cursor.
