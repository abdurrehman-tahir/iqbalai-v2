# CLAUDE.md

**You are working on IqbalAI v2.** This file is read automatically at the start of every Claude Code session and after every context compaction. Read it carefully. The rules below are non-negotiable.

## The §0 rule — the single most important reading rule

`docs/ARCHITECTURE.md` is ~8,800 lines. You do **NOT** read it cover-to-cover. Doing so wastes context and produces drift.

**Instead:**

1. Read `docs/ARCHITECTURE.md` **§0 Quick Index** first. It's a table mapping tasks → required sections.
2. Find your task in §0.1's table.
3. Read **only the sections listed for your task** — plus §0 itself.
4. Follow cross-references (`see §X`) only when actually needed.
5. **Track the sections you read.** They go in the PR description under "Sections read from ARCHITECTURE.md" — required by WORKFLOW.md §1.4.

If your task isn't in §0.1: read §0.2 (it tells you what to do). Often the answer is "ask Abd."

## The three project skills — when each fires

Three skills are installed at `.claude/skills/`. **Skills are heavy — read each SKILL.md ONLY when its narrow trigger truly fires.** Pre-commit hooks + CI catch any forbidden imports / stack violations regardless, so a missed trigger costs a re-commit, not a shipped bug.

| Skill | Apply ONLY when |
|---|---|
| **stack-enforcer** | The change does **at least one** of: (a) adds/modifies a Python import that resolves OUTSIDE the standard library; (b) adds a new dependency to `pyproject.toml`; (c) touches any file under `app/infrastructure/{rag,ml,llm,voice,storage,events,cache}/`. Do NOT load it for routine route/repo/schema/test files that only use standard library + already-approved deps. |
| **frontend-master** | The change touches `.tsx` under `frontend/src/` AND is doing one of: writing a form, a data-fetching component, an accessibility-sensitive interaction, a new visible page/screen, or adding a frontend dependency. Trivial label/text edits do NOT trigger it. |
| **phase-complete-review** | At PR time only — load this skill before opening the milestone PR. (It's the heaviest skill at 448 lines; it loads once per milestone at PR time, not per ticket.) |

**Skill priority over body rules:** when the body of this CLAUDE.md and a skill's SKILL.md both speak to the same concern, the skill's guidance is more specific and wins. The body rules below remain in force as the default; the skills add depth.

## Sub-agents — your first action on any ticket

Claude Code can spawn **sub-agents** that run in their own context window and return only a compact result to this main session. Use them to keep the main context lean. The agents live in `.claude/agents/`.

**MANDATORY first action when implementing any ticket:** when Hamza says any variant of `"Implement T-XXX"` (with or without a milestone path), your FIRST action — before any file read, any plan, any code — is to invoke the **`ticket-loader`** sub-agent:

> Use the `ticket-loader` agent to prepare ticket T-XXX.

The sub-agent locates the ticket, reads the cited spec § + cited ARCH §§ in its own context, and returns a compact **Ticket Dossier** (ticket body, rule excerpts, ARCH summaries, deps, acceptance criteria) to you. From that point you work from the dossier. **Reading the full milestone file, the full flow spec, or wide ranges of ARCHITECTURE.md directly in this main session is forbidden** — the only exception is following a specific cross-reference the dossier explicitly flagged. If the dossier is malformed or missing a field, abort and tell Hamza; do not paper over it by reading the source files yourself.

Other available sub-agents (use when relevant):

| Sub-agent | Use when |
|---|---|
| `ticket-loader` | MANDATORY first action on any "Implement T-XXX" request (above). |

**Prefer sub-agents / dynamic workflows for parallel exploration.** Opus 4.8 ships with dynamic workflows in Claude Code — if a task has multiple independent searches, audits, or extractions to do (e.g. "find every place a deprecated API is used," "verify acceptance items 1-8 in parallel"), spawn sub-agents/workflows instead of doing them serially in the main session. Each sub-agent runs in its own context and returns only the result.

## Session-state recovery (compaction)

This main session may be auto-compacted mid-work. To recover cleanly without re-reading everything, maintain `.claude/session-state.md` — a short file (≤30 lines) you update after each meaningful step (ticket loaded, file edited, tests written, commit made). Format: current ticket ID, status, last file edited, next intended step, dossier-source list. After a compaction, read this file first; it replaces the need to re-fetch the milestone/spec/ARCH from scratch.

## What to read — and when (conditional, not pre-loaded)

The ONLY files you load at session start are this CLAUDE.md (auto) and `docs/ARCHITECTURE.md` §0 (the task→sections quick-index). Every other reference doc is loaded **conditionally**, the moment its concern triggers — never pre-emptively. This keeps the main context lean and is essential for fitting a milestone's worth of tickets in one Claude Code session.

| File | Read only when |
|---|---|
| `docs/STACK_LOCK.md` | About to add/modify a dependency, an import touching an external service, or any change under `app/infrastructure/{rag,ml,llm,voice,storage,events,cache}/`. Otherwise: don't load it. (Pre-commit `check_imports.py` + `check_stack_lock.py` enforce it on every commit regardless.) |
| `docs/WORKFLOW.md` | Hamza's very first day, OR you can't recall a specific process step. The day-to-day loop is summarized in this CLAUDE.md ("Workflow you must follow" below). Don't reload WORKFLOW per ticket. |
| `docs/DEVIATIONS.md` | You're reading STACK_LOCK and you notice a possible deviation. Otherwise skip. |
| `docs/AMENDMENTS.md` | About to follow an ARCH § as authoritative — sanity-check it isn't amended. Use grep for the §-number rather than reading the whole file. |
| `docs/BRANCHING.md` | At PR time, or naming a feature branch. |
| `docs/ENV_VARS.md` | About to add or use a new env var. |
| `docs/TODO.md` | A feature seems missing or deferred — confirm before improvising. |
| `docs/feature-specs/<flow>.md` | The dossier (from `ticket-loader`) cites it AND the excerpt the dossier returned is insufficient — read only the cited section via line-range, never the whole file. |
| `docs/backlog/M-NN-*.md` | The `ticket-loader` sub-agent reads this for you. Reading it directly in the main session is forbidden (see "Sub-agents" below). |

**ARCHITECTURE.md is governed separately by the §0 rule above — read §0 + cited §§ only, never the whole file.**

## Two tenant types — fundamental architecture you must understand

IqbalAI runs **two distinct tenant types** in the same DB instance with separate Postgres schemas:

1. **`school` tenant** — the default. All hierarchy users (Platform Admin, District Admin, School Admin, Coordinator, Teacher, Student, Parent) live here. Per ARCH §3.16.
2. **`independent` tenant** — separate Postgres schema. Independent Teachers + Independent Students who self-sign up via `/independent/signup`. No school context. Each user is effectively their own micro-tenant.

This split affects EVERYTHING:
- DB schema (per ARCH §4.21 dual Alembic heads — `school` and `independent` branches)
- Authentik JWT claims (`tenant_type` field routes to correct schema)
- Repositories (use `schema_translate_map` based on JWT tenant_type)
- Cross-tenant operations forbidden except for Platform Admin (per ARCH §6.10)
- Feature specs always specify which tenant(s) apply

**When writing any feature code:** identify which tenant(s) the feature serves. School-only? Independent-only? Both? The spec tells you. The schema follows.

## Workflow you must follow (summary; full version in WORKFLOW.md)

The unit of work is a **ticket** (T-NNN) inside a **milestone** (M-NN).

1. **Hamza tells you which ticket to implement** (e.g., "Implement T-016").
2. **Your literal first action: invoke the `ticket-loader` sub-agent** with the ticket ID. The sub-agent returns a compact Ticket Dossier (ticket body, cited spec excerpts, ARCH summaries, deps, acceptance). Do NOT read the milestone / spec / ARCH directly in this main session.
3. **Verify deps:** the dossier lists `Depends on:` — confirm those tickets are marked done before proceeding.
4. **Read narrow skills only if their trigger fires** (see skill table above). Update `.claude/session-state.md` with the ticket ID + intended next step.
5. **Implement** — backend + frontend + migrations + tests as the ticket specifies. A ticket is a vertical slice.
6. **Verify acceptance** — each item in the dossier's `Acceptance:` block must be checkable.
7. **Run the format gate before committing** (see "Format gate" below). Then commit per Conventional Commits.
8. **Close out the ticket (mandatory, every ticket — not just at milestone close):** in the milestone file, set that ticket's `Status: done` and record the commit SHA on the ticket. Then update `.claude/session-state.md` (done list + next ticket). The milestone file is the durable per-ticket ledger; `session-state.md` is the fast within-session hint.

**Never:**
- Implement work without a ticket reference
- Read whole milestone files, whole flow specs, or wide ARCH ranges in the main session (use `ticket-loader`)
- Re-read whole ARCHITECTURE.md (use §0 + cited subsections only)
- Skip writing tests (tests live with the ticket)
- Modify a spec to match your code (code follows spec; spec changes via Awais + Abd. review first)

If Hamza asks you to "just build milestone X" without picking a specific ticket, **start with T-NNN at the top of the milestone file**. If he asks to skip the backlog and "just implement Flow 5" or "just build Phase 1," **refuse** and refer him to WORKFLOW.md.

## How decisions are made in this project

- **Locked items** in `STACK_LOCK.md` are non-negotiable. Use them exactly. Do not suggest alternatives.
- **Default items** in `STACK_LOCK.md` should be used unless an approved deviation exists.
- **Forbidden items** in `STACK_LOCK.md` Section 9 must NEVER be imported. Pre-commit hooks will reject commits that violate this.
- **Architecture decisions in ARCHITECTURE.md** are locked unless an entry exists in `docs/AMENDMENTS.md`. When something feels wrong, propose an amendment — don't silently work around it.
- **Open architecture questions** (`STACK_LOCK.md` Section 10): stop and ask the user before implementing. Do not pick a default.

## Decision-making behavior you must follow

When the user asks for a feature:

1. **Find your task in `ARCHITECTURE.md` §0.1.** Read only the listed sections, plus §0.
2. **Plan before coding.** State which files you will create or modify, which libraries from `STACK_LOCK.md` you will use, and what test coverage you will add. Wait for the user to confirm before generating code if the change touches more than one module.
3. **Use ONLY libraries listed in `STACK_LOCK.md`.** If a feature seems to need a library not in the stack, stop and ask the user. Do not propose adding a new dependency on your own initiative.
4. **Every new Python file's imports are verified against `STACK_LOCK.md` Section 9.** If you find yourself wanting to import something from the forbidden list, stop and tell the user.
5. **Every new component/screen uses shadcn/ui + Tailwind tokens.** No inline styles. No raw CSS. No new UI libraries.
6. **Every API endpoint has:** a Pydantic request model, a Pydantic response model, an access dependency (`require_role` etc.), error handling via the locked codes, structured logging, OpenAPI metadata.
7. **Every UI component has:** loading state, empty state, error state, success/idle state. No exceptions (§12.8).
8. **Every visible string in the frontend** goes through `next-intl` translation keys. Never hardcode English in JSX.
9. **Every secret or external URL** is read from an env var. Never hardcode.
10. **Every database schema change** has an Alembic migration in the same PR.

## CI invariants (non-negotiable)

`.github/workflows/*.yml` evolves as the codebase grows — you may amend it — but these rules are hard and must hold in every PR that touches CI:

1. **Dev dependencies are installed before any tool runs.** Every lint / test / type-check / coverage job MUST sync the dev dependency group BEFORE invoking the tool. For Python: a `uv sync` step that includes the dev group/extras (e.g. `uv sync --all-extras --dev`, or the named group your `pyproject.toml` declares) precedes any `uv run ruff|pytest|mypy`. For frontend: `pnpm install` against a real `frontend/package.json` precedes any `pnpm lint|test|build|typecheck`. A job that calls `ruff`/`pytest`/`mypy`/`eslint`/`vitest` without first installing it is broken — the `Failed to spawn: ruff` / `No such file or directory` class of error means this rule was violated.
2. **Job commands match the manifest exactly.** Script and command names invoked in CI MUST match exactly what `pyproject.toml` and `frontend/package.json` declare (same group/extras names, same `scripts` keys, same paths). If you rename a script or change a dependency group, update CI in the same PR.
3. **Edit, don't wholesale-replace.** Never regenerate `.github/workflows/*.yml` from scratch. Amend the existing file. Wholesale regeneration is how invariants silently get dropped.
4. **Frontend jobs guard on `frontend/` existing** via a post-checkout detect step that sets an output, NOT a job-level `if: hashFiles(...)` (which fails to parse — `hashFiles` is unavailable before checkout). Gate the real steps on the detect output.
5. **Any CI change is called out in the PR description.** If a PR touches `.github/workflows/`, say so explicitly and state what changed and why.
6. **Lint/format/type tool versions are identical across pre-commit, `uv run`, and CI.** The ruff / mypy / prettier versions pinned in `.pre-commit-config.yaml`, resolved by `uv run` (via `pyproject.toml`), and used in CI MUST be the same (per STACK_LOCK §8). A version mismatch means local autofix and CI disagree on formatting → the write→CI-fail→reformat churn loop. If you bump a tool version, bump it in all three places in the same PR.

## Coding conventions

- **Python:** Python 3.12, async/await everywhere, type hints on every function signature, Pydantic v2 for all I/O models. Format with `ruff format`. Lint with `ruff check`. Type-check with `mypy --strict`. **Concrete style (write to these so the formatter barely changes your output):** line length 100; double quotes; sorted imports (ruff isort, first-party `app`); trailing commas in multi-line collections; no `print()` (use `structlog`). The authoritative rule set + tool versions live in `pyproject.toml` and are pinned identically to `.pre-commit-config.yaml` and CI (see STACK_LOCK §8) — when in doubt, run the format gate below and let it settle.
- **TypeScript:** strict mode, no `any`, prefer functional components, hooks for state, server components by default in Next.js App Router. Format with `prettier`; lint with `eslint`.
- **File naming:** snake_case for Python files, kebab-case for TypeScript files, PascalCase for React components.
- **Folder structure:** locked in `docs/ARCHITECTURE.md` §2. Don't create new top-level folders without asking.
- **Tests:** pytest for backend, with at minimum a happy-path test and one failure-mode test per service function. Coverage target 70% for `app/features/<feature>/`.

## Format gate — run before EVERY commit (non-negotiable)

Code is written *to* the rules and formatted *before* committing — never written blind and reformatted after CI fails. Before every commit, run the SAME commands CI runs, in this order, and commit the settled result:

```bash
# Backend
uv run ruff format .
uv run ruff check --fix .
uv run mypy --strict app/
# Frontend (if frontend/ changed)
pnpm --dir frontend format
pnpm --dir frontend lint
```

Because `pyproject.toml`, `.pre-commit-config.yaml`, and CI all pin the **same** ruff/mypy/prettier versions + config (STACK_LOCK §8), the output of these commands is byte-identical to what CI checks — so if the gate passes locally, CI's format/lint checks pass. Pre-commit hooks run the same tools on `git commit`; do NOT bypass them with `--no-verify`. If you ever see CI reformat code that passed locally, the versions have drifted — fix the version alignment, don't hand-patch the formatting.

## Git workflow

- Base branch: `staging` (see `docs/BRANCHING.md`).
- Feature branches: `feature/phase<N>-<short-name>`.
- Commit format: Conventional Commits. Commits that touch files in `app/infrastructure/rag/`, `app/infrastructure/ml/`, `app/infrastructure/llm/`, or `app/infrastructure/voice/` MUST include a `## Stack-touching` block in the commit message listing the architecture decisions referenced.
- One PR = one logical change. Don't bundle.
- Open PRs with `gh pr create --base staging`.
- Auto-fill the PR template (`.github/PULL_REQUEST_TEMPLATE.md`) honestly. Don't tick boxes you didn't actually verify.
- **PR description MUST include a "Sections read from ARCHITECTURE.md" list** per WORKFLOW.md §1.3.

## Pre-commit hooks

The repo has pre-commit hooks installed (`pre-commit install`). They run automatically on `git commit`. If they fail:

1. Read the error carefully.
2. Fix the issue (do NOT skip with `--no-verify`).
3. Stage the fix and re-commit.

The hooks include:
- `ruff` — lint and format
- `mypy` — strict type check
- `scripts/check_imports.py` — verifies imports against `STACK_LOCK.md` allowed list
- `scripts/check_envvars.py` — rejects hardcoded URLs, keys, secrets
- `scripts/check_stack_lock.py` — rejects forbidden imports (cross-references `DEVIATIONS.md` for exceptions)
- `pytest --collect-only` — tests must at least be discoverable

If you (Claude) generate code that fails these hooks, the user will see the failure. Fix it and re-commit. Don't ask the user to disable hooks.

## When to ask for help

Stop and ask the user when:
- A feature seems to require a library not in `STACK_LOCK.md`.
- A pattern in `ARCHITECTURE.md` would need to be **changed** (not just followed) to ship the feature — propose an amendment via `docs/AMENDMENTS.md`.
- Your task isn't in `ARCHITECTURE.md` §0.1's task table and you're unsure which sections apply.
- A pre-commit hook fails in a way that suggests the stack itself needs revision (rare).
- You'd be touching more than 5 files in a single change AND the changes are not a single coherent vertical slice already authorised by the ticket (Opus 4.8 self-decides well on coherent changes — don't ask for permission on routine ticket implementation).
- You'd be modifying `docs/STACK_LOCK.md`, `docs/ARCHITECTURE.md`, `docs/DEVIATIONS.md`, `docs/AMENDMENTS.md`, or `docs/BRANCHING.md`.

## When NOT to ask

Don't ask permission for:
- Following the rules in this file or in `STACK_LOCK.md`.
- Fixing a pre-commit failure.
- Adding a test alongside a feature.
- Adding a migration alongside a schema change.
- Adding a translation key when adding visible UI text.

Just do these. They're table stakes.

## Project state

- **State of truth:** `docs/backlog/ROADMAP.md` is the live source for what's done, in progress, and pending — always check it for current milestone/ticket status rather than trusting any hardcoded note here. The foundation (`STACK_LOCK.md`, `ARCHITECTURE.md`, the flow specs in `docs/feature-specs/`, `WORKFLOW.md`, `BRANCHING.md`, `DEVIATIONS.md`, `AMENDMENTS.md`, `TODO.md`, the skills, the enforcement scripts, and this file) is complete and in active use.
- **What you do:** implement the ticket Hamza names, or resume at the first not-`done` ticket of the active milestone (see "Session start"). Milestone/ticket sequencing and blocked-status live in `ROADMAP.md` + the milestone files.

## Behavioral rules

- **Flag uncertainty rather than guess.** If the ticket dossier, the cited spec, or the cited ARCH section leaves a decision genuinely ambiguous — or you're not confident about an API/signature/edge case — say so explicitly in chat and ask, rather than producing confident code that might be wrong. Opus 4.8 is specifically trained to surface uncertainty; lean into that. Unsupported claims and silently-buggy code are worse than a one-line "I'm not sure about X — confirm before I proceed."

- **No hallucinated APIs.** If you don't know how a library works, read the docs or ask the user. Do not invent function signatures.
- **No "TODO" placeholders in committed code.** If you can't implement something now, raise the gap in the PR description and let the user decide.
- **No commented-out code.** Dead code that's been replaced or disabled must be deleted, not left commented.
- **Comment the *why*, not the *what* — and comments are encouraged where they help.** Add comments at the places they genuinely add value: non-obvious decisions and trade-offs, edge-case or gotcha warnings, section dividers in long config/YAML files (e.g. `ci.yml`, `docker-compose.yml`), and references to the governing ticket / spec / ARCHITECTURE § that drove a choice. Do NOT add noise comments that merely restate what the next line obviously does. **Critically: never strip existing explanatory or section comments as a side effect of an unrelated change** (e.g. a CI fix must not delete the section-divider comments in the workflow). Only remove a comment when the code it described is itself gone. A blanket "no comments" stance is wrong — under-commenting non-obvious logic is as much a defect as over-commenting the obvious.
- **No `print()` for debugging.** Use `structlog` per ARCHITECTURE.md §16.6.
- **No silently catching exceptions.** Log + re-raise, or handle deliberately with a comment explaining why.
- **No bypassing the LLM abstraction.** All LLM calls go through `app/infrastructure/llm/client.py`. Never `import openai`, `import anthropic`, `import groq` outside that file.
- **No bypassing the voice abstraction.** All TTS/STT goes through `app/infrastructure/voice/router.py`.
- **No reading all of ARCHITECTURE.md.** Follow §0.

## Session start (silent)

At session start, this CLAUDE.md auto-loads and you read `docs/ARCHITECTURE.md` §0. **Do NOT print a confirmation message** listing what you read. **Do NOT pre-load** STACK_LOCK / WORKFLOW / DEVIATIONS / AMENDMENTS / BRANCHING / ENV_VARS — load each only when its trigger fires (table above).

**Resume rule (where to start, even if Hamza says nothing specific):** before waiting, determine the resume point — (1) read `ROADMAP.md` to find the currently-active milestone (the first not `done`); (2) read that milestone file's ticket `Status:` fields — **the first ticket not marked `done` is where you resume**; (3) `.claude/session-state.md` is a fast hint for the same thing. **If `session-state.md` and the milestone file disagree, the milestone file's `Status:` fields win** (they're the durable source of truth; session-state is only a scratchpad). If Hamza names a specific ticket, that overrides the resume point. Then your literal first action for that ticket is to invoke the `ticket-loader` sub-agent.

After a context compaction, read `.claude/session-state.md` first to recover (do NOT re-fetch the milestone/spec/ARCH from scratch).

---

**Last updated:** 2026-05-12
**Owner:** @abdurrehman-tahir