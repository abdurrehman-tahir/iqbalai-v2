# Runbook: deploying to staging or production

**Status:** Stub — populated reactively when first triggered.
**Severity:** P2 — planned operation, not incident
**Trigger:** First production deploy after Phase 1 ships

## Until populated

See `docs/ARCHITECTURE.md` §15.6 for the architectural context. The `docs/runbooks/README.md` explains the stub-and-grow philosophy.

When this runbook fires for the first time, the on-call operator should:

1. Diagnose and resolve the incident (this is the priority).
2. Open a postmortem from `docs/runbooks/incident-postmortem-template.md`.
3. **Populate this runbook** with the commands used, the error messages observed, and the decision points encountered. The next person on-call should be able to follow this runbook without recreating the diagnostic work.

The README in this folder documents the minimal structure for a populated runbook.

---

**Cross-references:** ARCHITECTURE.md §15.6
