# Session state (live)

**Milestone:** M-09 Lecture Wizard + AI Generation
**Branch:** milestone/M-09-lecture-wizard-generation
**Done:** T-113 (`cf19314`), T-114 (`604fc01`), T-115 (`1a39885`), T-116 (`b5e0894`), T-117 (`dee320e`, amendment A-003), T-118 (`ebad1eb`), T-119 (`be464c8`), T-120 (`63b7144`), T-121 (`5222fe4`, voice — sd STT-only; migration not live-verified), T-122 (`5b0dcda`, cross-grade linking — self-link/auto-approve only; migration not live-verified), T-123 (`0ee38b1`, per-lecture access — student/section only, no Group model; fixed a role-inheritance gap in the access-settings endpoints specifically; migration not live-verified), T-124 (`7f351b0`, delivery tips/demo/examples — 2nd Celery-chained LLM call; generation+display only, no Print/Share; found+fixed a Celery-broker-in-unit-tests bug; migration not live-verified)
**Docker gap:** Docker Desktop has been unresponsive since mid-T-121 — no live migration upgrade/downgrade verification since T-120's school_0052. Flag to Hamza if this matters before merge.
**Current ticket:** T-125 (next)
**Next:** ticket-loader for T-125 — independent teacher stripped variant
**Unrelated pending item:** frontend/src/lib/auth.ts (+ its test) and api/app/features/{student_onboarding,tos}/service.py have uncommitted changes not from this session — not yet committed, flagged to Hamza, left untouched.
**Out of scope reminder:** Edit+versions → M-10; quiz/publish → M-11; viewer → M-12
