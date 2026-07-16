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
- **2026-07-06 (M-06, PR #20):** binary ZIP download routes (`data_rights` student/parent `download_export`) shipped with no `response_model` — the rule had no documented pattern for non-JSON endpoints. Fixed with `response_model=None` + `response_class=Response` + explicit `responses={200: {"content": {"application/zip": {}}}}` (keeps OpenAPI accurate). Gate caught it.
- **Promoted rule:** every endpoint MUST declare `response_model=` (typed, via `SuccessEnvelope[T]`); CI fails on a missing/`dict` response_model. **Binary/file endpoints declare `response_model=None` + `response_class` + explicit `responses` content-type** — never omit.

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
- **2026-07-03 (M-05, PR #19):** inline object literal on the student profile-complete body — **caught by the `client-request-type` lint** (hardened 06-09); fixed to `IndependentStudentProfileComplete`.
- **2026-07-09 (M-07, PR #22):** conflict resolution reintroduced an inline literal at `index.ts:495` — **caught by the same lint**; fixed to generated types.
- **Promoted rule:** API types are generated from OpenAPI (`pnpm gen:api`); hand-mirroring forbidden; CI fails on drift. **VERIFIED EFFECTIVE (2026-07):** both post-hardening recurrences were mechanically caught at PR time — the class no longer reaches users; residual work is authoring-side (CC still writes inline literals first-pass).

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
- **2026-06-13 (M-02):** all six new migrations (`0015`–`0020`) authored WITHOUT the headers — `recurred-after-rule`. The T-234 pytest gate (`test_migration_headers.py`) caught it in CI; headers backfilled.
- **Status:** promoted (→ backfilled in M-01a T-234) → **recurred-after-rule (2026-06-13)** → mechanically enforced (the pytest gate holds the line); authoring carrier still weak — HARDEN: add the §4.12 header block to the data-modeling skill's migration workflow step so it's written first-pass, not backfilled after a red CI.
- **Promoted rule:** every migration carries `Purpose` / `Risk` / `Reversible` headers; model-first autogenerate.

### [model-constraint] models authored without §4 data conventions
- **Class:** model-constraint
- **Occurrences:** 2026-06-06 (M-01a, T-230) — across the 14 M-00/M-01 models: stable status/type value-sets stored as bare `String` instead of native Postgres enums (`subscriptions`, `upload_records`, `reference_books`); `JSON` used where `JSONB` was intended (`subscription_tiers.caps`); FKs declared without an explicit `ondelete` + index (`subscriptions`, `subscription_payments`, `syllabus_topics`, `reference_books`, `user_tos_acceptances`); business-rule constraints missing (`syllabus_topics.depth` CHECK, ToS/Disclaimer `version_number` UNIQUE, single-Custom-persona partial-unique index); a column typed against the wrong Python type (`Notification.read_at` as `str`); and soft-delete scoping duplicated ad-hoc per repository instead of a shared predicate.
- **Existing rule when first seen?:** no (the `data-modeling` skill existed but predates these M-00/M-01 models; nothing enforced §4 at author time when they were written)
- **Target carrier:** → data-modeling skill (native-enum / JSONB / FK-ondelete-index / CHECK-UNIQUE rules) + CLAUDE.md #10 (model-first) + a future CI `model-metadata-lint`
- **2026-06-13 (M-02):** `user_invites.school_id`/`district_id` FKs authored without `ondelete` + index — caught by the T-230 metadata lint.
- **2026-07-06 (M-06, PR #20):** `graduation_requests.school_id` FK authored without `index=True` — caught by the same lint; fixed model-first inside unmerged migration 0041. (M-07's re-fix via migration 0045 was the phantom-branch losing M-06's fix, not a third authoring miss — 0045 carries a `pg_indexes` guard, verified.)
- **Status:** promoted (→ fixed in M-01a T-230; `not_deleted()` predicate; metadata + repo-scoping tests) → **recurred-after-rule ×2 (M-02, M-06)** — the promoted lint caught both (mechanical net effective; nothing reached staging), but first-pass authoring keeps missing FK `ondelete`/index despite data-modeling Rule 3. Suspected cause: sessions running on the stale, gitignored `.cursor` rule clone (frozen 06-24) instead of `.claude/` — resolve via the `.cursor` tracked-or-generated process rule; if recurrence continues after parity, strengthen the skill trigger.
- **Promoted rule:** every model follows §4 — native Postgres enums for stable value sets, `JSONB` (never `JSON`), every FK with explicit `ondelete` + index, business rules as DB `CHECK`/`UNIQUE`/partial-unique, tz-aware audit columns, and soft-delete reads scoped through the shared `not_deleted()` predicate.
- **Deferred to M-02 (scope, not drift):** UUIDv7 native PKs (PKs stay `String(36)`+`uuid4` via `_uuid7()`); FKs to not-yet-created `schools`/`districts`/`authentik_user_refs`; `TenantMixin` + `created_by`/`updated_by` actor columns; `metadata_json` stays a serialized JSON string (not `JSONB`) to avoid rippling through audit infra; the ~63-error `mypy --strict` baseline (verified pre-existing — T-230 added zero new errors).

### [error-envelope-parsing] client parses errors at the wrong level / ignores 422 detail
- **Class:** api-contract
- **Occurrences:** 2026-06-09 (M-01a impl) — `request()` read `body.code`/`body.message` (top level) instead of `body.error.code`/`body.error.message`, and never parsed FastAPI 422 `detail[]`; with no `onError` on the create modals, every failure showed as `UNKNOWN_ERROR` or a silently frozen modal.
- **Existing rule when first seen?:** no (the `{error:{code,message}}` envelope is locked in ARCH §5, but nothing verified the client parses it)
- **Target carrier:** → frontend-master Rule 9 (error-envelope parsing + mandatory `onError`) + a client error-handling test
- **Status:** new — promote after the F-03/F-04 fix lands
- **Promoted rule:** the api client reads `body.error.{code,message}` and parses FastAPI 422 `detail[]`; every mutation has an `onError` that surfaces the message.

### [fe-i18n] non-en locale files missing whole namespaces (key-set drift)
- **Class:** fe-state
- **Occurrences:** 2026-06-20 (M-04, PR #16) — new UI strings (curriculum/reference upload, browse, onboarding, capacity) added to `messages/en/common.json` only; `ur`/`sd`/`ps` never received the `school_library` (and most M-04) namespace — 400 lines vs `en`'s 1116. The M-03 PR carried forward the same gap (`coordinator` namespace missing in ur/sd/ps), so this is the second observed occurrence of the same class.
- **Existing rule when first seen?:** yes (CLAUDE.md #8 + ARCH §13.10 require all four `messages/*.json` to share one key set) — rule is prose-only, nothing enforces it, so en-only additions ship unblocked → `recurred-after-rule` candidate.
- **Target carrier:** → CI lint `i18n-key-parity` (fail when locale files diverge from the `en` key set) + frontend-master Rule (visible-string keys land in all four locales same PR)
- **Status:** new — promote at the M-04 boundary; the prose rule already exists and keeps being bypassed, so the fix is a CI lint, not more prose.
- **Promoted rule:** _(pending)_ every `messages/<locale>/*.json` carries the identical key set to `en`; CI `i18n-key-parity` fails on any missing/extra key (placeholder/`MISSING` values allowed for untranslated strings, absent keys not).

### [mock-contract-drift] tests mock the fetch layer with a shape that diverges from OpenAPI
- **Class:** test-gap
- **Occurrences:** 2026-06-09 (M-01a impl) — Vitest + Playwright mock the fetch layer (`mock-api.ts`) with the old `{ name, description }` shape, so tests (incl. the `e2e-smoke` job) went **green while the live API 422'd every create**. The mock certified the broken contract.
- **Existing rule when first seen?:** no (Rule 12 mandated tests but allowed them fully mocked; nothing required a real-backend path or a contract check)
- **Target carrier:** → frontend-master Rule 12 (create/update `@smoke` hits the real backend; mocks validated vs OpenAPI) + new CI `contract-test` + real-backend create smoke
- **Status:** new — promote after the F-05 fix + the new gates land
- **Promoted rule:** at least the create/update `@smoke` paths run against the real seeded backend (never mock the contract); a contract test asserts mock + client request shapes match the generated `*Create`/`*Update` schemas; CI fails on divergence.


### [identity-column-width] external-IdP identifier columns sized as UUID
- **Class:** model-constraint
- **Occurrences:** 2026-06-11 (post-M-01a, library upload) — Authentik JWT `sub` is a 64-char hash; `upload_records.uploaded_by`, `audit_log.actor_id`, `notifications.recipient_user_id` were `VARCHAR(36)` (UUID-width) → 500 on every library POST. Widened to `VARCHAR(255)` in `school_0014`.
- **Existing rule when first seen?:** no (data-modeling skill covers PKs/FKs, not external-identifier sizing)
- **Target carrier:** → data-modeling skill: columns storing **external IdP/third-party identifiers are `VARCHAR(255)`/`TEXT`, never UUID-width** — external ID formats are not ours to assume.
- **Status:** promoted (→ data-modeling Rule 7, 2026-07-13). Open architecture question flagged separately: whether raw `sub` should be stored in three places at all vs mapped once to an internal user UUID.

### [async-engine-loop] module-level async engine reused across event loops
- **Class:** backend-async
- **Occurrences:** 2026-06-11 (library ingest) — Celery prefork workers call `asyncio.run()` per task; reusing the API's module-level async engine bound connections to a closed loop → `RuntimeError: Future attached to a different loop`. Fixed with `db/celery_async.py` `run_db()` (disposable engine per call). · 2026-06-13 (M-02 test harness) — same root under Starlette `TestClient` + async middleware + asyncpg → rewrote to `httpx.AsyncClient` + `ASGITransport` + engine dispose between tests.
- **Existing rule when first seen?:** no
- **Target carrier:** → CLAUDE.md/stack-enforcer rule: **any non-API execution context (Celery task, script, test harness) does DB I/O via the disposable-engine path (`run_db()` / per-loop engine), never the API's module-level session factory**; tests use `httpx.AsyncClient + ASGITransport`, not `TestClient`, for async apps.
- **Status:** promoted (→ CLAUDE.md decision rule, 2026-07-13) — `celery_async.py` + the M-02 harness pattern are now the mandated path.

### [migration-enum-create] `sa.Enum` inside `op.create_table` double-creates Postgres enums
- **Class:** migration
- **Occurrences:** 2026-07-03 (M-05) — `independent_0002` (`independentuserrole`) and `independent_0005` (`personalcontenttype` et al.): idempotent `DO $$ … duplicate_object` enum blocks followed by `op.create_table(sa.Enum(..., create_type=False))` still emitted `CREATE TYPE` → `DuplicateObjectError` on fresh DBs. Fixed with raw-SQL `CREATE TABLE` referencing pre-created native enum types.
- **Existing rule when first seen?:** no (data-modeling skill Rule 4 covers enum *choice*, not Alembic enum *creation mechanics*)
- **Target carrier:** → data-modeling skill migration step: **never `sa.Enum` inside `op.create_table` for Postgres enums** — create types idempotently in a prior step and reference them as plain column types (raw SQL if needed).
- **Status:** promoted (→ data-modeling Rule 4 migration-mechanics, 2026-07-13).

### [migration-crossbranch-deps] dual-head migrations missing cross-branch `depends_on`
- **Class:** migration
- **Occurrences:** 2026-07-03 (M-05) — `independent_0004` created a view over `school.platform_reference_books` but ran before `school_0010` (parallel Alembic branches, no ordering) → `UndefinedTableError` on fresh DBs. Fixed with `depends_on = ("school_0010",)`.
- **Existing rule when first seen?:** no (ARCH §4.21 defines dual heads; nothing warned about cross-schema object ordering)
- **Target carrier:** → data-modeling skill (§4.21 note): **any migration referencing an object owned by the other Alembic branch declares an explicit cross-branch `depends_on`**; verify on a `docker compose down -v` fresh DB with `alembic upgrade heads` (plural) before opening the PR.
- **Status:** promoted (→ data-modeling workflow step 4, 2026-07-13).

### [test-side-effect-isolation] production code gains side effects; test fixtures don't mock them
- **Class:** test-gap
- **Occurrences:** 2026-07-08 (M-04, 2.4.5) — library API unit tests flaked when real Celery `apply_async` + notification calls fired inside them. · 2026-07-09 (M-07, BUG-07) — M-06 added `notify_account_event()` to enrollment; enrollment API tests overriding `get_db` with `None` crashed in `publish_notification` (`NoneType.add`).
- **Existing rule when first seen?:** no
- **Target carrier:** → CLAUDE.md testing rule: **when a service gains a side effect (Celery, notifications, NATS, email), the same commit updates the affected test fixtures with autouse mocks** (`AsyncMock` the publisher/task) — side effects never execute for real inside unit/API tests.
- **Status:** promoted (→ CLAUDE.md decision rule, 2026-07-13).

### [stale-generated-client] backend contract changed; `gen:api` not run before push
- **Class:** api-contract
- **Occurrences:** 2026-06-13 (M-02, §2) — `PostLoginResponse` schema rename pushed without regenerating. · 2026-07-03 (M-05, BUG 7) — new M-05 routes pushed without regenerating. (M-07's stale schema was conflict-marker fallout → counted under [merge-regression].)
- **Existing rule when first seen?:** partially (the `typed-client-drift` gate exists and caught every instance — this class never reached users)
- **Target carrier:** → CLAUDE.md workflow step: **any commit touching backend routes/schemas runs `pnpm gen:api` and commits the output before push** — the gate is the net, not the process; each miss costs a full CI round-trip.
- **Status:** promoted (→ CLAUDE.md decision rule, 2026-07-13) — the drift gate remains the net.

### [env-fallback] deploy-critical env var silently defaults to a dev/localhost value
- **Class:** config
- **Occurrences:** 2026-06-11 (library ingest) — `EMBEDDING_PROVIDER` unset in the rebuilt worker → Pydantic default `infinity` → ingestion silently hit a non-existent service. · 2026-07-08 (M-07 login audit, B1) — `NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000"` + all three auth vars absent from `.env.example` → deployed staging redirected users to a raw port (live-confirmed on the staging URL 2026-07-13).
- **Existing rule when first seen?:** no
- **Target carrier:** → CI lint `env-example-parity` (every `process.env.NEXT_PUBLIC_*` / Pydantic settings field has a documented `.env.example` key) + frontend-master/CLAUDE rule: **no silent localhost/dev fallback for deploy-critical URLs — fail loud in prod** (M-07a T-240 implements the auth instance).
- **Status:** promoted (→ frontend-master Rule 15 + `env-example-parity` CI guard spec, 2026-07-13; M-07a T-240 implements the auth instance).

### [enum-switch-drift] role/enum union extended; dependent switches and hand-enumerated tests not updated
- **Class:** fe-types
- **Occurrences:** 2026-07-03 (M-05, BUG 11) — `ROLE_HIERARCHY` gained independent roles; `test_role_hierarchy` count assertion stale. · 2026-07-08 (M-07 login audit, A1) — M-06 added `student`/`parent` roles + dashboards; `getPostLoginPath` (last touched M-05) had no cases → both roles landed on `/admin`; the unit test hand-enumerated 5 roles so the gap passed CI.
- **Existing rule when first seen?:** no
- **Target carrier:** → frontend-master/CLAUDE rule: **switches over role/enum unions are exhaustive (TS `never` guard; backend: exhaustive match or registry), and their tests derive the case list from the union — never hand-enumerated** (M-07a T-239 implements the login instance).
- **Status:** promoted (→ frontend-master Rule 14 + CLAUDE.md decision rule, 2026-07-13; M-07a T-239 implements the login instance).

### [merge-regression] merges/conflict resolutions silently drop or regress already-merged work
- **Class:** process
- **Occurrences:** 2026-06-13 (M-02, §4) — merge `b964037` (staging → M-02) overwrote `ci.yml`, silently deleting the `client-request-type-lint` + `contract-test` jobs (restored by hand). · 2026-07-03→09 (M-06/M-07 branch surgery) — M-07 forked from the pre-rebase M-06 branch; M-06 was then rebased before merge, leaving 13 phantom duplicate commits on M-07 whose conflict resolution (`f7a6b2a "comflict resolved"`) **committed literal conflict markers** (broke 16 test suites, OpenAPI export, contract gates) and transiently regressed staging fixes (pyproject pins, `response_model=None`, the 0041 FK index — re-fixed as guarded 0045). · 2026-07-09 (design branch, §8) — same phantom base regressed staging CI fixes.
- **Existing rule when first seen?:** no (WORKFLOW assumed clean milestone-off-staging branching; nothing forbade rebasing a parented branch or checked merge results)
- **Target carrier:** → process rules (fork-from-staging-only-after-prior-merge; never rebase a branch with children; conventional-commit lint) + two cheap CI guards: a **conflict-marker grep gate** (fail on `<<<<<<<`/`>>>>>>>` anywhere) and a **required-CI-jobs presence check** (fail if `ci.yml` loses a required job).
- **Status:** promoted (→ WORKFLOW Branching rules + CLAUDE.md branching gate + `conflict-marker-gate` / `required-jobs-presence` CI guard specs, 2026-07-13).

### [ungoverned-change] locked architecture/stack/auth surfaces changed without drafting-side approval
- **Class:** process
- **Occurrences:** 2026-06-11 — `fastembed` local embedder shipped in a debugging commit (`e403bb8`): second embedding provider at 384-dim + `platform_chunks_local` collection, deviating from STACK_LOCK §4.3 (BGE-M3/Infinity) with **zero** DEVIATIONS/AMENDMENTS entry (retro-entry pending; dev/prod embedding-parity risk flagged). · M-05/M-07 — a `/me/` endpoint added to `PUBLIC_PATHS` (auth exemption) with no review marker (removed by M-07a T-238). · 2026-07-08/09 — M-07b milestone drafted **and partially implemented** (BFF password login changing locked §6.4) without approval; retired, code died with closed PR #21. · 2026-06-24 — commit `bf32768` edited `.claude/CLAUDE.md` from the implementation side and introduced a **gitignored** parallel `.cursor/` rule clone (invisible, unsyncable, frozen at 06-24).
- **Existing rule when first seen?:** no explicit rule ("ARCHITECTURE never edited without AMENDMENTS" was drafting-side convention; nothing bound implementation sessions)
- **Target carrier:** → CLAUDE.md hard rule: **changes to locked architecture, auth surfaces, `PUBLIC_PATHS`, stack choices, or `.claude/`+`docs/` governing files require a drafting-side-approved AMENDMENTS/DEVIATIONS entry BEFORE implementation** + CI path-guard (fail any PR diffing those paths without an approval marker) + `.cursor/` tracked-or-generated (never gitignored).
- **Status:** promoted (→ CLAUDE.md hard governance gate + `.cursor` parity rule + `governance-path-guard` CI spec, 2026-07-13; fastembed retro-DEVIATIONS recorded + STACK_LOCK §4.3 row annotated).

### [spec-conformance-drift] feature shipped as a simplified version of a locked spec; nothing verified conformance
- **Class:** process
- **Occurrences:** 2026-07-08 (login audit C1/C2/C3, vs T-016/§6.4/§6.5/§6.17) — T-016 shipped sessionStorage tokens (spec: HttpOnly cookies), no PKCE/state/nonce with browser-side token exchange (spec diagram: API-owned, server-side), and a JWT validator with `verify_iss`/`verify_aud` off + RS256-only (spec: strict, ES256 primary). Passed all gates because no gate compared implementation against the ARCH section it implements. Remediated by M-07a T-241/T-244/T-245.
- **Existing rule when first seen?:** no (phase-complete-review audits ticket acceptance, not spec-section conformance)
- **Target carrier:** → phase-complete-review checklist line: **for any ticket implementing a numbered ARCH section (esp. §6 security), diff the implementation against the section's normative statements and list each deviation explicitly** — "simplified for now" requires a recorded deferral, never silence.
- **Status:** promoted (→ phase-complete-review Pass-2 spec-conformance diff, 2026-07-13).