us# M-07b — Custom Login + Unified Auth Hub (Authentik BFF)

<!-- MODERNIZED: hardened-template gates apply (post-M-01a). Do not remove. -->
> **Hardened-template note (post-M-01a).** The foundation gates apply to **every ticket here regardless of its wording**, enforced via `.claude/CLAUDE.md` + CI:
> - **Data-model blocks are design intent, not literal DDL** — implement model-first (`alembic revision --autogenerate` → review; one concern per migration; ARCH §4.12).
> - **Every endpoint declares `response_model=`**; its FE type is generated via openapi-typescript (`schema.d.ts`), never hand-mirrored (AMENDMENTS A-002).
> - **Any ticket with a frontend** requires Vitest + RTL **and** a Playwright E2E of the acceptance path, plus the UX-acceptance checklist (reachable from nav, real content, scrollable, responsive, RTL, i18n).
> The per-ticket fields (API contract / Tests / UX acceptance) are added just-in-time when each ticket is implemented; their absence here does **not** waive the gates.


**Status:** drafted
**Estimated duration:** 1-1.5 weeks
**Tickets:** T-238 through T-247 (non-positional numbering — off T-237 high-water mark; same convention as M-01a)
**Spec source:** `flow-1-platform-setup.md` §3.1 (login), `flow-2-admin-coordinator-setup.md` §3.1 (Path A invite), `flow-4-student-onboarding.md` §3.1 + §3.3 (student invite + parent signup), ARCH §6.1–§6.6 + §6.20

## Goal

Replace the current **redirect-to-Authentik-UI** login experience with a **fully branded IqbalAI auth surface**. End users type email + password on `/login` inside the app; the FastAPI backend authenticates against Authentik server-side (BFF pattern). Authentik remains the identity provider — passwords, MFA, lockout, and email verification stay in Authentik — but users never see the Authentik login screen in the normal path.

Unify scattered signup entry points (`/independent/signup`, `/parent/signup`, `/accept-invite`) under a single **Create account** hub so new users understand where to go. School users (admin, coordinator, teacher, student) still enter via invite — no public school signup.

**Scope boundary:** auth UX + BFF login/session only. Role onboarding (teacher profile, student mode pick, etc.) stays in M-04/M-05/M-06. Exam framework, diagnostic, lectures = later milestones.

**Demo at milestone end:**
- Any user (Platform Admin, School Admin, Teacher, Student, Parent, Independent Teacher/Student) logs in at `/login` with **email + password** on the IqbalAI-branded page — no Authentik UI redirect
- First login still runs post-login + ToS modal (M-01 behaviour preserved)
- Forgot password flow works end-to-end from `/login/forgot-password` (custom UI, Authentik-backed reset email)
- `/signup` hub shows: "I have an invite" → `/accept-invite`, "Independent teacher/student" → `/independent/signup`, "Parent" → `/parent/signup`, "School staff/student" → explain invite-only path
- After signup, user returns to custom `/login` (not Authentik authorize URL)
- OIDC browser redirect kept behind `AUTH_LOGIN_MODE=oidc_redirect` env fallback only (dev/SSO escape hatch)

---

## T-238 — Auth UX amendment: custom login BFF pattern (ARCH addendum)

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.1 (all roles log in)
- `flow-2-admin-coordinator-setup.md` §3.1 Path A (invited users set password, then log in)

### ARCH source
- `ARCHITECTURE.md` §6.1 (Authentik owns credentials), §6.4 (OIDC — amend with BFF primary path), §6.6 (AuthMiddleware)

### Depends on
- M-00 T-004 (Authentik), M-01 T-016 (post-login)

### What this ticket builds

Document the **locked amendment** to §6.4: primary login path becomes **BFF credential exchange**, not browser redirect to Authentik UI.

**Locked decisions (record in `AMENDMENTS.md` + ARCH §6.4 addendum):**
1. **Login identifier = email** (matches Authentik `username=email` convention from `infrastructure/authentik/client.py`). Display name is profile metadata only — never a login field.
2. **BFF flow:** `POST /api/v1/auth/login` receives `{email, password}` → FastAPI calls Authentik server-side (flow executor or token endpoint) → receives access + refresh tokens → sets HttpOnly cookies (`iqbalai_access`, `iqbalai_refresh` per §6.4) → frontend calls existing `POST /api/v1/auth/post-login` → role-based redirect.
3. **Authentik stays IdP:** no passwords stored in app DB; rate limiting + lockout delegated to Authentik.
4. **OIDC redirect** demoted to fallback (`AUTH_LOGIN_MODE=oidc_redirect`); default = `bff`.
5. **Session storage migration:** retire `sessionStorage` JWT for auth (current frontend); align with ARCH §6.4 HttpOnly cookies.

### Acceptance (demo script)

1. [ ] `AMENDMENTS.md` entry added with the five locked decisions above
2. [ ] ARCH §6.4 addendum documents BFF sequence diagram alongside existing OIDC redirect diagram
3. [ ] `ENV_VARS.md` documents `AUTH_LOGIN_MODE` (`bff` | `oidc_redirect`, default `bff`)

### Out of scope
- Implementation (T-239–T-245)

---

## T-239 — Authentik BFF auth client (server-side credential validation)

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 2 days
**Status:** todo

### ARCH source
- `ARCHITECTURE.md` §6.3 (Authentik setup), §6.12 (Authentik admin sync)
- `infrastructure/authentik/client.py` (extend — user lifecycle client stays separate)

### Depends on
- T-238 (amendment locked), M-00 T-004 (Authentik)

### What this ticket builds

**Backend:** `infrastructure/authentik/auth.py` — server-side auth chokepoint (parallel to existing user-lifecycle client):

- `authenticate(email, password) -> TokenPair` — validates credentials against Authentik; returns `access_token`, `refresh_token`, `expires_in`
- `refresh(refresh_token) -> TokenPair` — silent refresh
- `revoke(refresh_token) -> None` — logout
- `request_password_reset(email) -> None` — triggers Authentik recovery email (no account enumeration leak in API response)
- `confirm_password_reset(token, new_password) -> None` — completes reset when user clicks email link

`DevAuthentikClient` stub extended for local dev/tests (accept known seed passwords from `scripts/seed_dev.py`).

### API contract
- N/A (infrastructure module; consumed by T-240)

### Tests (required)
- pytest unit: successful auth returns tokens; wrong password → `INVALID_CREDENTIALS`; inactive user → `ACCOUNT_SUSPENDED`; dev stub parity

### Acceptance (demo script)

1. [ ] `authenticate()` returns a valid JWT for a seed-dev user
2. [ ] Wrong password raises structured error (no stack trace leak)
3. [ ] `refresh()` + `revoke()` round-trip works
4. [ ] Password reset request is idempotent (same response whether email exists or not)

### Out of scope
- HTTP endpoints (T-240)
- MFA UI (Phase 2 — Authentik handles MFA server-side if enabled)

### Notes / known gotchas
- Use Authentik's recommended server-side flow API; do **not** enable Resource Owner Password Grant on a public SPA client. Credentials hit only the FastAPI backend.

---

## T-240 — Auth API endpoints: login, refresh, logout, password reset

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.1, §3.6 (ToS gate after login)

### ARCH source
- `ARCHITECTURE.md` §6.4 (cookies), §6.6 (PUBLIC_PATHS), §5.4 (error envelopes)

### Depends on
- T-239 (BFF client), M-01 T-016 (`post-login` handler)

### What this ticket builds

**Backend endpoints** (all on `api/app/features/auth/router.py`):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/login` | email + password → set HttpOnly cookies → return `PostLoginResponse` (reuse post-login logic inline) |
| `POST` | `/api/v1/auth/refresh` | refresh cookie → new access cookie |
| `POST` | `/api/v1/auth/logout` | revoke refresh + clear cookies |
| `POST` | `/api/v1/auth/forgot-password` | `{email}` → trigger reset email |
| `POST` | `/api/v1/auth/reset-password` | `{token, new_password}` → complete reset |

Wire paths into `PUBLIC_PATHS` in middleware. Update `AuthMiddleware` to read JWT from `iqbalai_access` HttpOnly cookie **or** `Authorization: Bearer` header (header kept for API clients/tests during transition).

Error codes: `INVALID_CREDENTIALS`, `ACCOUNT_SUSPENDED`, `EMAIL_NOT_VERIFIED`, `RATE_LIMITED`.

### API contract
- **Endpoints:** as table above
- **Request models:** `LoginRequest`, `ForgotPasswordRequest`, `ResetPasswordRequest`
- **Response models:** `response_model=SuccessEnvelope[PostLoginResponse]` on login; `SuccessEnvelope[None]` on forgot-password (always 200)

### Tests (required)
- pytest API contract per endpoint; cookie attributes asserted (`HttpOnly`, `Secure` in prod, `SameSite=Lax`)
- suspended user login → `ACCOUNT_SUSPENDED`; unverified email → `EMAIL_NOT_VERIFIED` with resend hint

### Acceptance (demo script)

1. [ ] `POST /api/v1/auth/login` with valid seed credentials sets cookies + returns user role
2. [ ] Invalid credentials → 401 `INVALID_CREDENTIALS` (generic message — no "user not found" leak)
3. [ ] `POST /api/v1/auth/logout` clears cookies; subsequent protected call → 401
4. [ ] Forgot-password always returns 200 regardless of email existence
5. [ ] `PUBLIC_PATHS` includes all five new routes

### Out of scope
- Frontend forms (T-241, T-243)

---

## T-241 — Custom login page (email + password, IqbalAI branded)

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` §3.1

### ARCH source
- `ARCHITECTURE.md` §12 (frontend), §13 (i18n), `frontend-master/references/four_ui_states.md`

### Depends on
- T-240 (login endpoint), M-01 T-016 (post-login + ToS redirect logic)

### What this ticket builds

**Frontend:** Replace `/login` redirect-button with a real login form:

- Fields: **email**, **password** (show/hide toggle)
- Links: "Forgot password?" → `/login/forgot-password`; "Create account" → `/signup`
- Submit → `POST /api/v1/auth/login` (cookies set by browser) → if `tos_acceptance_required` → ToS modal (reuse `TosModal`) → else `getPostLoginPath(role)`
- Error states: invalid credentials, suspended, email not verified, rate limited
- Loading state on submit; form disabled while loading
- Language switcher preserved from current login page
- **No** `getLoginUrl()` redirect in the default path

Update `use-client-auth` hook + `apiClient` to send cookies (`credentials: 'include'`) instead of reading `sessionStorage` token.

### Tests (required)
- Vitest: form validation, error rendering, loading state
- Playwright `@smoke`: seed Platform Admin logs in via form → lands on `/admin`

### Acceptance (demo script)

1. [ ] `/login` shows email + password form in IqbalAI branding (not a redirect button)
2. [ ] Successful login routes Platform Admin to `/admin` without visiting Authentik UI
3. [ ] Wrong password shows inline error; no redirect
4. [ ] ToS modal still appears on first login / version bump
5. [ ] All strings via i18n keys in en/ur/sd/ps; RTL layout correct

### UX acceptance
- [ ] Reachable as app entry point (unauthenticated users hitting `/` redirect to `/login`)
- [ ] Four UI states handled
- [ ] Responsive + RTL-safe

### Out of scope
- Signup hub (T-242)
- Forgot-password page (T-243)

---

## T-242 — Unified signup hub (`/signup` + create-account routing)

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §3.1 Path A (school invite)
- `flow-4-student-onboarding.md` §3.1 (student invite), §3.3 (parent self-register)
- M-05 scope (independent self-signup)

### ARCH source
- `ARCHITECTURE.md` §6.20 (independent signup), §6.13 (parent)

### Depends on
- M-05 T-069 (independent signup), M-06 T-080 (parent signup), M-02 T-030 (invite accept)
- T-241 (login page links here)

### What this ticket builds

**Frontend:** New `/signup` landing page — **Create account** hub with four cards:

1. **"I have a school invite"** → `/accept-invite` (enter token or follow email link)
2. **"Independent teacher or student"** → `/independent/signup` (existing form)
3. **"Parent"** → `/parent/signup` (existing form)
4. **"School staff or student (no invite?)"** → informational panel: contact your school admin; no public school signup at launch

Each existing signup page gets a consistent header ("Back to login" → `/login`, "Back to signup options" → `/signup`). Remove post-signup redirect to `getLoginUrl()` (Authentik); redirect to `/login?email=<prefill>` instead.

### Tests (required)
- Playwright `@smoke`: hub renders four paths; independent signup success lands on `/login` with email hint

### Acceptance (demo script)

1. [ ] `/signup` hub reachable from `/login` "Create account" link
2. [ ] All three actionable paths route to the correct existing signup flow
3. [ ] School "no invite" card explains invite-only policy (no dead-end)
4. [ ] After independent/parent signup, user lands on custom `/login` (not Authentik)
5. [ ] i18n + RTL on hub page

### Out of scope
- Rewriting independent/parent signup forms (only navigation + post-signup redirect change)

---

## T-243 — Forgot password + reset password (custom UI)

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 1.5 days
**Status:** todo

### Spec source
- `flow-2-admin-coordinator-setup.md` §5.1 (invite expiry — distinct from password reset)

### ARCH source
- `ARCHITECTURE.md` §6.1 (Authentik owns password reset)

### Depends on
- T-240 (forgot/reset endpoints), T-241 (login page link)

### What this ticket builds

**Frontend:**
- `/login/forgot-password` — email form → `POST /api/v1/auth/forgot-password` → always shows "If an account exists, we sent instructions" success state
- `/login/reset-password?token=...` — new password + confirm → `POST /api/v1/auth/reset-password` → success → link to `/login`

**Backend:** ensure Authentik recovery email template links to `{APP_URL}/login/reset-password?token=...` (configure in Authentik or override redirect URL in BFF client).

### Tests (required)
- Vitest: form validation, success/error states
- Playwright: forgot-password submit shows success; reset with invalid token shows error

### Acceptance (demo script)

1. [ ] Forgot-password flow completes without exposing whether email exists
2. [ ] Reset link from email opens custom `/login/reset-password` page
3. [ ] Successful reset → user can log in at `/login` with new password
4. [ ] Expired/invalid token → clear error + link back to forgot-password

### Out of scope
- Invite-token password setup (`/accept-invite` — stays separate, M-02)

---

## T-244 — Session migration: HttpOnly cookies + remove sessionStorage auth

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 1.5 days
**Status:** todo

### ARCH source
- `ARCHITECTURE.md` §6.4 (HttpOnly cookies — locked), §6.6 (middleware)

### Depends on
- T-240 (cookie-setting endpoints), T-241 (login form)

### What this ticket builds

Migrate the entire frontend auth stack from `sessionStorage` JWT to cookie-based sessions:

- `apiClient` / TanStack Query hooks: `credentials: 'include'` on all authenticated requests; remove `Authorization` header assembly from `getToken()`
- `AuthMiddleware` backend: prefer `iqbalai_access` cookie, fall back to `Bearer` header for transition
- Remove `TOKEN_KEY` / `USER_KEY` sessionStorage usage for auth (keep `USER_KEY` as optional client-side cache of post-login response if needed, but not as auth source)
- Update `OidcCallbackClient` to work only in `oidc_redirect` fallback mode
- Update logout: `POST /api/v1/auth/logout` + clear any client cache
- Update all shells (`AdminShell`, `TeacherShell`, etc.) logout buttons

### Tests (required)
- Vitest: apiClient sends credentials
- pytest: middleware reads cookie; header fallback still works
- Regression: existing smoke tests updated to cookie auth

### Acceptance (demo script)

1. [ ] No auth token in `sessionStorage` after login (grep E2E assertion)
2. [ ] Protected API calls succeed with cookies only
3. [ ] Logout clears session completely
4. [ ] All role shells logout correctly

### Out of scope
- Mobile app auth (Phase 2)

### Notes / known gotchas
- This ticket touches many files — keep diff focused on auth transport only; do not refactor shells beyond logout wiring.

---

## T-245 — Deprecate OIDC redirect login (feature-flag fallback)

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 0.5 day
**Status:** todo

### ARCH source
- `ARCHITECTURE.md` §6.4 (OIDC redirect demoted to fallback)

### Depends on
- T-241 (custom login default), T-244 (cookie session)

### What this ticket builds

- `AUTH_LOGIN_MODE` env (`bff` default, `oidc_redirect` fallback) wired in frontend + backend
- When `bff`: `/login` shows credential form only; `getLoginUrl()` unused
- When `oidc_redirect`: restore current redirect-button behaviour (for dev/SSO debugging)
- Remove `getLoginUrl()` calls from signup success flows (already done in T-242)
- Document in `docs/runbooks/first-time-setup.md`

### Acceptance (demo script)

1. [ ] Default (`bff`) — no code path redirects end users to Authentik UI for login
2. [ ] `oidc_redirect` mode restores old behaviour for debugging
3. [ ] `.env.example` documents the flag

### Out of scope
- Authentik UI branding/theming (unnecessary once BFF is default)

---

## T-246 — E2E smoke test (custom login all personas)

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 1 day
**Status:** todo

### Depends on
- T-241 through T-245

### What this ticket builds

**Test harness:** Playwright `@smoke` spec `custom-login-smoke.spec.ts`:

1. Platform Admin — custom login → `/admin`
2. School Teacher (seed) — custom login → `/teacher`
3. Independent student (signup → custom login) → `/independent/student`
4. Parent (signup → custom login) → parent home
5. Forgot-password request returns success UI
6. Assert Authentik UI URL never appears in browser navigation during tests

Runs in CI against compose stack + `seed_dev.py`.

### Acceptance (demo script)

1. [ ] E2E green in CI
2. [ ] All four persona logins asserted
3. [ ] No Authentik UI navigation asserted
4. [ ] Cookie auth asserted (no sessionStorage token)

### Out of scope
- Full regression of every role shell (spot-check personas sufficient)

---

## T-247 — Milestone M-07b PR + demo

**Layer:** 2
**Milestone:** M-07b
**Estimate:** 0.5 day
**Status:** todo

### Depends on
- T-238 through T-246

### What this ticket builds

Single milestone PR per `WORKFLOW.md` Step 2. Demo video (5 min): custom login for two personas, signup hub navigation, forgot-password, confirm no Authentik UI visible.

### Acceptance (demo script)

1. [ ] All M-07b tickets `done`; CI green (including T-246 E2E)
2. [ ] PR description cites ARCH §6.4 amendment + AMENDMENTS entry
3. [ ] Live demo for Abd. + Awais
4. [ ] ROADMAP M-07b → done

### Out of scope
- Anything beyond M-07b ticket set

---

## Milestone notes

- **Why M-07b and not folded into M-01?** M-01 established OIDC redirect as the login path. This milestone is a deliberate UX pivot once core features (M-02–M-07) exist; numbering `07b` places it after exam framework without renumbering M-08+.
- **Authentik is still the IdP.** This milestone changes *where* users type credentials, not *who* stores them. No passwords in the app DB (ARCH §6.1 unchanged).
- **Login = email, not display name.** `display_name` is profile metadata collected at signup/onboarding.
- **School users remain invite-only.** The signup hub explains this; it does not add public school registration.
- **Highest-risk ticket: T-244** (session migration touches every authenticated surface). Implement after T-240–T-243 are stable.
- **Depends on:** M-00 (Authentik), M-01 (post-login + ToS), M-02 (invite accept), M-05 (independent signup), M-06 (parent signup — for hub routing; can stub parent card if M-06 not merged yet).

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-07-07 | Initial M-07b milestone drafted. Custom login BFF on Authentik, unified signup hub, forgot-password, cookie session migration. Tickets T-238–T-247. | @shaabii (with Claude) |
