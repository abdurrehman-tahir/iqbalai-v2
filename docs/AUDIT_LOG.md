# Audit Log — root-cause classes & the improvement loop

This log exists to **improve CC's first-pass output**, not to track PR pass/fail. It is the evidence buffer for the feedback loop: capture recurring authoring-mistake *classes* → promote each into the carrier CC reads at authoring time (a skill rule / CLAUDE.md gate / CI lint) → watch later audits to confirm the class stops recurring.

## What to log — inclusion bar (read before adding anything)

Log a finding **only if all three hold**:
1. It's a **systemic class** — a generalizable authoring pattern (e.g. "FK declared without `ON DELETE`"), not a one-off instance ("`lectures.teacher_id` on line 42").
2. A **carrier could prevent it** for *future* features (a skill rule, a CLAUDE.md gate, or a CI lint) — if the only fix is "fix this one line," don't log it.
3. It would otherwise **recur** — the kind of mistake CC will make again on the next similar feature.

**Do NOT log:** per-PR PASS/FAIL status, CI green/red, one-off typos/instance fixes, or anything that generalizes to no rule. Those live in phase-complete-review's transient per-PR checklist and just get fixed. This file stays short — its length is bounded by the number of distinct mistake-classes (a handful), never by the number of PRs.

## How to use it

- **Capture (per PR, by phase-complete-review):** when the pre-PR audit finds a qualifying class, **append a dated occurrence** to that class's entry below. If the class has no entry yet, create one. Never add a second entry for a class that already exists — add an occurrence line (dedupe rule).
- **Distill (milestone boundary, Abd. + Claude):** scan for classes with ≥2 occurrences or any high-severity single hit; **promote** each into its target carrier; set status `promoted (→carrier, date)`; record the generalized rule text.
- **Verify (ongoing):** after promotion, watch later audits. Class stops appearing = the rule worked. Class **recurs after its rule existed** (`recurred-after-rule`) = the rule is in the wrong carrier or too weak (e.g. prose where a CI lint was needed) → **harden** it, don't re-add it.

## Entry schema

```
### [class-tag] short title
- **Class:** model-constraint | fe-state | fe-nav | fe-render | fe-types | api-contract | migration | tenancy | test-gap | docs
- **Occurrences:** YYYY-MM-DD (M-NN, ticket/PR) — one line each, append-only
- **Existing rule when first seen?:** yes/no (yes + recurring = harden the carrier)
- **Target carrier:** → data-modeling Rule N | → frontend-master Rule N | → CLAUDE.md #N | → CI lint <name> | → STACK_LOCK | → spec
- **Status:** new | promoted (→carrier, date) | recurred-after-rule | hardened (date)
- **Promoted rule:** the generalized rule text, once promoted (records the fix, not just the complaint)
```

---

## Classes

### [api-contract] endpoints return `dict` / omit `response_model`
- **Class:** api-contract
- **Occurrences:** 2026-05-29 (M-01, foundation diagnosis) — ~25 routes wrapped in `success()` returning `dict[str, Any]`; typed schemas existed but weren't wired, so the generated client would be `dict`-typed.
- **Existing rule when first seen?:** no
- **Target carrier:** → CLAUDE.md #6 + CI lint `response-model-gate` + STACK_LOCK §1
- **Status:** promoted (→ CLAUDE.md #6 + `response-model-gate` + `SuccessEnvelope[T]`, 2026-05-29) — fixed in M-01a T-233
- **Promoted rule:** every endpoint MUST declare `response_model=` (typed, via `SuccessEnvelope[T]`); CI fails on a missing/`dict` response_model.

### [api-contract] routes omit `operation_id`
- **Class:** api-contract
- **Occurrences:** 2026-05-29 (M-01) — ~30 routes across 9 routers had no `operation_id`, degrading generated OpenAPI/client method names.
- **Existing rule when first seen?:** no
- **Target carrier:** → CI lint `response-model-gate` (extended)
- **Status:** promoted (→ `response-model-gate` checks both, 2026-05-29) — fixed in M-01a T-233
- **Promoted rule:** every route declares `operation_id`; the gate checks it alongside `response_model`.

### [fe-types] TS API types hand-mirrored from Pydantic
- **Class:** fe-types
- **Occurrences:** 2026-05-29 (M-00/M-01) — `types.ts` hand-written to mirror backend models → structural FE↔BE drift (frontend calling mismatched shapes).
- **2026-06-09 (M-01a impl, branch `milestone_1a`):** generation worked (`ExamSyllabusCreate` correctly had `exam_board`, no `description`) but the api-client **request** types were hand-written — `syllabiApi.create` typed `{ name, description }` instead of `ExamSyllabusCreate`; subscription-tiers create sent `applies_to_role` + omitted `slug`. Reads used generated types; **creates didn't** → 422 on every create.
- **Existing rule when first seen?:** no (ARCH §12.4/§2.13 had deliberately *deferred* generation to Phase 2)
- **Target carrier:** → frontend-master Rule 9 + openapi-typescript + AMENDMENTS A-002 + CI lint `typed-client-drift`
- **Status:** promoted (→ generated `schema.d.ts`, A-002, 2026-05-29) — regenerated in M-01a T-232. **RECURRED 2026-06-09 (M-01a impl) → `recurred-after-rule`:** the rule existed but was too weak — Rule 9 was prose-only and `typed-client-drift` checks schema *freshness*, not *consumption*, so a hand-written request type sailed through. **HARDENED 2026-06-09:** Rule 9 now mandates request bodies typed from the generated `*Create`/`*Update` schema (with the exact WRONG example) + new CI `client-request-type` lint + real-backend create/update smoke (mocking the contract forbidden). See _CHANGE_LOG 2026-06-09.
- **Promoted rule:** API types are generated from OpenAPI (`pnpm gen:api`); hand-mirroring forbidden; CI fails on drift.

### [fe-nav] pages built but unreachable (orphan routes)
- **Class:** fe-nav
- **Occurrences:** 2026-05-29 (M-01) — admin pages implemented with no working nav; users couldn't reach them.
- **Existing rule when first seen?:** no (frontend-master was component-scoped; no page/shell-reachability rule)
- **Target carrier:** → frontend-master Rule 13 + CLAUDE.md #7
- **Status:** promoted (→ frontend-master Rule 13, 2026-05-29) — fixed in M-01a T-231
- **Promoted rule:** every page renders in the app shell, registers a role-filtered nav entry, and is reachable — proven by a Playwright `@smoke`.

### [fe-render] page renders blank shell / non-scrolling content
- **Class:** fe-render
- **Occurrences:** 2026-05-29 (M-01) — bootstrap/Authentik ToS rendered with no visible text and no scroller.
- **Existing rule when first seen?:** no
- **Target carrier:** → frontend-master Rule 13 (+ Rule 3 four states)
- **Status:** promoted (→ frontend-master Rule 13, 2026-05-29) — fixed in M-01a T-232
- **Promoted rule:** every page renders real content on first paint (four states), and overflowing content scrolls; an `@smoke` asserts it.

### [test-gap] no frontend test harness — broken UI passes review
- **Class:** test-gap
- **Occurrences:** 2026-05-29 (M-00/M-01) — no Vitest/Playwright; `npm run test` was vacuous, so blank/broken UI passed the manual demo script.
- **Existing rule when first seen?:** no
- **Target carrier:** → frontend-master Rule 12 + CI lints `frontend-unit`/`e2e-smoke` + STACK_LOCK §2
- **Status:** promoted (→ frontend-master Rule 12 + CI, 2026-05-29) — harness built in M-01a T-223/T-235
- **Promoted rule:** every data component ships a four-states Vitest test + every page a Playwright `@smoke`, in the same PR; CI runs both.

### [migration] migrations lack §4.12 Purpose/Risk/Reversible headers
- **Class:** migration
- **Occurrences:** 2026-05-29 (M-00/M-01) — all 11 migrations had doc-comment summaries but not the structured §4.12 headers.
- **Existing rule when first seen?:** no (ARCH §4.12 specified the format; nothing enforced it)
- **Target carrier:** → CLAUDE.md #10 (model-first) + the §4.12 convention
- **Status:** promoted (→ backfilled in M-01a T-234), advisory — watch whether new migrations adopt the headers; harden to a CI lint if it recurs.
- **Promoted rule:** every migration carries `Purpose` / `Risk` / `Reversible` headers; model-first autogenerate.

### [model-constraint] models authored without §4 data conventions
- **Class:** model-constraint
- **Occurrences:** 2026-06-06 (M-01a, T-230) — across the 14 M-00/M-01 models: stable status/type value-sets stored as bare `String` instead of native Postgres enums (`subscriptions`, `upload_records`, `reference_books`); `JSON` used where `JSONB` was intended (`subscription_tiers.caps`); FKs declared without an explicit `ondelete` + index (`subscriptions`, `subscription_payments`, `syllabus_topics`, `reference_books`, `user_tos_acceptances`); business-rule constraints missing (`syllabus_topics.depth` CHECK, ToS/Disclaimer `version_number` UNIQUE, single-Custom-persona partial-unique index); a column typed against the wrong Python type (`Notification.read_at` as `str`); and soft-delete scoping duplicated ad-hoc per repository instead of a shared predicate.
- **Existing rule when first seen?:** no (the `data-modeling` skill existed but predates these M-00/M-01 models; nothing enforced §4 at author time when they were written)
- **Target carrier:** → data-modeling skill (native-enum / JSONB / FK-ondelete-index / CHECK-UNIQUE rules) + CLAUDE.md #10 (model-first) + a future CI `model-metadata-lint`
- **Status:** promoted (→ fixed in M-01a T-230; `not_deleted()` scoping predicate added to `db/base.py`; model-metadata + repo-scoping tests added), advisory — watch later milestones; harden to a CI `model-metadata-lint` if the class recurs.
- **Promoted rule:** every model follows §4 — native Postgres enums for stable value sets, `JSONB` (never `JSON`), every FK with explicit `ondelete` + index, business rules as DB `CHECK`/`UNIQUE`/partial-unique, tz-aware audit columns, and soft-delete reads scoped through the shared `not_deleted()` predicate.
- **Deferred to M-02 (scope, not drift):** UUIDv7 native PKs (PKs stay `String(36)`+`uuid4` via `_uuid7()`); FKs to not-yet-created `schools`/`districts`/`authentik_user_refs`; `TenantMixin` + `created_by`/`updated_by` actor columns; `metadata_json` stays a serialized JSON string (not `JSONB`) to avoid rippling through audit infra; the ~63-error `mypy --strict` baseline (verified pre-existing — T-230 added zero new errors).

### [error-envelope-parsing] client parses errors at the wrong level / ignores 422 detail
- **Class:** api-contract
- **Occurrences:** 2026-06-09 (M-01a impl) — `request()` read `body.code`/`body.message` (top level) instead of `body.error.code`/`body.error.message`, and never parsed FastAPI 422 `detail[]`; with no `onError` on the create modals, every failure showed as `UNKNOWN_ERROR` or a silently frozen modal.
- **Existing rule when first seen?:** no (the `{error:{code,message}}` envelope is locked in ARCH §5, but nothing verified the client parses it)
- **Target carrier:** → frontend-master Rule 9 (error-envelope parsing + mandatory `onError`) + a client error-handling test
- **Status:** new — promote after the F-03/F-04 fix lands
- **Promoted rule:** the api client reads `body.error.{code,message}` and parses FastAPI 422 `detail[]`; every mutation has an `onError` that surfaces the message.

### [mock-contract-drift] tests mock the fetch layer with a shape that diverges from OpenAPI
- **Class:** test-gap
- **Occurrences:** 2026-06-09 (M-01a impl) — Vitest + Playwright mock the fetch layer (`mock-api.ts`) with the old `{ name, description }` shape, so tests (incl. the `e2e-smoke` job) went **green while the live API 422'd every create**. The mock certified the broken contract.
- **Existing rule when first seen?:** no (Rule 12 mandated tests but allowed them fully mocked; nothing required a real-backend path or a contract check)
- **Target carrier:** → frontend-master Rule 12 (create/update `@smoke` hits the real backend; mocks validated vs OpenAPI) + new CI `contract-test` + real-backend create smoke
- **Status:** new — promote after the F-05 fix + the new gates land
- **Promoted rule:** at least the create/update `@smoke` paths run against the real seeded backend (never mock the contract); a contract test asserts mock + client request shapes match the generated `*Create`/`*Update` schemas; CI fails on divergence.