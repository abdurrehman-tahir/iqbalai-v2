# Runbooks

**Purpose:** Operational procedures — what to do when something fails, breaks, or needs maintenance.

---

## How this folder works

Most runbooks here are **stubs at launch**. They have a title, a one-line purpose, and a pointer to the relevant `docs/ARCHITECTURE.md` section. They get **populated reactively** — the first time an alert fires, the first time an operator works through a recovery, the runbook gets fleshed out with the actual commands, error messages, and decision points encountered.

This is deliberate. Runbooks written before reality lie. They reference commands that don't quite match what `docker compose logs` actually prints. They list "common causes" the author imagined instead of the ones that actually happen. The cost of populating a runbook reactively (15-30 minutes after the first incident) is far less than the cost of writing 17 fictional ones up front.

**Fully written at launch:**

| Runbook | Why fully written |
|---|---|
| `local-dev-setup.md` | Hamza needs this on day 1 — can't be reactive |
| `first-time-setup.md` | Deferred stub — fills in on first actual VM provision (post-M-23) |
| `incident-postmortem-template.md` | It's a blank form, not a procedure — write once, use forever |
| `README.md` | This file |

**Stubs at launch (populated as alerts fire):**

| Runbook | Trigger to populate |
|---|---|
| `deploy.md` | First production deploy. (Note: the script `scripts/ops/deploy.sh` does most of the work; runbook documents the wrapper.) |
| `rollback.md` | First time we need to roll back something |
| `secret-rotation.md` | First time we rotate a credential |
| `tls-renewal.md` | If `certbot` auto-renewal ever fails |
| `postgres-down.md` | First Postgres outage |
| `qdrant-down.md` | First Qdrant outage |
| `redis-down.md` | First Redis outage |
| `minio-down.md` | First MinIO outage |
| `nats-down.md` | First NATS outage |
| `authentik-down.md` | First Authentik outage |
| `llm-provider-down.md` | First LLM provider outage (e.g., Groq returns 5xx) |
| `high-error-rate.md` | First 5xx-rate alert |
| `slow-api.md` | First API latency alert |
| `queue-backlog.md` | First Celery queue backlog alert |
| `dlq-cleanup.md` | First DLQ alert |
| `disaster-recovery.md` | Activated only after backups are enabled (Phase 2) |

---

## When you populate a stub

Replace its contents with the standard runbook structure. Use `incident-postmortem-template.md` as a starting point for incident-specific runbooks, OR use this minimal structure:

```markdown
# Runbook: <name>

**Use this when:** <one-line trigger condition>
**Severity:** P1 | P2 | P3
**Estimated time to mitigate:** <minutes>
**On-call escalation:** Abd. (phase 1-2); future on-call rotation TBD

## What this means (in plain language)

<Two-sentence explanation of what's happening>

## What to check first

```bash
# Copy-paste-able diagnostic commands
docker compose logs --tail=200 <service>
```

## Common causes (in order of frequency)

1. <Cause> — <how to verify> — <how to fix>
2. <Cause> — <how to verify> — <how to fix>

## Mitigation steps

```bash
# Step-by-step recovery — exact commands
```

## When to escalate

<Conditions under which to wake someone up>

## Post-incident

Open a postmortem from `incident-postmortem-template.md`. Update this runbook with anything you learned that wasn't already captured.
```

---

## Why this approach

Three honest reasons we go stub-and-grow:

1. **Reality is the only good runbook author.** Until an actual error message lands in your terminal at 2am, you don't know which causes to list first or which commands to run.

2. **Bootstrap-phase runbooks rot.** If we write 17 detailed runbooks now and the system architecture shifts slightly, they're all wrong. Stubs don't rot — they have nothing to be wrong about.

3. **Mufti / Hamza / future ops people read fewer runbooks than the maintainers write.** Five well-written runbooks (covering the 80% of incidents) beat 17 mediocre ones.

---

## Cross-references

- ARCHITECTURE.md §14.13 — runbook philosophy
- ARCHITECTURE.md §15.14 — locked list of runbook filenames
- ARCHITECTURE.md §14.9 — the alerts that link to these runbooks
