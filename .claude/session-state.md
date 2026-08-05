# Session state (live)

**Milestone:** M-09 Lecture Wizard + AI Generation
**Branch:** milestone/M-09-lecture-wizard-generation
**Done:** T-113 (`cf19314`), T-114 (`604fc01`), T-115 (`1a39885`), T-116 (`b5e0894`), T-117 (`dee320e`, amendment A-003), T-118 (`ebad1eb`), T-119 (`be464c8`), T-120 (`63b7144`), T-121 (`5222fe4`, voice conversation — sd is STT-only, no verified AI4Bharat package; migrations not live-verified, Docker Desktop unresponsive), T-122 (`5b0dcda`, cross-grade/subject linking — scoped to self-link/auto-approve only, confirmed with Hamza; migration not live-verified, same Docker gap), T-123 (`0ee38b1`, per-lecture access control — no Group model so student/section only; found+fixed a role-inheritance gap in `_require_school_teacher` for the access-settings endpoints specifically (other lecture endpoints still have it — flagged as follow-up); migration not live-verified, same Docker gap)
**Current ticket:** T-124 (next)
**Next:** ticket-loader for T-124 — delivery tips + technique demo + real-world examples
**Unrelated pending item:** frontend/src/lib/auth.ts (+ its test) and api/app/features/{student_onboarding,tos}/service.py have uncommitted changes not from this session — not yet committed, flagged to Hamza, left untouched.
**Out of scope reminder:** Edit+versions → M-10; quiz/publish → M-11; viewer → M-12
