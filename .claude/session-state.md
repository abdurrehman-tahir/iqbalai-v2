# Session state (live — Claude Code updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** milestone/M-07a-login-flow-remediation (forked off staging @ 5e438cf, post-M-07)
**Current ticket:** T-247 in_progress (code shipped, acceptance unverified — see ledger). Next: fix the 11 broken `@smoke` specs (flagged below), then re-attempt T-247 acceptance once Docker/Authentik is available, then T-248/T-249.

## Environment
- uv at `~/.local/bin`; `export PATH="/c/Users/RAJA MUDASSAR/.local/bin:$PATH"` needed per Bash call. pnpm/node node_modules present — use `node_modules/.bin/<tool>` directly, no global pnpm/eslint on PATH.
- No GitHub push access was 403 earlier this session; Hamza asked to push again mid-T-247 — retry, don't assume still blocked.
- Pre-existing mypy stub gap (not my scope): celery/boto3/fastembed/openpyxl/jose/authlib import-untyped. Don't fix without asking.
- No Docker/Postgres/Authentik here → nothing in T-247 has been run, only format/mypy/unit-tested with fakes.
- Full backend suite (`uv run pytest -q`, no path filter) takes ~38 min in this environment — not hung, just slow.

## Done this milestone (commits, local — push status: see above)
T-238 12011ef+f46b363 · T-238-followup 0561141 · T-239 906f50c · T-240 ab13a87 · T-241 cd3266f · T-242 8d64e8b · T-243 57c9540 · T-244 bdd34ca · T-245 8dc0d4c · T-246 33d372e (POST /auth/logout, JTI blacklist) · T-247 (in_progress, uncommitted-or-just-committed at session end — check `git log`): seed_dev.py extended to 9 roles, new scripts/seed_e2e_auth_users.py (real Authentik identity provisioning via the already-proven AuthentikClient + new find_user_by_email), frontend/e2e/auth-real.spec.ts (@auth @real, 9 role journeys + ToS + unauth + tampered-callback + logout), admin-create-real.spec.ts Bearer→Cookie fix, ci.yml e2e-smoke real-backend lane wiring.

## Genuine open blocker for T-247 acceptance
`scripts/bootstrap_authentik.py` is still a stub — nothing anywhere automates creating the Authentik **OIDC application/provider** itself (user-account provisioning is fine, proven, and now reused). Until that exists (Authentik blueprint YAML or a scripted admin-API bootstrap — a real design decision, flagged not guessed), the CI real-backend lane brings the stack up but can't complete an actual OIDC exchange, and `@auth @real` will fail (not skip) rather than pass. This is the top blocker for actually closing T-247.

## Deferred (confirmed with Hamza, not yet done)
11 pre-existing `@smoke` specs are broken by T-245's sessionStorage removal (dead `sessionStorage.setItem` seeding + no `GET /auth/me` mock in their inline route handlers): admin-shell-smoke, academic-sessions-smoke, coordinator-curriculum-smoke, districts-smoke, exam-frameworks-smoke, independent-teacher-onboarding-smoke, m04-teacher-onboarding-milestone-smoke, subjects-smoke, teacher-library-browse-smoke, teacher-onboarding-smoke, teacher-reference-smoke. Hamza said fix it — do this first next session (add a `GET /auth/me` mock returning the seeded role/user to each inline installer + `helpers/mock-api.ts`, drop the dead sessionStorage calls).

## Outstanding (not auto-completable / flagged for Abd.)
- T-248/T-249 human-gated (ops access, live demo, real Authentik round-trip).
- `require_role`/ROLE_HIERARCHY cross-tenant gap (T-238 note) — other callers repo-wide unaudited.
- ARCH §2 folder-tree + phase-complete-review skill both still reference deleted `nginx/conf.d/*.conf` (T-243 note).
- FE global wiring of `isTosAcceptanceRequiredError()` into a QueryClient interceptor (T-242 note) — primitive shipped, app-wide wiring deferred.
- `lib/api/index.ts`'s `token` param across ~50 call sites is now inert (T-245 note) — cosmetic, not urgent.
- Real-Authentik round-trip for T-244/T-245/T-246/T-247 all still unverified — needs a machine with Docker + the Authentik bootstrap gap closed.
