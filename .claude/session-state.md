# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch.

---

**Current milestone:** M-01a — Foundation Remediation + FE/Integration Enforcement
**Current ticket:** T-225 (in progress) — response_model gate + SuccessEnvelope + operation_id backfill
**Ticket dossier loaded:** via direct milestone file read (ticket-loader sub-agent was malfunctioning; user authorized direct read)
**Dossier source files:** docs/backlog/M-01a-foundation-remediation.md

**Key facts learned:**
- Backend root is `api/app/` (NOT `app/`). Run uv from `api/`.
- Frontend keeps M-01 layout: `src/app/admin/*` + `src/components/*` (NO src/features/ migration — out of scope for audit-fix tickets).
- CI (`.github/workflows/ci.yml`) already has the 4 M-01a jobs pre-pasted (frontend-unit, typed-client-drift, response-model-gate, e2e-smoke) but they reference pieces not yet built. They are the contract:
  - `pnpm test --coverage`, `pnpm gen:api`, `pnpm e2e --grep @smoke`
  - `scripts/check_response_model.py`, `scripts/seed_dev.py`
  - Nightly full-Playwright schedule still TODO (in comments) — finish in T-229.
- No post-commit hook + pre-commit NOT installed in .git/hooks. Set ticket Status manually; run format gate manually (pnpm lint + typecheck).
- SuccessEnvelope target file: api/app/core/responses.py.

**Done this session (M-01a):**
- T-223: DONE (commit d7b6d73) — vitest coverage gate + @smoke Playwright harness + scripts. Coverage hits 60% only after T-235 backfill.
- T-224: DONE (commit 524574d) — offline OpenAPI export + gen:api + schema.d.ts + types.ts.

**T-225 work done (uncommitted):**
- responses.py: added SuccessEnvelope[T], PaginatedEnvelope[T], DeletedResponse (kept success()/paginated()).
- dependencies.py: require_role/require_scope return type object → params.Depends (fixes Depends list-item mypy errors).
- Wired response_model=SuccessEnvelope[...] / PaginatedEnvelope[...] + operation_id on ALL 38 routes (personas, exam_syllabi, subscriptions, tos, users, auth, audit, library, files, notifications, health, smoketest).
- scripts/check_response_model.py (AST gate: every route must have response_model + operation_id). Passes (rc=0).
- Tests: api/tests/test_check_response_model.py (5) + api/tests/test_openapi_contract.py (4) — 9 pass.
- OpenAPI verified: get_me → SuccessEnvelope_UserRead_; 17 envelope components; 0 routes missing operationId.
- NOTE: mypy --strict has ~baseline pre-existing errors (bare `dict` annotations, celery untyped decorators, extractor bytes) NOT introduced by T-225. CI uses `mypy app/ --ignore-missing-imports`. Pre-commit NOT installed.

**Next intended step:** finish mypy baseline check (confirm no NEW errors), run frontend format gate (only backend changed so FE unaffected), commit T-225, set milestone Status: done, then T-226.

**Format-gate run:** FE lint ✅ typecheck ✅ | coverage threshold red until T-235 (expected)
