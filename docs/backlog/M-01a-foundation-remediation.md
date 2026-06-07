# M-01a — Foundation Remediation + FE/Integration Enforcement

**Status:** drafted
**Layer:** 1
**Sequence:** after M-01, before M-02 (M-02 `Depends on` flips to M-01a)
**Ticket range:** T-223 to T-237 (off the T-222 high-water mark; **non-positional** numbering — same convention as M-22/M-23. The IDs do not need to sit between T-027 and T-028; the ROADMAP order is positional, the IDs are not.)
**One PR** (merge commit), like every milestone.

## Why this milestone exists

M-00/M-01 shipped with broken UX (admin pages unreachable — no working nav; the Authentik/bootstrap ToS rendered with no text/scroller) **even though the tickets specified those things correctly** (T-017 sidebar nav, T-019 ToS flow). Root cause was an **enforcement gap**, not a content gap: no frontend test framework existed (so `npm run test` was vacuous and broken UI passed the manual demo-script), FE types were hand-mirrored from Pydantic (so FE↔BE drift was structural — AMENDMENTS A-002), acceptance criteria were functional-not-UX-rigorous, and ticket DDL pulled implementation off the locked model-first autogenerate flow (ARCH §4.12).

M-01a closes the gap at the dependency root (only M-01 is done, so rework is cheap) and brings M-00/M-01 up to the new bar. Everything from M-02 onward inherits the gates via `.claude/CLAUDE.md` + CI — M-03→M-17 are **not** rewritten; each gets the just-in-time modernization check at its turn.

Two ticket groups: **foundation** (T-223–T-229, the new enforcement layer) then **audit-then-fix** (T-230–T-235: data+access, nav, ToS, typed client, migrations, FE tests — remediate M-00/M-01 against it); plus T-236 (container ergonomics) and T-237 (PR+demo). The audit-fix tickets write their systemic findings to `docs/AUDIT_LOG.md` at close-out, seeding the improvement loop (capture → milestone-boundary distillation, per `docs/backlog/README.md`).

---

## T-223 — Frontend test harness: Vitest + RTL + Playwright

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** done

### Spec source
- (foundation — no flow spec) STACK_LOCK §2 (FE testing row)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend architecture)
- `frontend-master/references/four_ui_states.md`

### Depends on
- (M-00 T-009 frontend skeleton)

### What this ticket builds
Vitest + React Testing Library configured for `frontend/` (jsdom env, coverage via v8, 60% target on `frontend/src/features/`). Playwright configured with a `@smoke` tag convention (smoke-on-PR, full-suite-nightly). `frontend/package.json` scripts: `test` (Vitest), `test:watch`, `e2e` (Playwright). A trivial example component test + a trivial `@smoke` E2E so the harness is provably running.

### Tests (required)
- The harness itself: one passing Vitest component test + one passing Playwright `@smoke` test (proves `pnpm test` and `pnpm e2e` are non-vacuous).

### Acceptance (demo script)
1. [ ] `pnpm test` runs Vitest + RTL, reports coverage
2. [ ] `pnpm e2e --grep @smoke` runs Playwright headless and passes
3. [ ] Coverage config enforces 60% on `frontend/src/features/`

### Out of scope
- CI wiring (T-229); backfilling tests for existing pages (T-235)

---

## T-224 — Typed API client via openapi-typescript

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** done

### Spec source
- (foundation) AMENDMENTS A-002; STACK_LOCK §2 (API types row)

### ARCH source
- `ARCHITECTURE.md` §12.4 / §12.5 (api.ts + apiClient — pattern unchanged)
- `ARCHITECTURE.md` §2.13 (deferral superseded by A-002)

### Depends on
- (M-00 backend OpenAPI)

### What this ticket builds
An offline OpenAPI export (`python -m app.openapi_export > openapi.json` — no running server) and a `frontend` `gen:api` script that runs **openapi-typescript** to produce `frontend/src/lib/api/schema.d.ts`. Feature `types.ts` files re-export request/response types from `schema.d.ts`; hand-mirrored types are removed. The locked `api.ts` client-object + TanStack Query hooks + base `apiClient` are unchanged — only the *types* feeding them become generated.

### API contract
- N/A (no new endpoints; consumes the existing OpenAPI)

### Tests (required)
- Vitest type-level test importing a generated type and asserting a known field exists (guards the generation path).

### Acceptance (demo script)
1. [ ] `pnpm gen:api` regenerates `schema.d.ts` from the live OpenAPI
2. [ ] A feature `types.ts` re-exports from `schema.d.ts`; no hand-mirrored interfaces remain
3. [ ] `apiClient` / hook signatures unchanged (no caller churn)

### Out of scope
- The CI drift check (T-229); regenerating M-00/M-01 features (T-233)

---

## T-225 — `response_model` gate + SuccessEnvelope + operation_id backfill

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** done

### Spec source
- (foundation) STACK_LOCK §1 (`response_model` mandate); CLAUDE.md CI invariant 7

### ARCH source
- `ARCHITECTURE.md` §5 (API design)

### Depends on
- (M-00/M-01 routes)

### What this ticket builds
`scripts/check_response_model.py` — fails if any FastAPI route (`@router.get/post/patch/put/delete`) lacks `response_model=` **or** `operation_id` (AST-based, not regex).

The blocker behind the M-01 `response_model=dict` violation: routes return the `success()` envelope (`dict[str, Any]`), so typed schemas (`SubscriptionTierRead`, `ExamSyllabusRead`, `PersonaRead`, `AuditLogEntryRead`, …) were never wired. Fix it properly:
- Add a generic **`SuccessEnvelope[T]`** Pydantic model in `core/responses.py` (the typed shape of `success()`), so `response_model=SuccessEnvelope[XxxRead]` is expressible.
- Rewire all ~25 M-00/M-01 routes to declare `response_model=SuccessEnvelope[…]` with the real schema (no more `dict`) — otherwise the openapi-typescript client (A-002) generates `dict` types and is worthless.
- Add **`operation_id`** to all ~30 routes across the 9 routers (clean OpenAPI method names — §5 Checklist C).

This closes the two ❌ "known violations" (response_model=dict, missing operation_id) inside M-01a rather than a follow-up ticket.

### Tests (required)
- pytest unit for the checker: a fixture route without `response_model` (or `operation_id`) fails; with both, passes.
- API contract test asserting a sample route returns the typed `SuccessEnvelope[XxxRead]` shape (not bare `dict`).

### Acceptance (demo script)
1. [ ] `python scripts/check_response_model.py` passes (every route has typed `response_model=` + `operation_id`)
2. [ ] No route uses `response_model=dict`; `SuccessEnvelope[T]` exists in `core/responses.py`
3. [ ] Generated `schema.d.ts` (T-224) shows real types (e.g. `PersonaRead`), not `dict`
4. [ ] Removing a `response_model=`/`operation_id` makes the gate fail

### Out of scope
- Wiring into CI (T-229)

---

## T-226 — Design tokens + shadcn base set

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** done (0f4081a)

### Spec source
- (foundation) STACK_LOCK §2 (design tokens — now RESOLVED to `tailwind.config.ts`)

### ARCH source
- `ARCHITECTURE.md` §12 (frontend); `frontend-master/SKILL.md`

### Depends on
- (M-00 T-009 Tailwind)

### What this ticket builds
Formalized design tokens in `tailwind.config.ts` (color scale, spacing, radius, typography scale, semantic tokens for surface/text/border). Install the shadcn base component set the admin UI uses. An ESLint/Stylelint rule (or CI grep) rejecting inline styles + ad-hoc hex. A one-screen token reference in `frontend-master` references.

### Tests (required)
- Vitest snapshot of a tokenized component rendering with token classes (no inline styles).

### Acceptance (demo script)
1. [ ] Tokens defined in `tailwind.config.ts`; components consume them (no ad-hoc hex)
2. [ ] shadcn base set present in `frontend/src/components/ui/`
3. [ ] Inline-style lint rule fails on a planted inline style

### Out of scope
- Re-skinning existing pages beyond token adoption (handled in T-231 nav fix)

---

## T-227 — App shell + role-aware nav (single shell all pages plug into)

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** done (2ddccd9)

### Spec source
- `flow-1-platform-setup.md` §2 (Platform Admin persona), §4 (permissions matrix)

### ARCH source
- `ARCHITECTURE.md` §12.13 (Layouts), §12 (frontend)
- `frontend-master/references/responsive_patterns.md` (sidebar → drawer)

### Depends on
- T-226 (tokens), (M-01 T-017 shell baseline)

### What this ticket builds
Harden the authenticated `/admin` layout into the **single shell** every page renders inside: persistent role-aware sidebar nav (items filtered by `require_role`), header (user + logout + language switcher), responsive sidebar→drawer, RTL-safe, four-UI-states-aware. New pages register their nav entry here — establishing the pattern so no future page is an orphan.

### Tests (required)
- Vitest: nav renders the role's items; hides items above role.
- Playwright `@smoke`: shell renders, every nav item routes to a page that renders content.

### Acceptance (demo script)
1. [ ] Authenticated admin sees the shell with role-filtered nav
2. [ ] Every nav item routes to a real page (no dead links / blank shells)
3. [ ] Sidebar collapses to drawer on mobile; RTL correct

### Out of scope
- Per-page content fixes (T-231)

---

## T-228 — `scripts/seed_dev.py` idempotent dev seed

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 0.5 day
**Status:** done (2d4de26)

### Spec source
- (foundation — enables reproducible demos + E2E)

### ARCH source
- `ARCHITECTURE.md` §16 (app factory), §4 (DB)

### Depends on
- (M-00 DB + M-01 admin bootstrap)

### What this ticket builds
An idempotent `scripts/seed_dev.py` that creates the bootstrap Platform Admin + one sample District/School + a School Admin/Coordinator/Teacher/Student set, safe to run repeatedly (upserts). Used by the E2E job and for manual demos so they're reproducible (not hand-made data).

### Tests (required)
- pytest: running the seed twice leaves the DB in the same state (idempotency).

### Acceptance (demo script)
1. [ ] `python scripts/seed_dev.py` populates a usable demo dataset
2. [ ] Re-running it does not duplicate rows

### Out of scope
- Production seeding / fixtures for unit tests (separate `conftest.py` fixtures)

---

## T-229 — CI wiring + branch protection

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- (foundation) CLAUDE.md CI invariant 7

### ARCH source
- `.github/workflows/ci.frontend-checks.snippet.yml` (paste source)

### Depends on
- T-223, T-224, T-225, T-228

### What this ticket builds
Paste the four jobs from `ci.frontend-checks.snippet.yml` into `ci.yml` (frontend-unit, typed-client-drift, response-model-gate, e2e-smoke) **by amending, not regenerating** (CI invariant 3). Add the nightly full-Playwright schedule trigger. Add the four check names to branch-protection required checks (alongside the existing `Ticket status (backlog ledger)`).

### Acceptance (demo script)
1. [ ] All four jobs run on a PR and block on failure
2. [ ] Full Playwright suite runs on the nightly schedule, not per-PR
3. [ ] Branch protection lists the four checks as required

### Out of scope
- (none)

---

## T-230 — AUDIT+FIX: M-00/M-01 data + access foundation

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §11 (data-model sketch), §6 (limits: single Custom-persona slot, etc.)
- `flow-2-admin-coordinator-setup.md` §11 (for the platform-wide models M-01 seeds)

### ARCH source
- `ARCHITECTURE.md` §4 (DB patterns/conventions), §3.16 (dual-schema), §3.13 (tenant-isolation pattern)
- `ARCHITECTURE.md` §12.x (repository layer / scoped queries)

### Depends on
- (M-00/M-01 models + repositories + services exist)

### What this ticket builds
A **data-and-access-foundation audit** of everything M-00/M-01 shipped beneath the FE/integration skin, fixing drift **in the model + repository + service layers** (migrations are then re-derived by T-234; this ticket does not hand-edit migration files). Three scoped areas — **auth-dependency correctness, error envelope/codes, config/secrets hygiene, and structured logging are explicitly OUT of scope** (left to per-feature tickets):

1. **Models (§4.x compliance):** plural table names; locked PK strategy; `created_at`/`updated_at` audit columns; `deleted_at` soft-delete where the spec calls for it; correct `nullable`/`server_default`; tz-aware timestamps; real `Enum` types (not bare strings); JSONB where intended; sane string lengths/numeric precision. **Constraints + indexes + relationships:** `NOT NULL`/`UNIQUE`/`CHECK` matching flow-spec business rules (e.g. single Custom-persona slot, unique codes); every FK with an **explicit `ondelete`** matching intent; an index on every FK + documented query path; `relationship()`/`back_populates` correctness with deliberate cascade/lazy. **Placement:** each model in the correct schema per §3.16.
2. **Repository tenancy (§3.13 pattern, not the M-02 test):** every read/write goes through a scoped repository — no raw unscoped queries; the base-repo scoping pattern is applied uniformly so it's correct when M-02's per-school data arrives. (The cross-tenant denial *test* still lands in M-02.)
3. **Locked service invariants:** the handful of business rules M-01 must enforce in the service layer get an explicit test — Custom-persona single-slot enforcement, ToS version + force-accept state transitions, exam-syllabus rules — i.e. the "type-correct but wrong-rule" gaps.

Also confirm each `…Read` Pydantic schema's fields are a true subset of its model columns (feeds T-233's `SuccessEnvelope[T]`/`response_model` wiring).

### API contract
- N/A (no new endpoints)

### Tests (required)
- pytest **model-metadata lint:** every table has a PK + audit columns + indexed FKs + explicit FK `ondelete`; enums are real Enum types.
- relationship round-trip tests; schema-vs-model field-alignment test.
- service-invariant tests (Custom-persona slot, ToS transitions, exam-syllabus rules).
- repository-scoping test: a query path without a scope filter is rejected/flagged.

### Acceptance (demo script)
1. [ ] Model-audit checklist passes with zero §4.x convention violations
2. [ ] Every FK has an explicit `ondelete` + an index; all enums are real `Enum` types
3. [ ] Locked service invariants covered by passing tests
4. [ ] After fixes, T-234's `alembic --autogenerate` yields an **empty** diff (models == migrations)

### Out of scope
- Migration-file mechanics (T-234); `response_model` decorator wiring (T-233 / now-T-233 backfill); auth-dependency / error-envelope / config-secrets / logging audits (per-feature tickets); the §3.13 cross-tenant **test** (M-02)

---

## T-231 — AUDIT+FIX: M-01 navigation reachability

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §2, §4 (the M-01 surfaces)

### ARCH source
- `ARCHITECTURE.md` §12.13 (Layouts)

### Depends on
- T-227 (shell), T-223 (Playwright)

### What this ticket builds
Audit every M-01 admin page (Languages, Personas, Exam Syllabi, Subscription Tiers, ToS/Disclaimer, Audit Log) against the hardened shell; fix any that are unreachable or render a blank shell so each is reachable from nav and renders real content.

### Tests (required)
- Playwright `@smoke`: log in → click each nav item → assert the page renders its real content (not an empty placeholder).

### Acceptance (demo script)
1. [ ] Each of the 6 admin sections is reachable from nav and renders content
2. [ ] The `@smoke` E2E covering all six passes
3. [ ] UX acceptance (reachable, real content, scrollable, responsive, RTL) holds for each

### Out of scope
- ToS render/scroll specifics (T-232)

---

## T-232 — AUDIT+FIX: ToS flows render + scroll + accept

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.6 (Disclaimer/ToS lifecycle), §5.6 (force-accept edge cases)

### ARCH source
- `ARCHITECTURE.md` §14.10 (audit log on publish)

### Depends on
- T-227, T-223, (M-01 T-016 bootstrap ToS + T-019 admin ToS)

### What this ticket builds
Fix the bootstrap/Authentik ToS acceptance page (T-016) **and** the admin ToS/disclaimer editor + force-accept modal (T-019) so the ToS **text renders**, the content **scrolls** when it overflows, and **Accept enables correctly** (and Decline → suspended). This is the concrete reported breakage.

### API contract
- Existing `GET/POST /api/v1/admin/tos` + `/disclaimer` (verify `response_model=` present — T-225)

### Tests (required)
- Playwright E2E: ToS modal shows text, is scrollable, Accept enables → continue; Decline → suspended state; admin edits + publishes v(n+1) → audit row.
- Vitest: the ToS modal component renders given content + handles empty/loading/error.

### Acceptance (demo script)
1. [ ] Bootstrap ToS page shows real text and scrolls; Accept works
2. [ ] Admin ToS editor publishes a version; force-accept modal renders text + scrolls
3. [ ] Decline → `SUSPENDED`; every publish writes an audit row

### Out of scope
- Multi-language ToS (still TODO per Flow 1 §9)

---

## T-233 — AUDIT+FIX: regenerate M-00/M-01 typed client

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- (foundation) AMENDMENTS A-002

### ARCH source
- `ARCHITECTURE.md` §12.4

### Depends on
- T-224, T-225
- T-230 (audited models — `…Read` schemas match real columns before regenerating types)

### What this ticket builds
Regenerate `schema.d.ts`; convert M-00/M-01 feature `types.ts`/`api.ts` to consume generated types; delete hand-mirrored interfaces; confirm hooks compile against generated types.

### Tests (required)
- typed-client-drift check passes (no diff after `gen:api`); existing component tests still green.

### Acceptance (demo script)
1. [ ] No hand-mirrored API types remain in M-00/M-01 features
2. [ ] `pnpm gen:api` produces no diff
3. [ ] FE builds + tests green

### Out of scope
- (none)

---

## T-234 — AUDIT+FIX: reconcile M-00/M-01 migrations to model-first

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** todo

### Spec source
- (foundation) ARCH §4.12 (model-first autogenerate)

### ARCH source
- `ARCHITECTURE.md` §4.12, §4.21 (dual heads)

### Depends on
- (M-00/M-01 migrations + models)
- T-230 (audited models are the source — autogenerate runs against sound models)

### What this ticket builds
Audit M-00/M-01 migrations: confirm each maps to a SQLAlchemy model (model is source of truth), was autogenerated-then-reviewed, is one-concern-per-file, and that both Alembic heads upgrade cleanly from zero. Fix any hand-written drift or conflicting/duplicate migrations; consolidate only where a migration doesn't match its model (no squashing that violates one-concern).

Also backfill the **§4.12 structured migration headers** (`Purpose:` / `Risk:` / `Reversible:`) on all 11 existing migrations — they currently have doc-comment summaries but not the required format. (All 11 are low-risk additive creates with `downgrade()` implemented.) This closes the ⚠️ migration-header known violation here, so M-02's first migration starts from a clean, compliant baseline.

### Tests (required)
- pytest: `alembic upgrade head` on a fresh DB succeeds for both schemas; model metadata matches the migrated schema (no pending autogenerate diff).

### Acceptance (demo script)
1. [ ] Fresh DB upgrades cleanly on both Alembic heads
2. [ ] `alembic revision --autogenerate` against the models produces an **empty** diff (models == migrations)
3. [ ] No duplicate/conflicting migration for the same table
4. [ ] All 11 migrations carry the §4.12 `Purpose` / `Risk` / `Reversible` headers

### Out of scope
- New schema (none added here)

---

## T-235 — AUDIT+FIX: backfill FE tests for M-00/M-01 surfaces

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` (M-01 acceptance paths)

### ARCH source
- `frontend-master/references/four_ui_states.md`

### Depends on
- T-223, T-231, T-232

### What this ticket builds
Backfill Vitest + RTL tests for existing M-00/M-01 admin components (four UI states each) and Playwright `@smoke` coverage for the M-01 acceptance paths, so the previously-vacuous `pnpm test` is now real.

### Tests (required)
- This ticket *is* tests: components reach the 60% feature coverage target; `@smoke` covers M-01 acceptance.

### Acceptance (demo script)
1. [ ] `pnpm test` covers M-00/M-01 components ≥60%
2. [ ] `@smoke` E2E covers the M-01 acceptance paths and passes

### Out of scope
- (none)

---

## T-236 — Container profiles + dev ergonomics (lean local stack)

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- (foundation — dev ergonomics) M-00 T-002/T-005 (compose topology)

### ARCH source
- `ARCHITECTURE.md` §15.1 (container topology), §16.1 (lifespan — eager `init_nats`)
- `STACK_LOCK.md` §1.4 (single root `docker-compose.yml`; no Makefile)

### Depends on
- (M-00 T-002/T-004/T-005/T-010/T-011 — all services exist)

### What this ticket builds
Make the local stack lean — core boots ~7 containers instead of 16 — without changing the locked single-compose topology.

- **Compose profiles** on the optional services in `docker-compose.yml`: leave **core** (postgres, redis, authentik-server, authentik-worker, authentik-redis, api, frontend) with **no** `profiles:` key (always start); tag `profiles: ["rag"]` (qdrant, infinity, minio), `["workers"]` (celery-worker, celery-beat), `["events"]` (nats), `["observability"]` (prometheus, grafana, loki).
- **`EVENTS_ENABLED` flag** (default `false` in `.env.example`): wrap `init_nats()` / `close_nats()` in the §16.1 lifespan so they no-op when false. This is required because NATS connects **eagerly** at startup — without the guard, a core-only boot (events profile off) would hang/fail at `init_nats()`. Flag true + `events` profile on from M-12. (Postgres/Redis stay eager + core; qdrant/minio are already lazy client-wrappers, so no flag needed.)
- **`mem_limit`** on the RAM-heavy services (authentik trio, infinity, qdrant) so they can't starve the host even when running.
- **`docs/DEV_CONTAINERS.md`**: the milestone → profiles table (M-01/01a/02/03/05/06 = core only; M-04/09/10/11/13/15 = `rag`+`workers`; M-07/08 = `workers`; M-12 = `rag`+`events`; M-14/16/17 = `rag`+`workers`+`events`; any perf/load work = `+observability`), plus the `COMPOSE_PROFILES=…` / `docker compose --profile …` usage and the `EVENTS_ENABLED` note.

### API contract
- N/A (no endpoints; one env flag `EVENTS_ENABLED`)

### Tests (required)
- pytest: app boots green with `EVENTS_ENABLED=false` and no NATS container reachable (lifespan does not attempt the connection).

### Acceptance (demo script)
1. [ ] Plain `docker compose up` starts **only** the 7 core containers (`docker compose ps` shows no qdrant/nats/minio/infinity/celery/observability)
2. [ ] `EVENTS_ENABLED=false` → API boots healthy with NATS absent; `=true` + `--profile events` → NATS connects
3. [ ] `docker compose --profile rag --profile workers up` adds exactly those 5 containers
4. [ ] `docs/DEV_CONTAINERS.md` documents the milestone→profile map + usage

### Out of scope
- Making qdrant/minio lazy (already are); per-service prod tuning; the nightly/perf observability story

---

## T-237 — M-01a PR + demo

**Layer:** 1
**Milestone:** M-01a
**Estimate:** 0.5 day
**Status:** todo

### Depends on
- T-223 … T-236

### What this ticket builds
One milestone PR (merge commit). Demo video: nav reaches every admin page with content; ToS renders + scrolls + accepts; `pnpm test` + `pnpm e2e` + typed-client-drift + response-model gates all green; `seed_dev.py` reproduces the demo data.

### Acceptance (demo script)
1. [ ] All M-01a tickets `done`; all CI gates green
2. [ ] Demo shows the fixed nav + ToS + passing FE tests + typed client
3. [ ] ROADMAP M-01a → done (auto-rolled-up); M-02 `Depends on: M-01a`

### Out of scope
- M-02 content

---

## Drafting completeness ledger

**Foundation audit (T-230):** M-00/M-01 data + access foundation — models (§4.x), repository-tenancy pattern (§3.13), locked service invariants; auth/error/config/logging left to per-feature tickets.
**Foundation delivered (T-223–T-229):** FE test harness (Vitest/RTL/Playwright), openapi-typescript typed client, `response_model` gate + backfill, design tokens + shadcn base, app shell + role-aware nav, `seed_dev.py`, CI wiring + branch protection.
**Remediation delivered (T-231–T-236):** nav reachability, ToS render/scroll/accept, typed-client regeneration, migration model-first reconciliation, FE-test backfill, PR+demo.
**Enforcement vectors closed:** the gates live in `.claude/CLAUDE.md` (per-ticket, CC reads it) + CI invariant 7 (blocking) + the README ticket template (future tickets) — so M-02→M-17 inherit them without rewrite, each via the just-in-time modernization check.
**No new BLOCKED-HOOKs.** **Stack:** all additions locked in STACK_LOCK §2 + AMENDMENTS A-002; no forbidden libs; pnpm-native; lightweight.
