# Session state (live — Claude Code updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** milestone/M-07a-login-flow-remediation (forked off staging @ 5e438cf, post-M-07)
**Current ticket:** T-244 done; next = T-245 (FE cutover to cookie auth)

## Environment
- uv at `~/.local/bin` (astral installer hung; used GitHub release zip directly). `export PATH="/c/Users/RAJA MUDASSAR/.local/bin:$PATH"` needed per Bash call. pnpm/node also working. Both stacks fully locally verifiable.
- No GitHub push access (403, Hamza-Nawaz5588) → all branches LOCAL ONLY, nothing pushed.
- Pre-existing, not-my-scope mypy gap: import-untyped for celery/boto3/fastembed/openpyxl/jose/**authlib** (T-244 added authlib to this same class). Don't fix without asking.
- No Docker here → can't run a real Authentik/compose stack. T-244's "real login E2E" acceptance item is unverified; token exchange mocked at the HTTP boundary per its own test spec.

## Done this milestone (commits, all local/unpushed)
T-238 12011ef+f46b363 · T-238-followup 0561141 (require_role cross-tenant gap, flagged) · T-239 906f50c · T-240 ab13a87 · T-241 cd3266f · T-242 8d64e8b (FE global wiring deliberately deferred) · T-243 57c9540 (ARCH §2/skill staleness flagged) · **T-244 bdd34ca** — server-side OIDC login/callback/refresh, cookie session, CSRF Origin check. New: `app/core/cookies.py`, `app/features/auth/{oidc_client,oidc_session,refresh_session}.py`, `get_post_login_path()`. 146/146 backend + 59/59 frontend green.

## Next step
Invoke ticket-loader for T-245 (FE cutover: LoginButton → `/api/v1/auth/login`, kill sessionStorage, `credentials:"include"`, remove Bearer dual-read, update OidcCallbackClient/auth helpers + tests). Depends on T-244 (done) + T-239 (done).

## Outstanding (not auto-completable)
- Push everything + open PRs (blocked on GitHub access) — incl. the standalone T-238 hotfix PR.
- T-248/T-249 human-gated (ops access, live demo).
- Flagged for Abd.: `require_role`/ROLE_HIERARCHY cross-tenant gap (T-238 note); ARCH §2 + skill `nginx/conf.d` staleness (T-243 note); FE global ToS-error wiring (T-242 note).
- T-244's real-Authentik login round-trip needs a machine with Docker to confirm.
