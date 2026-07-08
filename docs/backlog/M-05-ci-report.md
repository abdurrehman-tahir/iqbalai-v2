# M-05 CI Report — Independent Users

**Milestone:** M-05 — Independent Users: signup + Platform Library  
**Tickets:** T-069 through T-076  
**Branch:** `milestone/M-05-independent-users`  
**PR:** [#19](https://github.com/abdurrehman-tahir/iqbalai-v2/pull/19) → `staging` (merged 2026-07-03)  
**Earlier draft PR:** [#17](https://github.com/abdurrehman-tahir/iqbalai-v2/pull/17) (closed; superseded)

---

## Executive summary

M-05 introduced the first real traffic on the dual-schema (`school` + `independent`) Alembic setup. The milestone hit **three classes of failure**:

1. **Local / migration bugs** — Postgres enum duplication and cross-branch migration ordering on a fresh database.
2. **CI gate failures on first PR push** — dependency resolution, backlog ledger drift, frontend type/mock gaps, and flaky E2E selectors.
3. **One remaining red check at merge** — `backend-lint` (115 pre-existing ruff violations inherited from `staging`, not introduced by M-05).

All M-05-specific functional gates (backend tests, alembic-check, frontend tests, typed-client drift, Playwright smoke including independent signup) were **green on the merged PR**.

---

## Final CI status (PR #19, merge commit)

| Check | Result |
|-------|--------|
| Ticket status (backlog ledger) | ✅ |
| PR template completeness | ✅ |
| Typed client up to date (openapi-typescript) | ✅ |
| Client request types (no inline literals) | ✅ |
| Mock + client shapes match OpenAPI | ✅ |
| Every endpoint declares `response_model` | ✅ |
| Frontend tests (Vitest + RTL) | ✅ |
| frontend-lint | ✅ |
| frontend-tests | ✅ |
| Playwright E2E (smoke) | ✅ |
| backend-tests | ✅ |
| alembic-check | ✅ |
| stack-check | ✅ |
| **backend-lint** | ❌ (115 ruff errors — inherited debt) |

---

## Bugs encountered and resolutions

### 1. Local dev: wrong Alembic command (`upgrade head` vs `heads`)

| | |
|---|---|
| **Symptom** | `alembic upgrade head` failed with "multiple heads" on a dual-schema repo. |
| **Root cause** | M-00 established two Alembic branches (`school_*` and `independent_*`). `upgrade head` (singular) is ambiguous. |
| **Resolution** | Use `alembic upgrade heads` (plural). Documented in local dev runbook. |
| **Commits** | `7e6b17f` (runbook note) |

---

### 2. Migration `independent_0002`: duplicate Postgres enum (`independentuserrole`)

| | |
|---|---|
| **Symptom** | `DuplicateObjectError: type "independentuserrole" already exists` during `independent_0001 → independent_0002`. |
| **Root cause** | Migration created enums idempotently via a `DO $$ … EXCEPTION duplicate_object` block, then called `op.create_table()` with `sa.Enum(..., create_type=False)`. SQLAlchemy's `before_create` hook on `sa.Enum` **still emitted `CREATE TYPE`** — a known SQLAlchemy behaviour; `create_type=False` does not suppress it on table create. |
| **Resolution** | Two-step fix: (1) idempotent enum creation + skip if table exists (`7e6b17f`); (2) replace `op.create_table()` with **raw SQL `CREATE TABLE`** referencing the native Postgres enum types (`7abcef6`). |
| **Commits** | `7e6b17f`, `7abcef6` |
| **File** | `api/alembic/versions/independent/0002_independent_users.py` |

---

### 3. Migration `independent_0004`: missing `school.platform_reference_books`

| | |
|---|---|
| **Symptom** | `UndefinedTableError: relation "school.platform_reference_books" does not exist` when creating cross-schema view `independent.platform_reference_books`. |
| **Root cause** | Dual-head Alembic runs `school` and `independent` branches in parallel. `independent_0004` ran before `school_0010` (which creates the source table) because there was no cross-branch `depends_on`. |
| **Resolution** | Added `depends_on = ("school_0010",)` to `independent_0004` so the platform view is created only after the school table exists. |
| **Commits** | `74b405b` |
| **File** | `api/alembic/versions/independent/0004_platform_shared_views.py` |

---

### 4. Migration `independent_0005`: duplicate Postgres enum (`personalcontenttype`)

| | |
|---|---|
| **Symptom** | Same `DuplicateObjectError` pattern as bug #2, for `personalcontenttype`, `personalcontentstatus`, and `personalstructuredparsingstatus`. |
| **Root cause** | Identical SQLAlchemy `sa.Enum` + `op.create_table()` double-create issue. |
| **Resolution** | Same pattern as `0002`: idempotent enum `DO` blocks + raw SQL `CREATE TABLE` + `has_table` guard. |
| **Commits** | `74b405b` |
| **File** | `api/alembic/versions/independent/0005_independent_personal_content.py` |

---

### 5. CI: `uv sync` dependency resolution failure (fastembed / numpy)

| | |
|---|---|
| **Symptom** | `backend-tests`, `backend-lint`, `alembic-check`, and `Typed client up to date` jobs failed at `uv sync` with unsatisfiable `fastembed` / `numpy` constraints. |
| **Root cause** | `fastembed` 0.6.x requires `numpy>=2`; project pins `numpy<2` for older VPS CPU compatibility per `STACK_LOCK.md`. |
| **Resolution** | Pin `fastembed` to 0.5.x and cap `requires-python` to 3.12 only. |
| **Commits** | `eb33a74` (merged from staging into M-05 branch) |

---

### 6. CI: Ticket status (backlog ledger) out of sync

| | |
|---|---|
| **Symptom** | `[ticket-status-check] FAIL — ROADMAP milestone Status out of sync with ticket states`. |
| **Root cause** | M-05 tickets marked `done` in backlog file while `ROADMAP.md` still showed `drafted` or `in-progress`. Roll-up rule: any ticket `done` → milestone must not be `drafted`. |
| **Resolution** | Updated `ROADMAP.md` and closed milestone ledger (`8f26179`, `522fe22`). |
| **Commits** | `8f26179`, `522fe22` |

---

### 7. CI: Typed client drift (`schema.d.ts` stale)

| | |
|---|---|
| **Symptom** | `Typed client up to date (openapi-typescript)` gate failed — regenerated `schema.d.ts` did not match committed file. |
| **Root cause** | New M-05 API routes (independent signup, onboarding, platform library, private pool) added without running `pnpm gen:api`. |
| **Resolution** | Regenerated `frontend/src/lib/api/schema.d.ts` and re-exported M-05 types from `types.ts` per AMENDMENTS A-002. |
| **Commits** | `99bdaca` |

---

### 8. CI: Vitest — missing API mock for exam frameworks fetch

| | |
|---|---|
| **Symptom** | `IndependentSignupClient.test.tsx` — 2 tests failed: `No "independentStudentOnboardingApi" export is defined on the "@/lib/api" mock`. |
| **Root cause** | T-071 added `listExamFrameworks()` call on signup mount (student role); Vitest mock of `@/lib/api` was not updated. |
| **Resolution** | Added `independentStudentOnboardingApi.listExamFrameworks` to the test mock. |
| **Commits** | `5b6e579` |

---

### 9. CI: frontend-lint + client-request-types gates

| | |
|---|---|
| **Symptom** | (a) ESLint: `'useEffect' is defined but never used`. (b) `check_client_request_types`: inline object literal on student profile complete body instead of generated schema type. |
| **Root cause** | T-071 student onboarding client left an unused import; API client used hand-mirrored inline type. |
| **Resolution** | Removed unused `useEffect`; typed request body as `IndependentStudentProfileComplete` from generated schema. |
| **Commits** | `0bb80f5` |

---

### 10. CI: Playwright — independent signup smoke timeout

| | |
|---|---|
| **Symptom** | `independent-signup-smoke.spec.ts` — `locator.fill: Test timeout of 60000ms exceeded` when filling email field. |
| **Root cause** | `getByLabel(/^Email$/i)` did not match accessible name when a required-marker asterisk is present in the label (`Email *`). Also missing mock for exam-frameworks API on page load. |
| **Resolution** | Switched to explicit input `id` selectors; added route mock for `GET /independent/students/me/exam-frameworks`. |
| **Commits** | `64a7adb` |

---

### 11. CI: backend-tests — role hierarchy assertion stale

| | |
|---|---|
| **Symptom** | `test_role_hierarchy` count assertion failed after adding `independent_teacher` and `independent_student` roles. |
| **Root cause** | `ROLE_HIERARCHY` extended in T-069; test still expected pre-M-05 count. |
| **Resolution** | Updated count assertion and added peer-level coverage for independent roles. |
| **Commits** | `ea42fed` |

---

### 12. CI (carryover from staging): Playwright coordinator curriculum smoke

| | |
|---|---|
| **Symptom** | `coordinator-curriculum-smoke.spec.ts` — strict mode violation: `getByRole('status')` matched both ingestion badge and Next.js toast. |
| **Root cause** | Pre-existing flaky selector from M-04; surfaced on PR #17 first CI run. Fixed on staging before M-05 merge (M-04 fix commits `76f8431`). |
| **Resolution** | Not an M-05 code change; resolved by merging latest `staging` into the milestone branch. |

---

### 13. CI (carryover): PR template check on synchronize

| | |
|---|---|
| **Symptom** | `PR template completeness` failed on webhook `synchronize` events. |
| **Root cause** | Webhook payload can omit or linkify `@mentions` in section headers; static body comparison missed sections. |
| **Resolution** | `pr-template-check` workflow now fetches live PR body via GitHub REST API (`3f3be0e`). |

---

### 14. Outstanding at merge: `backend-lint` (115 ruff errors)

| | |
|---|---|
| **Symptom** | `uv run ruff check .` reports 115 errors on merged PR #19. |
| **Root cause** | Pre-existing lint debt on `staging` (import ordering, line length, unused imports across school-era modules). M-05 added a small number (e.g. one E501 in `0003_independent_teacher_profiles.py`) but the bulk is inherited. |
| **Status** | **Not resolved in M-05.** PR merged with this check red; tracked for a future lint remediation pass. |
| **M-05-specific lint** | `alembic/versions/independent/0003_independent_teacher_profiles.py:27` — E501 line too long (122 > 100). |

---

## Fix commit index

| Commit | Area | Summary |
|--------|------|---------|
| `eb33a74` | CI / deps | fastembed + numpy pin for `uv sync` |
| `3f3be0e` | CI / workflow | PR template check fetches live body |
| `76f8431` | CI / E2E | Playwright smoke stabilisation (staging) |
| `7e6b17f` | Migrations | Idempotent enum + table guard on `0002` |
| `7abcef6` | Migrations | Raw SQL table create on `0002` |
| `74b405b` | Migrations | `depends_on school_0010` on `0004`; raw SQL on `0005` |
| `5b6e579` | Frontend tests | Vitest mock for exam frameworks API |
| `0bb80f5` | Frontend lint / types | Named profile type; remove unused import |
| `99bdaca` | API types | Regenerate `schema.d.ts` |
| `64a7adb` | E2E | Independent signup smoke selectors + mock |
| `ea42fed` | Backend tests | Role hierarchy count for independent roles |
| `8f26179` | Backlog | Close M-05 milestone ledger |

---

## Lessons for future milestones

1. **Never use `sa.Enum` inside `op.create_table()` for Postgres enums in Alembic** — use idempotent `CREATE TYPE … DO $$ EXCEPTION` + raw SQL `CREATE TABLE`, or create enums in a prior migration and reference them as plain column types.
2. **Cross-schema views need `depends_on`** across Alembic branches when the source table lives in the other branch.
3. **Always run `alembic upgrade heads`** (plural) on dual-head repos; verify on a fresh `docker compose down -v` database before opening the PR.
4. **When a component gains a new `useEffect` API call**, update Vitest mocks and Playwright route mocks in the same commit.
5. **Run `pnpm gen:api`** whenever backend routes change — the typed-client drift gate is strict.
6. **Update ROADMAP milestone status** as tickets flip to `done`; the ticket-status-check gate runs on every PR push.

---

## Local verification commands (post-fix)

```bash
cd iqbalai-v2
docker compose down -v && docker compose up -d
docker compose exec api alembic upgrade heads
docker compose exec api pytest -q
cd frontend && pnpm test && pnpm e2e --grep @smoke
```

---

*Report generated: 2026-07-08. Author: milestone implementation session (M-05).*
