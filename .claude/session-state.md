# Session state (live — Claude Code updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** milestone/M-07a-login-flow-remediation (forked off staging @ 5e438cf, post-M-07)
**Current ticket:** T-245 done; next = T-246 (server-side logout + JTI blacklist)

## Environment
- uv at `~/.local/bin`; `export PATH="/c/Users/RAJA MUDASSAR/.local/bin:$PATH"` needed per Bash call. pnpm/node working too. Both stacks fully locally verifiable.
- No GitHub push access (403, Hamza-Nawaz5588) → all branches LOCAL ONLY, nothing pushed.
- Pre-existing mypy stub gap (not my scope): celery/boto3/fastembed/openpyxl/jose/authlib import-untyped. Don't fix without asking.
- No Docker/Postgres here → `tests/test_admin_create_real_backend.py` and any live-Authentik/Playwright checks are unverified (collectible/importable only). No @auth @real E2E possible until a machine with Docker picks this up (T-247's job anyway).

## Done this milestone (commits, all local/unpushed)
T-238 12011ef+f46b363 · T-238-followup 0561141 (require_role cross-tenant gap, flagged) · T-239 906f50c · T-240 ab13a87 · T-241 cd3266f · T-242 8d64e8b (FE global ToS-error wiring deferred, flagged) · T-243 57c9540 (ARCH §2/skill staleness flagged) · T-244 bdd34ca (server-side OIDC login/callback/refresh, cookie session, CSRF Origin check — new authlib dep) · **T-245 8dc0d4c** — FE cutover: deleted all sessionStorage token/user code from lib/auth.ts, added GET /auth/me + useCurrentUser() hook (replaces getUser() at 13 call sites), api/index.ts sends credentials:"include" (never Authorization), AuthMiddleware Bearer path removed (cookie-only now), OidcCallbackClient.tsx rewritten (only handles ?tos_required=1 landing). 151 backend + 207 frontend tests green.

## Next step
Invoke ticket-loader for T-246 (POST /auth/logout: revoke refresh token at Authentik, clear both cookies, blacklist access-token JTI in Redis until natural expiry — ARCH §6.8). Depends on T-244 (done).

## Outstanding (not auto-completable / flagged for Abd.)
- Push everything + open PRs (blocked on GitHub access) — incl. the standalone T-238 hotfix PR.
- T-248/T-249 human-gated (ops access, live demo, real Authentik round-trip).
- `require_role`/ROLE_HIERARCHY cross-tenant gap (T-238 note) — other callers repo-wide unaudited.
- ARCH §2 folder-tree + phase-complete-review skill both still reference deleted `nginx/conf.d/*.conf` (T-243 note).
- FE global wiring of `isTosAcceptanceRequiredError()` into a QueryClient interceptor (T-242 note) — primitive shipped, app-wide wiring deferred.
- `lib/api/index.ts`'s `token` param across ~50 call sites is now inert (T-245 note) — cosmetic cleanup, not urgent, not done.
- T-244/T-245's real-Authentik login round-trip + Playwright `@smoke` need a machine with Docker — first real chance to catch anything the mocked-boundary tests couldn't.
