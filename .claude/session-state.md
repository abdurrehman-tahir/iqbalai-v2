# Session state (live — Claude Code updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** milestone/M-07a-login-flow-remediation (forked off staging @ 5e438cf, post-M-07)
**Current ticket:** T-240 done; next = T-241

## Environment constraints (this dev clone — check before trusting "gate passed")
- No Python/uv/pre-commit/Docker installed here → backend ruff/mypy/pytest CANNOT be run locally. Backend commits this session are format-gate-unverified; need CI or a real toolchain to confirm.
- Frontend toolchain DOES work: `frontend/` has `pnpm install`'d node_modules now (large `next`/`@next/swc-win32-x64` tarballs need `--fetch-timeout 300000`, registry is slow on this network). `esbuild`'s postinstall was skipped by pnpm's build-approval gate — fixed by running `node node_modules/.pnpm/esbuild@0.21.5/node_modules/esbuild/install.js` once (`sharp`/`unrs-resolver` still unbuilt but unneeded for lint/typecheck/test). Run checks via the bash wrapper scripts directly (`./node_modules/.bin/tsc --noEmit`, `./node_modules/.bin/vitest run <file>`, `ESLINT_USE_FLAT_CONFIG=false ./node_modules/.bin/eslint <files>` — repo's `.eslintrc.json` is legacy format, ESLint 9 defaults to flat config). No `format`/prettier script exists in package.json despite CLAUDE.md's format gate listing `pnpm --dir frontend format` — pre-existing gap, not introduced this session.
- No GitHub push access (403 for authenticated account Hamza-Nawaz5588) → all branches are LOCAL ONLY, nothing pushed, no PRs opened yet.

## Done this milestone
- T-238 — Removed PUBLIC_PATHS auth-bypass for `/independent/students/me/exam-frameworks` (M-05 landed, audit C6). Gated route with `require_role("independent_student")`; added router 401/200/403 tests + PUBLIC_PATHS snapshot test. Hotfix commit 12011ef on local `fix/exam-frameworks-auth-bypass` (branched off staging, NOT pushed). Cherry-picked onto milestone branch as f46b363. Backend-only — NOT verified locally (no Python toolchain).
- T-239 — Exhaustive `getPostLoginPath` switch (student/parent cases + never-guard default), `Role` type re-exported from generated OpenAPI schema in `lib/api/types.ts`, `ALL_ROLES` single-source-of-truth array with compile-time completeness check, test rewritten to iterate `ALL_ROLES`. Commit 906f50c. VERIFIED locally: tsc clean, eslint clean, vitest 19/19 green.
- T-240 — `assertAuthEnv()` (src/lib/env-guard.ts) wired into next.config.ts: prod build fails loudly if NEXT_PUBLIC_AUTHENTIK_URL/APP_URL/AUTHENTIK_CLIENT_ID unset, dev warns. Documented all three in .env.example (/idp-form note) and fixed .env.prod.example's own raw-port bug. Commit ab13a87. VERIFIED locally incl. a real `NODE_ENV=production next build` actually failing/passing as expected (not just unit tests).

## Next step
- Invoke ticket-loader for T-241 (JWT §6.5: ES256+RS256, verify iss+aud, JWKS TTL 3600 — backend, audit C3). NOTE: check whether uv/Python install (attempted via astral.sh installer, background task) succeeded before assuming backend commits are still unverified.

## Outstanding human/ops gates (not auto-completable)
- Push `fix/exam-frameworks-auth-bypass` + open hotfix PR to staging (blocked on GitHub write access).
- T-248 (staging ops/Authentik theming) and T-249 (demo + milestone PR) are human-gated per the milestone brief.
- All backend commits need a real ruff/mypy/pytest run (CI or a machine with uv/Python) before any PR is trustworthy. Frontend commits from T-239 onward ARE locally verified.
