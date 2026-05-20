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

Three skills are installed at `.claude/skills/`. Each has a YAML-frontmatter description that tells you when to apply it. Read the SKILL.md when its trigger conditions match what you're doing.

| Skill | Apply when |
|---|---|
| **stack-enforcer** | Before writing or modifying ANY backend Python file under `api/app/`, before adding a dependency, before importing anything that touches an external service. Catches forbidden imports, layer-purity violations, and abstraction bypasses. |
| **frontend-master** | Before writing or modifying ANY `.tsx` file under `frontend/src/`, before adding a frontend dependency, before writing a form, before any data-fetching component. Enforces the four UI states, accessibility, design tokens, i18n keys, Server-Component-first, RTL-aware utilities. |
| **phase-complete-review** | At the END of feature implementation, BEFORE opening a PR for Abd.'s review. Audits the PR's declared "Sections read" against the actual file changes, then runs section-specific checklists (multi-tenancy, schema, API design, auth, RAG, LLM, events, tasks, uploads, frontend, observability, deployment). |

**Skill priority over body rules:** when the body of this CLAUDE.md and a skill's SKILL.md both speak to the same concern, the skill's guidance is more specific and wins. The body rules below remain in force as the default; the skills add depth.

## Critical: read these BEFORE writing any code

Before generating any code, before scaffolding, before installing any package, you MUST read:

1. **`docs/STACK_LOCK.md`** — The non-negotiable technology stack. Every library, service, and tool you use must appear here. If a library is not in `STACK_LOCK.md`, you are forbidden from using it unless an explicit deviation exists in `docs/DEVIATIONS.md`.
2. **`docs/ARCHITECTURE.md` §0 Quick Index** — then the specific sections §0 lists for your task. **Never read the full file.** If a section is needed because of a cross-reference, read that one too.
3. **`docs/WORKFLOW.md`** — **The only way features get built.** Every milestone follows this exact loop: pull latest → pick milestone → implement ticket-by-ticket → milestone PR + demo. **Tickets atomize the work — no feature is built outside its ticket.**
4. **`docs/DEVIATIONS.md`** — Approved exceptions to `STACK_LOCK.md`. Read this to know what's been pre-approved.
5. **`docs/AMENDMENTS.md`** — Architecture decisions that have been **changed** since launch. If something in ARCHITECTURE.md is amended, this file says so. **Always check AMENDMENTS.md before treating an ARCHITECTURE.md section as authoritative.**
6. **`docs/feature-specs/<flow>.md`** — When implementing or modifying a feature, the business rules live here, organized by FLOW (not per individual feature). A ticket cites which flow + section. **If the cited flow spec doesn't exist, STOP** — the ticket is blocked. See `docs/feature-specs/README.md` for the system.
7. **`docs/backlog/`** — The implementation backlog. Tickets are the unit of work. Hamza asks you to implement a specific ticket (T-NNN); you read the ticket's `Spec source:` + `ARCH source:` citations and implement. See `docs/backlog/README.md`.
8. **`docs/BRANCHING.md`** — How branches, PRs, and merges work. Follow exactly.
9. **`docs/TODO.md`** — Deferred work. Anything explicitly deferred lives here. Do not implement deferred items unless explicitly asked.
10. **`docs/ENV_VARS.md`** — Canonical env var reference. Before introducing a new env var, check here. New env vars require an entry in this file + `api/app/config.py` + `.env.example`.

If any of these files is missing, stop and tell the user. Do not improvise.

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

1. **Hamza tells you which ticket to implement** (e.g., "Implement T-016 per docs/backlog/M-01-platform-setup.md").
2. **Read the ticket file** — its `Spec source:` (flow spec sections to read), `ARCH source:` (ARCHITECTURE subsections), `Depends on:` (prior tickets — verify they're done), `Acceptance:` (demo script you must satisfy).
3. **Read cited sections only** — use line-range `view` for spec sections; never read whole flow specs or whole ARCHITECTURE.md. Per the §0 rule.
4. **Read relevant skills** — `frontend-master` if the ticket has UI; `stack-enforcer` always; `phase-complete-review` checklist N (spec-set additions) where applicable.
5. **Implement** — backend + frontend + migrations + tests as the ticket specifies. A ticket is a vertical slice.
6. **Verify acceptance** — each step in the ticket's `Acceptance:` block must be checkable.

**Never:**
- Implement work without a ticket reference
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

## Coding conventions

- **Python:** Python 3.12, async/await everywhere, type hints on every function signature, Pydantic v2 for all I/O models. Format with `ruff format`. Lint with `ruff check`. Type-check with `mypy --strict`.
- **TypeScript:** strict mode, no `any`, prefer functional components, hooks for state, server components by default in Next.js App Router.
- **File naming:** snake_case for Python files, kebab-case for TypeScript files, PascalCase for React components.
- **Folder structure:** locked in `docs/ARCHITECTURE.md` §2. Don't create new top-level folders without asking.
- **Tests:** pytest for backend, with at minimum a happy-path test and one failure-mode test per service function. Coverage target 70% for `app/features/<feature>/`.

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
- You'd be touching more than 5 files in a single change.
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

- **Phase:** Architecture complete. `STACK_LOCK.md`, `ARCHITECTURE.md` (16 sections), `WORKFLOW.md`, `BRANCHING.md`, `DEVIATIONS.md`, `AMENDMENTS.md`, `TODO.md`, this file, and the enforcement scripts exist.
- **Next milestone:** Phase 1 implementation plan (generated by Claude Code per WORKFLOW.md Step 1), then reviewed by Abd., then implementation.

## Behavioral rules

- **No hallucinated APIs.** If you don't know how a library works, read the docs or ask the user. Do not invent function signatures.
- **No "TODO" placeholders in committed code.** If you can't implement something now, raise the gap in the PR description and let the user decide.
- **No commented-out code.** If it's not used, delete it.
- **No `print()` for debugging.** Use `structlog` per ARCHITECTURE.md §16.6.
- **No silently catching exceptions.** Log + re-raise, or handle deliberately with a comment explaining why.
- **No bypassing the LLM abstraction.** All LLM calls go through `app/infrastructure/llm/client.py`. Never `import openai`, `import anthropic`, `import groq` outside that file.
- **No bypassing the voice abstraction.** All TTS/STT goes through `app/infrastructure/voice/router.py`.
- **No reading all of ARCHITECTURE.md.** Follow §0.

## Acknowledgment

When you start a session, your first message should confirm:

> "I've read CLAUDE.md, STACK_LOCK.md, ARCHITECTURE.md §0 (Quick Index), WORKFLOW.md, DEVIATIONS.md, AMENDMENTS.md, BRANCHING.md. For this task ('<task summary>'), §0 directs me to read: [list sections]. If implementing a feature, I'll also read its `docs/feature-specs/<feature>.md`. Reading those now."

Then proceed.

---

**Last updated:** 2026-05-12
**Owner:** @abdurrehman-tahir
