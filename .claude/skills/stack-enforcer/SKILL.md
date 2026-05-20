---
name: stack-enforcer
description: |
  Validate that backend code complies with STACK_LOCK.md (allowed libraries, forbidden
  imports, layer-purity rules) and ARCHITECTURE.md (no bypassing the LLM / voice / RAG /
  events / storage / cache abstractions). Use this skill before writing or modifying any
  Python file under api/app/, before adding a dependency, before importing anything that
  touches an external service, and before opening a PR that includes backend changes.
  Trigger whenever Hamza or another contributor asks Claude Code to "add a feature",
  "write an endpoint", "make a Celery task", "add a NATS event", "add a database table",
  "fix this import error", or any backend-coding action — even when the request doesn't
  explicitly mention the stack. Triggers also on phrases like "use openai", "use groq",
  "import from langchain", "talk to redis", or any direct mention of a third-party library.
---

# stack-enforcer

**You are working inside the IqbalAI v2 repo.** This skill enforces the locked tech stack and architectural boundaries documented in `docs/STACK_LOCK.md` and `docs/ARCHITECTURE.md`. Apply it whenever you write or modify backend (Python) code, OR any time you're tempted to add a new dependency.

## Why this skill exists

Backend drift happens silently. One developer adds `import openai` "just for this one quick thing." Another imports `langchain` because the stack-locked alternative felt slower. Within a month, the codebase has three different LLM clients, two different chunking libraries, and direct database access from routers. Pre-commit hooks catch some of this after the fact — this skill catches it **before** the code is even written.

The cost of getting it wrong: technical debt that compounds, security regressions (an unscrubbed external API call leaking PII), inconsistent error handling, untestable code.

## When to apply this skill

Apply on every one of these:

1. **Writing a new `.py` file under `api/app/`** — verify imports, verify layer-purity.
2. **Modifying imports in an existing file** — verify the new imports.
3. **Adding a Celery task** — verify it uses `@tenant_task` and the right queue.
4. **Adding a NATS publish or consume** — verify it goes through `infrastructure/events/`.
5. **Adding a Redis call** — verify it goes through `infrastructure/cache/`.
6. **Adding a database query** — verify it lives in a `repository.py`, not a router or service.
7. **Adding an LLM call** — verify it goes through `infrastructure/llm/client.py`.
8. **Adding a voice (TTS/STT) call** — verify it goes through `infrastructure/voice/router.py`.
9. **Adding a file upload or download** — verify it uses the `infrastructure/storage/` wrapper.
10. **Adding a dependency to `pyproject.toml`** — verify it's in STACK_LOCK.md or has an approved DEVIATIONS.md entry.

If you're about to do any of these, run through the checks below **before generating the code**.

## How to apply

Step 1: **Read `docs/STACK_LOCK.md` Section 9 (forbidden imports)** if you don't already have it in context. This is the authoritative list. The summary in `references/forbidden_imports.md` is a quick reference but the docs/STACK_LOCK.md file is the source of truth.

Step 2: **Read `docs/DEVIATIONS.md`** to know what's been pre-approved.

Step 3: For each new/modified line of code, apply the rules below in order. Stop at the first violation; surface it to the user.

## Rule 1 — Allowed libraries only

Every `import` in `api/app/` must be from one of:

- The Python standard library
- A package listed under "Allowed libraries" in `docs/STACK_LOCK.md` Sections 1–8
- A package listed in `docs/DEVIATIONS.md` with status "approved"

**Forbidden imports (Section 9 of STACK_LOCK.md):** see `references/forbidden_imports.md` for the full list. The most commonly attempted ones:

- `openai` — only inside `app/infrastructure/llm/providers/openai_compat.py`
- `anthropic` — only inside `app/infrastructure/llm/providers/anthropic_native.py`
- `groq` — only inside `app/infrastructure/llm/providers/openai_compat.py` (Groq is OpenAI-shape; we use the OpenAI SDK pointed at it)
- `langchain` — completely forbidden EXCEPT `langchain.text_splitter` inside `app/infrastructure/ingestion/chunker.py` (pre-approved deviation; see DEVIATIONS.md)
- `langgraph` — only inside `app/infrastructure/rag/` and `app/infrastructure/llm/`
- `pydantic_ai` — only inside `app/infrastructure/rag/pipelines/`
- Raw `requests` / `urllib.request` — use `httpx` instead
- Direct vector DB clients (`pinecone`, `weaviate`, `chromadb`) — we use Qdrant only
- Direct SDK for any LLM provider not listed above

**If a needed library isn't allowed:** stop. Tell the user and propose either (a) using the locked alternative, or (b) requesting a deviation in `docs/DEVIATIONS.md`. Do NOT silently add the dependency.

## Rule 2 — Single-chokepoint imports

Some imports are restricted to specific files. This protects critical abstractions from being bypassed.

| Import | Allowed only in | Reason |
|---|---|---|
| `openai`, `anthropic`, `groq`, `mistralai`, `ollama` SDKs | `app/infrastructure/llm/providers/*.py` | §8.2 single chokepoint |
| `qdrant_client` | `app/infrastructure/rag/retriever.py`, `app/infrastructure/rag/embedder.py` | §3.8 tenant filter chokepoint |
| `nats.aio` | `app/infrastructure/events/*.py` | §9.6 publisher chokepoint |
| `redis.asyncio` (raw) | `app/infrastructure/cache/*.py`, `app/infrastructure/events/dedup.py`, `app/tasks/celery_app.py` | §3.11 tenant-aware cache keys |
| `minio` | `app/infrastructure/storage/*.py` | §3.9 + §11.5 storage tenant scoping |
| `whisper`, `faster_whisper`, `piper`, `edge_tts` | `app/infrastructure/voice/*.py` | §1.5 voice chokepoint |
| `tiktoken` and per-provider tokenizers | `app/infrastructure/llm/*.py` | §8.13 token counting chokepoint |
| `langchain.text_splitter` | `app/infrastructure/ingestion/chunker.py` ONLY | DEVIATIONS.md scope rule |

**Detection:** if you see `from openai import …` or `import openai` in a file that is NOT under `app/infrastructure/llm/providers/`, that's a violation.

**Remediation:** the feature should call into the abstraction. For example:

```python
# WRONG — in a feature's service.py:
from openai import OpenAI
client = OpenAI(...)

# RIGHT:
from app.infrastructure.llm import llm_client
result = await llm_client.generate(...)
```

## Rule 3 — Layer purity (§2.4)

Within a feature folder, layers have strict responsibilities. Crossing them invites the kind of bugs that take a week to find.

| Layer | May import | May NOT import |
|---|---|---|
| `router.py` | service.py, schemas.py, dependencies.py, core/dependencies, core/responses | SQLAlchemy types, repository.py directly, models.py, another feature's router, raw HTTP exceptions |
| `service.py` | repository.py, schemas.py, infrastructure/*, other features' services | SQLAlchemy `Session` types, FastAPI types (Request, Response), router.py, another feature's repository |
| `repository.py` | models.py, schemas.py, db/session | service.py, router.py, infrastructure/* (other than db) |
| `models.py` | db/base, SQLAlchemy types | schemas.py, service.py, router.py, anything outside ORM concerns |
| `schemas.py` | Pydantic, datetime/uuid types | models.py, service.py, router.py, SQLAlchemy types |
| `tasks.py` | service.py, repository.py, tasks/base | Same as service plus: do business logic (thin wrapper only) |
| `events.py` | service.py | Same as service plus: do business logic (thin wrapper only) |

**Detection patterns:**

```python
# WRONG — router.py importing SQLAlchemy directly:
from sqlalchemy import select   # router should not touch SQLAlchemy
# RIGHT: call into the service which calls into the repository

# WRONG — service.py importing FastAPI Request:
from fastapi import Request  # service should be HTTP-agnostic
# RIGHT: router extracts what it needs and passes primitives to the service

# WRONG — feature A's repository importing feature B's repository:
from app.features.lectures.repository import LectureRepository  # in features/students/
# RIGHT: students' service calls lectures' service if needed

# WRONG — models.py importing schemas.py:
from .schemas import LectureRead  # models should not know about Pydantic
# RIGHT: services use both, mapping between them
```

## Rule 4 — Mandatory patterns

These patterns are required, not optional. If they're missing, the code is wrong.

### Routers (every endpoint)

Per §5 and §6.7:

- An access dependency: `Depends(require_role(...))` or `Depends(require_scope(...))` or `Depends(require_self_or_admin(...))` or `Depends(require_parent_of(...))` or `Depends(require_teacher_of(...))`
- `response_model=<Schema>`
- `operation_id="<feature>_<action>"`
- A `tags=["<feature>"]` declaration on the router
- For resource-creating POSTs: an `Idempotency-Key` header dependency (§5.9)
- For PUT/PATCH on versioned resources: an `If-Match` header dependency (§5.10)

### Repositories (every query)

Per §3.4 and §3.13:

- Methods that return tenant-scoped data take a `user: User` parameter
- Within-school scoping applied based on `user.role` and `user.scoped_ids`
- Returns Pydantic schemas or domain objects, NOT raw ORM models
- Soft-delete filtering by default (`WHERE deleted_at IS NULL`)

### Celery tasks (every task)

Per §10.3 and §10.4:

- Uses the `@tenant_task` decorator (NOT plain `@celery_app.task`)
- Includes `school_id` parameter (or explicitly opts out with `tenant_id=None` for system tasks)
- Accepts primitives/UUIDs only — never ORM objects, never `User` objects
- Has `acks_late=True` and `reject_on_worker_lost=True`
- Has both `soft_time_limit` and `time_limit`
- Has retry policy (`autoretry_for=...`, `max_retries=...`)
- Is idempotent — either naturally or via Redis dedup on a key

### NATS event publishing (every publish)

Per §9.5 and §9.6:

- Goes through `event_publisher.publish(...)` — NOT raw nats client
- Has a payload that's a Pydantic model registered in `infrastructure/events/registry.py`
- Has an `actor` parameter (or explicit `tenant_id` for system events)
- Publishes AFTER `await session.commit()` unless `requires_atomicity=True`

### Database tables (every new table)

Per §4 and §3.3:

- Inherits the appropriate mixins: `IdMixin`, `AuditMixin`, `SoftDeleteMixin`, `TenantMixin` (when tenant-scoped)
- Primary key is UUIDv7 (the IdMixin handles this)
- Tenant-scoped tables have RLS enabled in the migration (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY; ALTER TABLE ... FORCE ROW LEVEL SECURITY`)
- Every FK has an explicit `ON DELETE` action
- Every column has explicit nullability
- JSONB only (never JSON)
- Postgres native enums for stable values, reference tables for editable ones
- Migration template has the required header (Purpose, Risk, Reversible) per §4.12

## Rule 5 — Hardcoded values forbidden

Per §15.2:

- No hardcoded URLs (use env vars via `get_settings()`)
- No hardcoded API keys, tokens, secrets
- No hardcoded passwords
- No hardcoded service hostnames (use service names from compose)
- No hardcoded sleep/timeout durations longer than 5s without a comment justifying it

`scripts/check_envvars.py` enforces this in pre-commit. This skill catches it earlier.

## Rule 6 — Logging discipline

Per §14.3 and §16.6:

- `import structlog; logger = structlog.get_logger(__name__)` — NOT the stdlib `logging` module
- No `print()` anywhere
- No f-string formatting in log calls — use kwargs: `logger.info("user_login", user_id=u.id)` not `logger.info(f"user {u.id} logged in")`
- No raw user emails, phones, names, CNICs in log calls — use `user_id_hash` (the scrubber catches accidents, but don't rely on it)

## Workflow

When you (Claude Code) are about to write or modify code:

1. **Identify what you're about to do.** Is it a new file? A new import? A new feature? A new task?
2. **Apply the relevant rules.** Walk through Rules 1-6 in order for the change in question.
3. **If any rule would be violated:**
   - State the rule (e.g., "STACK_LOCK §9 forbids `import openai` outside `app/infrastructure/llm/providers/`")
   - State the locked alternative (e.g., "use `from app.infrastructure.llm import llm_client`")
   - Stop and ask the user before proceeding if the right alternative is unclear
4. **If all rules pass:** proceed with code generation, but include a brief line in your output explaining what you checked. The user wants to know the skill was actually applied, not just that it exists.

## What this skill does NOT cover

This skill is backend-focused. Frontend patterns (the four UI states, design tokens, i18n, accessibility) are covered by the `frontend-master` skill. End-of-feature comprehensive review (cross-tenant tests, schema checklist, etc.) is covered by `phase-complete-review`.

## Reference files

- `references/forbidden_imports.md` — concise list of forbidden imports + their allowed alternatives
- `references/layer_purity.md` — the layer responsibility matrix in detail
- `references/canonical_examples.md` — the canonical correct shapes (router, service, repository, task, event) that the user can copy
