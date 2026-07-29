# Session state (live)

**Fixed:** Curriculum "pysics" stuck on Pending ingestion.
**Causes:** (1) `SET LOCAL app.current_role` SQL error in Celery RLS; (2) stale `ingesting` skip; (3) missing School metadata for chunk FK.
**Status now:** `available` (topic tree parse degraded — sample PDF isn't a real curriculum).
**Commits:** a3dab76, 0d3d48e, + school_models FK import.
**Next for Hamza:** refresh Curriculum detail page.
