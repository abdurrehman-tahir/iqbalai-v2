# File path → expected ARCHITECTURE.md sections

This is the lookup the `phase-complete-review` skill uses in Pass 1 to audit the PR description's declared "Sections read from ARCHITECTURE.md" list against the actual file changes.

For each pattern below, when a file matching it appears in the PR, the listed sections are the ones Claude Code should have read. If they're absent from the PR's declared list, that's a finding to surface.

The skill applies these in declaration order; the first match wins. Note that this is an audit lookup — for the implementation-side guidance, use `docs/ARCHITECTURE.md §0.1` (which is task-oriented). This file is file-oriented.

## Backend — features

```
api/app/features/<feature>/router.py
  → §0, §2.3-2.5, §5, §6.7, §3.4

api/app/features/<feature>/service.py
  → §0, §2.3-2.5, §3.4-3.6
  → AND IF LLM used: §8
  → AND IF RAG used: §7
  → AND IF events published: §9.5, §9.9
  → AND IF cache used: §3.11

api/app/features/<feature>/repository.py
  → §0, §3 (entire), §4 (entire)

api/app/features/<feature>/models.py
  → §0, §4 (entire), §3.3

api/app/features/<feature>/schemas.py
  → §0, §5.3 (envelope)
  → AND IF error messages: §13

api/app/features/<feature>/tasks.py
  → §0, §10.3-10.5, §3.14

api/app/features/<feature>/events.py
  → §0, §9.8-9.10, §3.15

api/app/features/<feature>/dependencies.py
  → §0, §6.7, §3.4

api/app/features/<feature>/tests/test_*.py
  → §0
  → AND IF tenant-scoped feature: §3.13 (the cross-tenant denial test is mandatory)
```

## Backend — infrastructure (the abstraction layers)

```
api/app/infrastructure/llm/**
  → §0, §8 (entire)

api/app/infrastructure/llm/providers/<provider>.py
  → §0, §8 (entire), §15.2 (env-var routing)

api/app/infrastructure/llm/prompts/<name>_v<N>.py
  → §0, §8.6 (typed prompts), §13 (target_language handling)

api/app/infrastructure/rag/**
  → §0, §7 (entire), §3.8 (Qdrant tenant filter chokepoint)

api/app/infrastructure/rag/retriever.py
  → §0, §7.5-7.6, §3.8

api/app/infrastructure/rag/embedder.py
  → §0, §7.3 (Infinity), §3.8

api/app/infrastructure/rag/reranker.py
  → §0, §7.4

api/app/infrastructure/rag/pipelines/<name>.py
  → §0, §7 (entire), §3.8, §8

api/app/infrastructure/events/**
  → §0, §9 (entire)

api/app/infrastructure/events/publisher.py
  → §0, §9.5-9.7, §9.9

api/app/infrastructure/events/registry.py
  → §0, §9.3-9.4

api/app/infrastructure/events/consumer_base.py
  → §0, §9.8-9.10

api/app/infrastructure/events/dedup.py
  → §0, §9.10

api/app/infrastructure/storage/**
  → §0, §11 (entire), §3.9

api/app/infrastructure/storage/upload_pipeline.py
  → §0, §11.2-11.7

api/app/infrastructure/cache/**
  → §0, §3.11

api/app/infrastructure/voice/**
  → §0
  → AND for TTS/STT routing: refer to STACK_LOCK §4 voice section

api/app/infrastructure/ingestion/**
  → §0, §11 (entire)

api/app/infrastructure/ingestion/chunker.py
  → §0, DEVIATIONS.md (the pre-approved langchain.text_splitter scope)

api/app/infrastructure/ingestion/pdf_parser.py
  → §0, §11.7 (MIME / magic-byte)

api/app/infrastructure/ml/**
  → §0
  → ML at launch is heuristics; XGBoost training is Phase 2 per TODO

api/app/infrastructure/search/searxng_client.py
  → §0, §7.12 (Pattern A tier-3 web search)
```

## Backend — core (cross-cutting)

```
api/app/core/dependencies.py
  → §0, §6 (entire), §3 (entire)

api/app/core/exceptions.py
  → §0, §5.5 (locked error codes)

api/app/core/logging.py
  → §0, §14.3-14.4, §16.6

api/app/core/responses.py
  → §0, §5.3-5.6, §16.4

api/app/core/middleware.py
  → §0, §16.2 (middleware stack order)

api/app/core/security.py
  → §0, §6 (entire)

api/app/core/pagination.py
  → §0, §5.6, §16.5
```

## Backend — database

```
api/app/db/base.py
  → §0, §4 (entire), §3.3

api/app/db/mixins.py
  → §0, §4.2-4.5

api/app/db/session.py
  → §0, §4.13-4.14

api/app/db/engine.py
  → §0, §4.13, §15.2

api/alembic/env.py
  → §0, §4.12

api/alembic/versions/<rev>.py
  → §0, §4.12, §15.7
  → AND IF schema for tenant-scoped table: §3.7 (RLS in migration)
  → AND IF long-running: §15.7 (risk flag)
```

## Backend — Celery / tasks

```
api/app/tasks/celery_app.py
  → §0, §10 (entire), §15.2

api/app/tasks/base.py
  → §0, §10.3-10.4, §3.14

api/app/tasks/beat_schedule.py
  → §0, §10.6 (locked schedule)
```

## Backend — main / config

```
api/app/main.py
  → §0, §16.1 (app factory), §16.2 (middleware)

api/app/config.py
  → §0, §15.2, §16.3

api/app/api/v1/__init__.py
  → §0, §5.1
```

## Frontend

```
frontend/src/app/**/page.tsx (Server Component pages)
  → §0, §12.2-12.4, §13

frontend/src/app/**/layout.tsx
  → §0, §12.2-12.4, §13

frontend/src/app/api/**/route.ts (Next.js API routes, rare)
  → §0, §12.10 (apiClient)

frontend/src/features/<feature>/components/**.tsx
  → §0, §12 (entire), §13

frontend/src/features/<feature>/hooks/**.ts
  → §0, §12.11 (TanStack Query patterns)

frontend/src/features/<feature>/api.ts
  → §0, §12.10 (apiClient), §5

frontend/src/features/<feature>/schemas.ts
  → §0, §12.7 (forms + zod)

frontend/src/components/ui/*
  → §0, §12.5
  → Note: these are shadcn primitives. Modifying directly is a code smell — re-export instead.

frontend/src/components/empty-state.tsx
frontend/src/components/error-state.tsx
  → §0, §12.8 (four UI states)

frontend/src/lib/api/**
  → §0, §12.10 (apiClient + interceptors)

frontend/src/lib/i18n.ts
  → §0, §13 (entire)

frontend/middleware.ts
  → §0, §13.3 (locale resolution), §6 (auth middleware)

frontend/messages/*.json
  → §0, §13 (entire)

frontend/tailwind.config.ts
  → §0, §12.5 (design tokens)

frontend/next.config.ts
  → §0, §12.21 (perf budgets)

frontend/package.json
  → §0, §12.5 (allowed libraries)
```

## Operations / deployment

```
docker-compose.yml
  → §0, §1 (containers), §15.4

api/Dockerfile
  → §0, §15.5

frontend/Dockerfile
  → §0, §15.5

grafana/dashboards/*.json
  → §0, §14.7

grafana/provisioning/**
  → §0, §14.7-14.8

prometheus/prometheus.yml
  → §0, §14.6

prometheus/alerts/*.yml
  → §0, §14.9

loki/loki.yml
  → §0, §14.3

tempo/tempo.yml
  → §0, §14.8

alertmanager/alertmanager.yml
  → §0, §14.9

nginx/conf.d/*.conf
  → §0, §15.11

scripts/ops/deploy.sh
  → §0, §15.6, §15.15

scripts/authentik/bootstrap.py
  → §0, §6.3, §6.15

.github/workflows/*.yml
  → §0, §15.17

.env.example
  → §0, §15.2
```

## Documentation

```
docs/ARCHITECTURE.md
  → A change here is itself an architecture decision. Goes via AMENDMENTS.md.

docs/STACK_LOCK.md
  → Changes only with Abd. explicit approval. New deviation? Use DEVIATIONS.md instead.

docs/WORKFLOW.md
docs/BRANCHING.md
  → Process changes. Approved by Abd.

docs/DEVIATIONS.md
  → New deviation entry — verify the deviation has a scope (which file is exempt).

docs/AMENDMENTS.md
  → Architecture decision changed. Verify the matching ARCHITECTURE.md edit is in the same PR.

docs/TODO.md
  → Phase 2+ items.

docs/ENV_VARS.md
  → Updated whenever config.py or .env.example changes.

docs/runbooks/*.md
  → §0, §14.13, §15.14

docs/backlog/M-NN-*.md
  → Implementation milestone files. Tickets cite flow specs + ARCH sections.
  → Updated by Abd. + Claude in chat sessions; reviewed before milestone work starts.

docs/backlog/ROADMAP.md
  → Milestone overview. Updated when a milestone completes.

docs/HAMZA_START_HERE.md
  → Process doc. Approved by Abd.
```

## Tests

```
api/tests/**
  → §0
  → AND IF testing a tenant-scoped feature: §3.13

api/tests/conftest.py
  → §0, §3 (fixtures for two-school setup), §6 (auth fixtures)

frontend/src/**/*.test.tsx
  → §0
  → Component tests not yet mandatory at launch; deferred to TODO.
```

## Catch-all

If a file path doesn't match any pattern above, then:

1. **Top-level repo files** (`README.md`, `.gitignore`, `docker-compose.yml`, etc.) — no specific section expected; an "ops housekeeping" note in the PR is sufficient.
2. **Files in `scripts/`** — check whether they touch enforcement (forbidden imports, env vars, stack locks). If yes → §0 should be in the read list.
3. **Files under `tools/` or one-off helpers** — `phase-complete-review` skill should flag this as "unmapped path" and ask the user whether the change is in scope.

When in doubt, expect the contributor to read §0 — every PR starts there.

## How the skill uses this file

Pseudo-algorithm:

```python
declared_sections = parse_pr_body_sections_read(pr.body)
changed_files = pr.diff.changed_files
findings = []

for file in changed_files:
    expected = lookup_sections_for(file)  # from this file
    missing = set(expected) - set(declared_sections)
    if missing:
        findings.append({"file": file, "missing_sections": missing})

if findings:
    output_violations(findings)
else:
    output_pass()
```

The skill output references this file for the file → section mapping so contributors can verify the logic themselves.
