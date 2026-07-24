# Session state (live)

**Fixed:** Coordinator "outside your assigned scope" on grade create.
**Cause:** `coordinator@iqbalai.dev` had empty `scoped_ids` (deny-all).
**Live:** set scoped_ids to Grade 1–12; Authentik seed + JWT claim + login reconcile.
**Next for Hamza:** retry creating grades as coordinator (no re-login needed).
