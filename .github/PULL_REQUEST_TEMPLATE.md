<!--
  ⚠️  Do not delete sections from this template.
  Empty required fields will cause the `pr-template-check` workflow to BLOCK this PR.
  The `phase-complete-review` skill (when active) auto-fills most of this.
-->

## Summary

<!-- One paragraph: what does this PR do, in plain English? -->

## Type

<!-- Tick exactly one -->
- [ ] feat — new feature
- [ ] fix — bug fix
- [ ] chore — tooling, config, dependency bumps
- [ ] docs — documentation only
- [ ] refactor — code change without behavior change
- [ ] test — tests only
- [ ] perf — performance improvement
- [ ] deviation — adds an entry to docs/DEVIATIONS.md
- [ ] release — staging → main release

## Phase & feature reference

- **Phase:** <!-- e.g., Phase 2 — Teacher Onboarding -->
- **Feature(s) from v2 doc:** <!-- e.g., #17 Curriculum vs Reference Book, #18 Curriculum Structured Parsing -->

## Stack compliance

- [ ] I have read `docs/STACK_LOCK.md` before writing this code.
- [ ] All new imports are in `docs/STACK_LOCK.md` (or in `docs/DEVIATIONS.md`).
- [ ] All external services accessed via env vars (no hardcoded URLs or keys).
- [ ] If schema changed, an Alembic migration is included.
- [ ] If visible text was added, translation keys (not raw English) are used.

**Architecture decisions touched** (list section references from `docs/ARCHITECTURE.md` once it exists):

<!-- e.g., ARCHITECTURE.md §3.2 RAG pipeline, §5.1 Multi-tenancy -->

**Deviations from STACK_LOCK.md** (require @abdurrehman approval):

<!-- List any. If none, write "None." -->

## Self-review (auto-filled by `phase-complete-review` skill)

<!-- Claude Code fills this section. Do not edit manually. -->

- [ ] Read STACK_LOCK.md → confirmed compliant
- [ ] All libraries used appear in STACK_LOCK.md or DEVIATIONS.md
- [ ] Tests: happy path + ≥1 failure mode
- [ ] Pydantic models at every API boundary
- [ ] UI: loading / empty / error / success states present
- [ ] All visible strings use i18n keys
- [ ] Secrets in env vars, not hardcoded
- [ ] Logs are structured + PII-scrubbed
- [ ] Migration included if schema changed
- [ ] No `TODO` placeholders in committed code
- [ ] No commented-out code
- [ ] No `print()` debugging
- [ ] No `import *`
- [ ] All public functions have type hints
- [ ] mypy --strict passes
- [ ] ruff check passes
- [ ] Coverage: <!-- N% -->

## Testing

<!-- How did you verify this works? Manual steps + automated tests -->

- [ ] Happy path test added
- [ ] At least one failure-mode test added
- [ ] Edge cases covered: <!-- list them -->

## Screenshots / API examples (if applicable)

<!-- For UI changes: before/after screenshots. For API changes: request/response examples. -->

## Open questions for @abdurrehman

<!-- Anything that needs a human decision before merge. If none, write "None." -->

## Checklist

- [ ] CI is green
- [ ] Pre-commit hooks pass locally
- [ ] No merge conflicts with `staging`
- [ ] PR targets `staging` (not `main`)
- [ ] Branch name follows `feature/phase<N>-<short-name>` / `fix/<name>` / `hotfix/<name>`
- [ ] Commits follow Conventional Commits format
