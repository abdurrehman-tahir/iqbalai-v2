# Session state (live — Claude Code updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** milestone/M-07a-login-flow-remediation (forked off staging @ 5e438cf, post-M-07)
**Current ticket:** T-242 done; next = T-243

## Environment (toolchain now fully working — update from earlier session)
- uv installed manually to `~/.local/bin` (astral.sh installer script hung on this network; downloaded the GitHub release zip directly instead). `uv python install 3.12` + `uv sync --group dev` both work. Backend pytest/ruff/mypy genuinely run now. Each Bash call needs `export PATH="/c/Users/RAJA MUDASSAR/.local/bin:$PATH"` (not persisted globally in this environment).
- Frontend toolchain also works (pnpm installed, esbuild manually rebuilt — see earlier note). Both stacks are now locally verifiable.
- No GitHub push access (403 for Hamza-Nawaz5588) → all branches still LOCAL ONLY, nothing pushed, no PRs opened.
- Known pre-existing, NOT-my-scope mypy gap (confirmed present on staging before this session): `import-untyped` errors for celery/boto3/fastembed/openpyxl/jose across ~14 files repo-wide — no `types-*` stub packages declared. Don't fix without asking (adding deps needs approval).
- Full-repo `uv run pytest app/ -q` is slow (heavy ML/RAG deps) — don't block on it; prefer targeted test runs scoped to touched packages.

## Done this milestone
- T-238 — Removed PUBLIC_PATHS auth-bypass for `/independent/students/me/exam-frameworks`. Hotfix commit 12011ef on local `fix/exam-frameworks-auth-bypass` (not pushed). Cherry-picked onto milestone branch as f46b363.
- T-238 follow-up (commit 0561141) — verifying T-238 with the real toolchain surfaced: (1) `independent_student_onboarding/tests/` had no `__init__.py`, so its tests never actually ran; (2) once running, `require_role("independent_student")` on all 3 routes there was a no-op cross-tenant gate (ROLE_HIERARCHY's "X or higher" isn't tenant-aware — any authenticated role passed). Fixed with new `require_independent_student()` exact-match dependency + regression tests. **FLAGGED for Abd.: the shared `require_role`/ROLE_HIERARCHY design gap likely affects other independent-tenant routes using the same pattern — not fixed repo-wide, needs triage.**
- T-239 — Exhaustive `getPostLoginPath` switch. Commit 906f50c. Verified: tsc/eslint/vitest all green.
- T-240 — `assertAuthEnv()` fail-loud prod guard. Commit ab13a87. Verified incl. a real `next build` pass/fail check.
- T-241 — JWT §6.5 hardening: algorithms ["ES256","RS256"], iss/aud verification, JWKS TTL 300->3600, leeway=30 (had to move `leeway` inside `options={}` after a real pytest run caught a wrong top-level-kwarg attempt). Commit cd3266f. Verified: `pytest app/core/` 74/74 green. Full backend suite (544/544, ~38min) confirmed zero regressions.
- T-242 — ToS middleware gate: AuthMiddleware blocks POST/PUT/PATCH/DELETE with 403 TOS_ACCEPTANCE_REQUIRED unless the caller accepted the current ToS or is hitting an allowlisted path (post-login/accept-tos/decline-tos/logout — logout listed proactively for T-246). FE: `isTosAcceptanceRequiredError()` mapping primitive in lib/api/index.ts + tests. Commit 8d64e8b. Verified: backend 88/88 (core+tos) + full suite 544/544 green; frontend vitest 201/201 (52 files), tsc/eslint clean. **Deliberately NOT done**: wiring the FE mapping into a global QueryClient interceptor (providers.tsx) so it fires from any page — flagged as a follow-up needing its own UX sign-off, not guessed at.

## Next step
- Invoke ticket-loader for T-243 (delete inert nginx/ placeholder, audit B2).

## Outstanding human/ops gates (not auto-completable)
- Push `fix/exam-frameworks-auth-bypass` + open hotfix PR to staging (blocked on GitHub write access).
- T-248 (staging ops/Authentik theming) and T-249 (demo + milestone PR) are human-gated per the milestone brief.
- All local commits are now genuinely toolchain-verified (backend + frontend) but still need a push + real CI run before merge — nothing has left this machine yet.
- **New finding to raise with Abd.**: `require_role()`'s hierarchy check (ARCH §6.19) treats `independent_student`/`independent_teacher` as sharing a numeric scale with school-tenant roles, so `require_role("independent_student")` (and likely `require_role("independent_teacher")`) passes for ANY authenticated role. Only fixed at the 3 routes touched in T-238's follow-up — other callers of this pattern repo-wide are unaudited.
