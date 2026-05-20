# Flow 1 — Platform Setup

**Status:** draft (v2 — incorporates all decisions from Flows 1-6 review rounds)
**Owners (product):** @awais (TBD-github-handle)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** 2026-05-14
**Related ARCHITECTURE sections:** §3 (multi-tenancy, esp. §3.16 independent tenant, §3.17 subscription schema, §3.19 exam framework), §4 (DB patterns, §4.21 dual Alembic heads), §6 (auth, §6.19 inheritance, §6.20 independent signup), §7 (RAG), §8 (LLM, §8.20 Custom Persona, §8.21 framework refresh agent), §9 (NATS, §9.21 notification namespaces), §10 (Celery beats), §11 (uploads, §11.19 library profiles), §13 (i18n), §14 (observability/PII)
**Related feature specs:** `flow-2-admin-coordinator-setup.md`, `flow-3-teacher-onboarding.md`, `flow-4-student-onboarding.md`, `flow-13-subscriptions.md`
**v2 doc features covered:** #1, #6, #7, #8, #9, #12, #13, #14

---

## 1. Purpose

Platform Setup is what the IqbalAI team does **before any school, teacher, or student exists** on the platform. It establishes the foundation everything else depends on: the role hierarchy (#1), supported languages (#6), the **multi-source content library architecture** (#7), exam syllabi as inputs to the AI-driven Exam Framework engine (#8), teaching personas including the new **Custom 5th persona** (#9), the notification system with namespaced feature-specific boards (#12), the disclaimer and ToS (#13), and the data archival commitments (#14).

This flow is owned by the Platform Admin (the IqbalAI team — Abd. and a small operations group at launch). Most features are operational/configuration work performed once or periodically.

This flow gates everything else. Flow 2 cannot start until Flow 1's role hierarchy + first school exists. Flows 5-12 cannot start until reference content + exam syllabi are loaded.

---

## 2. Personas

| Persona | Role in this flow | Permissions |
|---|---|---|
| **Platform Admin** | The IqbalAI team. Owns all foundational configuration: role hierarchy bootstrap, language list, content library tier (platform-wide), exam syllabi, personas, disclaimer/ToS, data archival policies. Approves AI-generated exam framework study plans per Flow 4. | Full read/write on everything in this flow. |
| **District Admin** | Created by Platform Admin in Flow 2. Inherits view of Flow 1 outputs (which exam syllabi exist, etc.). Cannot modify Flow 1 platform-tier data. | Read-only on platform-tier content; per §6.19 inherits all School Admin permissions. |
| **School Admin** | Read-only on Flow 1's platform tier. Owns their own school's content library tier (covered in Flow 2). | Read-only on platform-tier; full ownership of their school tier. |
| **Coordinator** | Consumes platform-tier outputs through their assigned scope. | Read-only on platform-tier. |
| **Teacher, Student, Parent** | Consume Flow 1 outputs as user-facing surfaces (their selected exam framework, persona, language, library content visible to them). | No access to Flow 1 admin screens. |
| **Independent Users (Teacher + Student)** | Per §3.16 separate-schema tenant model. Use platform-tier exam syllabi + frameworks + Platform Library + languages + personas + ToS + disclaimer — same as school users — but isolated at the DB level. No school-tier library access. | Standard user access to platform-tier outputs; no admin access. |

---

## 3. Lifecycle

### 3.1 Role hierarchy bootstrap (#1)

The 6-level hierarchy. All roles are created and active from launch (per Flow 2 v3 feedback Q8 — no roles skipped).

```
Platform Admin
   ↓ creates (Flow 2)
District Admin (scoped to a district)
   ↓ creates (Flow 2)
School Admin (scoped to a school)
   ↓ creates (Flow 2)
Coordinator (scoped to a school, cross-subject within assigned grade range)
   ↓ creates (Flow 2)
Teacher (scoped to a school)
   ↓ enrolled by Coordinator (Flow 2, Grade-Section model)
Student (scoped to a Grade-Section within a school)
```

Plus **Parent** (peer to Student; per §6.13 ParentChildLink opt-in pattern; Flow 4 owns parent registration).

Plus **Independent Teacher** and **Independent Student** (per §3.16 separate Postgres schema; Flow 3 v3 + Flow 4 v3 own their onboarding).

**Locked rules:**
- Each user has exactly ONE primary role. A Teacher cannot also be a Coordinator (per Flow 1 §5.1 launch decision).
- Scope IDs cascade: District Admin's `district_id` is set at creation; downstream users inherit.
- **Permission inheritance (§6.19):** every action available to a role is also available to all roles above it within scope. Platform Admin can do anything a District Admin can do, which can do anything a School Admin can do, etc. Bounded by scope.
- Platform Admin is the only role with cross-tenant access; gated by `require_role(PLATFORM_ADMIN)`.
- All 6 roles created at launch per Q8 feedback.

### 3.2 Multilingual support lifecycle (#6)

At launch: 4 languages (en, ur, sd, ps). All UI text, AI responses, notifications, voice (where supported).

```
   LANGUAGES_DEFINED          (Platform Admin loads 4-language list at deployment)
       ↓ user selects preference
   USER_PREFERENCE_SET        (one language per user platform-wide, per Q9)
       ↓ user changes preference
   PREFERENCE_UPDATED         (UI re-renders on next route change; existing content preserved in original language)
```

**Locked rules:**
- 4 languages at launch. New language addition is a Platform Admin deployment-level action (no self-service UI).
- One language preference per user across all surfaces (UI + AI + notifications). Per-channel granularity deferred to Phase 2.
- RTL languages (ur, sd, ps) render via Tailwind logical utilities (`me-`, `ms-`, `text-start` per ARCHITECTURE.md §13).
- Disclaimer + ToS text English-only at launch with `__TODO__` markers blocking production for ur/sd/ps. Phase 2 unblocks via professional translation.
- Voice (TTS/STT) language matrix tracked in `infrastructure/voice/` config; degrades gracefully (text-only) where TTS is unavailable per Flow 6 §5.1.

### 3.3 Content Library architecture (#7) — REDEFINED per v3 feedback Q10

**The content library is multi-tier and multi-source:**

| Tier | Owner | Visibility | Source |
|---|---|---|---|
| **Platform Library** | Platform Admin | All schools (public to platform) | Platform Admin uploads (curricula, reference books spanning multiple schools) |
| **School Library** | District Admin / School Admin / Coordinator / Teacher (all roles can upload per §6.19) | Within own school only | Mix of admin uploads (always public to school) + teacher uploads (privacy toggle per Flow 3 v3 §3.4) |
| **Student Personal Pool** | Student | Private to student only | Student uploads in Flow 8 self-study mode |
| **Independent Personal Pool** | Independent User | Private to that user only | Independent teacher/student uploads in their own tenant |

**Cross-tier visibility rules:**

- Platform Library is visible to all schools' teachers AND students AND independent users (read-only).
- School Library is visible only within that school (teachers AND students per tag filtering).
- Student/Independent personal pools are private — NEVER cross to library tiers.

**Content lifecycle (curricula + reference books at the library tiers):**

```
   UPLOADED                   (Platform Admin OR school role uploads; tags applied: subject + grade_range + language + content_type=curriculum|reference + optional chapter_id)
       ↓ ingestion task fires
   INGESTING                  (chunking, embedding, structured-topic extraction for curricula per #18)
       ↓ success
   AVAILABLE                  (visible per visibility rules + tag filtering)
       ↓ admin action OR teacher action
   SOFT_DELETED               (hidden; embeddings retained for existing lecture citations)
       ↓ Platform Admin action OR 30-day timer
   HARD_DELETED               (Phase 2 — at launch, soft-delete is permanent)
```

**Locked rules:**

- **Tagging is mandatory at upload:** every item carries `{content_type, subject_id, grade_range[], language, optional: chapter_id}`. Per Flow 3 v3 §5.3 tag filtering — a teacher in Grade 9 Physics in Urdu sees items matching `subject=Physics AND 9 IN grade_range AND language=ur`.
- **Privacy rules** (per Flow 3 v3 §3.4 + v3 feedback Q6-Q7):
  - **Curriculum content** uploaded by ANY role: always public to its tier (Platform Library or School Library). No privacy toggle. Curriculum is by definition shared.
  - **Reference content** by uploader:
    - Platform Admin → Platform Library, public to all schools
    - District/School Admin/Coordinator → School Library, always public to school (no toggle)
    - **Teacher → School Library OR private pool** — toggle at upload, default PRIVATE (must opt-in to public)
    - **Student → personal pool always**, never enters library, no privacy toggle
- **Cross-grade unidirectional rule** (per Flow 2 v3): Grade N can access ≤Grade-N content; reverse blocked.
- **Privacy mutability** (per Flow 3 v3 §5.4): Private → Public allowed (teacher can publish later); Public → Private blocked (one-way; once shared, cannot un-share).
- **Soft-delete is reversible at launch**; hard-delete deferred to Phase 2 (per Q12).
- **Embeddings retention:** soft-deleted items retain embeddings so existing lectures keep their citations.
- **Re-uploading the same PDF** (same SHA-256) within a tier surfaces the existing entry (no duplicate ingestion).
- **Dedup scope:** Platform Library deduped globally; School Library deduped per-school; personal pools deduped per-user.
- **Independent users access Platform Library** (read-only) like school users; they have NO access to any School Library.

### 3.4 Exam syllabi lifecycle (#8)

Exam syllabi are STRUCTURED TOPIC TREES (framework → level → subject → topic) at the platform tier. They are an INPUT to the Exam Framework engine (per Flow 4 v3 §3.5).

**Lifecycle:**

```
   PLATFORM_ADMIN_CREATES     (manual entry of topic tree for an exam: Matric Punjab, O-Level Cambridge, etc.)
       ↓
   PUBLISHED                  (selectable by students; AI Exam Framework engine uses as input)
       ↓ Platform Admin edits (rare)
   PUBLISHED v2               (version bump; students pinned to v1 grandfathered; new selections use v2)
       ↓ Platform Admin action
   DEPRECATED                 (no longer offered to new students; existing students continue on selected version)
```

**Locked rules:**
- Topic tree is hierarchical: framework → level → subject → topic (chapter → section → sub-topic), depth limited to 4 levels (per Flow 1 §6 launch).
- Once a student selects an exam framework (Flow 4 §3.5.3), they're pinned to the version available at that moment. Admin edits don't retroactively change a student's tree.
- Deleting a topic with student progress recorded blocks via `PRECONDITION_FAILED`; topic must be soft-deleted (admin sees an affected-count warning).
- Initial launch set: Matric Punjab Board, FSc Punjab, O-Level Cambridge, A-Level Cambridge per Q-EF10. Others Phase 2 / on-demand.
- Exam syllabi are INPUTS to Flow 4 v3 Exam Framework engine; the framework engine's AI agent uses these topic trees as the starting structure for AI-generated study plans.

### 3.5 Teaching personas lifecycle (#9) — 4 named + 1 Custom slot

```
   SEEDED AT DEPLOYMENT       (4 personas: Strict, Friendly Tutor, Storyteller, Exam Coach)
       ↓ student picks at onboarding (Flow 4)
   ASSIGNED_PERSONA
       OR student picks "Custom"
   CUSTOM_PERSONA_ACTIVE      (per-student persona learned over time via §8.20 weekly batch)
       ↓ Platform Admin edits
   PERSONA_EDITED             (new prompt applies to NEW sessions only; active sessions retain cached prompt)
       ↓ Platform Admin deactivates
   INACTIVE                   (no new selections; existing users continue using it)
```

**Locked rules:**
- **4 named personas + Custom (5th) at launch** per Q1 feedback. No 2-TBD slots.
- **Custom persona** (per ARCHITECTURE §8.20):
  - Per-student global (not per-subject); one Custom profile per student
  - Weekly batch updates via Celery beat `persona.update_custom`; cadence configurable via env var `PERSONA_LEARNING_BATCH_DAYS` (default 7)
  - Process: pull last 7 days of student-AI interactions (max 50 turns) → LLM summarizes into ~200-word persona description string → stored as the student's persona profile → prepended to system prompt for that student's future AI calls
  - No fine-tuning, no ML training; just summary-prompt approach
  - Cost: ~$0.01/student/week at Groq prices; for 10K active students ≈ $100/week
  - First 7 days of new Custom selection: defaults to Friendly Tutor while learning data accumulates
- Personas cannot be hard-deleted; only deactivated. Deactivated personas: existing users continue, new students can't select.
- System prompts editable via Platform Admin CMS. Edits apply to NEW sessions only.

### 3.6 Disclaimer / ToS lifecycle (#13)

```
   PUBLISHED v1               (English text loaded at deployment)
       ↓ Platform Admin edits (rare)
   PUBLISHED v2               (users must re-accept)
       ↓ user action
   USER_ACCEPTED_v2
```

**Locked rules:**
- Disclaimer text appears INLINE next to every prediction (pass probability, predicted marks, exam confidence per Phase 6 features).
- ToS acceptance required at first login. Subsequent logins check accepted version; new ToS version blocks login until accepted.
- **At launch: English only** (per Q3 feedback — no production blocker). Ur/sd/ps translations are TODO items.
- **Legal review for full launch:** TODO entry — basic industry-standard ToS at launch (per Q2 feedback).
- Disclaimer max length: 500 characters (renders inline with predictions).

### 3.7 Notification system lifecycle (#12) — namespaced per Q13

**Two-tier notification model per Q14-Q17:**

1. **Per-feature notification boards** — each feature surface has its own bell icon at the top, opening a small panel for that feature's notifications.
2. **Global notification panel** — shows aggregate counts only ("3 new in Lectures, 1 new in Self-Study").

**Locked namespaces (7):**

- `lectures` — lecture-related (Flow 5, Flow 6, Flow 7)
- `self_study` — study plan, reminders, plan adherence (Flow 8)
- `quiz` — quiz-related (Flow 5 #23b, Flow 6 attempts)
- `connections` — teacher-student via enrollment, parent-child, capacity overrides (Flow 3 + Flow 4)
- `content_library` — library ingestion, version bumps, deprecation (Flow 3 + Flow 5 cross-refs)
- `system` — platform announcements, ToS updates, security, admin-only alerts (Platform Admin)
- `account` — suspensions, exports, deletions, profile milestones (Flow 4 + Flow 2)

**Locked rules:**
- Every notification carries `feature_namespace` field per ARCHITECTURE.md §9.21.
- Notifications CANNOT be turned off (per Q13 feedback).
- Per-feature bell icon at top of feature surface; opens small panel.
- Global panel shows aggregate counts only.
- Push notifications mode-agnostic (per Q17 — push for `lectures` items fires regardless of student's current Mode).
- 90-day inbox retention; audit log retains 7-year per §14.10.
- Push rate limit: 10 per user per minute (FCM limit).

### 3.8 Data archival lifecycle (#14) — all hot at launch

```
   HOT                        (current data; primary Postgres)
       ↓ time-based policy (Phase 2)
   WARM                       (read-replica or partitioned tables — Phase 2)
       ↓ time-based policy (Phase 2)
   COLD                       (object storage / cold bucket — Phase 2)
```

**Locked rule for launch:** all data stays HOT. The doc's tiering vision (hot/warm/cold) is preserved as a Phase 2 commitment per Q4 — TODO entry.

### 3.9 Subscription tier schema (Flow 13 cross-reference)

Platform Admin can create subscription tiers (defines caps, pricing, role-scope). Schema exists at launch; **no enforcement, no Stripe code, no payment processing** — placeholder UI only. Full subscription feature is Flow 13's domain.

```
   PLATFORM_ADMIN_DEFINES_TIER  (CRUD via subscription tier management page)
       ↓
   PUBLISHED_TIER              (visible to District/School subscribe pages as placeholder)
```

**Locked rule:** tier definitions purely informational at launch. No District or School can actually subscribe (button shows "Coming soon" modal per Flow 13).

---

## 4. Permissions matrix

Per §6.19 inheritance: every action available to a role is also available to roles above in scope.

| Action | Platform Admin | (+District+School+Coordinator+Teacher+Student per inheritance — bounded by scope) |
|---|:---:|:---:|
| Create role hierarchy users (next level only) | ✅ | inherit per-level (District creates School Admin, etc.) |
| Upload to Platform Library (#7) | ✅ | ❌ (only Platform Admin can upload at platform tier) |
| Upload to School Library | n/a (Platform Admin uploads to Platform Library) | school-tier roles (per Flow 2 v3 §4) — Coordinator + School Admin + District Admin + Platform Admin |
| Browse Platform Library | ✅ | inherit ✅ (all users see Platform Library scoped by tags) |
| Browse own School Library | n/a | school-tier roles (per tag filtering) |
| Create / edit exam syllabi (#8) | ✅ | ❌ |
| Create / edit exam framework (#3.19, Flow 4 v3) | ✅ | ❌ |
| Approve AI-generated framework plans (Flow 4 §3.5.1) | ✅ | ❌ |
| Edit teaching persona prompts (#9) | ✅ | ❌ |
| Custom Persona selection by student (#9) | n/a | Student (own) |
| Edit disclaimer / ToS text (#13) | ✅ (with legal sign-off) | ❌ |
| Define subscription tiers (Flow 13) | ✅ | ❌ |
| Configure language list (#6) | ✅ | ❌ |
| Set own language preference | ✅ | inherit ✅ (every user sets own) |
| View data archival policy | ✅ | view-only via inheritance |
| Change archival policy | ✅ | ❌ |
| Read own notification inbox | ✅ | inherit ✅ |
| Configure own notification preferences (per-namespace opt-out NOT allowed at launch per Q13) | ✅ | inherit ✅ (but cannot opt out of any namespace) |

**Locked rule:** every Flow 1 endpoint uses `require_role(PLATFORM_ADMIN)` for write actions per §6.7. School-tier library uploads are owned by Flow 2's permissions (not Flow 1's), but invoke the same upload pipeline (per §11.19).

---

## 5. Edge cases

### 5.1 Role hierarchy
- **Platform Admin attempts self-demotion:** blocked. There must always be ≥ 1 Platform Admin (per Flow 1 §5.1 + Flow 2 v3 lock). Returns `PRECONDITION_FAILED`.
- **A real person needs Coordinator AND Teacher role:** they must create two accounts with different emails. Strict per launch.
- **Parent created without a linked child:** allowed per Flow 4 §3.3; account inert until linked.
- **A user appears in two scopes:** forbidden. Two-account model.
- **Cross-tenant operation attempted by School Admin:** API returns 404 per §3.13 (don't leak existence of other schools' data).
- **District Admin creates a school in another district:** blocked at API. Each admin scoped to own district.

### 5.2 Multilingual (#6)
- **AI response in a language not in the 4-language launch set:** AI defaults to language of the question; if question is in en/ur/sd/ps, response matches; if in unsupported language, response is in English with a notice.
- **User switches language mid-session:** UI re-renders on next route change. Active AI streams continue in original language; subsequent prompts use new language.
- **Translation missing in a language file:** falls back to English with a logged warning. No `__TODO__` markers allowed in production builds (CI blocks).
- **RTL languages with mixed-direction text** (Urdu paragraph with English keyword): handled by Tailwind logical utilities + Unicode bidi.

### 5.3 Content Library (#7)
- **Cross-tier visibility violation:** independent user attempts to browse a School Library — API returns 404 (different tenant).
- **Teacher's privacy toggle defaulted private; later wants to publish:** allowed via "Publish to School" action (Flow 3 v3 §3.4); creates audit log entry.
- **Teacher attempts to un-publish (public → private):** blocked (per Flow 3 v3 §5.4); `PRECONDITION_FAILED` returned.
- **Same PDF uploaded to Platform Library AND a School Library (via teacher):** dedup is per-tier — they're treated as separate entries with separate selection records. Phase 2 may add cross-tier dedup.
- **Soft-deleted item with active lecture citations (Flow 5):** existing lectures grandfathered; new lecture generations blocked with banner per Flow 5 §5.2.
- **Tag mismatch attempt** (admin uploads "Physics" curriculum tagged for "Chemistry" subject): the upload completes; admin can edit tags; ingestion runs on whatever text is in the file (no semantic validation at launch).
- **Library item upload exceeds 100 MB:** rejected at upload pipeline (`school_library_content` or `platform_reference_book` profile cap per §11.19).

### 5.4 Exam syllabi (#8) + framework engine (§3.19)
- **Admin edits a published syllabus while students are mid-exam-prep:** existing students see v1 version; new selections use v2. (Per §3.4 Flow 1 lifecycle.)
- **Admin deletes a topic with student progress recorded:** blocked with `PRECONDITION_FAILED` listing affected students.
- **Deprecated syllabus**: existing students continue on selected version; new students see deprecation notice.
- **AI framework research fails for an exam syllabus:** per Flow 4 v3 §5.4 — lands in RESEARCH_FAILED status; Platform Admin can retry or manually input content.
- **Region-mismatch on syllabus** (student in Sindh selecting Punjab Matric syllabus): per Flow 4 v3 §5.4 — warning shown but allowed.

### 5.5 Personas (#9)
- **Persona prompt edited mid-session:** new prompt applies to NEW sessions only. Active sessions cache prompt that was current at session start.
- **Persona deactivated while in use:** users continue with cached persona; new students can't select. Bulk reassignment is a separate admin action.
- **Student picks Custom persona on day 1 (no interaction data yet):** first 7 days defaults to Friendly Tutor (per §3.5 rule). Weekly batch then generates first Custom profile.
- **Custom persona batch fails for a student:** retain previous persona description (carry-over). Alert Platform Admin if failures > 5% (per `system` namespace).
- **Student has zero interactions in past 7 days:** batch skips that student; persona description unchanged.

### 5.6 Disclaimer / ToS (#13)
- **User mid-session when new ToS publishes:** current request completes; next state-changing request forces ToS modal.
- **User refuses new ToS:** account suspended (not deleted); can re-accept later.
- **Disclaimer not yet translated** (ur/sd/ps): English fallback with one-time toast acknowledging gap; production blocked until Phase 6 (predictions) requires it (per Q3).

### 5.7 Notifications (#12)
- **High notification volume** (lecture published to 200-student Grade): batch via Celery in 60s windows.
- **Real-time push failure** (WebSocket disconnect): notification still written to DB; badge updates on reconnect via NATS replay.
- **Notification deep link to soft-deleted resource:** "This item is no longer available"; notification marked READ.
- **User attempts to disable a notification namespace:** UI prevents this at launch per Q13. Endpoint returns 403 if attempted via API.

### 5.8 Subscription schema (Flow 13)
- **District attempts to subscribe at launch:** Button opens "Coming soon" modal. No state change.
- **Platform Admin creates a tier with negative pricing or invalid cap:** rejected with `VALIDATION_ERROR`.

### 5.9 Cross-tenant (independent vs school)
- **Independent teacher uploads to private pool, identical to school library item:** dedup is per-schema — entries are independent (schemas isolated per §3.16). No cross-tenant sharing.
- **Platform Admin browsing data:** can see across tenants per `require_role(PLATFORM_ADMIN)`; per-action audit logged.

---

## 6. Limits

### Role hierarchy
- Max Platform Admins: not capped (operational guidance ≤ 5).
- Min Platform Admins: 1 (enforced).

### Languages (#6)
- Launch: 4 (en, ur, sd, ps).
- New language addition: Platform Admin deployment-level only.

### Content Library (#7)
- Max file size per upload: 100 MB (`platform_reference_book` and `school_library_content` profiles per §11.19).
- Allowed formats: PDF only at launch.
- Max items per library: not capped (operational).
- OCR cost ceiling per item: $5 (failed if exceeded; admin notified).
- Soft-delete retention: indefinite at launch; Phase 2 may add 1-year auto-hard-delete for orphans (per Q12).

### Exam Syllabi (#8)
- Max topics per subject tree: not capped (operational).
- Max nesting depth: 4 (framework → level → subject → topic).

### Teaching Personas (#9)
- Total active personas: 5 (4 named + Custom).
- System prompt max length: 8,000 chars.
- Custom persona description max length: 2,000 chars (generated by LLM, stored as text).
- `PERSONA_LEARNING_BATCH_DAYS`: env var, default 7.

### Notifications (#12)
- Inbox display: 100 most recent (paginated).
- Bell badge cap: "99+".
- Per-user retention: 90 days.
- Push rate limit: 10/user/minute.
- Namespace count: 7 (locked).

### Disclaimer / ToS (#13)
- Max disclaimer text: 500 characters.
- Max ToS text: no enforced limit.

### Subscription tiers (Flow 13)
- Max tiers per role-scope (District or School): 10 at launch (operational; no enforcement).

---

## 7. Notifications

All notification template keys use namespace prefixes per §9.21. Most Flow 1 notifications are platform-admin-targeted (`system` namespace) or system-wide events.

### Namespace: `system` (Platform Admin only)

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Platform Admin uploads new Platform Library reference book | Other Platform Admins | In-app | `system.platform_library_reference_added` |
| Platform Library ingestion fails | Uploading Platform Admin | In-app + email | `system.platform_library_ingest_failed` |
| Exam syllabus published v2 | Platform Admins | In-app | `system.syllabus_updated` |
| Teaching persona deactivated | Platform Admins | In-app | `system.persona_deactivated` |
| Custom persona batch job failure rate > 5% | Platform Admins | In-app + email | `system.persona_batch_failure_rate` |
| ToS v2 published | All users (on next login) | Forced modal | `system.tos_updated` |
| Subscription tier created (Flow 13 placeholder) | Platform Admins | In-app | `system.subscription_tier_created` |

### Namespace: `content_library`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| Platform Library content soft-deleted | All teachers who have selected it | In-app | `content_library.platform_deprecated` |
| Platform Library content version bumped | All teachers using v1 | In-app | `content_library.platform_version_available` |

### Namespace: `account`

| Trigger | Recipient | Channel | Template key |
|---|---|---|---|
| User accepts new ToS | (audit only — no user notification) | — | — |

**Notifications cannot be turned off** per Q13.

---

## 8. Open questions

1. **Custom persona — what happens if a student rarely interacts?** Recommendation: batch skips students with < 5 turns in past 7 days; persona profile unchanged until they accumulate interactions.

2. **Subscription module — is District-level subscribe a real launch use case?** Recommendation: schema exists at launch (Flow 13 thin spec) but pilot has no district-tier subscriptions; only School Admin-level placeholder UI exposed. Bigger decision deferred.

3. **Custom persona batch cost monitoring.** $0.01/student/week is the baseline. Recommendation: track total cost per week in Platform Admin dashboard; alert if exceeds $200/week (10K students × 2× = unusual spike).

4. **Initial exam syllabi load.** Q-EF10 launch set: Matric Punjab Board + FSc Punjab + O-Level Cambridge + A-Level Cambridge. **Question:** is this list locked? Recommendation: yes for pilot; expand based on student onboarding signal.

5. **Disclaimer translation timing.** English at launch; ur/sd/ps before Phase 6 (predictions). Recommendation: hire a translator before Phase 6 begins (parallel work during Phase 1-5).

6. **Reference book soft-delete retention.** Indefinite at launch. Recommendation: revisit in Phase 2 — books with zero downstream references (no lectures cite them) can be hard-deleted after 1 year. Books with references stay forever.

7. **Cross-school library sharing.** None at launch (per Flow 3 v3 §9). Recommendation: revisit in Phase 2 if multiple pilot schools want to share authored content.

8. **Audit log retention** for content library uploads. Recommendation: yes — log every upload action per §14.10. 7-year retention.

9. **Independent user access to platform-tier exam syllabi/frameworks.** Confirmed yes — they get same exam framework selection as school students. **Question:** any conflict with §3.16 schema isolation? Recommendation: no — platform-tier data is shared across both tenants by design (read-only from independent tenant's perspective).

10. **Independent user notifications cross-tenant.** **Question:** if a Platform Admin updates a Platform Library curriculum, do independent users who selected it also get notified? Recommendation: yes — same notification machinery, tagged with tenant_type for routing.

---

## 9. Out of scope (for now)

- **Hot/warm/cold data tiering.** All hot at launch. (TODO: `phase-2-data-tiering`)
- **Hard-delete of library content.** Soft-delete only at launch. (TODO: `phase-2-library-hard-delete`)
- **Fuzzy dedup** (cross-version dedup beyond SHA-256). Exact-match only at launch. (TODO: `phase-2-library-fuzzy-dedup`)
- **TMS integration** (Crowdin/Lokalise/Weblate). Manual JSON editing at launch per §13.16. (TODO: `phase-2-tms-integration`)
- **URL-prefixed locales** (`/en/...`, `/ur/...`). Cookie + user pref only at launch per §13.3. (TODO: `phase-2-url-locales`)
- **Per-channel language preferences** (UI in en, AI in ur). One per user at launch. (TODO: `phase-2-per-channel-language`)
- **Eastern Arabic digit display preference.** Standard digits at launch. (TODO: `phase-2-digit-display-pref`)
- **Hijri calendar.** Gregorian only at launch. (TODO: `phase-2-hijri-calendar`)
- **Self-service language addition** UI. Deployment-level only. (Permanent — never via UI.)
- **Subscription cap enforcement.** Schema only at launch (Flow 13 thin spec). (TODO: per Flow 13)
- **Audit log queryable UI for admins.** Audit logs are written; queryable UI deferred per §14.10. (TODO: `phase-2-audit-log-ui`)
- **Persona auto-switching** after N interactions. Manual selection only. Custom persona is the closest equivalent at launch. (TODO: `phase-6-persona-auto-switch`)
- **Customer support / help desk integration.** Not at launch. (TODO: `phase-3-help-desk`)
- **2 additional named personas** (the "TBD" from v2 doc original wording). Replaced by Custom persona slot per Q1. (Permanent — no more named personas planned.)
- **Cross-tier library dedup** (Platform Library + School Library uploading same PDF). Per-tier dedup at launch. (TODO: `phase-2-cross-tier-dedup`)
- **Public → Private "un-publish" for references.** One-way at launch. (TODO: `phase-2-unpublish-with-approval`)
- **Independent user parent linking** (independent students don't link to parents). (TODO: `phase-2-independent-student-parent-linking`)
- **Legal review of ToS.** TODO entry — basic industry-standard ToS at launch (per Q2). (TODO: `pre-pilot-full-legal-review`)
- **Disclaimer translations to ur/sd/ps.** English-only at launch. Phase 6 blocker before predictions feature. (TODO: `pre-phase-6-disclaimer-translations`)

---

## 10. Related ARCHITECTURE sections

- **§3 (entire)** — multi-tenancy
- **§3.16** — Independent users separate-schema tenant model
- **§3.17** — Subscription as cross-cutting tenant attribute (schema only)
- **§3.18** — Grade/Section/Subject model
- **§3.19** — Exam Framework engine (consumes Flow 1 exam syllabi as inputs)
- **§4.2-4.8** — DB mixins
- **§4.12** — Alembic migrations
- **§4.21** — Dual Alembic heads (school + independent schemas)
- **§5.1-5.7, §5.9** — API design + Idempotency-Key (for uploads)
- **§6.2** — Role matrix (canonical 6-role list defined here)
- **§6.7** — Dependency primitives (`require_role`, `require_scope`)
- **§6.10** — Cross-tenant operations (Platform Admin only)
- **§6.13** — ParentChildLink (foundation for Flow 4 parent registration)
- **§6.19** — Permission inheritance
- **§6.20** — Independent user signup path
- **§8.20** — Custom Persona learning batch (weekly LLM summarization)
- **§8.21** — Exam Framework refresh agent (consumes #8 syllabi for AI research)
- **§9.21** — Notification namespaces (7 locked)
- **§10.6** — Celery beat schedule: `persona.update_custom`, `framework.refresh_quarterly`, `library.soft_delete_sweep` (Phase 2), `tos.acceptance_check`
- **§11.2-11.10** — File upload pipeline
- **§11.16** — Upload profile registry
- **§11.19** — Upload profiles: `platform_reference_book`, `school_library_content`, `independent_personal_content`
- **§13** — i18n (key conventions, ICU MessageFormat, message file structure, locale resolution)
- **§14.3-14.4** — Logging discipline + PII scrubbing
- **§14.10** — Audit log (every Flow 1 admin action audit-logged; 7-year retention)

### Data model sketch

```
# Platform-tier (shared across school + independent tenants via cross-schema views):
platform_reference_books
  id (uuidv7), uploaded_by_user_id (Platform Admin), title, file_key (MinIO),
  file_size_bytes, file_sha256, content_type (enum: curriculum/reference),
  status (enum: ingesting/available/soft_deleted/ingestion_failed),
  tags_jsonb ({subject_id, grade_range[], language, chapter_id (nullable)}),
  vector_collection, version_number, created_at, updated_at, deleted_at

exam_syllabi
  id (uuidv7), framework_name, level_name, region, language,
  status (enum: published/deprecated), current_version, created_at, deprecated_at

syllabus_topics  (the topic_tree)
  id (uuidv7), syllabus_id (FK), parent_topic_id (nullable self-ref),
  subject_id, name, order_index, depth (1-4),
  version_number, is_active, created_at, deprecated_at

teaching_personas
  id (uuidv7), name, system_prompt, is_active, sort_order,
  is_custom (bool, true only for the Custom slot — single row),
  created_at, updated_at

custom_persona_profiles  (per-student Custom persona — only if student opted in)
  student_user_id (PK), tenant_type (school/independent), 
  persona_description (text, ~200 words), 
  last_batch_run_at, batch_run_count, created_at, updated_at

# Notifications table (per tenant schema):
notifications
  id (uuidv7), user_id (FK), tenant_id (school_id or null for independent),
  feature_namespace (enum: lectures/self_study/quiz/connections/content_library/system/account),
  type, payload (jsonb), link, read_at, created_at, deleted_at

# Disclaimer + ToS versions (platform-level):
tos_versions
  id (uuidv7), version_number, content_jsonb (keyed by language),
  published_at, effective_at, retired_at

disclaimer_versions
  id (uuidv7), version_number, content_jsonb (keyed by language),
  published_at, effective_at

user_tos_acceptances
  user_id (PK, FK), accepted_version (FK to tos_versions), accepted_at, ip_hash

# Subscription schema (Flow 13 — placeholder only at launch):
subscription_tiers
  id (uuidv7), name, applies_to_role (enum: district/school),
  caps_jsonb, pricing_jsonb, status (enum: active/draft/deprecated),
  created_at, updated_at

# (other Flow 13 tables: subscriptions, subscription_payments — see Flow 13)
```

---

## 11. Acceptance criteria

### Role hierarchy (#1)
- ✅ All 6 roles created at launch (no skipped roles per Q8)
- ✅ Platform Admin creates District Admin via Flow 2 endpoints
- ✅ Each role's JWT contains role + scope claims; protected endpoints enforce via `require_role` + `require_scope`
- ✅ Permission inheritance §6.19: District Admin can perform all School Admin actions in own district
- ✅ Cross-tenant test: District A user attempting to read District B → 404 per §3.13
- ✅ Last-Platform-Admin self-demotion blocked with `PRECONDITION_FAILED`

### Multilingual (#6)
- ✅ 4 languages loaded at deployment (en, ur, sd, ps)
- ✅ User can switch language via settings; UI re-renders next route
- ✅ AI responses in question's language (not necessarily user's UI language)
- ✅ TTS routes per language per `infrastructure/voice/`
- ✅ RTL languages render correctly with Tailwind logical utilities
- ✅ Missing translation falls back to English with logged warning
- ✅ CI blocks deploys with `__TODO__` markers in production

### Content Library (#7)
- ✅ Platform Admin uploads to Platform Library (visible to all schools)
- ✅ School Library uploads via school-tier roles (per Flow 2 v3)
- ✅ Teacher reference upload defaults PRIVATE; toggle to public available
- ✅ Admin reference uploads always public to school (no toggle)
- ✅ Student uploads always private (no library entry, personal pool)
- ✅ Tag filtering works: Grade 9 Physics Urdu wizard sees matching items only
- ✅ Cross-grade unidirectional rule enforced
- ✅ SHA-256 dedup per-tier (Platform, School, personal pool)
- ✅ Soft-delete preserves embeddings for existing citations
- ✅ Independent users see Platform Library; cannot access any School Library
- ✅ Privacy mutability: Private→Public allowed; Public→Private blocked

### Exam Syllabi (#8)
- ✅ Platform Admin creates topic tree per framework + level + subject
- ✅ Topic tree depth limited to 4 levels
- ✅ Editing creates new version; students pinned to v1 continue
- ✅ Topic deletion with student progress blocked
- ✅ Initial launch set: Matric Punjab + FSc Punjab + O-Level Cambridge + A-Level Cambridge
- ✅ Syllabi serve as input to Exam Framework engine (Flow 4 v3 §3.5)

### Teaching Personas (#9)
- ✅ 4 named personas seeded: Strict, Friendly Tutor, Storyteller, Exam Coach
- ✅ Custom persona (5th option) selectable by student
- ✅ Custom persona weekly batch via `persona.update_custom` Celery beat
- ✅ `PERSONA_LEARNING_BATCH_DAYS` env var (default 7); configurable
- ✅ First 7 days of Custom selection: defaults to Friendly Tutor
- ✅ Persona prompt edits apply to NEW sessions only (active sessions cache)
- ✅ Deactivation blocks new selections; existing users unaffected
- ✅ Persona descriptions render in all 4 languages

### Disclaimer / ToS (#13)
- ✅ ToS acceptance required at first login
- ✅ New ToS version blocks login until accepted
- ✅ Refused new ToS: account suspended
- ✅ Disclaimer renders inline next to every prediction
- ✅ English-only at launch with `__TODO__` markers for ur/sd/ps blocking Phase 6

### Notifications (#12)
- ✅ Notification creation produces row + WebSocket push + bell badge update
- ✅ Bell badge caps at "99+"; pagination via cursor per §5.6
- ✅ Per-feature notification boards (bell icon at top of feature surface)
- ✅ Global panel shows aggregate counts only ("3 new in Lectures")
- ✅ 7 namespaces locked: `lectures`, `self_study`, `quiz`, `connections`, `content_library`, `system`, `account`
- ✅ All notifications have `feature_namespace` field per §9.21
- ✅ Notifications cannot be turned off per Q13
- ✅ 90-day inbox retention; 7-year audit log
- ✅ Push mode-agnostic (Q17)

### Data Archival (#14) — launch posture
- ✅ All data stays HOT
- ✅ Hot/warm/cold tiering deferred per TODO

### Subscription schema (Flow 13 cross-ref)
- ✅ Platform Admin creates subscription tier definitions (CRUD endpoint)
- ✅ Tier UI exists but District/School subscribe buttons show "Coming soon" modal
- ✅ No Stripe code; no payment processing; no cap enforcement

### Cross-tenant access
- ✅ Independent users access Platform Library (read-only)
- ✅ Independent users see same exam syllabi + frameworks + personas as school users
- ✅ Independent users have ZERO access to any School Library (404)
- ✅ Platform Admin sees across tenants per `require_role(PLATFORM_ADMIN)`; audit logged

### Audit logging
- ✅ Every Platform Admin write action audit-logged per §14.10
- ✅ Library uploads, syllabi changes, persona edits, ToS/disclaimer publications all audit-logged
- ✅ 7-year retention

---

**Last reviewed:** 2026-05-14
**Reviewers:** @abdurrehman-tahir (technical), @awais (TBD-github-handle) (product)

**Change log v1 → v2:**
- **Personas (#9):** 4 named + 1 Custom slot (replaces v1's "4 + 2 TBD"). Custom persona uses LLM weekly batch summary per §8.20. Per Q1 feedback.
- **Disclaimer/ToS (#13):** English-only at launch with TODO for translations. No production blocker per Q3. Legal review TODO per Q2.
- **Content Library (#7):** redefined as multi-tier (Platform / School / Personal) multi-source architecture per Q10. Privacy rules per uploader role locked. Class-tag filtering rules referenced from Flow 3 v3 §5.3.
- **Permission inheritance:** §6.19 lock applied to permissions matrix.
- **Subscriptions (Flow 13 cross-ref):** schema-only at launch; placeholder UI; Stripe deferred. Tier definition lives at Platform Admin level.
- **All 6 roles created from start** per Q8 (District Admin no longer "skipped at launch").
- **Notification namespaces:** 7 locked (lectures, self_study, quiz, connections, content_library, system, account); per-feature boards + global aggregate panel per Q13-Q17.
- **One language per user platform-wide** per Q9 (no per-channel granularity).
- **Independent users** referenced throughout — Flow 1 platform-tier data is shared with independent tenant via §3.16.
- **Exam syllabi (#8)** explicitly framed as INPUT to Flow 4 v3 Exam Framework engine.
- **Subscription tier management page** added to Platform Admin responsibilities (Flow 13 cross-ref).
- All Open Questions Q1-Q13 from v1 resolved (incorporated into spec or moved to TODO).
