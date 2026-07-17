# Session state (live — Claude Code updates this)

**Current milestone:** M-07a — Login Flow Remediation
**Branch:** milestone/M-07a-login-flow-remediation (forked off staging @ 5e438cf, post-M-07)
**Current ticket:** T-238 done; next = T-239

## Environment constraints (this dev clone — check before trusting "gate passed")
- No Python/uv/pre-commit/Docker installed here → ruff/mypy/pytest CANNOT be run locally. Every commit this session is format-gate-unverified; needs CI or a real toolchain to confirm.
- No GitHub push access (403 for authenticated account Hamza-Nawaz5588) → all branches are LOCAL ONLY, nothing pushed, no PRs opened yet.

## Done this milestone
- T-238 — Removed PUBLIC_PATHS auth-bypass for `/independent/students/me/exam-frameworks` (M-05 landed, audit C6). Gated route with `require_role("independent_student")`; added router 401/200/403 tests + PUBLIC_PATHS snapshot test. Hotfix commit 12011ef on local `fix/exam-frameworks-auth-bypass` (branched off staging, NOT pushed — needs push+PR to staging separately). Cherry-picked onto milestone branch as f46b363.

## Next step
- Invoke ticket-loader for T-239 (exhaustive getPostLoginPath + TS never guard).

## Outstanding human/ops gates (not auto-completable)
- Push `fix/exam-frameworks-auth-bypass` + open hotfix PR to staging (blocked on GitHub write access).
- T-248 (staging ops/Authentik theming) and T-249 (demo + milestone PR) are human-gated per the milestone brief.
- All local commits need a real ruff/mypy/pytest run (CI or a machine with the toolchain) before any PR is trustworthy.
