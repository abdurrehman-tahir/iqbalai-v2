# Audit Log — root-cause classes & the improvement loop

This log exists to **improve CC's first-pass output**, not to track PR pass/fail. It is the evidence buffer for the feedback loop: capture recurring authoring-mistake *classes* → promote each into the carrier CC reads at authoring time (a skill rule / CLAUDE.md gate / CI lint) → watch later audits to confirm the class stops recurring.

## What to log — inclusion bar (read before adding anything)

Log a finding **only if all three hold**:
1. It's a **systemic class** — a generalizable authoring pattern (e.g. "FK declared without `ON DELETE`"), not a one-off instance ("`lectures.teacher_id` on line 42").
2. A **carrier could prevent it** for *future* features (a skill rule, a CLAUDE.md gate, or a CI lint) — if the only fix is "fix this one line," don't log it.
3. It would otherwise **recur** — the kind of mistake CC will make again on the next similar feature.

**Do NOT log:** per-PR PASS/FAIL status, CI green/red, one-off typos/instance fixes, or anything that generalizes to no rule. Those live in phase-complete-review's transient per-PR checklist and just get fixed. This file stays short — its length is bounded by the number of distinct mistake-classes (a handful), never by the number of PRs.

## How to use it

- **Capture (per PR, by phase-complete-review):** when the pre-PR audit finds a qualifying class, **append a dated occurrence** to that class's entry below. If the class has no entry yet, create one. Never add a second entry for a class that already exists — add an occurrence line (dedupe rule).
- **Distill (milestone boundary, Abd. + Claude):** scan for classes with ≥2 occurrences or any high-severity single hit; **promote** each into its target carrier; set status `promoted (→carrier, date)`; record the generalized rule text.
- **Verify (ongoing):** after promotion, watch later audits. Class stops appearing = the rule worked. Class **recurs after its rule existed** (`recurred-after-rule`) = the rule is in the wrong carrier or too weak (e.g. prose where a CI lint was needed) → **harden** it, don't re-add it.

## Entry schema

```
### [class-tag] short title
- **Class:** model-constraint | fe-state | fe-nav | fe-render | fe-types | api-contract | migration | tenancy | test-gap | docs
- **Occurrences:** YYYY-MM-DD (M-NN, ticket/PR) — one line each, append-only
- **Existing rule when first seen?:** yes/no (yes + recurring = harden the carrier)
- **Target carrier:** → data-modeling Rule N | → frontend-master Rule N | → CLAUDE.md #N | → CI lint <name> | → STACK_LOCK | → spec
- **Status:** new | promoted (→carrier, date) | recurred-after-rule | hardened (date)
- **Promoted rule:** the generalized rule text, once promoted (records the fix, not just the complaint)
```

---

## Classes

### [api-contract] endpoints return `dict` / omit `response_model`
- **Class:** api-contract
- **Occurrences:** 2026-05-29 (M-01, foundation diagnosis) — ~25 routes wrapped in `success()` returning `dict[str, Any]`; typed schemas existed but weren't wired, so the generated client would be `dict`-typed.
- **Existing rule when first seen?:** no
- **Target carrier:** → CLAUDE.md #6 + CI lint `response-model-gate` + STACK_LOCK §1
- **Status:** promoted (→ CLAUDE.md #6 + `response-model-gate` + `SuccessEnvelope[T]`, 2026-05-29) — fixed in M-01a T-233
- **Promoted rule:** every endpoint MUST declare `response_model=` (typed, via `SuccessEnvelope[T]`); CI fails on a missing/`dict` response_model.

### [api-contract] routes omit `operation_id`
- **Class:** api-contract
- **Occurrences:** 2026-05-29 (M-01) — ~30 routes across 9 routers had no `operation_id`, degrading generated OpenAPI/client method names.
- **Existing rule when first seen?:** no
- **Target carrier:** → CI lint `response-model-gate` (extended)
- **Status:** promoted (→ `response-model-gate` checks both, 2026-05-29) — fixed in M-01a T-233
- **Promoted rule:** every route declares `operation_id`; the gate checks it alongside `response_model`.

### [fe-types] TS API types hand-mirrored from Pydantic
- **Class:** fe-types
- **Occurrences:** 2026-05-29 (M-00/M-01) — `types.ts` hand-written to mirror backend models → structural FE↔BE drift (frontend calling mismatched shapes).
- **Existing rule when first seen?:** no (ARCH §12.4/§2.13 had deliberately *deferred* generation to Phase 2)
- **Target carrier:** → frontend-master Rule 9 + openapi-typescript + AMENDMENTS A-002 + CI lint `typed-client-drift`
- **Status:** promoted (→ generated `schema.d.ts`, A-002, 2026-05-29) — regenerated in M-01a T-232
- **Promoted rule:** API types are generated from OpenAPI (`pnpm gen:api`); hand-mirroring forbidden; CI fails on drift.

### [fe-nav] pages built but unreachable (orphan routes)
- **Class:** fe-nav
- **Occurrences:** 2026-05-29 (M-01) — admin pages implemented with no working nav; users couldn't reach them.
- **Existing rule when first seen?:** no (frontend-master was component-scoped; no page/shell-reachability rule)
- **Target carrier:** → frontend-master Rule 13 + CLAUDE.md #7
- **Status:** promoted (→ frontend-master Rule 13, 2026-05-29) — fixed in M-01a T-231
- **Promoted rule:** every page renders in the app shell, registers a role-filtered nav entry, and is reachable — proven by a Playwright `@smoke`.

### [fe-render] page renders blank shell / non-scrolling content
- **Class:** fe-render
- **Occurrences:** 2026-05-29 (M-01) — bootstrap/Authentik ToS rendered with no visible text and no scroller.
- **Existing rule when first seen?:** no
- **Target carrier:** → frontend-master Rule 13 (+ Rule 3 four states)
- **Status:** promoted (→ frontend-master Rule 13, 2026-05-29) — fixed in M-01a T-232
- **Promoted rule:** every page renders real content on first paint (four states), and overflowing content scrolls; an `@smoke` asserts it.

### [test-gap] no frontend test harness — broken UI passes review
- **Class:** test-gap
- **Occurrences:** 2026-05-29 (M-00/M-01) — no Vitest/Playwright; `npm run test` was vacuous, so blank/broken UI passed the manual demo script.
- **Existing rule when first seen?:** no
- **Target carrier:** → frontend-master Rule 12 + CI lints `frontend-unit`/`e2e-smoke` + STACK_LOCK §2
- **Status:** promoted (→ frontend-master Rule 12 + CI, 2026-05-29) — harness built in M-01a T-223/T-235
- **Promoted rule:** every data component ships a four-states Vitest test + every page a Playwright `@smoke`, in the same PR; CI runs both.

### [migration] migrations lack §4.12 Purpose/Risk/Reversible headers
- **Class:** migration
- **Occurrences:** 2026-05-29 (M-00/M-01) — all 11 migrations had doc-comment summaries but not the structured §4.12 headers.
- **Existing rule when first seen?:** no (ARCH §4.12 specified the format; nothing enforced it)
- **Target carrier:** → CLAUDE.md #10 (model-first) + the §4.12 convention
- **Status:** promoted (→ backfilled in M-01a T-234), advisory — watch whether new migrations adopt the headers; harden to a CI lint if it recurs.
- **Promoted rule:** every migration carries `Purpose` / `Risk` / `Reversible` headers; model-first autogenerate.
