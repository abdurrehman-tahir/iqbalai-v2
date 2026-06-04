# Flow 11 — Group Study + Dashboards

**Status:** drafted (v1)
**v2 doc features covered:** #73, #101, #102, #103, #104, #105 (student-facing Learning Record core; parent-view is Flow 10), #106
**Related feature specs:** `flow-9-ai-intelligence.md` (DNA/pass-prob/at-risk data the dashboards + #101 group suggestions read; #73 ranking data), `flow-5-teacher-creates-lecture.md` (#38 admin comparative metrics + #35 score timeline + #36 Innovation Record the teacher dashboard composes — built in M-10, reused not rebuilt), `flow-7-next-day-review.md` (pending reviews shown on the teacher dashboard; "Schedule Group Study" action originates here), `flow-6-student-studies-lecture.md` / `flow-8-self-study.md` (group sessions reuse the hybrid widget #57 + session components in both modes), `flow-10-parent-monitoring.md` (parent view of #105 — sibling surface over the same Flow 9 data), `flow-2-admin-coordinator-setup.md` (dashboards show migrated alumni in "Migrated" status)

## Purpose

Two bundled concerns that share an audience and data source: **group study** (students learning together, AI-mediated) and **dashboards** (the role-scoped views that turn Flow 9's intelligence + the platform's activity into something a teacher / coordinator / admin / student can act on). Flow 11 builds **no new prediction logic** — the dashboards compose Flow 9 outputs + the M-10 #38 teacher metrics; group study reuses the Flow 6/8 session components. It is the rendering + collaboration layer on top of everything already built.

**Two milestones** (see milestone split): **M-20a Group Study** (#101, #102, #103 + the "Schedule Group Study" scheduler) and **M-20b Dashboards** (#73, #104, #105, #106).

**One STACK_LOCK deviation** (pre-approved): #103 real-time collaborative *notes* need a CRDT — **Yjs**, scoped to group notes only (lecture editing stays non-CRDT TipTap). Shared/private *threads* + presence ride the existing FastAPI WebSocket + Redis pub/sub (no deviation).

## Personas

- **Student** — joins/creates groups; sees own Learning Record (#105) + above-average class rank (#73).
- **Teacher** — confirms AI-suggested groups (#101); views (not controls) student groups; sees the teacher dashboard (#104).
- **Coordinator / School Admin / Platform Admin** — role-scoped dashboards (#106).
- **System (Celery)** — daily group-suggestion scan; dashboard aggregate refresh.

Both tenants: group study works for school + independent students; independent students have no teacher, so #101 (teacher-suggested) and teacher views don't apply to them — they use #102 (student-created) only.

---

## 3. Lifecycle

### 3.1 Teacher group creation — AI-suggested (#101)

```
   DAILY (Celery job scans student performance — Flow 9 DNA/pass-prob/mistakes)
       ↓ proposes 3+ student groupings
   SUGGESTED  ├─ mixed group (weak + strong → peer tutoring)
              └─ all-weak group (focused remedial)
       ↓ teacher reviews
   TEACHER_CONFIRMS (or edits / dismisses) → group created
```

**Locked rules:**

- Daily Celery job reads Flow 9 performance signals (consumes the Flow 9 "#101 groups consume DNA/performance" hook) and **suggests** mixed (peer-tutoring) or all-weak (remedial) groups of 3+; **the teacher confirms** — never auto-created (suggest-and-approve, CXO rule).
- School-tenant only (#101 needs a teacher); not shown to independent students.
- Suggestions are advisory; teacher can edit membership or dismiss.

### 3.2 Student-created groups — both modes (#102)

```
   STUDENT creates group → shareable invite link
       ↓ peers join via link
   GROUP_ACTIVE  ├─ lecture mode    (AI knows which lecture the group is studying)
                 └─ reference mode  (AI knows which books — personal-pool/library)
       ↓ teacher (school) can VIEW, not control
```

**Locked rules:**

- Students create groups independently via a **shareable invite link**; works in both lecture mode (AI scoped to the lecture) and reference/self-study mode (AI scoped to the books).
- Teacher (school) **can view but not control** student-created groups; independent students have no teacher view.
- Group membership respects tenant isolation (no cross-tenant groups); cross-grade grouping follows the §7.21 rules.
- Both tenants.

### 3.3 Group AI — shared + private threads + collaborative notes (#103)

```
   GROUP SESSION
       ├─ SHARED AI THREAD     (everyone sees; FastAPI WebSocket + Redis pub/sub)
       ├─ PRIVATE THREAD       (per-student; questions they don't want to share)
       ├─ PRESENCE             (who's online / who's typing — WebSocket)
       └─ SHARED NOTES         (real-time collaborative editing — Yjs CRDT)  ← deviation
       ↓ all interaction emitted as NATS events (mode=group)
   FEEDS Flow 9 (each student's own DNA, tagged group context)
```

**Locked rules:**

- **Shared AI conversation** everyone in the group sees + a **private per-student thread** for unshared questions — both over FastAPI WebSocket + Redis pub/sub (already locked, no deviation).
- **Presence** (online / typing) via WebSocket.
- **Real-time collaborative shared notes** use **Yjs (CRDT)** — the one Flow 11 deviation (DEVIATIONS.md); the Yjs doc syncs over the existing WebSocket transport and persists as a binary doc. Lecture editing remains non-CRDT TipTap (the deviation is scoped to group notes only).
- Each student's group interaction still feeds **their own** Cognitive DNA (Flow 9), tagged with group context; privacy #72 applies to what reaches teacher surfaces.
- **"Schedule Group Study"** entry point (the M-16 hook): opens this group-session scheduler pre-filled from a review's triggering students — satisfies the Flow 7 / M-16 "Schedule Group Study" BLOCKED-HOOK.

### 3.4 Anonymised class comparison (#73)

```
   STUDENT view
       ↓ percentile rank within (same teacher + subject) cohort
   IF above average → "Top 35% of your Physics class"
   IF below average → show IMPROVEMENT TREND instead (never a negative rank)
       ↓ never identifies any other individual student
```

**Locked rules:**

- **Resolved placement: Flow 11** (was a "TODO confirm Flow 9/11" — Flow 9 produces the ranking data; Flow 11 renders this student-facing view).
- Percentile rank within the same teacher+subject cohort; **shown only when above average**; below-average students see their **own improvement trend**, never a negative rank, never another student's identity.
- School-tenant (needs a class cohort); independent students get a self-improvement trend only.

### 3.5 Teacher dashboard (#104)

```
   TEACHER_DASHBOARD (composes existing data — builds no new metrics)
       ├─ at-risk student cards     (FIRST; from Flow 9 pass-prob/DNA)
       ├─ 6-week lecture-quality trend  (reuses #35 timeline / #38 metrics, M-10)
       ├─ AI-suggested groups        (#101)
       ├─ pending next-day reviews   (Flow 7)
       └─ Teaching Innovation Record summary (#36, M-10)
```

**Locked rules:**

- **Composes** existing data — at-risk from Flow 9, quality trend from M-10 #35/#38, groups from #101, reviews from Flow 7, Innovation Record from M-10 #36. **Does not rebuild the #38 admin comparative table** (that stays the M-10 T-139 build); #104 is the teacher's own action-oriented view.
- At-risk students surfaced **first**.
- School teachers only.

### 3.6 Student Learning Record (#105 — student core)

```
   STUDENT_LEARNING_RECORD (own complete journey)
       topic progress · pass-probability gauge · exam confidence · saved highlights ·
       mistake history · cognitive DNA card · retention rates
```

**Locked rules:**

- The **student-facing** complete record, composed from Flow 9 (pass-prob #85, exam confidence #87, mistakes #81, DNA #83, retention #98) + Flow 6 highlights + topic progress.
- The **parent view** of this same data is Flow 10 (sibling surface, both read Flow 9 — no inter-dependency).
- Both tenants (independent students see their own record; no class-relative framing beyond #73's self-trend).

### 3.7 Admin + Coordinator dashboards (#106)

```
   ADMIN_DASHBOARD (scope per §6.19)
       ├─ platform adoption (DAU/WAU)
       ├─ lecture-quality trends      (aggregate of M-10 metrics)
       ├─ geographic heatmap          (which schools/districts struggle with which topics — ECharts)
       └─ composite platform-health score
   COORDINATOR → cross-subject aggregates for their schools
```

**Locked rules:**

- **Admin** (School/District/Platform, scope-restricted per §6.19) sees adoption, quality trends, the **geographic heatmap** (ECharts — STACK_LOCK §2 "heatmaps/complex viz"), and a composite health score. **Coordinator** sees cross-subject aggregates for their schools.
- Composes existing aggregates (M-10 #38, Flow 9 aggregates, activity events) — no new underlying metrics; **does not duplicate** the #38 comparative table, links to it.
- Migrated alumni (Flow 2 graduation) appear in **"Migrated" status with anonymized names** in school dashboards.
- Aggregate-anonymous; #72 inviolate at the individual level.

---

## 4. Permissions matrix

| Action | Student | Teacher | Coordinator | School/District/Plat Admin |
|---|---|---|---|---|
| Create student group (#102) | ✓ | — | — | — |
| Confirm AI-suggested group (#101) | — | ✓ (own) | — | — |
| View student groups | own | view-only (own students) | — | — |
| Group shared/private threads (#103) | own + shared | — | — | — |
| See own Learning Record (#105) | ✓ | — | — | — |
| Class comparison (#73) | own (above-avg only) | — | — | — |
| Teacher dashboard (#104) | — | ✓ (own) | — | — |
| Admin/Coordinator dashboard (#106) | — | — | ✓ (own schools) | ✓ (scope per §6.19) |

## 5. Edge cases

- Group with one member / all left → session ends gracefully; notes preserved.
- Below-average student → #73 shows improvement trend, never a rank.
- AI-suggested group the teacher dismisses → not recreated that day; re-suggested only on material change.
- Independent student → no #101, no teacher view, no class cohort (#73 = self-trend only).
- Concurrent note edits → Yjs CRDT resolves conflict-free; offline edits merge on reconnect.
- Migrated alumnus appears anonymized in dashboards; their group history is severed with the tenant move.

## 6. Limits

- Group size: a sane cap (e.g. 8) to keep shared-thread + presence performant (launch rec).
- #73 shown only above average; never a negative rank; never another student's identity.
- Dashboards compose cached aggregates (1hr cache, reusing M-10 pattern); no live per-keystroke recompute.
- Yjs CRDT scoped to group notes only — never lecture editing.
- Group-suggestion job caps suggestions per teacher per day.

## 7. Notifications

- `groups.suggested` (teacher, #101), `groups.invite` (student-created join, #102), `groups.session_starting`.
- `dashboards.*` are pull (viewed), not push.
- Group interaction events ride the existing NATS pipeline (`mode=group`) → Flow 9.

## 8. Open questions

(All built to launch recommendations per standing instruction.)
- **Q1 — #73 placement.** **Resolved: Flow 11** (render), Flow 9 produces ranking data.
- **Q2 — collaborative-notes mechanism.** **Resolved: Yjs (CRDT)** for group notes, scoped deviation; threads/presence stay plain WebSocket.
- **Q3 — group size cap.** Rec: 8. **Adopted.**
- **Q4 — #104/#106 vs M-10 #38 overlap.** **Resolved:** Flow 11 composes/links the M-10 #38 table; does not rebuild it.

## 9. Out of scope (for now)

- **New prediction/DNA metrics** — Flow 9 owns; Flow 11 only renders.
- **Rebuilding the #38 admin comparative table** — stays the M-10 T-139 build; #106 links to it.
- **Parent view of #105** — Flow 10.
- **Virtual-assistant surfacing of dashboards/groups** — Flow 12 (reads Flow 11 output; not a Flow 11 concern).
- **CRDT for lecture editing** — explicitly excluded; Yjs is group-notes only.

## 10. Related ARCHITECTURE sections

§2 frontend (ECharts heatmaps, Yjs deviation), §213 real-time (FastAPI WebSocket + Redis pub/sub), §7.21 (cross-grade group rules), §9 (`groups` namespace; `mode=group` events), §10 (daily group-suggestion job; dashboard aggregate refresh), §4 (`study_groups`, `group_members`, `group_threads`, `group_notes`), §6.19 (role-scoped dashboard visibility), Flow 9 (data source), Flow 5/M-10 #35/#36/#38 (composed metrics), §13 (i18n), STACK_LOCK §2 + DEVIATIONS.md (Yjs).

## 11. Data model sketch

```
# Both schemas (group study works for both tenants; dashboards school-scoped):
study_groups        id, tenant_type, created_by[teacher|student], mode[lecture,reference],
                    lecture_id(nullable), name, invite_token, source[ai_suggested,student_created], created_at
group_members       group_id, student_user_id, joined_at
group_threads       id, group_id, type[shared,private], owner_user_id(nullable for shared), created_at
group_messages      id, thread_id, sender_user_id, body, created_at
group_notes         id, group_id, yjs_doc (bytea — CRDT state), updated_at
# dashboards read existing tables (Flow 9 predictions/cognitive_dna, M-10 benchmarks, activity events) — no new metric tables
```

## 12. Acceptance criteria

1. Daily AI group suggestions (mixed / all-weak) from Flow 9 data; teacher confirms (#101); school-only.
2. Students create groups via invite link, both modes, teacher view-only (#102).
3. Group session: shared + private threads + presence (WebSocket) + real-time collaborative notes (Yjs CRDT) (#103); "Schedule Group Study" from a review opens it pre-filled (M-16 hook).
4. Class comparison shows above-average rank or self-improvement trend, never a negative rank or another student's identity (#73).
5. Teacher dashboard composes at-risk-first + quality trend + suggested groups + pending reviews + Innovation Record — no #38 rebuild (#104).
6. Student Learning Record composed from Flow 9 + highlights (#105 student core); parent view is Flow 10.
7. Admin/Coordinator dashboards: adoption + quality trends + ECharts geographic heatmap + health score, scope-restricted per §6.19; migrated alumni anonymized (#106).
8. Group events feed Flow 9 (mode=group); #72 inviolate; both tenants where applicable; i18n (en/ur/sd/ps, RTL).

---

## Milestone split (M-20 family)

- **M-20a — Group Study** (#101, #102, #103 + the M-16 "Schedule Group Study" scheduler). Includes the Yjs deviation for #103 notes. Depends on M-18b/c (Flow 9 performance data for #101) + Flow 6/8 session components.
- **M-20b — Dashboards** (#73, #104, #105, #106). Composes Flow 9 + M-10 #38/#35/#36 + activity aggregates. Depends on M-18b/c + M-10 T-139.

Order a → b. Ticket ranges assigned off M-19's last ticket at draft time.

## Drafting completeness ledger

**v2 features covered (7):** #73, #101, #102, #103, #104, #105 (student core), #106. (#105 parent-view = Flow 10.)

**BLOCKED-HOOKs consumed (satisfied):**
- M-16 T-205 "Schedule Group Study" scheduler → §3.3 / M-20a
- Flow 9 (M-18) DNA aggregate dashboards + class comparison #73 + student learning record #105 → §3.4/§3.5/§3.6/§3.7 / M-20b
- Flow 9 (M-18) AI-suggested study groups #101 consume DNA/performance → §3.1 / M-20a

**Cross-flow assertions honored:** analytics event store read by Flow 11 (Flow 6/M-14); ADMIN class/district DNA aggregates rendered here (Flow 9); migrated alumni "Migrated" status anonymized (Flow 2); Coordinator/School-Admin class aggregates (Flow 9); #105 student core here / parent view Flow 10.

**Consistency items resolved:** #73 placement → Flow 11 (fixed the flow-8 "TODO confirm placement" line); #104/#106 vs M-10 #38 → compose/link, don't rebuild; collaborative-notes mechanism → Yjs CRDT (DEVIATIONS.md + STACK_LOCK §2 row added, scoped to group notes).

**New BLOCKED-HOOKs deferred onward:** none. (All dependencies are on drafted/done flows: Flow 9, Flow 5/6/7/8, M-10. Flow 12 reads Flow 11 output but is not a Flow 11 dependency.)

**Stack deviation introduced:** Yjs (CRDT) for `group_notes` only — DEVIATIONS.md entry + STACK_LOCK §2 row; lecture editing stays non-CRDT TipTap.
