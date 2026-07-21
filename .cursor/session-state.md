# Session state (live — Cursor agent updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** (local clone; not pushed — no GitHub write access in this env)
**Current ticket:** T-247 — Per-role real-backend auth E2E — IN PROGRESS (two blockers implemented, unverified without Docker)

## Done this session (T-247)
- Blocker 2 (11 broken @smoke specs): added `GET /auth/me` mock (helpers/mock-api.ts + 7 inline-mock specs) and removed all dead `sessionStorage` token seeding across the 11 specs. Cookie-session shells now resolve `useCurrentUser()`.
- Blocker 1 (Authentik OIDC provider bootstrap): chose the **blueprint** approach.
  - New `infrastructure/authentik/blueprints/iqbalai-oidc.yaml` (OIDC provider + application `iqbalai` + custom `role`/`tenant_type` claims scope mapping).
  - docker-compose: mount blueprint dir into authentik-server + worker; add `AUTHENTIK_BOOTSTRAP_TOKEN` + OIDC `!Env` inputs.
  - `.env.example` + `docs/ENV_VARS.md`: `AUTHENTIK_BOOTSTRAP_TOKEN`, `OIDC_REDIRECT_URI`.
  - `scripts/bootstrap_authentik.py`: stub → read-only blueprint verifier.
  - `scripts/seed_e2e_auth_users.py` + `authentik/client.py`: new `set_attributes`; seed stamps role/tenant_type so claims mapping emits them (needed for the 2 independent journeys). Tests updated.
  - CI `e2e-smoke`: OIDC + bootstrap token wired; removed the "token stays unset / specs skip" stub path.

## NOT verified (no Docker/Node deps in this env)
- Nothing ran against live Authentik/Postgres. Blueprint schema (redirect_uris shape, flow slugs, cert name) is UNVERIFIED for goauthentik 2024.12 — confirm on first real CI run.
- Frontend: ReadLints clean + py_compile clean; prettier/eslint NOT run (no node_modules).

## Done this session (T-248 — repo-side theming, checklist #4 partial)
- Discovered the Authentik green rebrand already exists in-repo (commit `7e955d1`): `custom.css` (green skin), `login-bg.png` (designed green two-panel bg), `logo.png`. The ticket-loader dossier's "assets missing" claim was wrong (Glob didn't surface the committed PNGs).
- Only real gap = logo color: swapped the **blue** eagle for a **brand-green** eagle (same silhouette + "IQBAL AI" wordmark), trimmed + downscaled to 390×260 / ~93 KB. Only `infrastructure/authentik/logo.png` changed.
- T-248 stays `Status: todo` — remaining items are ops-on-the-staging-VM (nginx `/idp/`, real redirect URI/issuer, `NEXT_PUBLIC_AUTHENTIK_URL`, external-browser proof, `@auth @real` on staging).

## Follow-ups flagged
- `getLogoutUrl` still targets application slug `iqbalai-frontend` (+ NEXT_PUBLIC_AUTHENTIK_CLIENT_ID) — blueprint creates `iqbalai`. Logout test tolerates it (URL matches /end-session/), but align slug in a follow-up.
- Production role/tenant_type claim emission (invite flow) uses the same attribute path — verify invite/signup set these attributes too (out of T-247 scope).
- Optional T-248 reproducibility follow-up: declarative `authentik_core.brand` blueprint (title + logo + flow background) so branding self-applies instead of manual Brand-admin clicks.
- Brand consistency: the frontend app shell is still **blue** (`tailwind.config.ts` brand scale + `--primary`), while the login is green — reconcile if a single brand identity is intended (HARD GOVERNANCE GATE: locked design surface, needs an AMENDMENTS entry before changing).
