# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-01a — Foundation Remediation + FE/Integration Enforcement
**Current ticket:** T-229 (in progress) — CI wiring + branch protection
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

**Outstanding debt to clear in audit-fix tickets:**
- mypy --strict baseline ~55 pre-existing errors (bare `dict` annotations, celery untyped decorators) → catalog in T-230 docs/AUDIT_LOG.md.
- schema.d.ts stale after T-225 contract change → regenerate in T-233.
- FE coverage threshold red until T-235 backfill.

**Next intended step:** Implement T-227 (App shell + role-aware nav). Read milestone ticket body directly (ticket-loader authorized-bypass). frontend-master skill trigger fires (new visible page/screen + nav).
