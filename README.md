# IqbalAI v2

AI-powered education platform for Pakistan's school system.

---

## Where do I start?

**If you're new here:** read [`docs/HAMZA_START_HERE.md`](docs/HAMZA_START_HERE.md) first. About 5 minutes. It tells you what to read, in what order, and what to do.

**If you want to run the code locally:** the answer depends on whether **M-00 Foundation** has been merged yet.
- **Pre-M-00:** there's nothing to run yet. Open [`docs/backlog/M-00-foundation.md`](docs/backlog/M-00-foundation.md) and implement it ticket by ticket per [`docs/WORKFLOW.md`](docs/WORKFLOW.md).
- **Post-M-00:** follow [`docs/runbooks/local-dev-setup.md`](docs/runbooks/local-dev-setup.md). `cp .env.example .env`, `docker compose up -d`, done in ~30 minutes.

**If you're directing Claude Code to implement a ticket:** Claude Code reads `.claude/CLAUDE.md` automatically. Hand it a ticket ID (e.g. `T-001`); it reads the ticket + the spec citations and implements. Tickets and PRs follow [`docs/WORKFLOW.md`](docs/WORKFLOW.md).

---

## How does work get built here?

One sentence: **flows define the rules, backlog tickets atomize the build, Claude Code implements ticket-by-ticket, Hamza opens one PR per milestone.**

Long version:
1. **Flow specs** in [`docs/feature-specs/`](docs/feature-specs/) capture business rules per user journey (Flow 1 = Platform Setup, Flow 2 = Admin/Coordinator, etc.). Reviewed by Abd. + Awais. Permanent records.
2. **Backlog tickets** in [`docs/backlog/`](docs/backlog/) atomize each milestone (M-00 Foundation, M-01 Platform Setup, M-02 School Onboarding, ...) into ~1–3 day tickets. Each ticket cites which flow spec + which ARCHITECTURE sections it implements.
3. **Hamza picks a milestone**, implements tickets one at a time with Claude Code, then opens ONE PR per milestone (not per ticket).
4. **The PR** must satisfy the milestone's "Demo at end" criteria and pass the section-tracking checks in [`docs/WORKFLOW.md`](docs/WORKFLOW.md).

The full loop is in [`docs/WORKFLOW.md`](docs/WORKFLOW.md). Don't skim it — it's the contract.

---

## Where do I find things?

| File | What it is |
|---|---|
| [`.claude/CLAUDE.md`](.claude/CLAUDE.md) | Claude Code's behavioral rules. Loaded automatically every session. |
| [`docs/STACK_LOCK.md`](docs/STACK_LOCK.md) | The locked technology stack. What we use and what's forbidden. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | The full system design (~9,700 lines). **Don't read end-to-end** — start at §0 (Quick Index), which tells you what to read for any specific task. |
| [`docs/WORKFLOW.md`](docs/WORKFLOW.md) | The pull-latest → pick-milestone → ticket-by-ticket → milestone-PR loop. Every feature follows it. |
| [`docs/HAMZA_START_HERE.md`](docs/HAMZA_START_HERE.md) | Onboarding doc for new contributors. Read this first. |
| [`docs/BRANCHING.md`](docs/BRANCHING.md) | Branch & PR rules. |
| [`docs/DEVIATIONS.md`](docs/DEVIATIONS.md) | Pre-approved exceptions to `STACK_LOCK.md`. |
| [`docs/AMENDMENTS.md`](docs/AMENDMENTS.md) | Architecture decisions changed after launch. Always check before treating ARCHITECTURE.md as final. |
| [`docs/feature-specs/`](docs/feature-specs/) | Business rules per flow (lifecycle, permissions, edge cases, limits). Written and approved by Abd. + Awais BEFORE backlog tickets reference them. Permanent records, separate review track from tickets. |
| [`docs/backlog/`](docs/backlog/) | Implementation backlog. One file per milestone (`M-NN-<slug>.md`). Tickets atomize the work. See [`docs/backlog/README.md`](docs/backlog/README.md). |
| [`docs/backlog/ROADMAP.md`](docs/backlog/ROADMAP.md) | The milestone calendar. Which milestones are ready vs blocked vs done. |
| [`docs/TODO.md`](docs/TODO.md) | Phase 2+ deferred work. Don't implement deferred items unless asked. |
| [`docs/ENV_VARS.md`](docs/ENV_VARS.md) | Every environment variable, what it does, what type, default. |
| [`docs/runbooks/`](docs/runbooks/) | Operational procedures. `local-dev-setup.md` is the daily-driver runbook. Most others are stubs that get populated as alerts fire — see [`docs/runbooks/README.md`](docs/runbooks/README.md) for the philosophy. |
| [`scripts/`](scripts/) | Enforcement scripts (run by pre-commit + CI). |
| [`.github/`](.github/) | CODEOWNERS, PR template, CI/CD workflows. |

---

## What does Claude Code do for me?

It reads tickets, reads the spec sections the ticket cites (no more, no less), writes the code, and prepares the PR. Two skills enforce quality:

- **`stack-enforcer`** — refuses to introduce libraries not in `STACK_LOCK.md`.
- **`phase-complete-review`** — runs before every PR; validates section-tracking, spec adherence, and prep work.

Hamza's role is to direct Claude Code at a ticket, review the diff before commit, and run the demo at the end of each milestone.

---

## What's NOT in this repo yet?

If you're reading this before M-00 is merged, **the following don't exist yet** (they're built by M-00 tickets):

- `api/` (the FastAPI backend)
- `frontend/` (the Next.js frontend)
- `docker-compose.yml` (the dev/staging/prod compose stack — ONE file at the repo root)
- `.env.example` (env var template at the repo root)
- `Dockerfile` files under `api/` and `frontend/`
- Database migrations

Once M-00 ships, all of these appear. Until then, this is a docs-and-skills-only repo.

---

## Conventions

- **Docker:** ONE `docker-compose.yml` at the repo root. No split into `infra.yml` / `app.yml` / `override.yml`. No `Makefile`. Raw `docker compose` commands only. (Per `ARCHITECTURE.md` §15.4.)
- **Env:** ONE `.env.example` at the repo root. No per-service env files (`api/.env`, `frontend/.env.local`). The frontend reads `NEXT_PUBLIC_*` vars from the same root file. (Per `ARCHITECTURE.md` §15.2.)
- **Branching:** `staging` is the base branch for active development. PRs target `staging`. Promotion to `main` happens per `BRANCHING.md`.

---

## Contact

- Abd. (founder, FCTO) — code owner for ARCHITECTURE, WORKFLOW, STACK_LOCK, all spec/process docs
- Hamza (team lead developer) — primary implementer
- Awais (COO) — flow spec product review
