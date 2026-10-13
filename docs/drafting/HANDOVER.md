# Handover — 2026-10-13

The architect stepped away after this session. From here, the team owns drafting, building, reviewing and merging. Branch protection is off and there are no required approvers; anyone can merge.

`.github/CODEOWNERS` still names the former architect. With branch protection off it only auto-requests a review and blocks nothing. Remove that entry if the review requests are noise.

## Decisions made in the final session

1. **Build everything first.** All dev work goes into milestones and gets built before any rollout: the features in the flow specs, plus every not-yet-built dev item deferred under `phase-2`/`phase-3` tags. The client decides next steps after that.
2. **Items the specs mark "never build" by design are excluded.** They are decisions, not unbuilt work.
3. **Non-dev work goes into four Rollout milestones at the end:** Pilot readiness → Pilot → Production launch → Post-launch. The word is "Rollout", not "phase", because "phase" already means three different things in these docs.
4. **M-22 and M-23 come next, before M-16.** Both are largely built already, so their drafting step checks the code first.
5. **The team's coding sessions draft milestones from now on,** one per session, in a docs-only PR that merges before implementation starts. See `PLAYBOOK.md`.
6. **Flow 7's spec was missing from the repo.** A restored draft is committed and judged good enough.

## What this handover changed

- **`docs/feature-specs/flow-7-next-day-review.md`** — added.
- **`docs/backlog/ROADMAP.md`:**
  - M-22 and M-23 moved to the front, re-marked `drafted-spec`, and their old ticket ranges cleared — those ranges collided with M-16 and M-17.
  - M-01, M-04, M-07a and M-12 marked `done`.
  - Placeholder rows added for Deferred work and Rollouts 1 to 4.
  - Row order is now the build order.
- **Ledger close-out:**
  - M-01's T-027, M-04's T-068 and M-07a's T-249 were each the milestone's "PR + demo" ticket, never closed although the milestones merged (PRs #9, #16 and #27). Closed against those merge commits; whether the demos happened is not recorded.
  - M-12's tickets T-151 to T-165 (except T-155, already done) were closed against the milestone merge commit. Its branch commits never named tickets; PR #33 lists all fifteen as delivered.
  - Without this, the resume rule would have sent the next session back to M-01.
- **`.claude/CLAUDE.md`:** the resume rule now sends milestones with no backlog file into drafting mode, and one line requires a `BLOCKED-HOOK` marker for anything scoped out. `.cursor/` was regenerated to match.
- **`scripts/check_ticket_status.py`:** the milestone file-name pattern changed from `M-\d{2}a?` to `M-\d{2}[a-z]?`. The old pattern read M-18b, M-18c, M-18d, M-20b and M-21b as plain M-18, M-20 and M-21, so the ledger check would have failed permanently once those milestones started.
- **`docs/drafting/`** — this directory.

## Still open

None of these blocks the next milestone.

- **Open stack decisions past their milestone, still unchecked in `STACK_LOCK.md`:** Qdrant collection design (`resolve-before M-09`), NATS topic taxonomy and WebSocket connection lifecycle (`resolve-before M-12`), Celery queue priority tiers (`resolve-before M-14`). Those milestones shipped, so what was built is the decision in practice. Record it in `STACK_LOCK.md` when convenient.
- **`resolve-before pilot` items** (pooling sizing, embedding cache, PDPB PII handling, rate limiting, backup and restore) — the deferred register and Rollout 1 pick these up.
- **`docs/TODO.md`** only ever harvested flows 1 to 6 and 13. The deferred register harvests flows 7 to 12.
- **Known weak spots in CI and PR checks**, so that a green build is not read as proof of correctness:
  - The ticket ledger is blind to milestones whose commits do not name tickets.
  - The PR template check confirms sections exist, not what they say.
  - The governance check looks for a line anyone can type, and does not re-run when only the PR description changes.
  - Local pre-commit hooks are optional; nothing in CI confirms they ran.
  - `backend-lint` has merged red across several milestones.
- **The second coding tool reads rules generated from `.claude/`.** After editing `.claude/`, always regenerate with `python scripts/sync_cursor.py`, commit `.cursor/`, and reload the tool.
