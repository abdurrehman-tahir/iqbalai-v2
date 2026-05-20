# Incident postmortem — `<short title>`

**Status:** draft | published
**Severity:** P1 | P2 | P3 | P4
**Date of incident:** YYYY-MM-DD
**Detection time:** HH:MM PKT
**Resolution time:** HH:MM PKT
**Duration of impact:** ~N minutes/hours
**Authors:** @<github-handle>
**Last updated:** YYYY-MM-DD

---

## Summary (the headline)

One paragraph. What broke, how long, who was affected, what we did about it.

**Example:**
> *On 2026-07-12 between 14:23 and 14:51 PKT (28 minutes), API requests returning 5xx errors at ~18% rate. Affected ~150 active users across 4 schools. Root cause: Qdrant container crashed after the daily backup snapshot ran out of disk space. Mitigation: freed disk space, restarted Qdrant. No data loss.*

---

## Timeline (in PKT)

A chronological log of what happened, who did what, and when.

| Time | Event | Actor | Notes |
|---|---|---|---|
| 14:21 | Daily Qdrant snapshot starts | (automated) | |
| 14:23 | Qdrant container OOM-killed | (system) | |
| 14:23 | First 5xx error in API | (alert) | Alertmanager → Abd. WhatsApp |
| 14:25 | Abd. notified, SSH to VM | Abd. | |
| 14:28 | Identified Qdrant down | Abd. | `docker compose ps` showed it |
| 14:32 | Discovered disk full (`/var/lib/docker` at 100%) | Abd. | |
| 14:38 | Cleared old Qdrant snapshots | Abd. | freed 22 GB |
| 14:42 | Qdrant container started | Abd. | `docker compose up -d qdrant` |
| 14:48 | Qdrant fully ready (index reloaded) | (system) | |
| 14:51 | First successful API request | (system) | |
| 14:52 | Alert auto-cleared | (Alertmanager) | |
| 15:30 | Postmortem started | Abd. | |

---

## What went wrong

What was the actual cause, in plain language? Be specific.

- What system component failed?
- What user-visible symptom did it produce?
- Why did the safeguards we had in place fail to prevent it?

---

## What went right

Even in a bad incident, some things worked. Document them.

- What alerted us quickly?
- What was easy to diagnose?
- What recovery step worked smoothly?

---

## Where we got lucky

What could have made this worse? Document the parallel-universe version.

- If we'd noticed later, what would have happened?
- If the recovery hadn't worked, what was the backup plan?
- Did anything narrowly avert a bigger problem?

---

## Why this happened (root cause)

The actual systemic cause. Use "5 whys" reasoning if helpful.

**Example:**
> 1. Why was Qdrant down? — It crashed on OOM.
> 2. Why OOM? — The host had no disk space.
> 3. Why no disk space? — Qdrant snapshots accumulated.
> 4. Why did they accumulate? — No retention policy was set on the snapshot directory.
> 5. Why no retention policy? — Snapshot cleanup is deferred to Phase 2 (backup automation is in TODO.md).

---

## Action items

What we're going to change as a result. Each item must be:
- Concrete (not "improve monitoring")
- Owned by someone
- Tracked to completion

| # | Action | Owner | Status | Due |
|---|---|---|---|---|
| 1 | Add disk-space alert at 80% threshold | Abd. | Done 2026-07-13 | 2026-07-13 |
| 2 | Implement Qdrant snapshot retention (keep 7) | Abd. | Open | 2026-07-20 |
| 3 | Add docs/runbooks/qdrant-down.md based on this incident | Abd. | Open | 2026-07-15 |
| 4 | Pull backup automation forward from Phase 2 TODO | TBD | Discuss | 2026-08-01 |

---

## What we're NOT changing

Sometimes the right response is "do nothing." Document explicitly why.

- We are NOT moving Qdrant to a separate VM. Single-VM is locked in §1. Capacity is fine; the issue was operational.
- We are NOT switching from Qdrant. The product is solid; we just need disk hygiene.

---

## Lessons learned

What's the broader pattern? What should we be more vigilant about?

---

## Were our processes followed?

- [ ] Was an alert in place for this failure mode?
- [ ] Was the alert linked to a runbook?
- [ ] Did the runbook give the right next step?
- [ ] Did the on-call know what to do?

---

## Communication

Did affected users see anything? Was there a status page update? An email?

If not: should there have been?

---

## Cross-references

- ARCHITECTURE.md §<X.Y> — the relevant section
- `docs/runbooks/<related>.md` — the runbook (or stub) for this failure mode
- GitHub PRs that implemented the action items

---

**Postmortem published date:** YYYY-MM-DD
**Distributed to:** Abd., Awais, Mufti, Hamza (or whoever's relevant)
