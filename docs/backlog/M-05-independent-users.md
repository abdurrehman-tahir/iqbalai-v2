# M-05 — Independent Users: signup + Platform Library

**Status:** todo
**Estimated duration:** 2 weeks
**Tickets:** T-069 through T-076
**Spec source:** `flow-3-teacher-onboarding.md` v3 §3.2 (independent teacher), `flow-4-student-onboarding.md` v3 §3.2 (independent student), `flow-1-platform-setup.md` (Platform Library tier)

## Goal

Independent Teachers and Independent Students self-sign-up via the public route, land in the `independent` Postgres schema, and access the **Platform Library** (read-only) like school users do — but with zero school-tier access. This milestone exercises the dual-schema routing built in M-00, adds the Platform Library upload path (Platform Admin only, global dedup), and reuses the M-04 ingestion pipeline for platform-tier content.

**Scope boundary:** signup + onboarding + Platform Library only. Diagnostic execution = M-08. Self-study mode + study plans = M-08+. Lecture creation = M-09+. This milestone stops at "independent user exists, is onboarded, and can read the Platform Library + their own private pool."

**Demo at milestone end:**
- An Independent Teacher self-signs-up at `/independent/signup` → email verification → first-login profile → READY_TO_USE
- An Independent Student self-signs-up → **exam framework REQUIRED** + grade level + exam date → profile → READY_TO_STUDY (diagnostic deferred to M-08)
- Both land in the `independent` schema (verified: their data never appears in any school query)
- Platform Admin uploads a reference book to the **Platform Library** → ingests (reusing M-04 pipeline) → AVAILABLE
- Both independent users see the Platform Library item (read-only); neither can see any School Library
- An independent user uploads a reference book to their **private pool** (always private, no school-library option)

---

## T-069 — Independent signup path (Authentik group + tenant_type JWT + schema routing)

**Layer:** 3
**Milestone:** M-05
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.2, `flow-4-student-onboarding.md` §3.2 (public signup)

### ARCH source
- `ARCHITECTURE.md` §6.20 (independent user signup path), §3.16 (separate-schema tenant model)
- `ARCHITECTURE.md` §6.17 (Authentik IDP issues both JWT kinds)

### Depends on
- T-005 (Authentik, M-00), T-003 (dual schemas, M-00), T-007 (auth middleware, M-00)

### What this ticket builds

**Backend:** Public `GET/POST /independent/signup` creating an Authentik account in the "Independent Users" group with a property mapper setting `tenant_type=independent` + `role=independent_teacher|independent_student` (per form selection). Middleware routes requests to the `independent` schema via `schema_translate_map` based on the JWT claim. Email verification identical to school users.

**Frontend:** Public signup landing with role selection (Teacher / Student) + email + password + name + language. (Role-specific extra fields handled in T-070/T-071.)

### Acceptance (demo script)

1. [ ] `POST /independent/signup` creates an Authentik account in the Independent Users group
2. [ ] JWT carries `tenant_type=independent`, correct `role`, `school_id=None`
3. [ ] Middleware routes the authenticated request to the `independent` schema
4. [ ] Email verification flow works (identical to school)
5. [ ] An independent user's data is written to the independent schema (verified — absent from school schema)

### Out of scope
- Role-specific onboarding fields (T-070, T-071)
- Platform Library access (T-073)

### Notes / known gotchas
- Schema routing was built in M-00 (T-003/T-007); this ticket EXERCISES it for real independent traffic — don't re-implement the routing, wire signup into it.

---

## T-070 — Independent Teacher onboarding (profile → READY_TO_USE)

**Layer:** 3
**Milestone:** M-05
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.2 (independent teacher lifecycle #16)

### ARCH source
- `ARCHITECTURE.md` §3.16 (no school context), §6.20

### Depends on
- T-069 (independent signup)

### What this ticket builds

**Backend + frontend:** First-login minimal profile completion for independent teachers. `ready_to_use` derived = `profile_complete` (no assignment gate — independents have no Grade-Subject). NO capacity, NO subject/grade enforcement, NO school library access.

### Acceptance (demo script)

1. [ ] Independent teacher first login forces minimal profile screen
2. [ ] After profile complete → READY_TO_USE (no assignment needed)
3. [ ] No capacity field shown (N/A for independents)
4. [ ] No school-library entry points anywhere in their UI
5. [ ] Suspended independent teacher blocked from new content; existing readable

### Out of scope
- Doc-chat / lecture planner / quiz generator surfaces (later milestones)
- Private pool upload (T-074)

---

## T-071 — Independent Student onboarding (exam framework required + exam date)

**Layer:** 3
**Milestone:** M-05
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-4-student-onboarding.md` §3.2 (independent student lifecycle)

### ARCH source
- `ARCHITECTURE.md` §3.16, §3.19 (Exam Framework — selected at signup)
- `ARCHITECTURE.md` §6.20

### Depends on
- T-069 (independent signup)
- T-021 (exam syllabi/frameworks seeded, M-01)

### What this ticket builds

**Backend + frontend:** Independent student signup collects **exam framework (REQUIRED)** + grade level + (first login) exam date. `ready_to_study` derived = `profile_complete`. Self-Study Mode ONLY — no Mode Switcher rendered. Diagnostic availability is wired as a deferred hook (execution in M-08).

### Acceptance (demo script)

1. [ ] Independent student signup REQUIRES exam framework selection (blocks without it)
2. [ ] Grade level + exam date captured (exam date on first login)
3. [ ] After profile → READY_TO_STUDY
4. [ ] No Mode Switcher UI (Self-Study only)
5. [ ] Diagnostic entry point present but deferred (hook only; execution M-08)
6. [ ] No parent-linking option (independents have none at launch)

### Out of scope
- Diagnostic execution (M-08)
- Self-study sessions / study plans (M-08+, Flow 8)

### Notes / known gotchas
- Exam framework is REQUIRED for independents (no school structure to fall back on) — this is the key difference from school student onboarding.

---

## T-072 — Platform Library upload (Platform Admin, global dedup) + ingestion

**Layer:** 3
**Milestone:** M-05
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` (Platform Library tier; #7 platform upload)

### ARCH source
- `ARCHITECTURE.md` §11.19 (`platform_reference_book` profile — global SHA-256 dedup)
- `ARCHITECTURE.md` §7.2 (Pattern S ingestion — reused from M-04)

### Depends on
- T-056 (RAG ingestion pipeline, M-04), T-016 (Platform Admin, M-01)

### What this ticket builds

**Backend + frontend:** Platform Admin upload to the Platform Library via the `platform_reference_book` profile (100 MB, PDF, global scope, GLOBAL SHA-256 dedup, indefinite retention). Reuses the M-04 ingestion pipeline (parse → chunk → embed → Qdrant, platform-tier collection). Curricula at platform tier are always public; reference books at platform tier are always public (no privacy toggle at platform tier).

### Acceptance (demo script)

1. [ ] Platform Admin uploads a PDF to Platform Library → ingests via M-04 pipeline
2. [ ] Status → AVAILABLE; vectors in a platform-tier Qdrant collection
3. [ ] Global dedup (same file uploaded twice platform-wide → reused storage)
4. [ ] Only Platform Admin can upload at platform tier (others → FORBIDDEN)
5. [ ] Platform-tier items are always public (no privacy toggle)

### Out of scope
- School Library (M-04, done)
- Platform-tier curriculum topic-tree (reuse T-057 if curriculum; references skip it)

### Notes / known gotchas
- Dedup scope is GLOBAL for platform tier (vs per-school for M-04's school library). Don't reuse the school-scoped dedup.

---

## T-073 — Platform Library access (read-only, all tenants) + cross-schema views

**Layer:** 3
**Milestone:** M-05
**Estimate:** 2 days
**Status:** todo

### Spec source
- `flow-1-platform-setup.md` (Platform Library visible to all schools + independents, read-only)

### ARCH source
- `ARCHITECTURE.md` §3.16 (platform-shared tables via cross-schema read-only views)
- `ARCHITECTURE.md` §6.19 (read access)

### Depends on
- T-072 (platform content exists), T-060 (library browse UI, M-04)

### What this ticket builds

**Backend:** Expose platform-shared tables (incl. `platform_reference_books`) to the `independent` schema via cross-schema read-only views per §3.16. Platform Library browse/search available to ALL tenants (school teachers, school students, independent users) read-only. No tenant can see another tenant's school library; independents see ZERO school libraries.

**Frontend:** Platform Library tab in the library browser for all user types, read-only (no upload/edit for non-Platform-Admin).

### Acceptance (demo script)

1. [ ] Independent teacher + student both see Platform Library items (read-only)
2. [ ] School users also see Platform Library (read-only) alongside their school library
3. [ ] Independent users see NO school library (zero entries)
4. [ ] Cross-schema view returns platform content to independent schema queries
5. [ ] Non-Platform-Admin cannot upload/edit/delete platform items (FORBIDDEN)

### Out of scope
- Using platform content in lectures/study (later milestones)

### Notes / known gotchas
- Platform-shared tables physically live in the school schema; the independent schema reaches them via read-only cross-schema views (§3.16). Don't duplicate the data into the independent schema.

---

## T-074 — Independent private pool (reference upload, always private)

**Layer:** 3
**Milestone:** M-05
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.2/§3.4 (independent: private pool only, no privacy toggle)
- `flow-4-student-onboarding.md` §3.2 (independent student materials private)

### ARCH source
- `ARCHITECTURE.md` §11.19 (upload profiles), §3.16 (independent isolation)

### Depends on
- T-056 (ingestion), T-069 (independent users)

### What this ticket builds

**Backend + frontend:** Independent users upload reference material to their **private pool** (per-user dedup, always private — NO school-library option, NO privacy toggle). Ingested via the M-04 pipeline into a per-user Qdrant scope within the independent schema.

### Acceptance (demo script)

1. [ ] Independent user uploads a PDF → private pool, ingested → AVAILABLE
2. [ ] No "make public to school" toggle anywhere (independents have no school)
3. [ ] Per-user dedup (same file twice by same user → reused storage)
4. [ ] Pool is private to that user; isolated in the independent schema
5. [ ] No path to any school library from an independent account

### Out of scope
- Self-study sessions consuming the pool (M-08+, Flow 8)
- Curriculum upload by independents (Flow 8 territory)

---

## T-075 — E2E smoke test (independent signup → Platform Library)

**Layer:** 6
**Milestone:** M-05
**Estimate:** 1 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` §3.2, `flow-4-student-onboarding.md` §3.2

### ARCH source
- `ARCHITECTURE.md` §0 (E2E convention)

### Depends on
- T-069 through T-074

### What this ticket builds

**Test harness:** Automated E2E: independent teacher signs up → verifies → onboards → READY_TO_USE → reads Platform Library. Independent student signs up with exam framework → onboards → READY_TO_STUDY. Platform Admin uploads to Platform Library → both independents see it; neither sees any school library. Asserts schema isolation (independent data absent from school schema). Runs in CI with a fixture PDF.

### Acceptance (demo script)

1. [ ] E2E runs green end-to-end in CI
2. [ ] Independent signup → onboarding → READY asserted for both roles
3. [ ] Exam-framework-required gate asserted for independent student
4. [ ] Platform Library visibility asserted for independents; school-library invisibility asserted
5. [ ] Schema isolation asserted (independent rows not in school schema)

### Out of scope
- Frontend Playwright E2E (Phase 2)

### Notes / known gotchas
- Use a committed fixture PDF; no network fetch in CI.

---

## T-076 — Milestone M-05 PR + demo

**Layer:** 6
**Milestone:** M-05
**Estimate:** 0.5 day
**Status:** todo

### Spec source
- `flow-3-teacher-onboarding.md` v3 + `flow-4-student-onboarding.md` v3 (independent portions)

### ARCH source
- `ARCHITECTURE.md` §0 (section-tracking), per `WORKFLOW.md` §1.4 + §2.x

### Depends on
- T-069 through T-075

### What this ticket builds

The single milestone PR per `WORKFLOW.md` Step 2: open the M-05 branch PR, fill the description (spec source read, ARCH sections read per §1.4, acceptance summary per §1.3), run the `phase-complete-review` skill, run the live demo for Abd. + Awais, address review, merge to `staging`.

### Acceptance (demo script)

1. [ ] PR opened from `milestone/M-05` → `staging`, full description per WORKFLOW.md §1.3
2. [ ] `phase-complete-review` skill passes
3. [ ] CI green (including T-075 E2E)
4. [ ] Live demo runs cleanly for Abd. + Awais
5. [ ] Review addressed; merged to `staging`

### Out of scope
- Anything beyond the M-05 ticket set

---

## Milestone notes

- **First real independent-tenant traffic.** Dual-schema routing was built in M-00; M-05 is the first milestone that drives actual independent users through it. Schema isolation is the highest-value thing to assert (T-075).
- **Platform Library reuses the M-04 ingestion pipeline** — same Pattern S (parse → chunk → embed), different dedup scope (global, not per-school) and a platform-tier Qdrant collection.
- **Cross-schema read-only views** (§3.16) are how independents reach platform-shared tables without duplicating data.
- **Onboarding stops before the diagnostic** — independent students reach READY_TO_STUDY; diagnostic execution is M-08.
- **No parent linking for independents** at launch (Flow 4 v3 §3.3 lock).
- **Source flows:** Flow 3 v3 §3.2 + Flow 4 v3 §3.2 + Flow 1 Platform Library — all finalized, no blockers.
