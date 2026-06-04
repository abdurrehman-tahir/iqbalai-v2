# WORKFLOW.md — How we build IqbalAI v2

**Status:** Locked
**Owner:** @abdurrehman-tahir
**Audience:** Hamza, Hamza's Claude Code, Abd.
**Last reviewed:** 2026-05-14

This document defines the **only** way we move from the v2 product doc to merged code in `staging`. Every milestone of v2 follows this exact loop. No skipping steps.

If you (Claude Code) are reading this for the first time in a session, the read-rules live in `.claude/CLAUDE.md` (auto-loaded). Do NOT pre-load reference docs from this file — `CLAUDE.md` has the conditional-trigger table.

**The §0 rule (enforced):** ARCHITECTURE.md is ~9,800 lines. You read **§0 + only the sections §0 lists for your task** — nothing else unless you follow an explicit cross-reference. Every PR description must list which sections were read; mismatch with the code changes is a PR-blocker.

---

## The build loop, in one diagram

```
                  ┌─────────────────────────────────────────┐
                  │   STEP 0: PULL LATEST + PICK MILESTONE  │
                  │   Hamza                                 │
                  │                                         │
                  │   - git checkout staging && git pull    │
                  │   - Read docs/backlog/ROADMAP.md        │
                  │   - Find next milestone (status: todo,  │
                  │     unblocked, lowest M-NN)             │
                  │   - Open docs/backlog/M-NN-*.md         │
                  │   - Create feature branch:              │
                  │     `git checkout -b milestone/M-NN`    │
                  └─────────────────────┬───────────────────┘
                                        │
                                        ▼
                  ┌─────────────────────────────────────────┐
                  │   STEP 1: IMPLEMENT, TICKET BY TICKET   │
                  │   Hamza + Claude Code                   │
                  │                                         │
                  │   For each ticket T-XXX in milestone:   │
                  │     - Tell Claude Code: "Implement      │
                  │       T-XXX"                            │
                  │     - Claude reads:                     │
                  │         * ticket file                   │
                  │         * cited spec sections           │
                  │         * cited ARCH sections           │
                  │         * relevant skill references     │
                  │     - Claude implements (backend+UI)    │
                  │     - Hamza reviews + commits           │
                  │     - Mark ticket "done" in M-NN file   │
                  │     - Next ticket                       │
                  └─────────────────────┬───────────────────┘
                                        │
                                        ▼
                  ┌─────────────────────────────────────────┐
                  │   STEP 2: MILESTONE PR + DEMO           │
                  │   Hamza + Abd. (+ optionally Awais)     │
                  │                                         │
                  │   - All milestone tickets "done"        │
                  │   - Hamza records 5-min demo video      │
                  │   - Opens ONE PR for whole milestone    │
                  │     branch (tickets = commits)          │
                  │   - Abd. reviews + approves             │
                  │   - Merge to staging                    │
                  │   - Update ROADMAP.md status → done     │
                  └─────────────────────┬───────────────────┘
                                        │
                                        ▼
                          Milestone done → repeat for next milestone
```

---

## Step 0: Pull latest + pick milestone

Before opening Claude Code for a fresh session:

```bash
git checkout staging
git pull origin staging
```

**Why mandatory:** specs, backlog, and ARCHITECTURE.md are living documents. Abd. + Awais may have merged spec updates between your sessions. Claude Code reads local files — if local is stale, you implement against outdated rules.

Read `docs/backlog/ROADMAP.md` and find the next milestone with:
- Status `todo`
- Lowest M-NN number among `todo` milestones
- Not `blocked` (blocked = its flow spec doesn't exist yet)

If multiple `todo` milestones are unblocked, pick the lowest number — never skip a milestone for a later one unless the lower one is blocked.

Open the milestone file (e.g., `docs/backlog/M-03-grade-section-subject.md`). Create your milestone branch:

```bash
git checkout -b milestone/M-NN-short-name
```

(e.g., `milestone/M-03-grade-section-subject`)

### 0a. If a spec changes mid-milestone

If you're already on a milestone branch and Abd. merges a flow spec change that affects your in-progress work:

1. **Stop coding immediately.**
2. **Ping Abd.** (WhatsApp / direct) — describe what you've already built on the milestone branch and what the spec change covers.
3. Abd. decides one of:
   - **(a) Pin to old spec version** — your milestone uses the spec as-of-branch-creation; new spec applies to future milestones
   - **(b) Rebase / partial redo** — you rebase the milestone branch and adapt affected tickets to the new spec
   - **(c) Abort milestone** — rare; only if the spec change invalidates the entire milestone direction
4. Continue only after Abd. confirms which path.

**Why:** silent drift between an in-flight milestone and an updated spec is the most expensive class of bug. The ping costs 5 minutes; the rework costs days. Always ping.

---

## Step 1: Implement, ticket by ticket

For each ticket in the milestone (in the order listed in the milestone file):

### 1.1 Tell Claude Code which ticket

Open Claude Code in repo root. Say something like:

> "Implement T-016 per `docs/backlog/M-01-platform-setup.md`."

### 1.2 What Claude Code does

Claude Code must follow this exact sequence:

1. **Open `docs/backlog/M-NN-*.md`** and find ticket T-XXX
2. **Read the ticket's `Spec source:` files** (only the cited line ranges via `view`, not whole files)
3. **Read the ticket's `ARCH source:` subsections** (only the cited subsections per §0 rule)
4. **Read `docs/STACK_LOCK.md`** (always; small)
5. **Read `.claude/CLAUDE.md`** (always; small)
6. **Read `docs/AMENDMENTS.md`** (always; small) — confirm no recent amendments affect the sections just read
7. **Read `docs/ENV_VARS.md`** if the ticket adds env vars
8. **Read the relevant skills** in `.claude/skills/` (e.g., `frontend-master/` for UI tickets, `stack-enforcer/` for backend boundaries)
9. **Implement the ticket** — backend + frontend + migration + tests. Tests are mandatory (pytest + contract test per endpoint; Vitest+RTL + a Playwright E2E whenever the ticket touches the frontend). Migrations are model-first (model → `--autogenerate` → review; ticket data-model = intent, not DDL — ARCH §4.12). FE types are generated via openapi-typescript, never hand-mirrored

### 1.3 What the PR description carries

The milestone PR (Step 2) will list, per ticket completed:

```markdown
## T-XXX Title

**Spec source read:**
- flow-N-XYZ.md §A.B
- flow-N-XYZ.md §C.D

**ARCH sections read:**
- §3.16 Independent users tenant
- §6.19 Permission inheritance

**Acceptance:** (copy from ticket; check off each)
- [x] Step 1 of demo
- [x] Step 2 of demo
- [x] Step 3 of demo
```

As each ticket completes, its `Status:` is set to `done` in the milestone file **and the commit SHA is recorded on the ticket** (commit the change as `chore(backlog): mark T-XXX done`). This is mandatory per ticket, not deferred to milestone close — the milestone file is the **durable per-ticket ledger a fresh Claude Code session resumes from** (it reads ROADMAP → active milestone → first ticket not `done`). `.claude/session-state.md` is only a fast within-session hint; if the two disagree, the milestone file wins.

### 1.4 Section-tracking is enforced

The `phase-complete-review` skill compares declared "Sections read" against the files you changed. Mismatch — e.g., you changed `app/features/<feature>/models.py` but didn't list §3 (multi-tenancy) and §4 (DB patterns) — fails the check.

### 1.5 Spec adherence is enforced

`phase-complete-review` Checklist M compares your implementation against the spec's §11 (acceptance criteria). Drift between code and spec is a PR-blocker — either the spec is updated (separate PR, Awais + Abd. review) or the code is corrected.

### 1.6 If a cross-reference (§X) inside a section you're reading is genuinely needed

Read it. Add it to your "Sections read" list. The point isn't to read less; it's to read only what's needed and declare it.

### 1.7 Format gate — run before every commit

Before committing a ticket's work, run the SAME format/lint/type commands CI runs, and commit the settled output (per CLAUDE.md "Format gate"):

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy --strict app/
# + pnpm --dir frontend format && pnpm --dir frontend lint   (if frontend changed)
```

Because pre-commit, `uv run`, and CI all pin the same tool versions + config (STACK_LOCK §8), passing this gate locally means CI's format/lint checks pass. Never commit code "blind" and let CI surface formatting — that creates rework. Never use `git commit --no-verify`.

### 1.8 Conventional Commits per ticket

Commit per ticket with conventional commit messages:

- `feat(scope): description (T-XXX)`
- `fix(scope): description (T-XXX)`
- `chore(backlog): mark T-XXX done`
- `docs(arch): update §X.Y per T-XXX (T-XXX)`

The ticket ID at the end is mandatory — it links commits back to the backlog.

---

## Step 2: Milestone PR + demo

When all tickets in the milestone are `done` and committed to the milestone branch:

### 2.1 Pre-PR checklist

- [ ] All tickets in milestone file marked `done`
- [ ] `pnpm test` (Vitest+RTL, frontend) + `pytest` (backend) green locally
- [ ] `pnpm e2e` (Playwright) green — every page-bearing ticket's acceptance path passes its E2E
- [ ] No skipped tests without justification comment
- [ ] Typed client up to date: `schema.d.ts` regenerated from OpenAPI shows **no diff**; no hand-mirrored types
- [ ] Every endpoint declares `response_model=` (the `response_model` CI check is green)
- [ ] Every new page is reachable from the app nav and renders real content (UX-acceptance items checked)
- [ ] All notification template keys translated in all 4 languages (no `__TODO__` markers)
- [ ] Migrations are model-first (autogenerated + reviewed, one concern each) and cleanly upgrade both Alembic heads
- [ ] Demo video recorded (5-7 min) showing the milestone's acceptance criteria end-to-end

### 2.2 Open the PR

PR title: `feat(milestone): M-NN — <short milestone name>` (e.g., `feat(milestone): M-03 — Grade / Section / Subject + GSO`)

PR body uses the template in `.github/PULL_REQUEST_TEMPLATE.md`. Includes:
- Summary (2 paragraphs)
- Link to the milestone file
- List of tickets completed with their declared "Sections read"
- Demo video link (attached or YouTube unlisted)
- Migration plan (which Alembic heads upgraded)
- Notifications added (per Flow 1 v2 §3.7 namespace list)

### 2.3 Abd. reviews

Abd.'s review:
1. **Watches the demo video** (first; gut-check the milestone delivers what was promised)
2. **Reads the milestone file** to verify ticket scope matches spec
3. **Reads the diff** at the level of "is this where I expected the changes?"
4. **Confirms ARCH sections declared in PR match actual diff** (uses `phase-complete-review` skill)
5. **Spot-checks tests** for at least 2 tickets
6. **Comments "APPROVED <YYYY-MM-DD>"** when satisfied; merges PR

### 2.4 Post-merge

- Update `docs/backlog/ROADMAP.md` — set milestone status to `done`
- Move to next milestone (back to Step 0)

---

## What "milestone branch" means + branch hygiene

- One milestone = one feature branch off `staging`
- Tickets within milestone = sequential commits on that branch
- Branch lives 2-3 weeks (avg)
- Don't merge other people's PRs INTO your milestone branch unless they're blocking
- If your milestone branch falls behind `staging` by > 1 week → rebase

---

## Spec adherence — the contract

The feature spec is the contract:
- Lifecycle in the spec = state machine in the code
- Permissions matrix in the spec = `require_*` dependencies in router endpoints
- Edge cases in the spec = either implemented OR explicitly deferred (TODO.md + spec amendment)
- Limits in the spec = config values / constants with same numbers
- Notifications in the spec = NATS publishes + template keys present
- Acceptance criteria in the spec = passing tests
- Open questions = empty (resolved) when PR opens

Silent divergence = PR blocked.

---

## Anti-patterns — what kills this workflow

Be alert. Stop and ask if you see any of these forming:

- **Hamza skips Step 0 (no pull).** Specs may have changed. Always pull.
- **Hamza tries to "implement Phase 1" or "implement Flow 5" in bulk.** Refuse. Milestones are the unit.
- **Claude Code re-reads whole ARCHITECTURE.md.** Violates §0 rule. Use line-range views on cited subsections only.
- **A "small" change touches multiple milestones in one PR.** Split it.
- **Hamza opens a PR mid-milestone with only some tickets done.** No — one PR per milestone (or per logical sub-grouping if Abd. agrees).
- **DEVIATIONS.md grows by 5+ entries in one milestone.** That's a signal the stack lock is wrong, not that we need more exceptions. Convene with Abd.
- **A ticket takes >5 days.** Either the ticket was sized wrong (split it) or you're stuck (ask Abd. before continuing).
- **Tests added in a separate PR after the milestone.** No. Tests live with their ticket.
- **Hamza modifies a spec to match the code.** Backwards. Code follows spec, not other way. Spec changes go through Abd. + Awais first.

---

## When this workflow does NOT apply

- **Bug fixes:** single PR direct to `staging`, no milestone branch needed. Cite the broken behavior + the spec section it violates.
- **Hotfixes:** see BRANCHING.md hotfix flow.
- **Tooling / CI changes:** single PR, no milestone branch.
- **Refactors confined to one file or one feature folder:** single PR.
- **Doc updates:** see BRANCHING.md §8.1 docs-only PR fast track.

If in doubt, ask Abd. before deciding the workflow applies.

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-11 | Initial workflow definition (phase-based) | @abdurrehman-tahir (with Claude) |
| 2026-05-14 | T0 batch: added §3.0 always-pull + §3.0a mid-milestone spec drift | @abdurrehman (with Claude) |
| 2026-05-14 | Workflow rewritten for milestone/ticket/backlog model (replaces phase-plan-doc approach). Old "Step 1: Plan" deleted entirely; `docs/plans/` directory deprecated. Backlog (`docs/backlog/`) is now the implementation source. Three-step loop simplified to: pull latest + pick milestone → implement ticket-by-ticket → milestone PR + demo. | @abdurrehman (with Claude) |