# M-07a — Login Flow Remediation (§6.4 Conformance + Audit Fixes)

**Status:** drafted
**Layer:** 3 (rides between M-07 and M-08)
**Sequence:** after M-07 merges, before M-08 (M-08 `Depends on` flips to M-07a)
**Ticket range:** T-238 to T-249 (off the T-237 high-water mark; **non-positional** numbering. Note: T-238–T-247 were briefly assigned to the retired M-07b draft — that milestone was rejected, its doc was never committed, and its partial code died with closed PR #21, so the range is free and reassigned here. This paragraph is the authoritative record of that reuse.)
**One PR** (merge commit). **Branch off `staging` only after the rebuilt M-07 PR (#22) has merged** — several tickets touch files M-07's branch also touches (`middleware.py`, `auth.ts`).
**Estimate:** ~1 week (CC-tiered). This is a real milestone, not a patch batch — T-244/T-245 rework the token transport, which ripples into the API client and E2E auth helpers.

## Why this milestone exists

The login-flow audit (2026-07-08, run against the M-07 branch) confirmed the tester-reported breakage and surfaced one code bug, several deployment gaps, and — most importantly — that T-016 shipped a **simplified version of the locked ARCH §6.4 flow**: tokens in `sessionStorage` instead of HttpOnly cookies (§6.17), no PKCE/state/nonce, token exchange in the browser instead of the API, no server-side logout (§6.8), plus a JWT validator that skips issuer/audience checks (§6.5) and a missing ToS middleware gate (T-016's own spec). The proposed M-07b (custom password/BFF login) was **rejected** — it changed the locked auth architecture to solve a branding problem the sanctioned path (env fix + nginx `/idp` + Authentik theming) solves for free.

This milestone therefore does two things, once and for all: **(1) fixes every audit finding** (C6, A1, B1, C3, C4, B2) and **(2) completes the OIDC flow to the locked §6.4 diagram** — the API owns state/nonce/PKCE and the code exchange (steps 8–9), sets the `iqbalai_access`/`iqbalai_refresh` HttpOnly cookies (step 11, §6.17), enforces CSRF per §6's threat table (SameSite=Lax + `state` + Origin/Referer middleware check), and implements server-side logout (§6.8). **Authentik stays. No password form. No new auth dependencies.**

Deployment items (host nginx `/idp` per §15.11, Authentik redirect-URIs/issuer → public URL, `NEXT_PUBLIC_AUTHENTIK_URL`, Authentik green theming) are ops on the staging box, not repo code — they live in T-248 as an executable checklist, because the milestone's goal (testers log in via the public URL) is unreachable without them.

---

## T-238 — Remove PUBLIC_PATHS auth-bypass (audit C6)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.25 day
**Status:** done
**Commit:** 12011ef (hotfix, branch `fix/exam-frameworks-auth-bypass`); cherry-picked onto `milestone/M-07a-login-flow-remediation` as f46b363. **Not pushed** — this dev environment has no GitHub write access (403); needs a push + CI run before the hotfix PR is opened and this ticket is truly closed.
**Follow-up commit:** 0561141 — verifying this ticket with a real Python toolchain (installed mid-session) surfaced that `independent_student_onboarding/tests/` had no `__init__.py` (pre-existing on staging), so its tests — including this ticket's own router test — were never actually collected/run. Fixed, and collecting them exposed a second bug: `require_role("independent_student")` on all 3 routes in that file is a no-op cross-tenant gate (any authenticated role passes). Fixed with an exact-match `require_independent_student()` dependency; see commit for full detail. **Flagging the underlying `require_role`/`ROLE_HIERARCHY` "X or higher" design gap (ARCH §6.19) as a new finding for Abd. — not tenant-aware, likely affects other independent-tenant routes using the same pattern. Not fixed repo-wide in this session (out of ticket scope, ~50+ other callers).**

### Spec source
- Login-flow audit C6; ARCH §6.6 (PUBLIC_PATHS is a small allowlist of auth/health/docs only)

### ARCH source
- `api/app/core/middleware.py:38` — `"/api/v1/independent/students/me/exam-frameworks"` inside `PUBLIC_PATHS`

### Depends on
- (M-07 merged)

### What this ticket builds
**Gate first:** `git log -S "students/me/exam-frameworks" -- api/app/core/middleware.py` to date the line. If it landed in M-05 (already live on `staging`), this fix ships as an immediate **hotfix PR to staging** and this ticket becomes its verification record; if M-07-era, it ships here. Either way: remove the entry — a `/me/` endpoint cannot resolve a user without auth, so its exemption is an auth-bypass, not a feature. Fix whatever 401 the exemption was papering over at the route/dependency level (the endpoint must authenticate like every other `/me/` route).

### API contract
- No new endpoints. `GET /api/v1/independent/students/me/exam-frameworks` now requires auth like its siblings.

### Tests (required)
- pytest: unauthenticated request to the endpoint → 401; authenticated independent student → 200.
- pytest: `PUBLIC_PATHS` snapshot test — the set contains **only** the §6.6 allowlist (auth/health/docs), so any future addition fails loudly and must be justified in review.

### Acceptance (demo script)
1. [ ] Unauthenticated curl to the endpoint returns 401 (was 200)
2. [ ] The authenticated flow through the student UI still works
3. [ ] The PUBLIC_PATHS snapshot test is in place and green

### Out of scope
- The CI guard that flags any PR diffing `PUBLIC_PATHS` (parked process-rule batch, drafting side)

---

## T-239 — Exhaustive role → dashboard routing (audit A1)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.5 day
**Status:** done
**Commit:** 906f50c (local, not pushed — see session-state.md environment constraints). Verified locally: `tsc --noEmit` clean, `eslint` clean, `vitest run` 19/19 green.

### Spec source
- Login-flow audit A1; T-016 (each role lands on its dashboard)

### ARCH source
- `frontend/src/lib/auth.ts:81+` (`getPostLoginPath` switch — no `student`, no `parent` case; both fall to the default `/admin`)
- `api/app/features/users/models.py` `UserRole` (7 school-tenant roles incl. `STUDENT`, `PARENT`) + the independent-tenant role strings the existing switch already handles (`independent_teacher`, `independent_student`)

### Depends on
- (M-07 merged)

### What this ticket builds
Make `getPostLoginPath` an **exhaustive switch over the full role union** (7 `UserRole` values + the 2 independent-tenant strings): add `case "student": return "/student"` and `case "parent": return "/parent"`, and add a TypeScript `never`-check on the switch argument so **any future role addition fails typecheck** instead of silently falling through. Replace the default-→`/admin` fallthrough with the `never` guard + an explicit `platform_admin` case. Rewrite the unit test to **derive its case list from the role union type** (compile-time mirror of the backend enum via the generated types if the enum is exposed there; otherwise a single source-of-truth array asserted against the switch) — never a hand-enumerated list, which is exactly how this gap passed CI.

### API contract
- N/A (frontend routing only)

### Tests (required)
- Vitest: every role in the union maps to its documented dashboard path; the test enumerates the union programmatically.
- Type-level: removing a case breaks the build (the `never` guard).

### Acceptance (demo script)
1. [ ] A `student` login lands on `/student`; a `parent` login lands on `/parent` (not `/admin`)
2. [ ] Deleting any case from the switch fails `tsc`
3. [ ] The unit test covers all 9 roles without hand-listing them

### Out of scope
- The per-role E2E proof (T-247); the `[enum-switch-drift]` audit-log entry (parked batch)

---

## T-240 — Auth env vars: documented, required, fail-loud (audit B1)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.5 day
**Status:** done
**Commit:** ab13a87 (local, not pushed). Verified locally: `tsc --noEmit` clean, `eslint` clean, `vitest run` 6/6 green, and live-confirmed `NODE_ENV=production next build` fails at config-eval with no env vars set / proceeds once all three are set. Also fixed `.env.prod.example`'s own `NEXT_PUBLIC_AUTHENTIK_URL` (was modeling the raw-port bug).

### Spec source
- Login-flow audit B1; root cause of the tester-reported `localhost:9000` redirect

### ARCH source
- `frontend/src/lib/auth.ts:57` (`NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000"`, same fallback in `getLogoutUrl`)
- `.env.example` frontend block (ships only `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_WS_URL`)

### Depends on
- (M-07 merged)

### What this ticket builds
1. Add to `.env.example` with comments: `NEXT_PUBLIC_AUTHENTIK_URL` (**documented as the public `/idp` form**, e.g. `https://<domain>/idp` — never a raw port; localhost:9000 acceptable for local dev only), `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_AUTHENTIK_CLIENT_ID`.
2. **Fail-loud guard:** in production builds (`NODE_ENV=production`), an unset `NEXT_PUBLIC_AUTHENTIK_URL` **fails the build** (assert in `next.config` or a prebuild check) — a deployed app must never silently point users at localhost. Dev keeps the localhost default.
3. Apply the same treatment to every deploy-critical `NEXT_PUBLIC_*` the login path reads (login + logout URLs).

Note: after T-244/T-245 land, the *browser* no longer builds the authorize URL (the API does) — but the env-parity + fail-loud principle still applies to whatever public URLs the frontend and API read; this ticket establishes it, T-244 inherits it for the API-side settings (which use Pydantic Settings and should declare these **required**, no default, in prod config).

### API contract
- N/A

### Tests (required)
- Prebuild-check unit test: production + unset var → build fails with a clear message; dev + unset → default with a console warning.

### Acceptance (demo script)
1. [ ] `.env.example` documents all three vars with the `/idp` public-form note
2. [ ] A prod build without `NEXT_PUBLIC_AUTHENTIK_URL` fails loudly
3. [ ] Local dev without it still works (warned)

### Out of scope
- The `env-example-parity` CI lint (parked process-rule batch); the staging box's actual values (T-248)

---

## T-241 — JWT validation hardening (audit C3, §6.5)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.5 day
**Status:** done
**Commit:** cd3266f (local, not pushed). Verified locally with a real toolchain: `uv run pytest app/core/` 74/74 green, `ruff format`/`check` clean, `mypy --strict` clean on this file (0 new errors beyond the repo's pre-existing import-untyped stub gaps). No dev-leniency flag added — local Authentik's issuer/audience already match `OIDC_ISSUER_URL`/`OIDC_CLIENT_ID`, so strict-by-default needed no escape hatch (acceptance item 3 satisfied trivially).

### Spec source
- Login-flow audit C3; ARCH §6.5 (ES256 primary / RS256 fallback; verify issuer + audience; JWKS cache 1h)

### ARCH source
- `api/app/core/security.py:76-77` (`algorithms=["RS256"]`, `verify_aud: False`, `verify_iss: False`) + `:18` (`_JWKS_TTL_SECONDS = 300`)

### Depends on
- (M-07 merged)

### What this ticket builds
Bring token verification to §6.5: `algorithms=["ES256","RS256"]`; `verify_iss=True` against the configured Authentik issuer; `verify_aud=True` against our client-id audience; JWKS TTL → 3600s. Issuer/audience come from Pydantic Settings (required in prod — pairs with T-240's fail-loud principle). Keep a documented dev override **only** if local Authentik genuinely can't satisfy a check — explicit env flag, defaulting to strict, never silently lenient.

### API contract
- No endpoint changes; every authenticated request now enforces iss/aud.

### Tests (required)
- pytest: token with wrong issuer → 401; wrong audience → 401; valid → 200. ES256-signed token accepted (fixture keys).
- pytest: JWKS cache honors the 1h TTL (time-mocked).

### Acceptance (demo script)
1. [ ] A token minted for another issuer/audience is rejected
2. [ ] Real Authentik login still verifies end-to-end
3. [ ] Config is strict by default; any dev-leniency is an explicit flag

### Out of scope
- Cookie transport (T-244/T-245); JTI blacklist (T-246)

---

## T-242 — ToS middleware gate (audit C4, T-016 conformance)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- Login-flow audit C4; M-01 T-016: "Block any state-changing endpoint if user hasn't accepted current ToS (middleware check)"

### ARCH source
- `api/app/core/middleware.py` (`AuthMiddleware` gates account-status only today)
- `api/app/features/users/service.py` (first-login users created `ACTIVE` with `tos_acceptance_required=true`)

### Depends on
- (M-07 merged)

### What this ticket builds
Add the missing enforcement leg: in `AuthMiddleware`, when the resolved user has `tos_acceptance_required=true`, **reject state-changing methods** (POST/PUT/PATCH/DELETE) with the locked error envelope (a dedicated code, e.g. `TOS_ACCEPTANCE_REQUIRED`) — allowlisting only the endpoints needed to *complete* acceptance (the ToS-accept endpoint itself, `post-login`, `logout`). GET stays readable so the FE can render the modal + content. Today a user who dismisses the modal keeps a fully-capable token; after this, the modal is enforcement, not decoration.

### API contract
- No new endpoints. New error code documented in the error-codes registry; the FE already handles the modal — verify it also handles the 4xx (surfaces the modal again rather than a dead error).

### Tests (required)
- pytest: user with `tos_acceptance_required=true` → POST to any feature endpoint → the ToS error code; ToS-accept endpoint itself allowed; after acceptance the same POST succeeds.
- Vitest: FE maps the new error code to re-presenting the ToS modal.

### Acceptance (demo script)
1. [ ] Dismiss the ToS modal, attempt a state-changing action → blocked with the ToS error
2. [ ] Accept ToS → the same action succeeds
3. [ ] Decline → suspended path unchanged

### Out of scope
- ToS versioning/publishing (M-01, unchanged)

---

## T-243 — Remove the inert nginx placeholder (audit B2)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.25 day
**Status:** todo

### Spec source
- Login-flow audit B2

### ARCH source
- `nginx/conf.d/iqbalai.conf` (T-001 placeholder: no `/idp/`, no SSL, compose service names); STACK_LOCK/ARCH §15.11 (nginx is host-level; the locked config shape lives in §15.11)

### Depends on
- (M-07 merged)

### What this ticket builds
Delete the `nginx/` folder (it is not wired into compose and diverges from §15.11 — a second, wrong "source of truth" that already misled this audit). Add one line to `docs/DEV_CONTAINERS.md` (or the deploy runbook): "nginx is host-level; the only authoritative config shape is ARCH §15.11 — there is intentionally no nginx file in this repo."

### Tests (required)
- N/A (deletion + doc line); CI green proves nothing referenced it.

### Acceptance (demo script)
1. [ ] `nginx/` gone; grep shows no references
2. [ ] The runbook line points to §15.11

### Out of scope
- The staging box's real nginx conf (T-248)

---

## T-244 — Server-side OIDC: API-owned login/callback + §6.17 cookie session (audit C1/C2 backend)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- Login-flow audit C1/C2; ARCH §6.4 (the locked flow diagram: API performs steps 8–9 code+PKCE exchange, step 11 sets HttpOnly cookies), §6.17 (cookie spec), §6 threat table (CSRF row: SameSite=Lax + `state` + **Origin/Referer check on mutating endpoints in middleware**)

### ARCH source
- `api/app/features/auth/router.py` (today: only `post_login` + `accept_invite`); `PUBLIC_PATHS` already reserves `/api/v1/auth/login`, `/api/v1/auth/callback`, `/api/v1/auth/logout` — the API was always meant to own these steps

### Depends on
- T-241 (strict JWT validation underneath the session)

### What this ticket builds
Implement §6.4 as drawn, in the API:
1. **`GET /api/v1/auth/login`** — generates `state` (CSRF), `nonce`, and PKCE verifier+S256 challenge; stores them server-side (Redis, short TTL, keyed by a transient cookie) ; 302-redirects to Authentik's authorize endpoint with challenge+state+nonce. Accepts an optional safe `next` path (allowlisted, relative-only).
2. **`GET /api/v1/auth/callback`** — validates `state`; exchanges `code` + PKCE verifier **server-side** (authlib, per the locked stack); validates the id_token `nonce`; runs the existing `post_login` user-provisioning logic (reuse, don't duplicate); sets the two locked cookies — `iqbalai_access` (JWT, 24h) and `iqbalai_refresh` (opaque reference, 30d), both `Path=/`, `Secure`, `HttpOnly`, `SameSite=Lax` per §6.17; 302-redirects to the role dashboard (or ToS state) using the same role→path mapping as T-239 (single source: return the path from `post_login` or expose the mapping via the API so FE and BE cannot drift).
3. **Refresh** — implement the `iqbalai_refresh` exchange path as §6.17 defines it (opaque reference → new access JWT; rotation on use), server-side only.
4. **Middleware:** `AuthMiddleware` reads the access token **from the cookie** (Authorization-header support may remain during this one milestone for tooling, removed by T-245's cutover commit); add the §6-threat-table **Origin/Referer check on mutating methods** (reject cross-origin POST/PUT/PATCH/DELETE whose Origin isn't our app URL).
- The failed-exchange path returns a real error page/redirect with the locked error envelope semantics — never a hang.

### API contract
- `GET /api/v1/auth/login` → 302 (no body); `GET /api/v1/auth/callback` → 302 + `Set-Cookie` ×2; refresh endpoint per §6.17 with `response_model=` on any JSON leg; all with `operation_id`. `openapi.json`/`schema.d.ts` regenerated.

### Tests (required)
- pytest (API contract, no mocks of our own code): login sets state/nonce/PKCE and redirects with S256 challenge; callback with wrong/missing `state` → rejected; wrong `nonce` → rejected; happy path (Authentik token endpoint faked at the HTTP boundary only) sets both cookies with the exact §6.17 attributes; refresh rotates; cross-origin POST with valid cookie → rejected by the Origin check.
- Cookie-attribute assertions are explicit (HttpOnly, Secure, SameSite=Lax, Max-Age) — this is the C1 fix, prove it.

### Acceptance (demo script)
1. [ ] Full login against real local Authentik: `/login` → Authentik → callback → cookies set → dashboard; no token ever visible to JS
2. [ ] Tampered `state` or `nonce` → clean rejection
3. [ ] Mutating request from a foreign origin → rejected

### Out of scope
- Frontend cutover (T-245); logout (T-246); password/BFF anything (rejected M-07b — this is redirect-flow completion, not replacement)

---

## T-245 — Frontend cookie cutover: retire sessionStorage (audit C1/C2 frontend)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 1 day
**Status:** todo

### Spec source
- Login-flow audit C1; ARCH §6.17 ("Never localStorage. Never JS-accessible.")

### ARCH source
- `frontend/src/lib/auth.ts` (sessionStorage get/set/clear; `getLoginUrl` builds the authorize URL in the browser); `frontend/src/app/auth/callback/OidcCallbackClient.tsx` (browser-side code exchange); `frontend/src/lib/api/index.ts` `request()` (attaches Bearer token)

### Depends on
- T-244, T-239

### What this ticket builds
Cut the frontend over to the API-owned flow: `LoginButton` → navigate to **`/api/v1/auth/login`** (no browser-built authorize URL); delete the browser code-exchange (`OidcCallbackClient` shrinks to handling the post-redirect landing/ToS state the API sends it to); remove every `sessionStorage` token read/write; `request()` sends `credentials: "include"` and stops attaching Authorization headers; user-display state (name/role for the shell) comes from a `GET /auth/me`-style read or the post-login payload — not from a JS-readable token. Remove the now-dead Bearer path from `AuthMiddleware` in the same PR (the one-milestone dual-read T-244 allowed ends here). Update every Vitest/Playwright auth helper to authenticate via the cookie flow.

### API contract
- Consumes T-244's endpoints; if a `/auth/me` read is added it declares `response_model=` + `operation_id` and lands in the regenerated typed client.

### Tests (required)
- Vitest: `request()` sends credentials and never sets Authorization; no module imports sessionStorage for tokens (lint/grep test: `sessionStorage` token usage count = 0 in `src/lib/auth.ts`).
- Playwright `@smoke`: login lands on dashboard with **no token in sessionStorage/localStorage** (explicit assertion) and the session survives a full page reload (cookie, not memory).

### Acceptance (demo script)
1. [ ] Login end-to-end; devtools shows HttpOnly cookies, empty session/local storage
2. [ ] Hard refresh keeps the session; API calls succeed via cookie
3. [ ] All existing suites green under the new auth helpers

### Out of scope
- Any visual login redesign (Authentik theming is T-248; the two-panel design died with M-07b/#21)

---

## T-246 — Server-side logout (audit C5, §6.8)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- Login-flow audit C5; ARCH §6.8 (steps: revoke refresh at Authentik; clear both cookies; JTI blacklist — §6.8 offers blacklist as option 2, **chosen here**: Redis is already in core and `AuthMiddleware` is the single chokepoint, so the cost is one lookup for a real containment win)

### ARCH source
- `frontend/src/lib/auth.ts:100+` (`getLogoutUrl` hits Authentik end-session directly today); `PUBLIC_PATHS` already reserves `/api/v1/auth/logout`

### Depends on
- T-244

### What this ticket builds
`POST /api/v1/auth/logout`: revokes the refresh token at Authentik's revocation endpoint, clears `iqbalai_access` + `iqbalai_refresh` (Max-Age=0), blacklists the access JWT's JTI in Redis with TTL = remaining lifetime; `AuthMiddleware` checks the blacklist. FE logout calls this endpoint (then optionally forwards to Authentik end-session for full SSO sign-out), replacing the direct end-session jump.

### API contract
- `POST /api/v1/auth/logout` → `response_model=SuccessEnvelope[...]`, `operation_id`, in PUBLIC_PATHS (it must work with a dying session), CSRF-safe (Origin check applies).

### Tests (required)
- pytest: logout clears cookies + the old access token is rejected on the next request (blacklist hit) + refresh no longer exchanges.
- Playwright: logout → protected page redirects to `/login`; back-button doesn't resurrect the session.

### Acceptance (demo script)
1. [ ] Logout; the previous access cookie replayed via curl → 401
2. [ ] Refresh token no longer works
3. [ ] UI lands on `/login`, clean state

### Out of scope
- Global "log out all devices" (not specced)

---

## T-247 — Per-role real-backend auth E2E suite (audit D1)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 1 day
**Status:** todo

### Spec source
- Login-flow audit D1; frontend-master Rule 12 (create/update + auth smoke against the REAL backend — never mock the contract)

### ARCH source
- `scripts/seed_dev.py` (extend to seed one user of **every** role in T-239's union, incl. Authentik-side creation — document how each is provisioned)

### Depends on
- T-239, T-244, T-245, T-246, T-242

### What this ticket builds
Playwright specs tagged `@auth @real` (no route mocking), one per role in the union: start at `/login` → complete real OIDC against seeded Authentik → assert callback lands on **that role's** dashboard (T-239's mapping) rendering real content; first-login shows the ToS modal, accept proceeds, and (T-242) a state-changing call while unaccepted is blocked; unauthenticated hit on a protected page → `/login`; negative cases: tampered callback params → clean error, logout kills the session. Wire into the `e2e-smoke` job's real-backend lane so a broken login can never ride a green PR again — this suite is the milestone's proof.

### Tests (required)
- This ticket *is* tests. Red-then-green rule: at least one spec must be demonstrated failing against a deliberately broken config before the fixes make it green (no theater).

### Acceptance (demo script)
1. [ ] All 9 role journeys green against the real composed stack
2. [ ] The suite runs in CI's real-backend lane on every PR (`@auth @real` selected)
3. [ ] Negative cases (tampered state, logout replay, unauth access) covered

### Out of scope
- Load/perf on Authentik

---

## T-248 — Staging deployment alignment + Authentik theming (audit D2/D3 + the M-07b UX goal, sanctioned path)

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.5 day (ops, on the staging box)
**Status:** todo

### Spec source
- Login-flow audit D2/D3; ARCH §15.11 (host nginx config shape incl. `/idp/*` → authentik), §6.15 (users see `<domain>/idp/...`, never a raw port); the branding goal that motivated M-07b, delivered the sanctioned way

### Depends on
- T-240 (documented env vars), T-244/T-245 merged (the flow being deployed)

### What this ticket builds (executable checklist — evidence pasted into the PR)
1. [ ] `sudo nginx -T` on the staging box: conf matches §15.11 — upstreams, SSL server, **`location /idp/` → authentik**; fix to shape if not.
2. [ ] Authentik provider: redirect URI = `https://<domain>/api/v1/auth/callback` (the API callback after T-244), issuer = the public `/idp` application URL — no localhost anywhere.
3. [ ] Frontend + API env on the box: `NEXT_PUBLIC_AUTHENTIK_URL=https://<domain>/idp`, API issuer/audience settings per T-241, `EVENTS_ENABLED` etc. untouched.
4. [ ] **Theme Authentik's hosted login** to the green brand: logo (IqbalLogo SVG from the design work), brand colors on the flow background/buttons via Authentik's branding settings + custom CSS — salvaging the approved visual language from the closed design PR, minus the password-form architecture.
5. [ ] End-to-end proof from a clean external browser: open the app URL → Sign in → branded `/idp` login → role dashboard. Awais/Mufti can be handed **one URL**.

### Tests (required)
- T-247's `@auth @real` suite run against the staging deployment (not just local compose) — pasted output.

### Acceptance (demo script)
1. [ ] A non-technical tester logs in from outside the VM using only the app URL
2. [ ] The URL bar never shows a raw port; the login page carries the green brand
3. [ ] D2/D3 evidence attached to the PR

### Out of scope
- Production box (repeat at pilot); DNS/TLS issuance (assumed present)

---

## T-249 — M-07a PR + demo

**Layer:** 3
**Milestone:** M-07a
**Estimate:** 0.25 day
**Status:** todo

### Depends on
- T-238 … T-248

### What this ticket builds
One milestone PR (merge commit) off post-M-07 `staging`. Demo video: the full tester journey (public URL → branded login → each key role's dashboard), the ToS gate blocking then allowing, logout killing the session, devtools showing cookie-only auth, and the CI run with the `@auth @real` suite green. ROADMAP M-07a → done (auto-rolled-up); M-08 `Depends on: M-07a`.

### Acceptance (demo script)
1. [ ] All M-07a tickets `done`; all CI gates green incl. the new auth suite
2. [ ] Demo covers login/ToS/logout/cookie evidence + staging deployment
3. [ ] No `sessionStorage` token code remains anywhere (repo-wide grep in the demo)

### Out of scope
- M-08 content

---

## Drafting completeness ledger

**Audit fixes delivered:** C6 (T-238, with M-05 hotfix gate), A1 (T-239), B1 (T-240), C3 (T-241), C4 (T-242), B2 (T-243).
**§6.4 conformance delivered:** C1+C2 (T-244 backend + T-245 frontend cutover), C5 (T-246) — the flow now matches the locked diagram: API-owned state/nonce/PKCE + exchange, §6.17 cookies, §6-threat-table CSRF (SameSite=Lax + state + Origin/Referer middleware), server-side logout with JTI blacklist (§6.8 option 2, decision recorded in T-246).
**Proof + deployment:** T-247 per-role `@auth @real` suite (red-then-green obligation); T-248 staging alignment + Authentik green theming (replaces the rejected M-07b's UX goal on the sanctioned path).
**Explicit non-goals:** no password form, no BFF credential exchange, no IdP change (Auth0 remains forbidden), no login-page redesign in-app (visuals live in Authentik theming). M-07b is retired; its T-238–T-247 range is reclaimed here (recorded in the header).
**Decisions recorded:** §6.8 option-2 JTI blacklist chosen (T-246); dual Bearer/cookie middleware read allowed only within this milestone, removed at T-245.
**No new BLOCKED-HOOKs.** **Stack:** authlib (already locked) does the server-side exchange; Redis (core) holds state/PKCE + blacklist; zero new dependencies.
