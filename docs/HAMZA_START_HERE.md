# Hamza — start here

**Read this once.** It tells you what to do, in what order. Everything else is a pointer.

Time to read this file: **5 minutes.**

---

## 0. Before anything else: install and clone

Follow `docs/runbooks/local-dev-setup.md` to:

1. Install prerequisites (Docker Desktop, pnpm, uv, git, your editor).
2. Clone the repo.
3. Bring up the local stack.
4. Verify everything is working at `localhost`.

If you hit any step that fails, paste the error to Claude Code and ask. Don't push through silently.

---

## 1. Read these three docs, in this exact order

Take ~30 minutes total. Don't skim.

| # | File | What it tells you |
|---|---|---|
| 1 | `.claude/CLAUDE.md` | The rules Claude Code follows. Read so you know what Claude Code will and won't do. |
| 2 | `docs/WORKFLOW.md` | The pull-latest → pick milestone → implement loop. **This is how we build every feature.** No exceptions. |
| 3 | `docs/STACK_LOCK.md` | The tech stack. Skim Section 1-3 carefully, glance at the rest. |

Then skim:
- `docs/backlog/README.md` — how the implementation backlog works (3 min)
- `docs/backlog/ROADMAP.md` — the milestone map (2 min)

**Do NOT read `docs/ARCHITECTURE.md` cover to cover.** It's ~9,800 lines. Reading it all is a waste — Claude Code reads only the sections needed per task, guided by ARCHITECTURE.md §0 (the Quick Index). You should know §0 exists, but you don't read the document by hand.

---

## 1.1 Claude Code model + effort settings (one-time)

Use **Opus 4.8** as your default model (`/model claude-opus-4-8` in Claude Code). It's a drop-in replacement for 4.7 at the same price, with two things that matter for our workflow: (a) it's roughly 4× less likely to let flaws in its own code slip past unmentioned — it surfaces uncertainty instead of confidently guessing — which fits the new "flag uncertainty rather than guess" rule in `.claude/CLAUDE.md`; (b) better agentic coding, especially on multi-file vertical slices (i.e. our tickets). Leave Claude Code on its default effort level for routine tickets. For genuinely hard tickets — RAG pipelines, complex migrations, anything touching `app/infrastructure/{rag,ml,llm,voice}/`, or the heaviest tickets in M-09+ (e.g. T-116, T-121) — use `/effort xhigh` at the start of the session for that ticket; revert afterwards. Skip Claude Code's `/fast` mode for our work — speed isn't worth the quality drop on architecture-critical code.

---

## 2. The loop you'll repeat for every milestone

```
0. PULL LATEST
   `git checkout staging && git pull origin staging`
   Always pull before opening a new Claude Code session — specs and the
   backlog are living documents.

1. PICK A MILESTONE
   Open `docs/backlog/ROADMAP.md`.
   Find the next milestone with status `todo`, not `blocked`, lowest M-NN.
   Open its file (e.g., `docs/backlog/M-03-grade-section-subject.md`).
   Create a milestone branch:
     `git checkout -b milestone/M-03-grade-section-subject`

2. IMPLEMENT TICKET BY TICKET
   For each ticket in the milestone (in order):
     Ask Claude Code:
       "Implement T-XXX per docs/backlog/M-NN-*.md"

     → Claude reads:
         - The ticket file
         - The cited spec sections (line-range reads, not whole files)
         - The cited ARCH subsections
         - Relevant skills (frontend-master, stack-enforcer, etc.)
     → Claude implements backend + frontend + migrations + tests
       per the ticket's acceptance criteria.
     → You review the changes.
     → Commit with message: `feat(scope): description (T-XXX)`
     → Mark ticket status `done` in the milestone file.
     → Commit: `chore(backlog): mark T-XXX done`
     → Move to next ticket.

3. MILESTONE PR + DEMO
   When ALL tickets in the milestone are `done`:
     → Record a 5-7 min demo video showing the milestone's acceptance flow.
     → Open ONE PR for the whole milestone branch (tickets = commits).
     → PR title: `feat(milestone): M-NN — <short name>`
     → Abd. reviews + comments "APPROVED <YYYY-MM-DD>" + merges.
     → Update `docs/backlog/ROADMAP.md` — milestone status → `done`.
     → Back to step 0 for the next milestone.
```

That's it. The loop is the same every milestone.

**Important separation of concerns:**

| Doc | What it answers | Who writes it |
|---|---|---|
| `docs/feature-specs/<flow>.md` | WHAT this workflow does (business rules) | Abd. + Awais (chat sessions), BEFORE backlog tickets reference it |
| `docs/backlog/M-NN-*.md` | HOW IT'S BUILT — atomized tickets, sequenced, with spec citations | Abd. + Claude (chat sessions), reviewed before milestone work starts |
| `docs/backlog/ROADMAP.md` | WHEN — the milestone calendar | Abd., updated as milestones complete |
| `docs/ARCHITECTURE.md` | TECHNICAL HOW (patterns, infra, conventions) | Abd., already locked; changes via AMENDMENTS.md |

If you're reading a flow spec and notice missing business rules: don't make up answers. Stop and ask Abd. The flow spec is the source of truth for what the workflow should do. If a TICKET references a spec section that doesn't exist or is unclear, also stop — the ticket cannot be implemented until the spec is finalized.

---

## 3. When something doesn't fit the rules

Three situations come up often. Use the right escape hatch — never silently work around.

| Situation | What you do |
|---|---|
| You want a library not in `STACK_LOCK.md` | **Don't use it without asking.** Either: (a) find an alternative that IS locked, or (b) ask Abd. for a deviation. Document the approved deviation in `docs/DEVIATIONS.md`. |
| The architecture doc says X but reality shows X is wrong | **Don't quietly do Y.** Open a PR to `docs/AMENDMENTS.md` explaining what changed and why. Get Abd.'s approval. Update ARCHITECTURE.md in the same PR. |
| A pre-commit check fails | **Read the error.** It points to the rule you broke. Fix it. Don't use `--no-verify`. If the check itself is wrong, that's a bug — tell Abd. |
| You're stuck on a runbook step for >15 minutes | **Paste the error to Claude Code.** It can read the runbook + ARCHITECTURE for you and tell you the next step. If Claude can't help, tell Abd. |
| A flow spec changes mid-milestone | **Stop coding. Ping Abd.** Per WORKFLOW.md §0a. Never silently keep coding against an outdated spec. |
| A ticket cites a flow spec that doesn't exist | **Stop. Mark ticket BLOCKED.** Skip to next unblocked ticket OR tell Abd. so the spec can be drafted. |

**Locked rule:** never silently bypass a check, a rule, or a doc. Either follow it, or formally propose changing it. The amendments and deviations processes exist so you can push back without going rogue.

### 3.1 Two tenant types — what this means for your code

The system has **two tenant types** that share infrastructure but are isolated at the DB level:

- **`school` tenant** — schools, districts, and all hierarchy users (Platform Admin, District Admin, School Admin, Coordinator, Teacher, Student, Parent). The default. Most milestone work is here.
- **`independent` tenant** — Independent Teachers + Independent Students who self-sign up. Separate Postgres schema (per ARCH §3.16 + §4.21).

**What this means when you write code:**
- Every flow spec + every ticket tells you which tenant(s) the feature serves. Read it.
- Repositories use SQLAlchemy `schema_translate_map` based on JWT `tenant_type` claim — handled by the framework, you usually don't touch it.
- Migrations have branch labels: `branch_labels = ('school',)` or `branch_labels = ('independent',)` — choose correctly per the spec + ticket.
- Cross-tenant operations are forbidden except for Platform Admin (per ARCH §6.10). Never write a repository method that joins across schemas.

If you're not sure which tenant a feature belongs to — the flow spec answers it. If still unclear, ask Abd.

---

## 4. What Claude Code does for you vs. what you do yourself

| Claude Code does | You do |
|---|---|
| Generates phase plans following the WORKFLOW template | Reviews the plan's reasoning before opening the PR |
| Reads ARCHITECTURE.md §0 + the right sections per task | Reviews PRs before pushing them |
| Writes backend + frontend feature code following the locked patterns | Runs commands locally (the runbooks tell you which) |
| Writes Alembic migrations | Inspects migrations before they merge (the auto-generate isn't perfect) |
| Writes tests alongside features | Watches CI; fixes anything red |
| Fills in the PR template honestly | Pushes the actual PR, responds to review comments |
| Generates docs/runbooks/ entries when alerts fire | SSHes into the VM and runs deploy commands |
| Explains errors and proposes fixes | Decides when to ask for help vs. dig in |

**You are NOT writing line-by-line code by hand.** You direct Claude Code, review its output, and ship it. The thinking is yours; the typing is Claude's.

**Expectation about frontend appearance:** until the design system PR lands (planned for after Hamza onboarding completes), the frontend will look generic — clean shadcn defaults with our tokens, but no distinctive brand polish. That's intentional. We ship vertical slices (backend + frontend per feature) and polish the visual layer after the design system. Don't try to invent custom styling to make it "look better" before then; you'll have to redo it. Follow the locked patterns; the polish pass is logged in `docs/TODO.md`.

---

## 5. The five things that go wrong most often

These are the recurring traps from earlier projects. If you see them, you're off the rails.

1. **Building without a plan.** "I'll just add this small thing real quick." No. Plan → review → implement. Even small things.
2. **Reading all of ARCHITECTURE.md.** It's huge. §0 tells you what to read. Trust §0.
3. **Skipping the four UI states.** Every screen has loading / empty / error / success. The `phase-complete-review` skill (when we ship it) catches this. Better to do it right the first time.
4. **Skipping translation keys.** Hardcoded English in JSX is forbidden. Always `t("key")`. The i18n CI check catches this.
5. **Bypassing the LLM or voice abstraction.** All LLM calls go through `app/infrastructure/llm/client.py`. All TTS/STT through `app/infrastructure/voice/`. Pre-commit catches direct imports.

If you find yourself doing any of these, stop, undo, do it right. Faster than fixing it after a failed review.

---

## 6. Your communication with Abd.

**WhatsApp** — urgent questions, deploy issues, "I'm stuck."

**PR comments / GitHub** — normal review back-and-forth.

**Don't:**
- Save up a week of questions and dump them on Friday.
- Silently work around a rule and hope Abd. doesn't notice.
- Ship something to staging without your PR being approved.
- Touch `main` directly. Ever.

**Do:**
- Ask early when you're unsure.
- Push back if a rule genuinely doesn't work — use `docs/AMENDMENTS.md`.
- Ping Abd. when CI is green and you need a review.

---

## 7. Where everything lives

```
.claude/
├── CLAUDE.md             — Claude Code's rules
└── skills/               — three project skills (stack-enforcer, frontend-master,
                            phase-complete-review). Claude Code uses them automatically.
docs/
├── STACK_LOCK.md         — locked tech stack
├── ARCHITECTURE.md       — system design (read §0 only; §0 tells you what else)
├── WORKFLOW.md           — the plan → review → implement loop
├── BRANCHING.md          — branch & PR rules
├── DEVIATIONS.md         — approved exceptions to STACK_LOCK
├── AMENDMENTS.md         — architecture changes we approved after launch
├── TODO.md               — Phase 2+ deferred work
├── ENV_VARS.md           — every env var (kept in sync with app/config.py)
├── feature-specs/        — business rules per FLOW (Abd. + Awais write & approve)
│   ├── README.md         —   how this folder works (flow-based, not feature-based)
│   ├── _TEMPLATE.md      —   the locked structure for new specs
│   ├── flow-1-*.md       —   one per flow; each flow covers 4-19 v2 features
│   └── flow-13-*.md
├── backlog/              — implementation tickets (Abd. + Claude write; Hamza reads & implements)
│   ├── README.md         —   how the backlog works
│   ├── ROADMAP.md        —   milestone overview; current state of work
│   ├── _TEMPLATE_TICKET.md — ticket structure
│   └── M-NN-*.md         —   one file per milestone; tickets sequenced inside
└── runbooks/             — ops procedures (most are stubs at launch; populated
                            as alerts fire — see runbooks/README.md)
scripts/
├── check_stack_lock.py   — pre-commit: forbidden imports
├── check_imports.py      — pre-commit: import style
└── check_envvars.py      — pre-commit: hardcoded secrets
.github/
├── CODEOWNERS
├── PULL_REQUEST_TEMPLATE.md
└── workflows/            — CI/CD
```

---

## 8. The first time you sit down to write code

1. Run through `docs/runbooks/local-dev-setup.md` end-to-end. Don't write code until your local stack is up.
2. `git checkout staging && git pull origin staging` — always pull latest.
3. Open `docs/backlog/ROADMAP.md`. The first milestone is **M-00 — Foundation**. Open `docs/backlog/M-00-foundation.md` and read the goal + ticket list.
4. Create your milestone branch: `git checkout -b milestone/M-00-foundation`
5. Open Claude Code. Say:
   *"Read CLAUDE.md, STACK_LOCK.md, ARCHITECTURE.md §0 Quick Index, WORKFLOW.md, docs/backlog/README.md. Then implement T-001 per `docs/backlog/M-00-foundation.md`."*
6. Claude reads the ticket + cited specs + cited ARCH sections + relevant skills + writes code.
7. Review the changes. Commit with: `feat(scope): description (T-001)` then `chore(backlog): mark T-001 done`.
8. Next ticket: "Implement T-002 per `docs/backlog/M-00-foundation.md`."
9. Repeat until ALL M-00 tickets are done.
10. Record a 5-min demo video. Open ONE PR for the whole milestone branch titled `feat(milestone): M-00 — Foundation`.
11. Tell Abd. the PR is ready for review.

That's your first milestone. Everything after that is the same loop, milestone by milestone.

---

**Welcome aboard. The rules are strict, but they're there to make sure we ship something that lasts. Push back when something's wrong; use the right channels.**

---

**Last updated:** 2026-05-12
**Owner:** @abdurrehman-tahir