# All checklists — consolidated with fix templates

This is the lookup the `phase-complete-review` skill uses for Pass 2. Each checklist is per area (A through L). For each item, this file gives:
- The pass criterion
- The most common failure mode
- The exact fix (copy-paste-able)

Walk through only the checklists relevant to the PR's file changes.

---

## Checklist A — Multi-tenancy (§3)

### A.1 — Every new endpoint has an access dependency

**Pass:** every route decorator-level `Depends(...)` includes a `require_role`, `require_scope`, `require_self_or_admin`, `require_parent_of`, or `require_teacher_of` call. Plain `Depends(get_current_user)` alone is a fail.

**Fail mode:** authentication without authorization — any logged-in user can hit the endpoint.

**Fix template:**

```python
# WRONG
@router.get("/students/{student_id}/grades")
async def get_grades(student_id: UUID, user = Depends(get_current_user), ...):
    ...

# RIGHT
@router.get("/students/{student_id}/grades")
async def get_grades(
    student_id: UUID,
    user = Depends(require_self_or_admin(UserRole.TEACHER, UserRole.PARENT)),
    ...
):
    ...
```

### A.2 — Tenant-scoped tables inherit TenantMixin

**Pass:** every new table that holds user-owned data has `TenantMixin` in its base list.

**Fail mode:** missing `school_id` column → cross-tenant data leak.

**Fix:**

```python
class Lecture(Base, IdMixin, AuditMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "lectures"
    ...
```

### A.3 — RLS enabled in migration

**Pass:** every migration creating a tenant-scoped table includes both `ENABLE` and `FORCE` RLS, plus a policy.

**Fail mode:** RLS off → a buggy query bypasses tenant scoping.

**Fix in the migration:**

```python
def upgrade() -> None:
    op.create_table(
        "lectures",
        ...,
    )
    op.execute("ALTER TABLE lectures ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE lectures FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation ON lectures
        USING (school_id = current_setting('app.school_id')::uuid);
    """)
```

### A.4 — Repository method takes `user` and applies scoping

**Pass:** every method returning tenant-scoped data takes `user: User` and applies role-based narrowing.

**Fail mode:** repository returns data for all schools because the user filter is missing.

**Fix (see canonical example in stack-enforcer/canonical_examples.md).**

### A.5 — Qdrant queries via `build_tenant_filter()`

**Pass:** every `qdrant.query_points()` call sites lives in `infrastructure/rag/retriever.py` and passes through the chokepoint.

**Fail mode:** feature code calls Qdrant directly without tenant filter.

**Fix:** route through `QdrantRetriever.search()` which calls `build_tenant_filter(user, collection)` internally.

### A.6 — Celery tasks use `@tenant_task`

**Pass:** every task in `tasks.py` files uses `@tenant_task`.

**Fix:**

```python
# WRONG
@celery_app.task
def ingest_curriculum(curriculum_id: str):
    ...

# RIGHT
@tenant_task(queue="ingestion", name="curricula.ingest", soft_time_limit=540, time_limit=600, max_retries=3)
async def ingest_curriculum(curriculum_id: UUID, school_id: UUID):
    ...
```

### A.7 — NATS consumer scopes tenancy from envelope

**Pass:** consumer reads `envelope.tenant_id` for routing, never uses payload-asserted IDs for authorization.

**Fail mode:** event payload contains `school_id` that doesn't match `envelope.tenant_id` → privilege escalation.

**Fix:** in the handler, always derive the working tenant from `envelope`, not from `payload`.

### A.8 — Cross-tenant denial test exists (§3.13)

**Pass:** for any new tenant-scoped feature, `tests/test_<feature>_cross_tenant.py` exists with the canonical denial pattern.

**Fail mode:** security guarantee unproven — feature may work but tenant isolation untested.

**Fix template:**

```python
async def test_cross_tenant_denial(test_client, two_school_fixture):
    school_a, school_b = two_school_fixture
    # User in school A creates a resource
    response = await test_client.post(
        "/api/v1/lectures",
        json={"title": "...", ...},
        headers=school_a.headers,
    )
    lecture_id = response.json()["data"]["id"]

    # User in school B tries to read it — must 404 (not 403)
    response = await test_client.get(
        f"/api/v1/lectures/{lecture_id}",
        headers=school_b.headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
```

---

## Checklist B — Database schema (§4)

### B.1 — UUIDv7 primary key

**Pass:** `IdMixin` applied (which uses `uuid_utils.uuid7()`).

**Fail mode:** random UUID4 — defeats time-ordered indexes.

**Fix:** add `IdMixin` to the model's base list.

### B.2 — AuditMixin

**Pass:** `created_at`, `updated_at` present (via `AuditMixin`).

**Fix:** add `AuditMixin`.

### B.3 — SoftDeleteMixin

**Pass:** `deleted_at` present (via `SoftDeleteMixin`) for user-data tables. Exempt: append-only tables (`audit_logs`, `events`, `task_tracking`).

**Fix:** add `SoftDeleteMixin` unless explicitly append-only.

### B.4 — Explicit nullability

**Pass:** every `mapped_column(...)` has `nullable=True` or `nullable=False` explicitly.

**Fail mode:** implicit nullability — surprises later.

### B.5 — FK ON DELETE

**Pass:** every `ForeignKey(...)` has an explicit `ondelete=`.

**Fix:**

```python
owner_id: Mapped[UUID] = mapped_column(
    ForeignKey("users.id", ondelete="RESTRICT"),
    nullable=False,
)
```

### B.6 — JSONB not JSON

**Fail mode:** `JSON` columns instead of `JSONB` — no GIN indexes, slower queries.

**Fix:** `Mapped[dict] = mapped_column(JSONB, ...)`

### B.7 — Enums correctly typed

**Pass:** stable values use Postgres native enums (`StrEnum` + `sa.Enum`); editable values use a reference table.

### B.8 — Migration header

**Pass:** every migration has the locked header:

```python
"""<short description>

Purpose: <one-line purpose>
Risk: low | medium | high
Reversible: yes | no — <explanation if no>
"""
```

### B.9 — downgrade() implemented or explicitly skipped

**Pass:** `downgrade()` either reverses the change OR raises `NotImplementedError("...")` with a clear reason.

**Fail mode:** silently broken `downgrade()` — rollback impossible.

---

## Checklist C — API design (§5)

### C.1 — URL pattern `/api/v1/<plural-resource>`

**Pass:** path follows §5.1 exactly. Plural resource. v1 prefix.

**Fail mode:** singular resources, missing v1, snake_case in URLs.

**Fix:** rename. `/api/v1/lecture` → `/api/v1/lectures`. `/api/v1/lectureItems` → `/api/v1/lectures/{id}/items`.

### C.2 — HTTP method correctness

**Pass:** POST creates, GET reads (no side effects), PATCH partial-updates, PUT full-replaces, DELETE soft-deletes.

### C.3 — Status code correctness

**Pass:** 201 on create, 202 on async/enqueued, 204 on delete, 200 on read/update.

### C.4 — 404 for "can't see it"

**Pass:** the error returned to user-B-viewing-school-A-data is 404 (RESOURCE_NOT_FOUND), not 403.

**Reason:** 403 reveals the resource exists, leaking information across tenants.

**Fix:** in the service, when the within-school filter returns no row, raise `NotFoundError`, not `PermissionDeniedError`.

### C.5 — Response envelope

**Pass:** every success response is `{ "data": <obj or list>, "meta": {...} }`. Every error is `{ "error": { "code", "message", "details"? } }`.

**Fix:** use the helpers in `core/responses.py`:

```python
return success_response(LectureRead.model_validate(lecture))
# or
return error_response("VALIDATION_ERROR", "...", details=[{"field": "title", "message": "..."}])
```

### C.6 — Error code is locked

**Pass:** the error code is one of the 13 locked codes (§5.5).

**Fail mode:** ad-hoc error codes ("LECTURE_INVALID") — frontend can't translate them.

**Fix:** map your specific error to the closest locked code; put feature-specific detail in `error.details`.

### C.7 — Route decorator completeness

**Pass:** every route has `response_model=`, `operation_id="<feature>_<action>"`, and `tags=["<feature>"]`.

### C.8 — Idempotency-Key on POST creates

**Pass:** POSTs that create resources require an `Idempotency-Key` header via dependency.

**Fix:**

```python
@router.post("/lectures", ...)
async def create(
    payload: LectureCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    _: None = Depends(idempotency_required),
    ...
):
```

### C.9 — If-Match on PUT/PATCH (versioned resources)

**Pass:** resources with optimistic concurrency require `If-Match` header.

### C.10 — Cursor-based pagination

**Pass:** list endpoints accept `cursor` and `limit`, return `{ items, next_cursor }`. No `offset`.

### C.11 — Rate limiting matches the endpoint type

**Pass:** the route is reached via the right nginx zone (general, llm, auth). New "expensive" routes added to the `api_llm` zone via the nginx regex update if needed.

---

## Checklist D — Auth & RBAC (§6)

### D.1 — Access dep at dependency level

**Pass:** `require_role(...)` or equivalent is in `Depends(...)`, not in the function body.

**Reason:** dependency-level checks run before the function; body checks run after the request is parsed (worse UX, easier to forget).

### D.2 — Role list matches intent

**Pass:** the role list reflects who should actually have access.

**Fail mode:** `require_role(*UserRole)` (all roles) used as a shortcut.

**Fix:** be explicit — list only the roles that should access.

### D.3 — `get_current_user` not used alone

**Pass:** if `get_current_user` appears, it's because something else (a `require_*`) is also wrapping the route.

### D.4 — New role = enum + migration + matrix update

**Pass:** if a new role is added: the `users.role` enum is extended in a migration AND `docs/ARCHITECTURE.md §6.2` role matrix is updated.

### D.5 — ParentChildLink opt-in for parent access

**Pass:** parent-accessing-child endpoints check `ParentChildLink` (consent), not just family relationship.

---

## Checklist E — RAG (§7)

### E.1 — Pattern explicit

**Pass:** the service or pipeline file's docstring declares "Pattern S" or "Pattern A."

### E.2 — Tenant filter chokepoint

**Pass:** every Qdrant `query_points` call lives in `infrastructure/rag/retriever.py` and passes through `build_tenant_filter(user, collection)`.

### E.3 — Chunk payload has school_id

**Pass:** every chunk inserted into Qdrant has `school_id` in its payload (or is in a non-tenant-scoped collection like `originality_index`).

### E.4 — RAG context budget respected

**Pass:** `assemble_context(top, budget_tokens=...)` is called; the LLM client checks the resulting prompt fits within `LLM_MAX_CONTEXT_TOKENS - margin`.

### E.5 — Citations preserved

**Pass:** retrieved spans have `chunk_id` and `source` tracked from query → reranker → context assembler → LLM prompt → output.

### E.6 — low_confidence flag

**Pass:** when retrieval signals are weak (no high-confidence chunks, low recall@5), the response envelope includes `meta.flags: ["low_confidence"]`.

---

## Checklist F — LLM (§8)

### F.1 — Single chokepoint

**Pass:** no `import openai`, `import anthropic`, `import groq` outside `infrastructure/llm/providers/`.

### F.2 — task ID locked

**Pass:** the `task=` parameter is one of the 14 locked task IDs.

### F.3 — Typed prompts

**Pass:** prompts are in `infrastructure/llm/prompts/<name>_v<version>.py` with typed Pydantic input/output models.

**Fail mode:** inline f-string prompts in feature code.

### F.4 — Versioned prompt filenames

**Pass:** prompt files have `_v<N>` suffix and old versions are retained.

### F.5 — Fallback opt-out where appropriate

**Pass:** for privacy-sensitive tasks (e.g., processing student PII), the LLM call specifies `fallback=False` so the call won't bounce to a different provider.

---

## Checklist G — Events (§9)

### G.1 — Subject naming

**Pass:** `<domain>.<entity>.<event>` exactly. Reuse existing domain/entity names where possible.

### G.2 — Registered in event registry

**Pass:** subject + payload schema added to `infrastructure/events/registry.py`.

### G.3 — Versioned payload schemas

**Pass:** payload Pydantic class ends in `V1`, `V2`, etc.

### G.4 — Publish through `event_publisher.publish`

**Pass:** no raw `await nats.publish(...)` in feature code.

### G.5 — Publish after commit

**Pass:** `event_publisher.publish(...)` is called AFTER `await session.commit()` (typically outside the `async with session.begin():` block).

**Fail mode:** publish before commit → event consumers process a "lecture created" event for a lecture that doesn't exist (rollback) or hasn't been persisted yet.

### G.6 — Consumer idempotent

**Pass:** either the consumer's effect is naturally idempotent OR the handler wraps with `if await deduped(envelope.event_id, "<consumer-name>"): return`.

### G.7 — WS channel naming

**Pass:** Redis pub/sub channels follow `ws:<entity>:<id>`. WebSocket endpoints follow `/ws/v1/<endpoint>?<query>`.

---

## Checklist H — Celery tasks (§10)

### H.1 — `@tenant_task` decorator

**Pass:** uses `@tenant_task(...)`. Not plain `@celery_app.task`.

### H.2 — Primitives only

**Pass:** function signature has only `UUID`, `str`, `int`, `float`, `bool`, `datetime`, lists/dicts of these. No `User`, no ORM objects, no Pydantic models with complex types.

### H.3 — `school_id` parameter

**Pass:** `school_id: UUID` is present (or task explicitly opts out for system-wide jobs).

### H.4 — `acks_late=True` + `reject_on_worker_lost=True`

**Pass:** both set on the `@tenant_task` invocation.

### H.5 — Time limits

**Pass:** `soft_time_limit=N` and `time_limit=N+small_buffer`.

### H.6 — Retry policy

**Pass:** `autoretry_for=(...)`, `max_retries=N`, `retry_backoff=True` declared.

### H.7 — Idempotent

**Pass:** running the task twice produces the same effect. If not naturally idempotent, uses Redis dedup on a deterministic key.

### H.8 — Right queue

**Pass:** `queue="default" | "ingestion" | "ml" | "notifications"` — matches the task's nature.

### H.9 — Beat-scheduled tasks in locked list

**Pass:** if the task is on the beat schedule, it appears in the locked schedule (§10.6) — not ad-hoc.

---

## Checklist I — Uploads (§11)

### I.1 — Canonical pipeline reused

**Pass:** uses `upload_pipeline.handle(...)` — does not implement uploads from scratch.

### I.2 — UploadProfile defined

**Pass:** the profile is one of the 7 active profiles or a new profile registered in §11.3.

### I.3 — Bucket + key prefix include school_id

**Pass:** the MinIO key is `<school_id>/<profile>/<resource_id>/<filename>` or equivalent.

### I.4 — Two-layer type check

**Pass:** filename extension AND magic-byte check both applied.

### I.5 — Size enforced server-side

**Pass:** the server enforces the profile's max size, not just the client.

### I.6 — Streaming

**Pass:** upload uses `StreamingResponse`/streaming consumption. No full-file in-memory buffer.

### I.7 — Presigned URL expiry

**Pass:** `≤ 5 min` for download URLs.

---

## Checklist J — Frontend (§12)

Use `frontend-master/SKILL.md` for the full list. The pass criteria here are the audit version — read the SKILL.md for fix templates.

- J.1: Server Components by default
- J.2: All four UI states present on every fetch-using component
- J.3: All visible strings via `useTranslations` / `getTranslations`
- J.4: All four `messages/*.json` files updated
- J.5: Forms use `react-hook-form` + `zodResolver`
- J.6: Server state via TanStack Query
- J.7: shadcn/ui primitives only
- J.8: Tailwind design tokens (no inline styles, no raw hex)
- J.9: Logical Tailwind utilities for direction-sensitive layout
- J.10: `next/image` for images
- J.11: Dynamic imports for heavy components
- J.12: Accessibility — every interactive element has a name
- J.13: No `localStorage` for auth state
- J.14: Performance budgets respected (bundle ≤ 200 KB gzipped)

---

## Checklist K — Observability & PII (§14)

### K.1 — structlog only

**Pass:** no `import logging` (stdlib) in the diff. `import structlog` used everywhere.

### K.2 — No `print()`

**Pass:** zero `print()` calls in the diff.

### K.3 — No f-string log messages

**Fix:**

```python
# WRONG
logger.info(f"user {user.id} logged in")

# RIGHT
logger.info("user_login", user_id_hash=hash_user_id(user.id))
```

### K.4 — `user_id_hash`, not raw `user_id`

**Pass:** logs containing user identity use the SHA-256 hash, not the raw UUID.

### K.5 — Bounded metric labels

**Pass:** new metrics have ≤ 10 label values per dimension. Never `user_id`, `request_id`, raw URL as a label.

### K.6 — Audit log for sensitive ops

**Pass:** auth events, admin actions, deletions, role changes have an `audit_logs` row written synchronously.

---

## Checklist L — Deployment & ops (§15)

### L.1 — Env vars documented

**Pass:** every new env var read from `Settings` (or `get_settings()`) is also in `.env.example` (at repo root) AND `docs/ENV_VARS.md`.

### L.2 — No hardcoded secrets

**Pass:** `scripts/check_envvars.py` passes.

### L.3 — Dockerfile invariants preserved

**Pass:** Dockerfile remains multi-stage, non-root, no compilers in final.

### L.4 — Compose matches §1.3 container table

**Pass:** if a new container is added, §1.3 is updated in the same PR.

### L.5 — nginx config patterns followed

**Pass:** new nginx rules use the locked patterns — rate-limit zones, SSE timeouts, WS upgrade.

### L.6 — Runbook added for new ops concern

**Pass:** if the feature introduces an alert or a recovery procedure, a runbook exists at `docs/runbooks/<concern>.md`.

---

## Checklist M — Feature spec adherence (`docs/feature-specs/`)

For any PR that implements or modifies a feature.

### M.1 — Feature spec referenced in PR body

**Pass:** PR body contains a "Feature spec implemented:" field pointing to `docs/feature-specs/<feature>.md`.

**Fail mode:** PR body has no spec reference, or the referenced file doesn't exist.

**Fix:** add the reference. If no spec exists yet — STOP the PR. Open a feature-spec PR first; get it approved by Abd. + Awais; merge it; THEN proceed with this implementation PR.

### M.2 — Spec is merged (not draft)

**Pass:** `docs/feature-specs/<feature>.md` shows `**Status:** approved` in its header and is on the `staging` branch.

**Fail mode:** spec is still in-review or draft.

**Fix:** wait for spec approval. Implementation PRs cannot land before their spec PR.

### M.3 — Lifecycle matches

**Pass:** every state in the spec's §3 lifecycle diagram appears in code as either (a) a value in the relevant Postgres native enum or (b) an accepted string in a `status` column with explicit validation.

**Fail mode:** spec says states `DRAFT → REVIEWED → PUBLISHED → ARCHIVED`. Code only has `draft` and `published`. Or code has `pending_review` (not in spec).

**Fix:** either update the code to match the spec, or open a spec amendment to redefine the lifecycle (Abd. + Awais re-approve), then update the code.

### M.4 — Permissions matrix matches

**Pass:** every ✅ cell in the spec's §4 matrix maps to a `require_*` dependency in a router endpoint. Every ❌ cell has NO API path to that action.

**Fail mode:** spec says "Parent: read published lectures (if linked)" but the lecture-read endpoint uses `require_role(STUDENT, TEACHER, ADMIN)` with no parent path. Or vice versa: the endpoint allows STUDENT but the spec doesn't list student permission.

**Fix:** align. If the discrepancy is real (the spec is wrong or the code is wrong), open a spec amendment or fix the code. Don't ship the divergence.

### M.5 — Edge cases handled or deferred

**Pass:** for every edge case in the spec's §5:
- either a test exists that exercises the case and confirms the documented behavior, OR
- a TODO.md entry exists explaining why the edge case is deferred.

**Fail mode:** spec lists "Concurrent edit handled via If-Match → 412 PRECONDITION_FAILED" but no test exists for the 412 response on concurrent updates.

**Fix:** write the test (or, if the case was genuinely out of scope, open a spec amendment moving it to §9 "Out of scope" and add a TODO.md entry).

### M.6 — Limits enforced

**Pass:** every numerical limit in the spec's §6 has a corresponding enforcement point in the code (constant, config value, nginx rate-limit, or database check).

**Fail mode:** spec says "Max lectures per teacher per day: 50" but the code has no rate-limit on the create endpoint.

**Fix:** add the enforcement. Either as a database check (count query before insert), a nginx rate-limit zone match, or a config value used in a service-layer check.

### M.7 — Notifications wired

**Pass:** every row in the spec's §7 notification table has:
- a NATS publish call in the relevant service
- a consumer in the notifications worker (or a sync notification dispatch)
- a translation key resolvable in `frontend/messages/*.json` (for in-app) or in the backend templates for email/SMS/push

**Fail mode:** spec says "Teacher gets in-app notification when lecture generation fails" but no `lecture.generation.failed` event is published, or no consumer handles it.

**Fix:** wire the missing pieces. Notification flows are end-to-end — a missing piece breaks the chain.

### M.8 — No open questions remaining

**Pass:** spec's §8 "Open questions" list is empty (or all items checked off as resolved).

**Fail mode:** spec has unresolved open questions but implementation is proceeding anyway — Claude Code is silently guessing answers.

**Fix:** stop implementation. Resolve the open questions via a spec amendment PR. Once resolved (Awais + Abd. approve), continue implementation.

### M.9 — Acceptance criteria tested

**Pass:** every checkbox in the spec's §11 acceptance criteria has a corresponding test (unit, integration, or E2E). The test name should reference the criterion.

**Fail mode:** spec says "✅ Concurrent edit by two teachers produces 412 PRECONDITION_FAILED" but no test exercises this. Implementation may be correct, but it's unverified.

**Fix:** add tests. The acceptance criteria are the contract.

### M.10 — No silent divergence

**Pass:** if the implementation differs from the spec, the difference is documented in EITHER (a) a spec amendment PR opened in parallel, OR (b) a TODO.md entry with explicit reasoning.

**Fail mode:** the code does something the spec doesn't describe, and there's no PR or TODO explaining why.

**Fix:** for divergences caught in review — pick one of:
1. Update the code to match the spec (preferred if spec is right)
2. Open a spec amendment PR (if reality showed the spec was wrong)
3. Add a TODO entry with explicit reasoning (only acceptable as temporary)

Never let the code silently differ from the spec. The spec is the contract; silent drift means the contract is broken.

---

## Checklist N — Spec-set additions (T0 batch decisions)

These checklists apply to features that touch the spec-set decisions introduced in the 2026-05-14 T0 batch. See AMENDMENTS A-001 + ledger.

### N.1 — Tenant type identified (§3.16)

**For:** any feature that adds tables, endpoints, or workflows.

Verify the PR or feature spec explicitly identifies tenant type(s):
- `school` only
- `independent` only
- both (with cross-schema view if platform-shared table)

Tables must live in the correct schema. Migrations have correct `branch_labels = ('school',)` OR `('independent',)`.

### N.2 — Permission inheritance (§6.19)

**For:** any feature with role-gated endpoints.

Verify:
- `require_role(MIN_ROLE)` enforces inheritance (allows MIN_ROLE OR HIGHER)
- Higher roles inherit lower-role permissions without separate rows in permission matrix
- Scope bounded — District Admin can act as Teacher within own district, not other districts
- Audit log entry for "elevated" actions (admin acting at lower role's level)

### N.3 — Dual Alembic head (§4.21)

**For:** any migration.

Verify:
- Migration has `branch_labels = ('school',)` OR `('independent',)`
- Migration does NOT reference cross-schema tables directly (use views per §4.21)
- No cross-schema FKs (forbidden)
- `alembic upgrade heads --sql` runs cleanly with no head conflicts

### N.4 — Custom Persona awareness (§8.20)

**For:** any per-student AI surface (Q&A, study plan, etc.).

Verify:
- Persona resolution goes through `infrastructure/llm/persona.py`
- Custom persona description prepended to system prompt (style only)
- Compatible with per-session adaptation context (Flow 6 §3.9 — persona = STYLE, adaptation = STRATEGY)
- First 7 days of new Custom selection default to Friendly Tutor (no fail-on-empty)

### N.5 — Vision-LLM routing (§8.22)

**For:** any AI surface that consumes image attachments.

Verify:
- Hybrid widget #57 used for input (no duplicate widget implementations)
- Request payload includes optional `attached_images[]` field
- Routing via `infrastructure/llm/client.py` (auto-selects vision model if present)
- `LLM_VISION_MODEL` env var used (default `groq:llama-3.2-90b-vision-preview`)
- Per Flow 6 v2: max 3 images, 5 MB each, JPEG/PNG/WEBP only
- `student_question_image` upload profile per §11.19

### N.6 — Notification namespaces (§9.21)

**For:** any feature that creates notifications.

Verify:
- Every notification has `feature_namespace` field set
- Namespace value ∈ {lectures, self_study, quiz, connections, content_library, system, account}
- NO ad-hoc namespaces invented
- Template keys follow `{namespace}.{event_name}` convention
- No opt-out toggles added (notifications cannot be turned off per Flow 1 Q13)
- All template keys translated in all 4 languages (no `__TODO__` markers in production)

### N.7 — Grade / Section / Subject model (§3.18)

**For:** any feature touching school structure.

Verify:
- Uses `grades` / `sections` / `grade_subject_offerings` tables (NOT legacy "Class" model)
- Teacher assignment at GradeSubjectOffering level (NOT per-Section)
- Cross-grade content access respects unidirectional rule (§7.21): target Grade N retrieves only from grades ≤ N
- Teacher capacity check at assignment time (default 5, override audit-logged)

### N.8 — Subscription module (§3.17, Flow 13)

**For:** any feature that interacts with subscription state.

Verify (at launch):
- NO Stripe SDK imports (forbidden)
- NO cap enforcement at request time (deferred to Phase 2)
- District/School subscribe buttons show "Coming soon" modal
- `subscription_tiers` table accessible to Platform Admin CRUD; `subscriptions` table empty
- `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET` env vars exist as placeholders (empty acceptable)

### N.9 — Exam Framework engine (§3.19, §8.21)

**For:** any feature that uses framework data.

Verify:
- Framework data accessed via `framework_study_plans` (versioned, approved-only)
- Student selections pinned to specific version (no retroactive changes)
- `framework.refresh_quarterly` Celery beat respects `FRAMEWORK_REFRESH_DAYS` (default 90)
- Pattern-A research run cost-capped at `FRAMEWORK_RESEARCH_COST_CEILING_USD` (default 10)
- Platform Admin approval gate enforced (72hr SLA via `FRAMEWORK_APPROVAL_SLA_HOURS`)
- Copyright handling: AI cites sources; practice problems AI-generated, never copying copyrighted

### N.10 — Upload profile correctness (§11.19)

**For:** any new file upload surface.

Verify:
- Uses an existing profile from §11.19 list (`platform_reference_book`, `school_library_content`, `independent_personal_content`, `lecture_image`, `bulk_import`, `student_question_image`, `va_upload_chunks`, `recovery_bundle`)
- New profile additions go through `infrastructure/storage/profiles.py` + ARCH §11.19 PR
- Profile enforces correct: max size, formats, dedup scope, retention
- For `student_question_image`: EXIF stripped at ingest, 1-year retention, max 3 per question

### N.11 — Promotion approval workflow (§6.21)

**For:** any feature touching the promotion state machine.

Verify:
- State transitions respect lock: pending_approval → (approved | rejected | expired)
- Approval endpoint requires `require_role('school_admin')` (inheriting District Admin / Platform Admin via §6.19)
- Atomic Celery transaction with 5-retry on failure
- Grade 12 promotion triggers graduation cascade (Flow 4 v3 §3.9)
- Audit log per approval/rejection/execution per §14.10

### N.12 — Graduation lifecycle (Flow 4 v3 §3.9)

**For:** any feature touching graduated students.

Verify:
- During 6-month read-only window (`GRADUATION_GRACE_DAYS`): student in school tenant, lecture viewer read-only, no new content
- Migration is atomic via `graduation.migrate_eligible_students` daily Celery beat
- Parent-child links auto-severed on migration
- All learning data preserved (highlights, flashcards, framework selections move to independent tenant)

---

## Final summary template

When all checks pass for the touched areas:

```markdown
## Phase Complete Review — PASSED

Areas touched: A, B, C, D, J
All checks: ✅

This PR is ready for Abd.'s review.
```

When some fail:

```markdown
## Phase Complete Review — BLOCKED

Areas touched: A, B, C, D, J
Failures:
- A.8 — Cross-tenant denial test missing → see fix template in checklists.md
- J.3 — Hardcoded English in 3 places (file:line, file:line, file:line) → wrap in t()

Once fixed, re-run this skill to re-verify.
```
