# Runbook: Celery queue backlog

**Status:** Stub — populated reactively when first triggered.
**Severity:** P2 — async tasks delayed but not failed
**Trigger:** Celery queue depth >100 for 10 min — Alertmanager fires

## Until populated

See `docs/ARCHITECTURE.md` §10.13, §14.9 for the architectural context. The `docs/runbooks/README.md` explains the stub-and-grow philosophy.

When this runbook fires for the first time, the on-call operator should:

1. Diagnose and resolve the incident (this is the priority).
2. Open a postmortem from `docs/runbooks/incident-postmortem-template.md`.
3. **Populate this runbook** with the commands used, the error messages observed, and the decision points encountered. The next person on-call should be able to follow this runbook without recreating the diagnostic work.

The README in this folder documents the minimal structure for a populated runbook.

---

**Cross-references:** ARCHITECTURE.md §10.13, §14.9
