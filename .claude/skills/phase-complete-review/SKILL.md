---
name: phase-complete-review
description: |
  Run the comprehensive end-of-feature review before any PR is opened for review by Abd.
  This skill cross-references the PR's declared "Sections read from ARCHITECTURE.md" list
  (per WORKFLOW.md §1.3) against the actual file changes, then runs the section-specific
  checklists locked in ARCHITECTURE.md (§3.13 cross-tenant denial test, §4.20 schema review,
  §5.20 API design review, §6.7 access-dep audit, §11.16 upload-pipeline review, §12.21
  frontend pattern audit, §14.4 PII-scrubbing check, §10.10 task review, §9.10 event review).
  Use this skill at the END of every feature implementation — when Hamza or Claude Code
  thinks the PR is ready, BEFORE requesting Abd.'s review. Trigger whenever the user says
  "review my PR", "is this ready", "check before I push", "phase N feature X is done",
  "I'm about to open a PR", or any phrase indicating the implementation is wrapping up.
  Also trigger when CI fails on a `phase-review` step. The skill output is a violations
  list with exact fixes, or a green-light statement if all checks pass.
---

# phase-complete-review

**You are about to ship code.** This skill is the last line of defense between a half-checked feature and Abd.'s review queue. Run this BEFORE asking Abd. to look at the PR. The fewer surprises Abd. finds, the faster the feature ships.

## Why this skill exists

`stack-enforcer` catches forbidden imports and layer violations during writing. `frontend-master` catches missing UI states and hardcoded strings during writing. But there's a class of bugs that neither catches:

- **Cross-feature inconsistencies** — endpoint follows §5, but its access dep is the wrong role
- **Missing tests** — the cross-tenant denial test isn't there, so the security guarantee isn't proven
- **Schema/migration mismatches** — the model has 7 columns; the migration has 6
- **Documentation drift** — the PR says it changes auth flows but doesn't update §6
- **Section-reading mismatch** — Hamza changed `events.py` but didn't list §9 as read

The §0 enforcement model assumes Claude Code reads the right sections — this skill audits that assumption against the actual file changes. It's the audit layer for the §0 rule.

## When to apply this skill

Apply at the end of every feature implementation, BEFORE the PR is opened OR before asking Abd. to review:

1. **Hamza says "I'm ready to push" or "is this PR ready?"**
2. **Hamza says "review this before I open the PR"**
3. **Claude Code finishes the implement step in WORKFLOW.md Step 1** and is about to call `gh pr create`
4. **CI fails on a check** (run the relevant section of this skill to diagnose)
5. **Abd. asks for a pre-review** of a draft PR

## How to apply

Walk through the checklist in two passes:

**Pass 1 — Section-reading audit.** Read the PR description's "Sections read from ARCHITECTURE.md" list. Match against the actual file changes. Identify any mismatches.

**Pass 2 — Per-area checklists.** For each area of the codebase touched by the PR, run the relevant section's checklist. Surface violations with exact fixes.

Output: a markdown checklist showing PASS / FAIL per check, with specific fix instructions for each FAIL.

**Then capture systemic findings to the audit log.** For each FAIL (or fix-on-review) that is a *systemic class* — a generalizable authoring pattern a carrier could prevent, per the inclusion bar in `docs/AUDIT_LOG.md` — append a **dated occurrence** to that class's entry (create the entry if it's new; never duplicate a class — add an occurrence line). Do NOT log per-PR PASS/FAIL, CI status, or one-off instance fixes; those just get fixed here. This is the always-on capture for the improvement loop; the milestone-boundary distillation (promoting recurring classes into a skill / CLAUDE.md / CI carrier) lives in `docs/backlog/README.md`.

---

## Pass 1 — Section-reading audit

Get the file list:

```bash
gh pr diff --name-only
# or for a not-yet-opened PR:
git diff --name-only origin/staging...HEAD
```

For each changed file, look up which sections should have been read using the table below. Compare against the PR's declared "Sections read" list.

### File → expected sections map

This expands `docs/ARCHITECTURE.md §0.1` to file-level granularity.

| File path or pattern | Expected sections to have been read |
|---|---|
| `api/app/features/<feature>/router.py` | §0, §2.3-2.5, §5, §6.7, §3.4 |
| `api/app/features/<feature>/service.py` | §0, §2.3-2.5, §3.4-3.6, §8 (if LLM), §7 (if RAG), §9.5 (if publishing events) |
| `api/app/features/<feature>/repository.py` | §0, §3 (entire), §4 (entire) |
| `api/app/features/<feature>/models.py` | §0, §4 (entire), §3.3 |
| `api/app/features/<feature>/schemas.py` | §0, §5.3 (envelope), §13 (if user-facing error messages) |
| `api/app/features/<feature>/tasks.py` | §0, §10.3-10.5, §3.14 |
| `api/app/features/<feature>/events.py` | §0, §9.8-9.10, §3.15 |
| `api/app/features/<feature>/tests/test_*.py` | §0, §3.13 (cross-tenant denial test required) |
| `api/alembic/versions/<rev>.py` | §0, §4.12, §15.7 |
| `api/app/infrastructure/llm/**` | §0, §8 (entire) |
| `api/app/infrastructure/rag/**` | §0, §7 (entire), §3.8 |
| `api/app/infrastructure/events/**` | §0, §9 (entire) |
| `api/app/infrastructure/storage/**` | §0, §11 (entire), §3.9 |
| `api/app/infrastructure/cache/**` | §0, §3.11 |
| `api/app/infrastructure/voice/**` | §0 + ARCHITECTURE references for STT/TTS routing |
| `api/app/core/dependencies.py` | §0, §6 (entire), §3 (entire) |
| `api/app/core/exceptions.py` | §0, §5.5 (error codes) |
| `api/app/core/logging.py` | §0, §14.3-14.4, §16.6 |
| `api/app/core/responses.py` | §0, §5.3-5.6, §16.4 |
| `api/app/db/**` | §0, §4 (entire) |
| `api/app/tasks/celery_app.py` | §0, §10 (entire) |
| `api/app/tasks/base.py` | §0, §10.3-10.4, §3.14 |
| `api/config.py` | §0, §15.2, §16.3 |
| `api/Dockerfile`, `docker-compose.yml` | §0, §1 (containers), §15 |
| `frontend/src/app/.../page.tsx` | §0, §12.2-12.4, §13 |
| `frontend/src/features/<feature>/components/*.tsx` | §0, §12 (entire), §13 |
| `frontend/src/features/<feature>/api.ts` | §0, §12.10 (apiClient), §5 |
| `frontend/src/features/<feature>/hooks/*.ts` | §0, §12.11 (TanStack Query patterns) |
| `frontend/src/components/ui/*` | §0, §12.5 (shadcn/ui — shouldn't be modified directly) |
| `frontend/messages/*.json` | §0, §13 (entire) |
| `frontend/middleware.ts` | §0, §13.3 (locale resolution), §6 (auth middleware) |
| `nginx/conf.d/*.conf` | §0, §15.11 |
| `grafana/dashboards/*.json` | §0, §14.7 |
| `prometheus/*.yml` | §0, §14.6, §14.9 |
| `docs/runbooks/*.md` | §0, §14.13, §15.14 |

### Audit logic

For each changed file `F`:
1. Look up `F`'s expected sections in the table above
2. Check whether ALL of those sections appear in the PR's declared "Sections read" list
3. If any are missing: that's a violation — output the file + the missing section(s)

If the PR body has an optional **"Sections NOT read (justification)"** block (some teams choose to declare these explicitly per WORKFLOW.md §1.3), evaluate whether the justifications hold. A "feature doesn't touch RAG" is valid when no `infrastructure/rag/` files are changed; it's invalid if `infrastructure/rag/retriever.py` was modified. **This block is optional — its absence is not a fail.**

---

## Pass 2 — Per-area checklists

Run these only for areas the PR touches. Skip irrelevant ones to save effort.

### Checklist CI — GitHub Actions workflows (`.github/workflows/`)

If the PR touches any file under `.github/workflows/`:

- [ ] **Dev deps installed before tools** — every lint/test/type/coverage job has a dependency-sync step (Python: `uv sync` incl. dev group/extras; frontend: `pnpm install` against a real `frontend/package.json`) BEFORE any `uv run ruff|pytest|mypy` / `pnpm lint|test|build`. A `Failed to spawn`/`No such file or directory` for a tool = FAIL. (CLAUDE.md CI invariant 1)
- [ ] **Commands match the manifest** — job script/command/group names match `pyproject.toml` + `frontend/package.json` exactly. (invariant 2)
- [ ] **Edited, not regenerated** — the workflow was amended, not wholesale-replaced. (invariant 3)
- [ ] **Frontend jobs guard correctly** — `frontend/` existence is detected via a post-checkout step output, NOT a job-level `if: hashFiles(...)`. (invariant 4)
- [ ] **CI change called out** — the PR description explicitly states the CI change and why. (invariant 5)

### Checklist A — Multi-tenancy (§3)

If the PR adds/modifies anything user-data-touching:

- [ ] **Every new endpoint has an access dependency** (`require_role`, `require_scope`, etc.) — not just authentication. `Depends(get_current_user)` alone is NOT enough; you also need a role/scope check. (§6.7)
- [ ] **Every new tenant-scoped table inherits `TenantMixin`** — `school_id` column present. (§3.3)
- [ ] **Every new tenant-scoped table has RLS enabled in its migration** — `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`. (§3.7)
- [ ] **Every new repository method that returns user-data takes a `user: User` parameter** and applies within-school narrowing. (§3.4)
- [ ] **Every new Qdrant query goes through `build_tenant_filter()`** — raw `query_points` calls outside `infrastructure/rag/retriever.py` are forbidden. (§3.8)
- [ ] **Every new Celery task uses `@tenant_task`**, not plain `@celery_app.task`. (§3.14)
- [ ] **Every new NATS consumer applies tenant scoping** in the handler — never trusts the event payload's `tenant_id` for authorization, only for routing. (§3.15)
- [ ] **§3.13 cross-tenant denial test exists** — there's a test that creates two schools, has school A's user request school B's resource, asserts 404. **This test is mandatory for any new tenant-scoped feature.**

### Checklist B — Database schema (§4)

If the PR adds a new table or modifies an existing one:

- [ ] **UUIDv7 primary key** via `IdMixin` — not random UUID4, not auto-increment integer
- [ ] **`AuditMixin` applied** (created_at, updated_at) where appropriate — most tables
- [ ] **`SoftDeleteMixin` applied** to user-data tables (deleted_at column) — except append-only tables (audit_logs, events, task_tracking)
- [ ] **`TenantMixin` applied** to tenant-scoped tables (school_id with FK)
- [ ] **Every column has explicit `nullable=True` or `nullable=False`** — no defaults
- [ ] **Every FK has explicit `ON DELETE` action** — CASCADE / RESTRICT / SET NULL — none implied
- [ ] **JSONB only**, never JSON (§4.6)
- [ ] **Enums use Postgres native enums for stable values**, reference tables for editable ones (§4.7)
- [ ] **Index strategy documented in migration comment** — every index has a comment explaining which query it supports
- [ ] **Alembic migration has the required header** — Purpose, Risk, Reversible (§4.12)
- [ ] **`downgrade()` is implemented** OR raises `NotImplementedError` with explanation
- [ ] **High-risk migrations flagged** — long-running, requires manual scheduling (§15.7)
- [ ] **No reuse of column names** that previously meant something different
- [ ] **Soft-delete filtering by default** in repository queries

### Checklist C — API design (§5)

For every new endpoint:

- [ ] **URL follows `/api/v1/<plural-resource>`** pattern — kebab-case multi-word resources (§5.1)
- [ ] **HTTP method matches the operation** — POST for create, GET for read, PATCH for update, DELETE for soft delete (§5.2)
- [ ] **Status code is correct** — 200 OK, 201 Created, 202 Accepted (async), 204 No Content, 404 (also for "you can't see it"), 422 for validation (§5.7)
- [ ] **404 returned for both "doesn't exist" AND "you can't see it"** — never 403 for a resource the user shouldn't know exists (§5.7)
- [ ] **Response envelope follows the locked shape** — `{ data, meta }` for success; `{ error: { code, message, details? } }` for error (§5.3-5.4)
- [ ] **Error code is one of the 13 locked codes** (§5.5)
- [ ] **`response_model` declared** in the route decorator
- [ ] **`operation_id` declared** — used for OpenAPI generation
- [ ] **`tags` declared** on the router or route — matches the feature name
- [ ] **`Idempotency-Key` header required** on resource-creating POSTs (§5.9)
- [ ] **`If-Match` header required** on PUT/PATCH for versioned resources (§5.10)
- [ ] **Pagination is cursor-based** — no offset pagination (§5.6)
- [ ] **Rate limiting considered** — nginx rate-limit zone matches the endpoint's category (general / llm / auth)

### Checklist D — Auth & RBAC (§6)

If the PR touches auth or adds new role-gated functionality:

- [ ] **Every endpoint has `Depends(require_*)` at the dependency level** — not inside the function body
- [ ] **The dependency's role list matches the feature's owner intent** — over-permissive role checks ("any authenticated user") are a violation
- [ ] **`get_current_user` is NEVER used standalone for authorization** — always paired with a `require_*` dependency
- [ ] **No new role created without an entry in `users.role` enum** + migration + RBAC matrix update
- [ ] **OIDC flow changes coordinated with Authentik** — property mappers, redirect URIs, scopes
- [ ] **`ParentChildLink` opt-in check enforced** for parent endpoints accessing child data (§6.13)
- [ ] **Cross-tenant operations gated by `platform_admin` only** — never by `school_admin` or below (§6.10)

### Checklist E — RAG pipeline (§7)

If the PR adds or modifies RAG-using code:

- [ ] **Pattern S vs Pattern A explicitly chosen** — declared in the service or pipeline file's docstring (§7.2)
- [ ] **`build_tenant_filter()` used for every Qdrant query** — chokepoint enforced
- [ ] **Chunks include `school_id` in their payload** — no exceptions
- [ ] **Embedding/reranking goes through `infrastructure/rag/`** — not called directly from feature code
- [ ] **`context` budget respected** — total prompt tokens stay within `LLM_MAX_CONTEXT_TOKENS` minus margin
- [ ] **Citations preserved end-to-end** — source spans tracked from retrieval to LLM output
- [ ] **`low_confidence` flag set** when retrieval-side signals warrant it (recall@5 below threshold, no high-confidence chunks)
- [ ] **For Pattern A: tools registered with explicit schemas** — no free-form tool args (§7.12)

### Checklist F — LLM calls (§8)

If the PR adds or modifies LLM-using code:

- [ ] **All LLM calls go through `infrastructure/llm/client.py`** — no `import openai` in feature code
- [ ] **The `task` parameter is one of the 14 locked task IDs** (§8.3)
- [ ] **Prompts are defined in typed Python files** under `infrastructure/llm/prompts/` — not inline strings (§8.6)
- [ ] **Prompts have versioned filenames** — `student_qa_v1.py`, `student_qa_v2.py` — old versions retained for replay
- [ ] **PII scrubber runs pre-call** — automatic via the client, but verified by the model's input shape (§8.11)
- [ ] **Token counting + cost telemetry emitted** — automatic via client, no manual instrumentation
- [ ] **Fallback opt-out specified per-call when relevant** — for tasks where falling back to OpenAI is wrong (privacy-sensitive content)
- [ ] **Retry policy respected** — no custom retry loops outside the abstraction

### Checklist G — Events & real-time (§9)

If the PR publishes or consumes events:

- [ ] **Every new subject follows `<domain>.<entity>.<event>`** naming (§9.3)
- [ ] **Subject is added to the canonical list in `infrastructure/events/registry.py`** — not just used ad-hoc
- [ ] **Payload schema is a Pydantic model versioned `V1`, `V2`** — registered in the event registry
- [ ] **Publish goes through `event_publisher.publish(...)`** — not raw NATS calls
- [ ] **Publishing happens AFTER `await session.commit()`** unless `requires_atomicity=True` (§9.9)
- [ ] **Consumer is idempotent** — either naturally or via `deduped()` helper (§9.10)
- [ ] **Consumer name is unique** — registered in `infrastructure/events/consumers.py`
- [ ] **DLQ behavior considered** — failed events land somewhere actionable
- [ ] **WebSocket fan-out uses Redis pub/sub** — channel naming `ws:<entity>:<id>` (§9.12)
- [ ] **WebSocket endpoint follows `/ws/v1/<endpoint>?<query>`** pattern (§5.12, §9.13)

### Checklist H — Background jobs (§10)

If the PR adds/modifies Celery tasks:

- [ ] **`@tenant_task` decorator used** — not plain `@celery_app.task` (§10.3)
- [ ] **Task takes only primitives/UUIDs** — never `User` objects, ORM models, or other rich types (§10.4)
- [ ] **Task has `school_id` parameter** — or explicit `tenant_id=None` for system tasks
- [ ] **`acks_late=True` and `reject_on_worker_lost=True`** — standard at-least-once delivery (§10.5)
- [ ] **`soft_time_limit` AND `time_limit`** declared — values realistic
- [ ] **Retry policy explicit** — `autoretry_for`, `max_retries`, `retry_backoff`
- [ ] **Task is idempotent** — natural idempotency preferred; Redis dedup acceptable when needed
- [ ] **Queue assignment correct** — `default`, `ingestion`, `ml`, `notifications` (§10.2)
- [ ] **Beat-scheduled tasks added to the locked schedule list** — not ad-hoc beat entries (§10.6)
- [ ] **`task_tracking` row created** for tasks the UI polls (§10.8)

### Checklist I — File upload pipeline (§11)

If the PR adds a new upload surface:

- [ ] **Reuses the canonical pipeline** — does not implement upload-from-scratch (§11.2)
- [ ] **An `UploadProfile` is defined** — one of the 7 active profiles (curriculum, reference_book, lecture_attachment, student_upload, va_session, audio, export) or a new profile registered in §11.3
- [ ] **MinIO bucket and key prefix include `school_id`** (§11.5)
- [ ] **Two-layer file-type check** — extension AND magic bytes (§11.7)
- [ ] **File size enforced server-side** — not just client-side
- [ ] **Streaming upload** — no full-file in-memory buffering
- [ ] **Soft delete on metadata table** + 30-day hard-delete cleanup task scheduled
- [ ] **Presigned URLs ≤ 5 min** (§11.10)
- [ ] **Per-profile MIME type whitelist enforced** (§11.7)
- [ ] **Ingestion task enqueued** (where applicable) — `<feature>.ingest` on the `ingestion` queue

### Checklist J — Frontend (§12)

If the PR touches `frontend/`:

- [ ] **Server Components by default** — `"use client"` pushed down (§12.2)
- [ ] **Every data-fetching component has all four UI states** — loading skeleton, empty state, error state, success (§12.8)
- [ ] **Every visible string uses `useTranslations` / `getTranslations`** — no hardcoded English in JSX (§13.5)
- [ ] **All four `messages/*.json` files updated** — same key set (§13.10)
- [ ] **Forms use `react-hook-form` + `zodResolver`** — never raw `<form>` with `onSubmit` (§12.7)
- [ ] **Server state via TanStack Query** — never `fetch()` in `useEffect` (§12.11)
- [ ] **shadcn/ui primitives** — no MUI / Chakra / Mantine
- [ ] **Tailwind design tokens** — no inline `style={{...}}` for visuals, no raw hex
- [ ] **Logical Tailwind utilities** for direction-sensitive layout (`me-`, `ms-`, `text-start`) (§12.6, §13.6)
- [ ] **`next/image` for images** — not raw `<img>`
- [ ] **Dynamic imports for heavy components** — charts, calendars, markdown editors
- [ ] **Accessibility: labels, ARIA, semantic HTML** — every interactive element has a name
- [ ] **No `localStorage` / `sessionStorage` for auth state** — auth cookies only (§6.4)
- [ ] **Performance budgets respected** — bundle <200 KB gzipped, LCP <2.5s (§12.21)
- [ ] **Query key convention followed** — hierarchical `[<feature>, <surface>, <id>]`

### Checklist K — Observability & PII (§14)

If the PR adds/modifies logging, metrics, or anything PII-sensitive:

- [ ] **structlog used, not stdlib `logging`** (§14.3)
- [ ] **No `print()`** anywhere in the diff
- [ ] **No f-string formatting in log calls** — always kwargs
- [ ] **`user_id_hash` used in logs, never raw `user_id`** (§14.4)
- [ ] **No raw email/phone/CNIC in log call kwargs** — scrubber catches, but don't rely
- [ ] **New metrics follow naming convention** — `snake_case`, `_total`/`_seconds`/`_bytes` suffixes
- [ ] **Metric labels are bounded** — never user_id, request_id, raw URLs as labels (§14.6)
- [ ] **PII-sensitive operations log with `pii=True` flag** — triggers stricter audit
- [ ] **Audit log entry for security-relevant actions** — auth events, admin actions, deletions (§14.10)
- [ ] **No new collection of sensitive PII without DPIA path defined** — flag to Abd. if uncertain

### Checklist L — Deployment & ops (§15)

If the PR touches deployment-related files:

- [ ] **All new env vars added to `.env.example` AND `docs/ENV_VARS.md`** (§15.2)
- [ ] **No hardcoded URLs / keys / secrets** — `scripts/check_envvars.py` enforces
- [ ] **Dockerfile changes preserve multi-stage + non-root + no-build-tools-in-runtime** (§15.5)
- [ ] **Compose changes match container table in §1.3** — counts and roles consistent
- [ ] **nginx config follows §15.11 patterns** — rate-limit zones, SSE timeouts, WS upgrade headers
- [ ] **Migration runs successfully on staging before main merge** — verified
- [ ] **Smoke test passes** — `/api/v1/health/ready` returns 200 within 30s after deploy
- [ ] **Runbook added or updated** if a new operational concern was introduced (§15.14)

### Checklist M — Feature spec adherence (`docs/feature-specs/`)

If the PR implements (or modifies) a feature:

- [ ] **The PR body's "Feature spec implemented:" field is filled in** — pointing to a real, merged `docs/feature-specs/<feature>.md` file. Absent or pointing to a non-existent file is a hard fail.
- [ ] **The spec is merged on `staging`** — not draft, not in-review. Read the spec's status header.
- [ ] **Lifecycle in the spec matches the lifecycle in the code** — every state in the spec's §3 diagram appears as a value in the relevant ORM enum (or the `status` column's accepted values).
- [ ] **Permissions in the code match the spec's §4 matrix** — every cell marked ✅ in the spec's permission matrix has a corresponding `require_*` dependency in the router endpoint. Cells marked ❌ have NO path to that action through the API.
- [ ] **Edge cases in the spec's §5 have implementations or tests** — for each edge case the spec lists, the code either handles it (and a test proves so) or the implementation explicitly documents that this edge case is deferred (with TODO.md entry + spec amendment if needed).
- [ ] **Limits in the spec's §6 are enforced** — every numerical limit declared in the spec appears as a constant in the code or a config value with the same number. Mismatch is a hard fail.
- [ ] **Notifications in the spec's §7 are wired** — for every row in the spec's notification table, the corresponding NATS publish + consumer + template key exists.
- [ ] **No open questions** — the spec's §8 list is empty (resolved) when this PR is opened. If a new open question surfaced during implementation, open a spec-amendment PR first, get it approved, THEN implement.
- [ ] **Acceptance criteria in the spec's §11 have corresponding tests** — every checkbox in the spec's acceptance section is exercised by a test (unit / integration / E2E).
- [ ] **If the implementation diverges from the spec:** the divergence is documented either as (a) a spec amendment PR (preferred, when the spec was wrong), or (b) a TODO.md entry explaining why the divergence is acceptable temporarily. Silent divergence is a hard fail.

**Why Checklist M is mandatory:** the spec is the contract with Awais (product) and Abd. (technical). When the code drifts silently from the spec, two things break: (1) future contributors trust the spec and discover the code is different, leading to bug reports that are actually correct behavior; (2) Awais's product review loses meaning. The spec must remain the source of truth.

### Checklist N — Spec-set additions (T0 batch — AMENDMENTS A-001)

If the PR touches any of the spec-set decisions introduced in the 2026-05-14 T0 batch, run the relevant N.X items from `references/checklists.md`. Apply only the ones that match the PR's surface area:

- [ ] **N.1 — Tenant type identified** — if PR adds tables/endpoints/workflows: which tenant(s) does it serve? (school / independent / both) — per ARCH §3.16
- [ ] **N.2 — Permission inheritance** — if PR adds role-gated endpoints: `require_role(X)` allows X or HIGHER within scope per §6.19
- [ ] **N.3 — Dual Alembic head** — if PR adds a migration: correct `branch_labels`, no cross-schema FKs per §4.21
- [ ] **N.4 — Custom Persona awareness** — if PR adds a per-student AI surface: goes through `infrastructure/llm/persona.py` per §8.20
- [ ] **N.5 — Vision-LLM routing** — if PR adds AI surface that consumes image attachments: uses hybrid widget #57, routes via `LLM_VISION_MODEL` per §8.22
- [ ] **N.6 — Notification namespaces** — if PR creates notifications: `feature_namespace` set, namespace ∈ 7 locked values per §9.21
- [ ] **N.7 — Grade / Section / Subject model** — if PR touches school structure: uses `grades`/`sections`/`grade_subject_offerings` (NOT legacy "Class") per §3.18
- [ ] **N.8 — Subscription module** — if PR interacts with subscription state: no Stripe SDK; no cap enforcement; placeholder UI only per §3.17 + Flow 13
- [ ] **N.9 — Exam Framework engine** — if PR uses framework data: versioned `framework_study_plans`, approved-only, Pattern-A research per §3.19 + §8.21
- [ ] **N.10 — Upload profile correctness** — if PR adds a file upload: uses an existing profile from §11.19; new profiles require ARCH §11.19 PR
- [ ] **N.11 — Promotion approval workflow** — if PR touches promotion state machine: state lock + atomic Celery + School Admin approval per §6.21
- [ ] **N.12 — Graduation lifecycle** — if PR touches graduated students: read-only window + atomic migration per Flow 4 v3 §3.9

Full guidance in `references/checklists.md` Checklist N.

---

## Output format

After running both passes, output a markdown report:

```markdown
## Phase Complete Review

### Pass 1 — Section-reading audit

**PR-declared sections read:**
- §0 Quick Index
- §2.3-2.5
- §5
- §6.7

**Files changed:**
- api/app/features/lectures/router.py
- api/app/features/lectures/service.py
- api/app/features/lectures/models.py    ← expects §4 not declared
- api/app/features/lectures/tasks.py     ← expects §10 not declared

**Verdict:** FAIL — 2 file/section mismatches.

**To fix:**
1. Read ARCHITECTURE.md §4 (entire) and §10.3-10.5
2. Update PR body's "Sections read" list to include §4 and §10
3. Verify your model + task implementations against those sections (use this skill again)

---

### Pass 2 — Per-area checklists

#### Checklist A — Multi-tenancy
✅ Every new endpoint has access dependency
✅ TenantMixin applied
❌ Cross-tenant denial test missing
   Fix: add `tests/test_cross_tenant_denial.py` per §3.13 template

#### Checklist B — Database schema
✅ UUIDv7 primary key
✅ AuditMixin applied
✅ FK ON DELETE explicit
⚠️ Migration `downgrade()` not implemented
   Recommend: implement reversal or raise NotImplementedError with reason

(... continue per area touched ...)

---

### Summary

- ❌ 1 file/section reading mismatch (Pass 1)
- ❌ 1 mandatory test missing (Checklist A)
- ⚠️ 1 advisory item (Checklist B)

**This PR is NOT ready for Abd.'s review.**

Fix the ❌ items, then re-run this skill. The ⚠️ items can be addressed in this PR or in a follow-up — your call.
```

## When all checks pass

```markdown
## Phase Complete Review — PASSED

### Pass 1 — Section-reading audit
✅ All file changes covered by declared sections

### Pass 2 — Per-area checklists
✅ Multi-tenancy
✅ Database schema
✅ API design
✅ Auth & RBAC
✅ Frontend
✅ Observability

**This PR is ready for Abd.'s review.**

Suggested PR body opener:
> "Phase-complete review passed. Sections read: §0, §2.3-2.5, §5, §6.7, §3.4. No deviations from ARCHITECTURE.md."
```

## What this skill does NOT do

- It does not run unit tests. CI does that.
- It does not run static type-checking. `mypy` / `tsc` do that in pre-commit.
- It does not run linters. `ruff` / `eslint` do that in pre-commit.
- It does not run the cross-tenant denial test. It verifies the test EXISTS.
- It does not approve or merge PRs. Abd. does that.

This skill is the architectural-conformance layer. The other layers (pre-commit, CI, Abd.'s review) complement it.

## Reference files

- `references/checklists.md` — all checklists A through L in a single document with copy-paste fix templates
- `references/file_section_map.md` — the file-path → expected-sections lookup table (Pass 1 input)