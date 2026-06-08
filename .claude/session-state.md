# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-01a — Foundation Remediation + FE/Integration Enforcement
**Current ticket:** T-231 (next) — AUDIT+FIX M-01 navigation reachability
**Ticket dossier loaded:** via direct milestone file read (ticket-loader sub-agent was malfunctioning; user authorized direct read)
**Dossier source files:** docs/backlog/M-01a-foundation-remediation.md

**Key facts learned:**
- Backend root is `api/app/` (NOT `app/`). Run uv from `api/`.
- Frontend keeps M-01 layout: `src/app/admin/*` + `src/components/*` (NO src/features/ migration — out of scope for audit-fix tickets).
- Shell cwd is already `frontend/`. `pnpm test` / `pnpm lint` run there.
- No `format` script + prettier NOT installed in FE → frontend format gate = `pnpm lint` (next lint) only.
- CI (`.github/workflows/ci.yml`) already has the 4 M-01a jobs pre-pasted (frontend-unit, typed-client-drift, response-model-gate, e2e-smoke). Nightly full-Playwright schedule still TODO — finish in T-229.
- Pre-commit NOT installed in .git/hooks. Set ticket Status manually; run format gate manually.

**Done this session (M-01a):**
- T-223: DONE (d7b6d73) — vitest coverage gate + @smoke Playwright harness.
- T-224: DONE (524574d) — offline OpenAPI export + gen:api + schema.d.ts + types.ts.
- T-225: DONE (09cb1e7) — response_model gate + SuccessEnvelope/PaginatedEnvelope + operation_id on all 38 routes + check_response_model.py + contract tests.
- T-226: DONE (0f4081a) — design tokens (globals.css HSL vars + tailwind.config.ts semantic map + radius/fonts, light+dark), tokenized Card primitive, components.json, ESLint inline-style ban (react/forbid-dom-props + forbid-component-props), Vitest snapshot test (5 tests), design_tokens.md reference.
- T-227: DONE (2ddccd9) — role-aware nav in AdminShell.tsx: NAV_ITEMS gained `roles`, filtered by user role via navItemsForRole(). Vitest (platform_admin→7, teacher→0, null→0) + Playwright @smoke (e2e/admin-shell-smoke.spec.ts, seeds session + mock-api, every nav item reaches content). FE 38 tests pass.
- T-228: DONE (2d4de26) — scripts/seed_dev.py idempotent dev seed (bootstrap Platform Admin + district/school chain). seed_users() DB-decoupled via injected callbacks. api/tests/test_seed_dev.py (3 tests, in-memory fake). Script adds api/ to sys.path. NOTE: no schools/districts tables exist — sample hierarchy = stable demo IDs on users.school_id/district_id.
- T-229: DONE (2293c55) — ci.yml: fixed inv.1 in the 4 M-01a gates. typed-client-drift now `uv sync` in api/ (no root pyproject); response-model-gate dropped uv (pure-AST stdlib, runs on setup-python); e2e-smoke made offline (Playwright self-hosts via webServer; @smoke stubs API) + guarded `if != schedule`; added e2e-full nightly (`if == schedule`) + `schedule: cron "0 2 * * *"`; removed DUPLICATE ticket-status-check (kept one, PR-only guard); cleaned stale "PASTE THIS" comments. BRANCHING.md: documented required-check set (4 M-01a gates + ticket-ledger) as source of truth (protection paywalled) + change-log. NOTE: frontend-unit (`pnpm test --coverage`) stays RED until T-235 backfill — accepted intermediate state.

**Outstanding debt to clear in audit-fix tickets:**
- mypy --strict baseline ~55 pre-existing errors (bare `dict` annotations, celery untyped decorators) → catalog in T-230 docs/AUDIT_LOG.md.
- schema.d.ts stale after T-225 contract change → regenerate in T-233.
- FE coverage threshold red until T-235 backfill.

- T-230: DONE (482d3f5) — §4 data-foundation audit-fix. Native PG enums (subscriptions/upload_records/reference_books); JSON→JSONB (caps); FK+ondelete+index where target table exists; depth CHECK; tos/disclaimer version_number UNIQUE; single-custom-persona partial-unique; Notification.read_at str→datetime; UploadStatusResponse↔model alias; not_deleted() scoping helper in db/base.py applied across repos. 4 tests added (model-metadata, schema-align, service-invariants, repo-scoping). 112 backend tests pass. Deferred to M-02 (logged docs/AUDIT_LOG.md [model-constraint] class): UUIDv7 PK swap, schools/districts/authentik_user_refs FKs, TenantMixin+created_by/updated_by, metadata_json→JSONB, 63-err mypy --strict baseline (zero new errors from T-230).
- NOTE: acceptance #4 (empty autogenerate diff) is T-234's job — T-234 regenerates migrations FROM these models.

**T-231 NEXT — AUDIT+FIX M-01 navigation reachability:**
Spec: flow-1 §? + flow-2 (admin nav). Audit every M-01 page is nav-reachable, renders, scrolls; prove via Playwright @smoke. frontend-master trigger fires (read SKILL.md). Depends on T-227 (app shell + role-aware nav — DONE). FE coverage gate stays RED until T-235.
**Next intended step:** read T-231 ticket body in milestone file, load frontend-master skill, audit src/app/admin/* pages for nav reachability + render + scroll.
