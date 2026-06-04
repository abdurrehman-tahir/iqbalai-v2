# Flow 10 — Parent Monitoring

**Status:** drafted (v1)
**v2 doc features covered:** #100, #105 (parent-view portion; the student-facing Learning Record core is Flow 11)
**Related feature specs:** `flow-4-student-onboarding.md` (#10 parent account + child linking — the account + link are built there/M-06; Flow 10 is what a *linked* parent sees), `flow-9-ai-intelligence.md` (source of pass-probability #85, DNA #83, mistakes #81, retention #98, exam confidence #87 — Flow 10 reads these directly), `flow-7-next-day-review.md` (mini-lecture assignment → parent notification), `flow-8-self-study.md` (adherence miss → parent alert; #72 governs self-study visibility), `flow-1-platform-setup.md` (#12 notification inbox the parent alerts ride)

## Purpose

The read-only window a linked parent gets into their own child's learning, plus the alert system that proactively warns them when the child is at exam risk. Flow 10 builds **no new prediction or learning logic** — it renders Flow 9's outputs for a parent audience and routes the alert events the prior flows emit (proactive low-probability #100, mini-lecture assignment, adherence miss) to the linked parent through the existing notification inbox. The parent account, child-link, revocation, and the read-only access-state flag already exist (Flow 4 / M-06 T-082); Flow 10 consumes that gate.

**Tenant scope (resolved):** parent monitoring is **school-tenant only at launch**, consistent with M-06 ("parent linking to independent students not allowed at launch") and the graduation migration that auto-severs parent links. Independent-guardian linking is a documented future extension (same mechanism), **out of scope at launch** — an independent student with no linked parent simply gets no parent surface.

## Personas

- **Parent** — read-only view of their own child only; receives + configures alerts.
- **Student** — their data is the subject; #72 governs what self-study content a parent can see.
- **System (Celery)** — nightly escalation of unresolved proactive alerts.
- (Teacher / Coordinator / Admin have no role here — parent data is parent-and-child only.)

---

## 3. Lifecycle

### 3.1 Parent monitoring dashboard (#105 — parent view)

```
   PARENT logged in + LINKED (read-only access-state = LINKED, M-06 gate)
       ↓ selects a child (may have multiple)
   PARENT_DASHBOARD (read-only, own child only)
       ├─ topic progress
       ├─ pass-probability gauge        (from Flow 9 #85)
       ├─ exam confidence + countdown   (from Flow 9 #87 + exam date #52)
       ├─ cognitive DNA card            (from Flow 9 #83/#84, parent-appropriate framing)
       ├─ mistake history summary        (from Flow 9 #81, aggregate)
       ├─ retention overview            (from Flow 9 #98)
       └─ recent activity / adherence    (aggregate; self-study detail gated by #72)
```

**Locked rules:**

- Reads **Flow 9 outputs directly** (pass-prob, DNA, mistakes, retention, exam confidence) + the exam date (#52) + Flow 6 highlights — it does **not** depend on Flow 11's student-facing Learning Record component; both render the same underlying Flow 9 data for different audiences (no inter-flow dependency).
- **Read-only, own child only.** A parent never sees other students, never edits, never sees teacher-facing raw analytics beyond what's framed for parents.
- **#72 inviolate:** self-study question content is never exposed to a parent; only **aggregate** adherence/activity is shown (per Flow 8 §3.12 + Flow 6/7 locks).
- Cognitive DNA shown in the **positive, parent-appropriate** framing (#84), not the raw teacher view.
- Multi-child: a parent linked to several students switches between them; each is independently gated by its own link state.

### 3.2 Proactive parent alert (#100)

```
   NIGHTLY (Flow 9 emits the signal: pass_prob < 40% AND days_to_exam < 30)
       ↓ Flow 10 consumes
   GENERATE plain-language alert (LLM, §8.6 parent-alert prompt — supportive, not alarming)
       ↓ send to linked parent(s) via notification inbox (#12) + their chosen channels
   ALERTED
       ↓ if not improved by next nightly run
   ESCALATE → daily alerts until probability recovers or exam passes
```

**Locked rules:**

- **Flow 9 emits** the `pass_prob < 0.4 AND days_to_exam < 30` signal (ARCH Path C); **Flow 10 generates + sends** the parent alert — satisfies the Flow 9 #100 BLOCKED-HOOK.
- Alert copy is **plain-language, supportive** (LLM via §8.6), with the child's name, the concern, and a concrete next step — never raw probability jargon, never alarmist.
- **Escalation:** if the condition persists across nightly runs, escalate to **daily** alerts until the probability recovers or the exam date passes; de-escalate on recovery.
- Routes only to **linked** parents; a child with no linked parent → no alert (logged, no error).
- Both school students (linked parents) covered; independent guardians out of scope at launch.

### 3.3 Parent notification routing + preferences

```
   ALERT SOURCES (all route to the linked parent via inbox #12)
       ├─ proactive low-probability (#100, §3.2)
       ├─ mini-lecture assigned to child   (Flow 7 / M-16 emits)
       └─ adherence miss (2 consecutive)   (Flow 8 / M-17 emits)
       ↓ per-parent preferences
   PARENT_SETTINGS (channel: push/email/SMS; per-alert-type on/off; default ON)
```

**Locked rules:**

- One unified parent-notification surface consuming three event sources — satisfies the **M-16** (mini-lecture assignment) and **M-17** (adherence miss) parent-notification hooks, plus #100.
- Per-parent preferences: channel choice (push/email/SMS via the Flow 8 #68 channels) + per-alert-type toggle; **default ON** (parent may disable any type, per Flow 8 §3.10).
- Mini-lecture / adherence notifications are **read-only informational** (parent can't act on the child's behalf) — they mirror what the student received.
- Independent students with a (future) linked guardian use the same mechanism; none linked → no routing.

### 3.4 Access gating + revocation

**Locked rules:**

- The **read-only access-state flag** (LINKED / UNLINKED) built in M-06 T-082 is the gate — Flow 10 surfaces are visible only while LINKED.
- **Revocation is immediate** from either side (M-06): on revoke, the parent instantly loses dashboard access + alert routing; link history preserved for audit.
- **Graduation:** when a final-grade student auto-migrates to the independent tenant (M-06), parent links are auto-severed → the parent surface goes dark for that child (expected, not an error).

---

## 4. Permissions matrix

| Action | Parent (linked) | Parent (unlinked) | Student | Teacher/Coordinator/Admin |
|---|---|---|---|---|
| View own child's dashboard | ✓ read-only | — | own (via Flow 11) | — |
| View another child | — | — | — | — |
| See child's self-study question content | — (aggregate only, #72) | — | own | per #72 / role |
| Receive child alerts | ✓ (configurable) | — | — | — |
| Configure alert preferences | ✓ | — | — | — |
| Edit any child data | — | — | — | per role |

## 5. Edge cases

- Multiple parents on one child → each independently linked + configured; both alerted.
- Parent linked mid-crisis (child already <40%) → next nightly run alerts them; no backfill of past alerts.
- Link revoked during an active escalation → routing stops immediately.
- Child has no exam date set → no pass-probability, so no #100 alert (dashboard still shows progress).
- Child migrated to independent (graduation) → link severed, surface goes dark with an explanatory message.
- No linked parent → all parent routing silently no-ops.

## 6. Limits

- Read-only throughout — Flow 10 creates no student-affecting writes (only parent preferences + alert records).
- Proactive alert escalation capped at once-daily (no spam).
- Parent sees aggregate self-study activity only — never individual self-study question text (#72).
- School-tenant only at launch.

## 7. Notifications

- `parent.proactive_alert` (#100, escalating), `parent.mini_lecture_assigned` (mirrors Flow 7), `parent.adherence_miss` (mirrors Flow 8) — all via the #12 inbox + chosen channels, respecting per-parent preferences.
- No `system`-namespace alerts originate here.

## 8. Open questions

(All built to launch recommendations per standing instruction.)
- **Q1 — escalation cadence.** Rec: daily after the first unresolved nightly trigger; de-escalate on recovery. **Adopted.**
- **Q2 — independent-guardian linking.** Rec: out of scope at launch (M-06 disallows independent parent links); revisit when independent onboarding adds a guardian step. **Adopted (deferred).**
- **Q3 — how much DNA detail a parent sees.** Rec: positive-framed DNA card only (not raw teacher dimensions). **Adopted.**

## 9. Out of scope (for now)

- **Independent-guardian linking** — future; school-tenant only at launch.
- **Student-facing Learning Record (#105 core)** — Flow 11 / M-20 (Flow 10 renders the parent view of the same Flow 9 data).
- **Parent-initiated actions on the child's behalf** — none; Flow 10 is read-only + alerts.
- **Any new prediction/DNA logic** — owned by Flow 9; Flow 10 only reads it.

## 10. Related ARCHITECTURE sections

§C Path C (nightly low-probability trigger source), §9 / §9.21 (`parent` namespace), §12 (#12 notification inbox), §6.19 (parent read-only permissions; own-child gate), §4 (`parent_alert_preferences`, `parent_alerts`), M-06 T-082 (read-only access-state flag), §3.16 (school-tenant), §13 (i18n; parent-facing copy in en/ur/sd/ps), Flow 9 (data source).

## 11. Data model sketch

```
# school schema (parent monitoring is school-tenant at launch):

parent_alert_preferences   parent_user_id, child_user_id, push_enabled, email_enabled, sms_enabled,
                           proactive_enabled(default true), mini_lecture_enabled(default true),
                           adherence_enabled(default true), updated_at
parent_alerts              id, parent_user_id, child_user_id, alert_type[proactive,mini_lecture,adherence],
                           body, escalation_level, sent_at, resolved_at
# (parent_link / read-only access-state already exists from M-06 T-082)
```

## 12. Acceptance criteria

1. Linked parent sees a read-only dashboard of their own child only: topic progress, pass-prob gauge, exam confidence + countdown, positive DNA card, aggregate mistakes/retention/activity — all sourced from Flow 9 (#105 parent view).
2. #72 inviolate: parent never sees individual self-study question content, only aggregate activity.
3. Proactive alert (#100): nightly pass_prob<40% & days<30 → plain-language LLM alert to linked parent(s); escalates daily until recovery/exam; de-escalates on recovery.
4. Unified parent notifications route proactive + mini-lecture + adherence events (satisfies the M-16/M-17/Flow-9 hooks); per-parent channel + per-type preferences, default ON.
5. Read-only access-state flag (M-06) gates all surfaces; revocation immediate; graduation severs the link and darkens the surface.
6. Multi-parent / multi-child handled; no exam date → no #100; no linked parent → silent no-op.
7. School-tenant only at launch; i18n (en/ur/sd/ps, RTL); parent copy supportive, never alarmist.

---

## Milestone mapping

Flow 10 is small (2 features, mostly rendering + routing over existing infra) → a **single M-19** (no family). Ticket range assigned off the last M-18d ticket at draft time. **M-19 depends on M-18b/c** (DNA + pass-probability must exist) and M-06 T-082 (parent-link gate).

## Drafting completeness ledger

**v2 features covered (2):** #100; #105 (parent-view portion — student-record core is Flow 11). #10 parent account/linking = Flow 4/M-06 (not re-claimed here).

**BLOCKED-HOOKs consumed (satisfied):**
- M-06 T-082 parent read-only monitoring surface → §3.1 / §3.4
- M-16 T-204 parent notification on mini-lecture assignment → §3.3
- M-17 T-219 parent adherence alert (2 misses) → §3.3
- Flow 9 (M-18c) proactive parent alert #100 (low-probability signal) → §3.2

**Cross-flow assertions honored:** parent read-only own-child via Flow 10 (Flow 8); parent dashboard/view lives in Flow 10; aggregate-only self-study (no individual content, #72); alert configurable default-ON (Flow 8); both-tenant routing mechanism noted, school-only at launch.

**New BLOCKED-HOOKs deferred onward:** none. (The #105 student-record core is a sibling Flow 11 surface reading the same Flow 9 data, not a Flow 10 dependency — no forward hook.)

**Resolved consistency item:** M-06 "no independent parent links at launch" vs Flow 8 "independent guardian" → Flow 10 locked to **school-tenant at launch**; independent-guardian linking documented as future (§9).
