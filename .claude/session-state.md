# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-02 — School Onboarding
**Branch:** milestone/M-02-school-onboarding (from origin/staging @7000c23)
**Current ticket:** T-029 — Platform Admin creates District: API + UI — **done** (committing)
**Dossier source files:** docs/backlog/M-02-school-onboarding.md; flow-2 §4/§3.1/§5.6; ARCH §5.1, §5.9, §6.7, §6.19

**Done this session (T-029):**
- Backend (pre-compaction): District model + cols (region, language_preference) + migration school/0013; schemas/repository/service/router (full CRUD, soft-delete); Idempotency-Key infra (infrastructure/cache/client.py redis.asyncio + core/idempotency.py, 24h TTL, 409 mismatch); IdempotencyKeyMismatchError. Tests: test_district_service(8), test_district_api(6), test_idempotency(8). redis>=5.0.0 added to pyproject.
- Frontend (this session): districtsApi in src/lib/api/index.ts (create sends Idempotency-Key via crypto.randomUUID); /admin/districts page + DistrictsClient.tsx (4 UI states, create + delete modals, RHF+Zod, TanStack Query); Building2 nav item in AdminShell + en districts block + __TODO__ ur/sd/ps; Vitest+RTL test (5); e2e/districts-smoke.spec.ts (@smoke) + mock-api extended.

**Verified:** ruff format/check OK, mypy --strict on all T-029 backend files OK, backend schools+idem pytest 31 pass, frontend vitest 34/34 (5 new). T-029 FE files typecheck/lint clean.

**PRE-EXISTING repo issues flagged to Hamza (NOT from T-029; block shared CI gates):**
1. `pnpm typecheck` red: e2e/platform-admin-smoke.spec.ts:30 stale `@ts-expect-error` (unused since @playwright/test is a committed devDep). Pre-existing at HEAD.
2. `pnpm lint` red: src/test/mocks/next-intl.ts:18 `_date` unused-var. Pre-existing (committed at "milestone 1").
3. M-01a CI gaps: ci.yml `typed-client-drift` runs `pnpm gen:api` + diffs src/lib/api/schema.d.ts — NO gen:api script, NO schema.d.ts, openapi-typescript not a dep. `e2e-smoke` calls `pnpm e2e` but script is `test:e2e`. Both jobs broken regardless of T-029.
4. A-002 tension: repo intent is generated FE types, but ALL features (incl. T-029) hand-write src/lib/api/index.ts — generation pipeline never wired. T-029 follows the established sibling pattern.

**Next intended step:** commit T-029, then T-030 (Path A invitation flow) — depends on T-029.
