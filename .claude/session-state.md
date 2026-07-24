# Session state (live)

**Fixed:** District Admin schools 403 (`District scope required`).
**Cause:** `district.admin` had role but empty `district_id` (middleware enriches scope from app DB).
**Code:** Authentik seed + OIDC blueprint emit `district_id`/`school_id`; login reconciles org scope from JWT.
**Live:** app DB `district.admin` → Sample District; Authentik attrs reseeded.
**Next for Hamza:** Refresh Schools page (no re-login needed if DB already patched); after fresh Authentik seed, sign out/in once.
