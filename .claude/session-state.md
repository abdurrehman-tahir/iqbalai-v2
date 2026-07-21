# Session state (live — Claude Code updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** milestone/M-07a-login-flow-remediation (forked off staging @ 5e438cf, post-M-07)
**Current ticket:** T-246 done; next = T-247 (Playwright @auth @real per-role suite + CI real-backend lane)

## Environment
- uv at `~/.local/bin`; `export PATH="/c/Users/RAJA MUDASSAR/.local/bin:$PATH"` needed per Bash call. pnpm/node working too. Both stacks fully locally verifiable.
- No GitHub push access (403, Hamza-Nawaz5588) → all branches LOCAL ONLY, nothing pushed.
- Pre-existing mypy stub gap (not my scope): celery/boto3/fastembed/openpyxl/jose/authlib import-untyped. Don't fix without asking.
- No Docker/Postgres here → `tests/test_admin_create_real_backend.py` and any live-Authentik/Playwright checks are unverified (collectible/importable only). No @auth @real E2E possible until a machine with Docker picks this up (T-247's job anyway).
- Full backend suite (`uv run pytest -q`, no path filter) takes ~38 min in this environment (heavy import chains, e.g. qdrant_client/fastembed) — it's not hung, just slow; don't kill it early, let it finish or scope to touched dirs for quick iteration.

## Done this milestone (commits, all local/unpushed)
T-238 12011ef+f46b363 · T-238-followup 0561141 (require_role cross-tenant gap, flagged) · T-239 906f50c · T-240 ab13a87 · T-241 cd3266f · T-242 8d64e8b (FE global ToS-error wiring deferred, flagged) · T-243 57c9540 (ARCH §2/skill staleness flagged) · T-244 bdd34ca (server-side OIDC login/callback/refresh, cookie session, CSRF Origin check — new authlib dep) · T-245 8dc0d4c (FE cutover: sessionStorage removed, GET /auth/me + useCurrentUser() hook, credentials:"include", Bearer path removed) · **T-246 33d372e** — POST /auth/logout: revokes refresh token at Authentik (RFC 7009), clears both cookies, blacklists access JWT's jti in Redis (checked in AuthMiddleware.dispatch). Deviated from ticket's `SuccessEnvelope` wording → 204/response_model=None (ARCH §6.8 has no response body, matches /refresh precedent) — flagged in ledger. FE: performLogout() in lib/auth.ts, wired into all 9 shells' handleLogout(). Full backend suite 693 passed/3 skipped/0 failed; frontend 209/209 green; tsc/eslint/ruff/mypy clean; openapi.json+schema.d.ts regenerated.

## Next step
Invoke ticket-loader for T-247 already done once (dossier captured below) — resume implementing from it. **Two genuine blockers the dossier surfaced, user chose "full scope, best-effort" (all 3 AskUserQuestion options were: full-scope-flagged-unverified / partial-scope-split / stop-and-ask-Abd — user picked full scope):**
1. No Authentik user-provisioning automation exists anywhere in the repo — `scripts/bootstrap_authentik.py` is still a literal stub (prints manual instructions, exits). Must write a real one (Authentik API, following that script's existing shape) to create the 9 per-role login-capable identities — **cannot verify against a live Authentik here (no Docker)**, so this violates "no hallucinated APIs" in this one narrow spot; flag explicitly wherever this API is called.
2. `.github/workflows/ci.yml`'s `e2e-smoke` job's `@real` step runs against `pnpm dev` only (Next.js dev server) — no docker-compose stack, no Authentik, no seeded DB today. T-247 needs to wire that in (CI invariant 3: edit, don't replace).
Also: extend `scripts/seed_dev.py`'s `SEED_USERS` (currently 6 roles) with `parent`/`independent_teacher`/`independent_student` (3 missing) — note independent roles are self-signup/no-school-context, don't fit `SeedUser`'s shape as-is, document provisioning per ticket text. Existing `frontend/e2e/admin-create-real.spec.ts` uses `Authorization: Bearer` — now stale post-T-245's Bearer removal; flag in T-247's PR, not this ticket's job to fix.
Role→dashboard map for E2E assertions (confirmed via direct read, T-239's source of truth): platform_admin→/admin, district_admin→/admin/district/schools, school_admin→/school/admin, coordinator→/coordinator, teacher→/teacher, student→/student, parent→/parent, independent_teacher→/independent/teacher, independent_student→/independent/student.

## Outstanding (not auto-completable / flagged for Abd.)
- Push everything + open PRs (blocked on GitHub access) — incl. the standalone T-238 hotfix PR.
- T-248/T-249 human-gated (ops access, live demo, real Authentik round-trip).
- `require_role`/ROLE_HIERARCHY cross-tenant gap (T-238 note) — other callers repo-wide unaudited.
- ARCH §2 folder-tree + phase-complete-review skill both still reference deleted `nginx/conf.d/*.conf` (T-243 note).
- FE global wiring of `isTosAcceptanceRequiredError()` into a QueryClient interceptor (T-242 note) — primitive shipped, app-wide wiring deferred.
- `lib/api/index.ts`'s `token` param across ~50 call sites is now inert (T-245 note) — cosmetic cleanup, not urgent, not done.
- T-244/T-245/T-246's real-Authentik login/logout round-trip + Playwright `@smoke` need a machine with Docker — T-247 is meant to close this but is itself unverifiable here (see blockers above).
