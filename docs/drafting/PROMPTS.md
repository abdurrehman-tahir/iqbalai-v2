# Prompts — what to type

The rules live in the repo, so prompts stay short. The same prompts work in Claude Code and in Cursor, as long as Cursor's rules are current (`python scripts/sync_cursor.py`, then reload Cursor).

| When | Type this | What happens |
|---|---|---|
| Start of any session | `Continue.` | Reads `ROADMAP.md` and picks the first row not `done`. Implements its next ticket, or switches to drafting mode if it has no backlog file yet. |
| You want the next milestone drafted | `Draft the next milestone.` | Drafting mode (`PLAYBOOK.md`) on the first not-`done` row. One docs-only PR, then stops. |
| You want a specific ticket built | `Implement T-NNN.` | Ticket-loader dossier first, then the ticket. |
| You want the deferred-work register early, for estimating | `Build the deferred-work register per docs/drafting/PLAYBOOK.md §5. Do not draft any milestone yet.` | The register file plus roadmap rows, in a docs-only PR. |
| Every build milestone is on the roadmap | `Draft the next rollout per docs/drafting/PLAYBOOK.md §6.` | One Rollout milestone of non-dev tasks, in a docs-only PR. |
| A milestone PR has just merged | `Close out M-NN: confirm every ticket is done and the ROADMAP row matches.` | Fixes the ledger before the next session picks the next row. |

**If a session seems confused about what is next,** check `ROADMAP.md` first. The first row not marked `done` decides everything, so a stale status there sends every session to the wrong place.
