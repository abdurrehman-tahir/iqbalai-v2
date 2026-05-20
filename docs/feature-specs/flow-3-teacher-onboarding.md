# Flow 3 — Teacher Signup & Setup

**Status:** draft (v3 — curriculum vs reference clarified, library privacy toggle, capacity redefined as Grade-Subject assignments, independent users)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-14
**Related ARCHITECTURE sections:** §3 (multi-tenancy, esp. §3.16 independent tenant model), §4 (DB patterns + dual Alembic heads §4.21), §6 (auth, esp. §6.19 permission inheritance + §6.20 independent signup), §7 (RAG ingestion), §11 (file uploads, esp. §11.19 library profiles), §13 (i18n)
**Related feature specs:** `flow-1-platform-setup.md`, `flow-2-admin-coordinator-setup.md`, `flow-4-student-onboarding.md`, `flow-5-teacher-creates-lecture.md`
**v2 doc features covered:** #11, #16, #17, #18

---

## 1. Purpose

Two distinct kinds of teacher exist on IqbalAI:

1. **School-onboarded teachers** — created by a School Admin in Flow 2 via admin invitation. Belong to the school's tenant. Complete profile, then are assigned by the Coordinator to specific Grade-Subject offerings before they can create lectures.
2. **Independent teachers** — sign up themselves via the public signup flow. Belong to the `independent` tenant (separate Postgres schema per ARCHITECTURE.md §3.16). Use IqbalAI as a personal AI workspace: doc-chat, lecture-plan generation, quiz generation on their own uploaded materials. NO students on platform, NO school context, NO content library access — only their private uploaded materials.

This flow owns both teacher types' onboarding through to "ready to use the platform." Critical foundations:

- **Curriculum vs reference book** distinction (#17) — curriculum = official course book (e.g., Punjab Textbook Board Physics Grade 9); reference book = supplementary/helping material (notes, past papers, additional readings). Different parsing pipelines, different RAG weights, different privacy rules.
- **Structured parsing** of curriculum content (#18) — chapter → section → sub-topic extraction.
- **Teacher capacity** (#11) — redefined as the number of **Grade-Subject assignments** a teacher holds (not number of students). School teachers only; N/A for independent.
- **Library privacy toggle** for teacher uploads of reference materials (private vs public to school).
- The teacher's **profile + region** (#16) — required for both types.

---

## 2. Personas

| Persona | Role in this flow |
|---|---|
| **School Teacher** | Account created by School Admin in Flow 2. Completes profile, browses/selects from school content library (filtered by Grade-Subject tags). Gets Grade-Subject assignments from Coordinator. Eventually creates lectures (Flow 5). |
| **Independent Teacher** | Self-signs-up via public signup page. Completes minimal profile, uploads own materials to private pool. No students, no school context. |
| **School Admin** | Per Flow 2: created the School Teacher account. Sees teachers' onboarding status; can override capacity (audit-logged). Approves promotion requests (Flow 2). |
| **Coordinator** | Per Flow 2: assigns School Teachers to Grade-Subject offerings within own scope; this is where teacher capacity is consumed. Approves nothing in Flow 3 directly. |
| **District Admin / Platform Admin** | Per §6.19 permission inheritance, inherit all rights of lower roles in scope. |
| **Student / Parent** | Will see School Teacher names automatically through Grade enrollment (Flow 4 — no #19/#20 discovery). Independent teachers are never visible to students. |

---

## 3. Lifecycle

### 3.1 School Teacher onboarding lifecycle (#16)

```
   ACCOUNT_CREATED         (Flow 2 — School Admin created the user)
       ↓ first login
   PROFILE_INCOMPLETE      (forced profile-completion screen)
       ↓ profile filled
   PROFILE_COMPLETE
       ↓ Coordinator assigns ≥ 1 Grade-Subject offering (Flow 2)
   ASSIGNED
       ↓ teacher selects from school library OR uploads own materials
   READY_TO_TEACH          (can create lectures in Flow 5)
       ↓ admin action (rare)
   SUSPENDED               (from Flow 2 #3)
```

**Key change from v2:** READY_TO_TEACH no longer requires content selection at onboarding — a teacher is "ready" once assigned to a Grade-Subject by Coordinator. Content selection is per-lecture (in Flow 5 wizard). The teacher can browse and pre-select content if they want, but it's not a gate.

### 3.2 Independent Teacher onboarding lifecycle (#16)

```
   SIGNUP_INITIATED        (public signup: email + password + role=independent_teacher + name + language)
       ↓ email verification (Authentik)
   PROFILE_INCOMPLETE      (first login → minimal profile completion)
       ↓ profile filled
   READY_TO_USE            (can immediately use doc-chat, lecture planner, quiz generator on uploaded materials)
```

**Locked rules (both types):**
- Onboarding mandatory before primary feature surfaces.
- "READY" is derived — School Teacher: `profile_complete AND ≥ 1 Grade-Subject assignment`; Independent Teacher: `profile_complete`.
- Suspended users blocked from creating new content; existing content readable.

**Locked rules (School Teacher only):**
- The 6-level scope inheritance applies; School Teacher's `school_id` set at creation by School Admin.

**Locked rules (Independent Teacher only):**
- Lives in `independent` Postgres schema per §3.16.
- Auth uses same Authentik IDP per §6.20; signup at `/independent/signup`; JWT claim `tenant_type=independent`.
- NO capacity (no students); NO subject/grade enforcement; NO school content library access.

### 3.3 Curriculum lifecycle (#17, #18)

**Curriculum** = the OFFICIAL course book for a subject+grade (e.g., Punjab Textbook Board Physics Grade 9). Used as the primary content source for lecture generation; RAG-weighted higher than reference books.

**For School Teachers** — curricula come from the school content library (uploaded by Admin/Coordinator roles, who upload curricula on behalf of the school). A School Teacher who needs a different curriculum can upload one to the library (becomes public to school, not optional).

```
   ADMIN/COORDINATOR uploads curriculum to school library (tagged subject+grade+language; content_type=curriculum)
       ↓ ingestion task fires
   INGESTING               (parsing, chunking, embedding, structured-topic extraction)
       ↓ success
   AVAILABLE               (visible in Flow 5 wizard; ready for lecture generation)
       ↓ admin action
   SOFT_DELETED            (hidden from new uses; existing lectures retain citations)
```

For Teachers uploading curricula: same flow, but the upload is **always public to school** (curricula are not optional per §5.2 rules below).

**For Independent Teachers** — uploads curricula to their private pool:

```
   UPLOADED → INGESTING → AVAILABLE → REMOVED (existing lecture plans retain citations)
```

**Locked rules:**
- **Structured parsing applies to curricula only** — produces `topic_tree_jsonb` with chapter → section → sub-topic.
- Reference books skip structured parsing (chunked + embedded only).
- The curriculum/reference distinction is encoded as `content_type` enum on library items; RAG retrieval weights `curriculum` chunks higher than `reference` chunks.
- A teacher can use multiple curricula in one lecture (e.g., primary curriculum + cross-grade reference from lower grade).

### 3.4 Reference book lifecycle (#17)

**Reference book** = supplementary/helping material (notes, past papers, problem sets, additional readings, video transcripts). NOT the official course book.

**Privacy rules (the new model):**

| Uploader role | Default visibility | Can choose? |
|---|---|---|
| Platform Admin uploads to Platform Library | Public to all schools | No (always public at platform tier) |
| District/School Admin/Coordinator | Public to school library | No (always public when admin uploads) |
| **Teacher** | **Choice at upload: private or public** | **YES — toggle, default private** |
| **Student** | Always private to student | No (always private) |

**For School Teachers** — when uploading a reference book:

```
   UPLOAD
       ↓ teacher chooses privacy at upload time
   PRIVATE (default)                          PUBLIC TO SCHOOL
   (visible only to teacher)                  (in school library, visible to other teachers + students per tags)
       ↓ ingestion task                            ↓ ingestion task
   INGESTING / AVAILABLE                      INGESTING / AVAILABLE
       ↓ teacher action
   REMOVED                                    REMOVED (selection record only; item stays in library if other teachers use it)
       OR
       ↓ teacher action
   PUBLISHED                                  (not applicable — already public)
   (changes private → public; one-way)
```

**Locked rules:**
- **Default is private** for teacher reference uploads. Teacher must opt-in by toggling "Make available to the school in the Content Library" at upload.
- **Private → Public allowed** later (teacher can publish a previously private item).
- **Public → Private blocked** (already shared, can't un-share). Teacher can remove their own selection of a public item; the item stays public for others who selected it.
- Reference books are chunked + embedded but skip structured parsing.
- Same SHA-256 dedup applies (per Flow 1 §5.2). For school library uploads, dedup is school-scoped (two teachers uploading same PDF → same storage entry, separate selection records, separate privacy state if both private).

**For Independent Teachers** — uploads reference books to private pool only; no privacy toggle (always private).

### 3.5 Teacher capacity lifecycle (#11, School Teachers only) — REDEFINED

**Capacity is now defined as number of Grade-Subject assignments**, not number of students.

```
   PROFILE_COMPLETE        (no assignments yet)
       ↓ Coordinator assigns Grade-Subject offering
   ASSIGNMENT_COUNT = 1
       ↓ more assignments
   ASSIGNMENT_COUNT = N (up to teacher_capacity)
       ↓ at cap
   AT_CAPACITY             (Coordinator's attempt to add another → PRECONDITION_FAILED)
       ↓ School Admin (or higher) override OR Coordinator unassigns one
   PARTIAL_LOAD
```

**Locked rules:**
- Default capacity: **5 Grade-Subject assignments** per teacher. Min: 1. Max: 20 (operational ceiling).
- Realistic teachers max out around 8-10 (per Q16 confirmation).
- When Coordinator tries to assign a 6th Grade-Subject to a teacher at cap=5: API returns `PRECONDITION_FAILED` with a clear message. **No automatic waitlist for admin-driven assignments.** Coordinator must either unassign one or request School Admin override.
- School Admin (and higher per §6.19) can **override** capacity: assigns above cap, logs audit entry, teacher gets notification (`connections` namespace).
- Capacity is teacher-managed (teacher can edit their cap within [1, 20]); School Admin can override (audit-logged).
- **N/A for Independent Teachers.**

**Rationale (per Q7 redesign):** Pakistani teachers physically teach 200+ students per grade. Capping by student count was always wrong. The real cognitive limit is how many distinct Grade-Subject preparations a teacher can sustain.

---

## 4. Permissions matrix

Per ARCHITECTURE.md §6.19 (Permission Inheritance): every action available to a role is also available to all roles ABOVE it in the hierarchy, bounded by scope. The matrix below shows ownership; inheritance is implicit.

**For School Teacher resources:**

| Action | School Teacher (self) | Coordinator (assigned) | School Admin | (+District+Platform Admin per inheritance) |
|---|:---:|:---:|:---:|:---:|
| Edit own profile (#16) | ✅ | view-only | ✅ | inherit ✅ |
| Set / change region (#16) | ✅ | view-only | ✅ | inherit ✅ |
| Browse/select from school library | ✅ | view-only | ✅ | inherit ✅ |
| Upload curriculum to school library | ✅ (auto-public) | ✅ (auto-public) | ✅ (auto-public) | inherit ✅ |
| Upload reference (private OR public) | ✅ (toggle) | ✅ (auto-public — admin role) | ✅ (auto-public) | inherit ✅ |
| Publish private reference to school library | ✅ (own) | n/a | ✅ (audit-logged) | inherit ✅ |
| Trigger structured parsing (#18) | (auto on curriculum upload) | manual re-trigger ✅ | manual re-trigger ✅ | inherit ✅ |
| Set / change own capacity (#11) | ✅ | view-only | override ✅ (audit) | inherit ✅ |
| View own Grade-Subject assignments | ✅ | ✅ (assigned scope) | ✅ (own school) | inherit ✅ |

**For Independent Teacher resources:**

| Action | Independent Teacher (self) | Platform Admin |
|---|:---:|:---:|
| Edit own profile | ✅ | ✅ |
| Upload to private pool | ✅ | ✅ (for support/troubleshooting) |
| Trigger re-ingestion | ✅ | ✅ |
| View own dashboard + history | ✅ | ✅ |
| Account deletion (#15, Flow 4) | ✅ | ✅ |

**Locked rule:** every endpoint enforces `require_role(MIN_ROLE)` per §6.7, where MIN_ROLE is the lowest role that can perform; the dependency interprets this as "MIN_ROLE or higher within correct scope" per §6.19. Independent teacher endpoints route to the `independent` schema repository.

---

## 5. Edge cases

### 5.1 Profile (both types)
- **Teacher tries to use platform before profile completion:** redirected to profile screen.
- **Required fields not translated yet:** form labels render in user's preferred language with English fallback.
- **Suspended teacher:** all content operations blocked. Active lectures remain readable to students until School Admin reassigns Grade-Subject.
- **Independent teacher tries to access school-only features:** API returns 404 — endpoint not registered in independent tenant routes.
- **Profile region change after teacher has Grade-Subject assignments:** allowed; assignments unaffected. (Region is no longer used for discovery since #19/#20 are removed — see Flow 4 v2.)

### 5.2 Curriculum (#17, #18)
- **Curriculum upload is always public to school** regardless of uploader role. Teachers cannot mark a curriculum as private (it would defeat the purpose — curriculum is the shared official course material).
- **Curriculum identical to existing library item (same SHA-256):** dedup applies; uploader sees "this curriculum already exists in the school library — using existing version." Additional tag metadata can be added.
- **Structured parsing fails:** lands in `INGESTION_FAILED`. Uploader gets notification (`content_library` namespace); can retry OR use in degraded mode (unstructured chunks only). Degraded items carry a warning badge in Flow 5 wizard.
- **Curriculum soft-deleted by School Admin:** existing lectures grandfathered; new generations blocked with banner "this curriculum is no longer maintained — pick a replacement."
- **Curriculum version bump:** banner to teachers using v1; existing lectures stay on v1; new lectures use teacher's selected version.
- **Upload exceeds 100 MB:** rejected at upload pipeline (profile `school_library_content` for school teachers; `independent_personal_content` for independent teachers — see ARCHITECTURE §11.19).
- **Unidirectional cross-grade:** if a teacher in Grade 10 wants Grade 9 content during lecture generation, allowed in Flow 5 wizard. Grade 9 teacher CANNOT browse Grade 10 content. Wizard hides items where `min(grade_range) > target_grade`.

### 5.3 Library tag filtering
- Library items tagged `{content_type, subject_id, grade_range[], language, optional: chapter_id}`.
- Teacher in Flow 5 wizard for Grade 9 Physics in Urdu sees: `subject=Physics AND 9 IN grade_range AND language=ur`, both curricula and references.
- Multi-grade tagged items (`grade_range=[9,10,11]`) visible to all three.
- Cross-grade (Grade 10 reading Grade 9): wizard has "include lower grades" toggle; reveals items where `max(grade_range) ≤ 10` (unidirectional rule).

### 5.4 Reference books (#17) — privacy nuances
- **Teacher uploads reference with privacy toggle unchecked (default = private):** item stored, marked private, visible only to that teacher.
- **Teacher uploads with toggle checked → public to school:** item visible to teachers + students per tag filtering. SHA-256 dedup against EXISTING school-library reference items.
- **Teacher uploads private reference, identical to existing public school reference:** dedup logic — what happens? **Rule:** the teacher's selection record links to the existing public item; teacher's "privacy" toggle is ignored for already-public items (they can't make a public thing private). UI shows "this material is already in the school library; using existing public version."
- **Teacher uploads private reference, identical to ANOTHER teacher's private reference:** dedup at file-storage level (single underlying file); each teacher has independent selection record with their own privacy state. Both stay private to their respective teacher.
- **Teacher publishes private → public:** selection record's privacy flips; item becomes searchable in school library. Other teachers can now select it. Action is logged.
- **Teacher tries to "unpublish" a public reference (revert to private):** blocked. Returns `PRECONDITION_FAILED` with message "Once shared with the school, content cannot be made private. You can remove your selection but the content stays available to others."
- **Student tries to upload to school library:** not exposed in student UI; if attempted via API, returns 403.
- **Admin role uploads reference book:** always public, no privacy toggle shown. If admin needs a private reference, they upload via a personal teacher account (rare).

### 5.5 Capacity & Grade-Subject assignments (#11, new model)
- **Coordinator assigns Grade-Subject to teacher at cap=5:** returns `PRECONDITION_FAILED` with current assignment count + cap.
- **School Admin override:** allowed; audit log + teacher notification (`connections` namespace).
- **Teacher lowers cap below current assignment count:** allowed; existing assignments retained, new blocked.
- **Teacher leaves school (deactivated):** all Grade-Subject assignments removed; Coordinator gets a list of unassigned subjects to reassign.
- **N/A for Independent Teachers.**

### 5.6 Cross-tenant
- **School teacher cannot view another school's data:** 404 per §3.13.
- **School teacher cannot view independent teacher data:** 404 (separate schema, separate routes).
- **Independent teacher cannot access school endpoints:** 404 (endpoint not registered in independent routing).
- **Independent teacher cannot view another independent teacher's data:** 404 (each independent user is their own micro-tenant; only Platform Admin sees across).

---

## 6. Limits

### Profile
- Fields: name (required), region (required for School Teachers — province/district picker; optional for Independent), bio (optional, 500 char), photo (optional, 5 MB JPEG/PNG), language preference (required).
- Subjects assignable (School Teacher): driven by Grade-Subject assignments, no separate cap.
- Subjects for Independent Teacher: tagged per upload, not assigned globally.

### Curricula (#17, #18)
- Max curricula per teacher selected: 10.
- Max file size: 100 MB (per `school_library_content` or `independent_personal_content` profile per §11.19).
- Allowed formats: PDF only at launch.
- Structured parsing timeout: 10 minutes per file (Celery `soft_time_limit`).

### Reference books (#17)
- Max reference books per teacher (selected): 30.
- Same size/format limits.
- Privacy: default private for teacher uploads.

### Capacity (#11, School Teacher only) — REDEFINED
- Default cap: **5 Grade-Subject assignments**.
- Min cap: 1. Max cap: 20.
- Practical realistic range: 1-10.

### Independent Teacher
- Past sessions retained indefinitely (subject to #15 deletion rights).
- Free at launch — no rate limits beyond §15.11 default anti-abuse.

---

## 7. Notifications

All notification template keys use namespace prefixes per ARCHITECTURE.md §9.21. Triggers route to the relevant feature's notification board; global panel shows aggregate counts only.

### Namespace: `content_library`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Curriculum ingestion completes | Uploader | In-app + push | `content_library.curriculum_ready` |
| Curriculum ingestion fails | Uploader | In-app + email | `content_library.curriculum_ingest_failed` |
| Curriculum version bump (admin re-upload) | Teachers using v1 | In-app | `content_library.curriculum_version_available` |
| Curriculum / reference deprecated (soft-deleted by admin) | Teachers using it | In-app | `content_library.content_deprecated` |
| Reference ingestion completes | Uploader | In-app | `content_library.reference_ready` |
| Reference ingestion fails | Uploader | In-app | `content_library.reference_ingest_failed` |
| Teacher publishes private → public | Teacher (confirmation) | In-app | `content_library.reference_published` |

### Namespace: `connections` (School Teacher only)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Coordinator assigns Grade-Subject | Teacher | In-app + push | `connections.grade_subject_assigned` |
| Coordinator unassigns Grade-Subject | Teacher | In-app | `connections.grade_subject_unassigned` |
| School Admin overrides capacity | Teacher | In-app + push | `connections.capacity_admin_override` |
| Capacity 80% threshold | Teacher | In-app | `connections.capacity_warning` |
| Capacity full | Teacher | In-app | `connections.capacity_full` |

### Namespace: `account`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Profile completed (onboarding done) | Teacher | In-app | `account.profile_complete` |
| Account suspended (Flow 2 #3) | Teacher | Login banner | `account.suspended` |
| Account reactivated | Teacher | Email + in-app | `account.reactivated` |

**Notifications cannot be turned off** per Flow 1 Q13.

---

## 8. Open questions

1. **Curriculum upload — who's the typical uploader?** With the new model, curricula are uploaded primarily by Admin/Coordinator roles (school owns the curriculum library). **Question:** is a Teacher uploading a curriculum a rare scenario, or normal? Recommendation: rare — curricula are typically pre-loaded by Coordinator at session start. Teachers can upload if needed (e.g., a niche subject not yet in library).

2. **Independent teacher session history — foldering?** Q4 confirmed flat reverse-chronological list at launch. Sub-question for Phase 2: tag-based or folder-based organization? Defer the answer.

3. **Structured parsing quality target (#18).** Target 90%+ success rate; failures surface with retry + degraded fallback. Confirmed.

4. **Region picker source.** 4 provinces + ICT + GB + AJK at launch. Confirmed.

5. **Re-parsing platform-wide.** Platform Admin can re-trigger fleet-wide; affected teachers notified. Existing lectures unaffected.

6. **Teacher publishing private → public reference — review step?** **Question:** when a teacher flips a private reference to public, should School Admin review/approve before it goes live? Recommendation: no review at launch (trust-based, audit-logged); Phase 2 may add review step.

7. **Capacity default = 5 Grade-Subjects.** Confirming with Awais this is realistic. Pakistani teachers typically handle 3-6 distinct preparations; cap=5 is the typical middle.

8. **What happens if a teacher's last Grade-Subject assignment is removed?** They go back to ASSIGNED → PROFILE_COMPLETE state? Or do they stay "available" for new assignments? Recommendation: revert to PROFILE_COMPLETE; can't create new lectures until assigned again. Existing lectures remain readable.

9. **Cross-grade access in Flow 5 wizard.** Per-lecture toggle, remembers teacher's last choice but not binding. Confirmed.

10. **Independent teacher email domain restrictions.** No restrictions at launch.

11. **Teacher uploads curriculum — naming collision with platform-tier curriculum.** A teacher uploads a curriculum that's identical to one in the Platform Library (Flow 1 cross-school content). **Question:** dedupe at platform level (school library refs the platform item)? Recommendation: yes — platform library is the master; school library refs are shortcuts. Avoids duplicate ingestion.

12. **Independent teacher data export — same #15 mechanism as students?** Yes — same export/deletion mechanics, separate schema, separate storage path.

---

## 9. Out of scope (for now)

- **Subscription-tier caps** (e.g., max-curricula-per-school based on tier). Schema exists, NOT enforced at launch. (TODO: per Flow 13)
- **Independent-to-school migration.** Independent users keep accounts; school re-onboards as separate account. (TODO: `phase-2-independent-to-school-migration`)
- **Independent teacher analytics dashboards** beyond past-session history. (TODO: `phase-3-independent-teacher-analytics`)
- **Independent teacher peer connections / collaboration.** Isolated at launch. (TODO: `phase-3-independent-teacher-collaboration`)
- **Credential verification.** Trust-based at launch. (TODO: `phase-2-credential-verification`)
- **Cross-school curriculum sharing.** School-scoped only. (TODO: `phase-2-cross-school-curriculum`)
- **Curriculum customization** (annotating, customizing structure). Read-only at launch. (TODO: `phase-2-curriculum-customization`)
- **Public → private "un-publish"** of references. Once shared, stays shared. (TODO: `phase-2-unpublish-with-admin-approval`)
- **Review step on teacher publishes** (private → public). Direct publish at launch. (TODO: `phase-2-library-moderation`)
- **Teacher rating by students.** Out per "coaching not grading" policy.
- **Region-weighted recommendation algorithm.** Discovery (#19/#20) removed for school students per Q17 follow-up. (TODO: `phase-2-cross-grade-teacher-discovery`)
- **Dynamic capacity** tied to schedule. Static at launch. (TODO: `phase-2-dynamic-capacity`)
- **Mentorship pairing** between teachers. (TODO: `phase-3-teacher-mentorship`)
- **OCR pipeline improvements** for scanned curricula. Launch assumes typed-text PDFs. (TODO: `phase-2-improve-ocr-pipeline`)
- **Foldering / tagging** in Independent Teacher dashboard. Flat list at launch. (TODO: `phase-2-independent-foldering`)
- **Bulk teacher import.** Teachers invited individually at launch. (TODO: `phase-2-bulk-teacher-import`)

---

## 10. Related ARCHITECTURE sections

- **§3 (entire)** — multi-tenancy patterns
- **§3.16** — Independent users tenant model
- **§3.17** — Subscription as cross-cutting tenant attribute (schema only at launch)
- **§3.7-3.8** — RLS + Qdrant tenant filter
- **§4.2-4.8** — DB mixins
- **§4.12** — Alembic migrations
- **§4.21** — Dual Alembic heads (school schema + independent schema)
- **§5.1-5.7, §5.9** — API design + Idempotency-Key for uploads
- **§6.7** — Dependency primitives
- **§6.19** — Permission inheritance semantic
- **§6.20** — Independent user signup path
- **§7.3-7.10** — RAG pipeline
- **§8.6** — Typed prompts; `curriculum_parse_v1.py`
- **§9.21** — Notification namespaces (`content_library`, `connections`, `account`)
- **§10.3-10.5** — Celery `@tenant_task`
- **§11.19** — Upload profiles: `school_library_content`, `independent_personal_content`
- **§13** — i18n for all teacher-facing text

### Data model sketch

```
# In school schema:
teacher_profiles
  user_id (PK, FK to users), name, region_province, region_district (nullable),
  bio, photo_key (nullable MinIO), years_of_experience (nullable),
  is_profile_complete (bool, derived), capacity_max (default 5, range [1, 20]),
  created_at, updated_at, deleted_at

teacher_grade_subject_assignments
  id (uuidv7), teacher_user_id (FK), grade_subject_offering_id (FK to Flow 2 entity),
  assigned_at, unassigned_at, assigned_by_user_id, last_overridden_by_admin_id

school_library_content
  id (uuidv7), school_id, uploaded_by_user_id, content_type (enum: curriculum/reference),
  title, file_key, file_sha256, status (enum), version_number,
  visibility (enum: public/private — only meaningful for reference + teacher uploader),
  structured_parsing_status (enum, for curricula only),
  topic_tree_jsonb (nullable, curricula only), vector_collection,
  tags_jsonb ({subject_id, grade_range[], language, chapter_id (nullable)}),
  created_at, updated_at, deleted_at
  -- Note: curricula always have visibility=public; references default private for teacher uploads, public for admin uploads.

teacher_content_selections
  id (uuidv7), teacher_user_id, library_content_id (FK), 
  visibility_at_selection (snapshot of public/private at time of selection),
  selected_version, selected_at, removed_at

# In independent schema:
independent_teacher_profiles
  user_id (PK, FK to users in independent schema), name, language_preference,
  is_profile_complete (bool), created_at, updated_at, deleted_at

independent_personal_content
  id (uuidv7), user_id, content_type (enum: curriculum/reference),
  title, file_key, file_sha256, status (enum),
  structured_parsing_status (enum, for curricula only),
  topic_tree_jsonb (nullable), vector_collection (per-user namespace),
  created_at, updated_at, deleted_at
```

---

## 11. Acceptance criteria

### School Teacher onboarding (#16)
- ✅ First login Teacher in PENDING_INVITE → forced profile-completion screen
- ✅ All fields render in user's preferred language (en/ur/sd/ps)
- ✅ Region picker shows 4 provinces + ICT + GB + AJK
- ✅ Profile completion advances to PROFILE_COMPLETE
- ✅ Coordinator-assigned Grade-Subject offering advances to ASSIGNED
- ✅ ASSIGNED state allows lecture creation in Flow 5
- ✅ Suspended teacher: existing lectures readable; new creation blocked

### Independent Teacher onboarding (new)
- ✅ Public signup at `/independent/signup` creates user in `independent` tenant
- ✅ Authentik property mapper assigns `tenant_type=independent` claim in JWT
- ✅ Email verification before login
- ✅ First login → forced minimal profile (name + language)
- ✅ Profile complete advances to READY_TO_USE
- ✅ JWT routes request to independent schema repository
- ✅ Independent Teacher cannot access school endpoints (404)

### Curriculum (#17, #18)
- ✅ Admin/Coordinator/Teacher can upload curriculum to school library (always public to school)
- ✅ Curriculum upload triggers ingestion + structured parsing
- ✅ Structured parsing produces `topic_tree_jsonb` chapter → section → sub-topic
- ✅ Failed structured parsing surfaces with retry + degraded fallback
- ✅ Independent Teacher uploads curricula to private pool
- ✅ SHA-256 dedup: school-scoped for school teachers, user-scoped for independent
- ✅ Cross-grade unidirectional: Grade N wizard accesses ≤Grade-N content
- ✅ NATS event `curriculum.ingested` published with `tenant_type` field

### Reference books (#17) — with privacy toggle
- ✅ Teacher upload UI shows "Make available to school library" toggle (default unchecked)
- ✅ Unchecked → reference stored as private (visible only to teacher)
- ✅ Checked → reference stored as public (visible per tag filtering to all school users)
- ✅ Admin uploads of references → always public, no toggle shown
- ✅ Student uploads → always private, no toggle shown, never enter library
- ✅ Private → Public allowed via separate "Publish to school" action
- ✅ Public → Private blocked (returns `PRECONDITION_FAILED`)
- ✅ SHA-256 dedup at file level; selection records carry per-teacher privacy state
- ✅ Privacy state visible in teacher's content management UI

### Capacity (#11, new model)
- ✅ Default cap = 5 Grade-Subject assignments per teacher
- ✅ Cap editable within [1, 20] by teacher
- ✅ Coordinator assignment beyond cap → `PRECONDITION_FAILED` with clear message
- ✅ School Admin override creates audit log + teacher notification
- ✅ District Admin / Platform Admin inherit override right per §6.19
- ✅ Last assignment removed → teacher reverts to PROFILE_COMPLETE state
- ✅ No auto-waitlist for admin-driven assignments (waitlist concept retired here)

### Library tag filtering
- ✅ Flow 5 wizard for Grade 9 Physics Urdu shows ONLY items matching `subject=Physics AND 9 IN grade_range AND language=ur`
- ✅ Cross-grade toggle reveals items with `max(grade_range) ≤ target_grade` only
- ✅ Curriculum/reference both filterable in wizard UI

### Cross-tenant
- ✅ School Teacher cannot read another school's library (404)
- ✅ School Teacher cannot read independent teacher data (404)
- ✅ Independent Teacher cannot read any school data (404)
- ✅ District Admin / Platform Admin inherit access per §6.19

### Notifications
- ✅ Every template key in correct namespace (`content_library`, `connections`, `account`)
- ✅ Notifications route to feature's local board per §9.21
- ✅ Global panel shows aggregate counts only
- ✅ Templates render in all 4 languages; no `__TODO__` in production

### i18n
- ✅ All teacher-facing UI in en/ur/sd/ps
- ✅ RTL languages render correctly with logical Tailwind utilities

---

**Last reviewed:** 2026-05-14
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log from v2 → v3:**
- Curriculum and reference clarified: curriculum = official course book (always public to school); reference = supplementary material (privacy toggle for teacher uploads)
- Library privacy toggle introduced: default private for teacher reference uploads; admins always public; students always private
- Teacher capacity REDEFINED as number of Grade-Subject assignments (was: number of students); default cap = 5
- Removed waitlist concept for admin-driven assignments (replaced with PRECONDITION_FAILED + override)
- Aligned terminology with new Grade-Subject offering model from Flow 2 v3
- Subscription tier reference added to §3.17 (schema only, not enforced)

**Change log from v1 → v2:** (retained for reference)
- Added Independent Teacher persona, lifecycle, permissions, edge cases
- Permission inheritance semantic (§6.19) applied throughout matrix
- Cross-grade linking flipped to unidirectional
- Notification namespaces (`content_library`, `connections`, `account`)
- School Library tag-filtering rule documented
