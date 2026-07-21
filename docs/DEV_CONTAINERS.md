# Dev Containers — running a lean local stack

**Purpose:** the full stack is 16 containers, but most milestones need only ~7. This maps which containers each milestone needs so your machine isn't running the heavy ones (infinity, observability, etc.) before they're useful.

> Requires the Compose profiles + `EVENTS_ENABLED` guard from **M-01a / T-236** to be merged for the `--profile` commands and the lean core boot to work.

## How it works (Compose profiles)

Core services carry **no** profile, so they always start. Optional groups are tagged with a profile and start only when that profile is on.

- **core (always on, ~7):** `postgres`, `redis`, `authentik-server`, `authentik-worker`, `authentik-redis`, `api`, `frontend` — enough to log in + do CRUD/UI.
- **`rag`:** `qdrant`, `infinity`, `minio` — with `EMBEDDING_PROVIDER=local` (default in compose), **infinity is optional** for library upload; Celery embeds in-process via fastembed/ONNX (~150 MB).
- **`workers`:** `celery-worker`, `celery-beat`
- **`events`:** `nats` (also needs `EVENTS_ENABLED=true` — see note)
- **`observability`:** `prometheus`, `grafana`, `loki` (off by default; only for perf/dashboards)

```bash
docker compose up                              # core only (~7 containers)
docker compose --profile rag --profile workers up    # core + qdrant/infinity/minio + celery
COMPOSE_PROFILES=rag,workers docker compose up        # same, via env (put in .env per session)
```

### `EVENTS_ENABLED` note
NATS connects **eagerly** at app startup (`init_nats()` in the §16.1 lifespan), so it can't just be profiled off — a core-only boot would hang. The `EVENTS_ENABLED` env flag (default `false`) makes `init_nats()` a no-op. To use events: set `EVENTS_ENABLED=true` **and** turn on the `events` profile (from M-12). Postgres/Redis are also eager but are always in core; qdrant/minio are lazy (connect on first use), so they need no flag.

## Milestone → profiles (add on top of core)

| Milestone(s) | Add profiles | Why |
|---|---|---|
| M-00 | (run all once) | foundation smoke-test must prove every service works |
| M-01, M-01a, M-02, M-03, M-05, M-06 | none — core only | auth + CRUD + UI; no files/RAG/events |
| M-04 | `rag` + `workers` | curriculum upload (minio) + ingest (qdrant/infinity) + async |
| M-07, M-08 | `workers` | agentic/async + beat jobs |
| M-09, M-10, M-11, M-13, M-15 | `rag` + `workers` | RAG generation / scoring / enrichment |
| M-12 | `rag` + `events` (`EVENTS_ENABLED=true`) | RAG Q&A + first real-time |
| M-14, M-16, M-17 | `rag` + `workers` + `events` | full event pipeline / reviews |
| any perf or load-test work | + `observability` | only when you actually need metrics/dashboards |

## Notes
- nginx is host-level infrastructure; the only authoritative configuration shape is
  ARCH §15.11. There is intentionally no nginx configuration in this repository.
- Authentik is 3 of the heaviest containers but is needed from M-01 on (login), so it stays in core.
- `infinity` (BGE-M3 embeddings) is RAM-heavy and only runs under `rag`. Skip it locally by keeping `EMBEDDING_PROVIDER=local` (default) — embeddings run inside `celery-worker` via fastembed (ONNX) instead.
- **Apple Silicon:** compose pins `michaelf34/infinity:0.0.75` (multi-arch). Do **not** use `:latest` locally — it is amd64-only and crash-loops under Rosetta. First boot downloads ~2 GB of models; wait until `curl -f http://localhost:7997/health` succeeds (often 2–5 min).
- `mem_limit`s are set on the heavy services (authentik trio, infinity, qdrant) so they can't starve the host even when running.
