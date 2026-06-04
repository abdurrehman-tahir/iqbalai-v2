# Flow 12 — AI Chatbot + Virtual Assistant

**Status:** drafted (v1)
**v2 doc features covered:** #107, #108
**Related feature specs:** `flow-5-teacher-creates-lecture.md` / `flow-6-student-studies-lecture.md` / `flow-8-self-study.md` (the RAG stack + hybrid widget #57 + retrieval patterns the chatbot reuses), `flow-9-ai-intelligence.md` (revision-due #94/#95, pass-probability #85, 3 actions #91, at-risk signals the VA surfaces), `flow-7-next-day-review.md` (pending reviews the VA surfaces to teachers), `flow-11-group-study-dashboards.md` (at-risk / dashboard signals the VA surfaces), `flow-1-platform-setup.md` (#12 notification inbox)

## Purpose

The final flow — the conversational + proactive surface over everything else. **#107 Chatbot:** a floating, always-available tutor any user can open from any screen to ask about any subject, answered from the curriculum + their accessible materials with source badges. **#108 Virtual Assistant:** the proactive counterpart — instead of waiting for a question, it watches each user's history and surfaces what they need next ("revision due, pass probability dropped 3%, here are 3 actions"), and can **draft actions on the user's behalf for confirmation**. Flow 12 builds **no new intelligence or retrieval** — the chatbot reuses the existing RAG stack; the VA **composes** signals Flow 9/7/8/11 already produce. It is presentation + orchestration, nothing more.

**Two milestones:** **M-21a Chatbot** (#107 — self-contained RAG surface) and **M-21b Virtual Assistant** (#108 — proactive aggregator + action-drafting). Order a → b (the VA reuses the chatbot's conversational surface).

**CXO action rule (locked):** the VA **suggests and drafts; it never acts autonomously.** Every action it can take on a user's behalf (schedule revision, open recovery mode, draft a message, adjust a plan) requires explicit user confirmation — consistent with the platform-wide suggest-and-approve rule.

## Personas

- **Student** — opens the chatbot for subject Q&A; receives proactive VA nudges (revision, pass-prob, actions).
- **Teacher** — chatbot for subject/teaching questions; VA surfaces at-risk students, pending reviews.
- **Coordinator / Admin** — chatbot scoped to their data; VA surfaces role-relevant summaries.
- **System (Celery)** — VA proactive triggers (morning digest, revision-due, probability-drop).

Both tenants. Independent students get the chatbot + VA scoped to their own pool/exam-syllabus (no teacher/class signals).

---

## 3. Lifecycle

### 3.1 AI Chatbot — always-available subject Q&A (#107)

```
   FLOATING BUTTON (every screen)
       ↓ any user opens, any time
   CHATBOT (hybrid widget #57 — text / voice / image)
       ↓ question (not tied to a specific lecture)
   RAG over the user's accessible scope:
       student → curriculum (§7.21 overlay) + personal pool (Pattern P) + reference books
       teacher → curriculum + school library
       ↓ answer with SOURCE BADGES (which book/lecture/page)
   CONTINUOUS conversation (follow-ups keep context)
```

**Locked rules:**

- **Standalone + always-available** — a floating button on every screen; not tied to a lecture or session. Opens the hybrid widget #57 (text/voice/image).
- **Reuses the existing RAG stack** — no new retrieval. Scope is **role + tenant scoped**: a student gets their curriculum overlay (§7.21) + personal pool (Pattern P) + accessible reference books; a teacher gets curriculum + school library; admins get their data. Never returns content outside the user's access scope.
- **Source badges** on every answer (which lecture/book/page), like the in-lecture Q&A.
- **Continuous conversation** — follow-ups retain context within a session.
- Interactions emit NATS events (`mode=chatbot`) → Flow 9 (feeds DNA like any other Q&A), respecting #72.
- Both tenants; independent students scoped to their own pool + exam syllabus (no curriculum/class data).

### 3.2 Virtual Assistant — proactive personalised guide (#108)

```
   TRIGGERS (Celery + event-driven — composes EXISTING signals, creates none)
       ├─ morning digest                  (daily, per user)
       ├─ revision due / forgetting-curve  (Flow 9 #94/#95)
       ├─ pass-probability drop            (Flow 9 #85/#86)
       ├─ pending next-day reviews         (Flow 7, teachers)
       └─ at-risk students                 (Flow 9 / Flow 11, teachers)
       ↓ personalise from va_memory + full history
   PROACTIVE MESSAGE
       student: "Physics revision due — about to forget electromagnetic induction;
                 pass probability −3% yesterday. Here are 3 actions." (Flow 9 #91)
       teacher: "3 students struggle with diagram 4 in your Newton lecture."
       ↓ may include DRAFTED ACTIONS
   SUGGEST + CONFIRM  (schedule revision / open recovery / draft message / adjust plan)
       ↓ user confirms → action executes via the owning flow
```

**Locked rules:**

- **Proactive, not reactive** (the distinction from #107): the VA watches each user's full history and surfaces what they need **without being asked**.
- **Composes existing signals** — revision-due (Flow 9 #94/#95), probability drop (Flow 9 #85/#86), 3 actions (Flow 9 #91), pending reviews (Flow 7), at-risk (Flow 9/11). The VA **creates no new intelligence**; it personalises + bundles what those flows emit.
- **`va_memory`** (`user_id, key, value, updated_at`) stores per-user preferences + state (what's been surfaced, snooze, tone) so the VA doesn't repeat or nag.
- **Actions are suggest-and-confirm** (CXO rule): the VA may *draft* an action (schedule a revision, open Recovery Mode #93, draft a parent/teacher message, tweak a study plan) but **executes only after explicit user confirmation**, and the action runs through the owning flow (never a VA-private side effect).
- Frequency-capped + snoozable (no nagging); respects the user's notification preferences (#12 + Flow 8 #68 channels).
- Both tenants; teacher-facing VA is school-only (independent students have no teacher signals).

---

## 4. Permissions matrix

| Action | Student | Teacher | Coordinator/Admin |
|---|---|---|---|
| Open chatbot (own scope) | ✓ | ✓ | ✓ (own data) |
| Chatbot returns out-of-scope content | — | — | — |
| Receive VA proactive guidance | ✓ (own) | ✓ (own students) | ✓ (role summaries) |
| VA executes an action | only after own confirmation | only after own confirmation | only after own confirmation |
| VA acts autonomously | — | — | — |

- Chatbot + VA are strictly **scoped to what the user may already access**; they never widen a user's data reach. #72 inviolate (a VA never surfaces a student's private self-study content to a teacher).

## 5. Edge cases

- Chatbot question outside the user's scope → "I can only answer from your available materials" (no leakage).
- VA with no signals for a user (new account) → light onboarding nudges only, no fabricated urgency.
- VA action draft the user ignores → no execution; re-surfaced per frequency cap, then dropped.
- Voice/image chatbot input reuses the #57 widget paths (vision via §8.22).
- Independent student → VA surfaces only own-pool/exam signals (no class/teacher data).
- User snoozes VA → respected via `va_memory`; nothing fires until snooze expires.

## 6. Limits

- Chatbot strictly role+tenant scoped; never out-of-scope retrieval.
- VA composes existing signals only — no new prediction/retrieval logic here.
- VA actions: suggest-and-confirm only; never autonomous; always routed through the owning flow.
- VA frequency-capped + snoozable; respects notification preferences.
- Chatbot cost: per-message LLM cost; reuses existing RAG cost controls.

## 7. Notifications

- `assistant.proactive` (VA nudges — digest, revision, probability, reviews, at-risk), routed via #12 inbox + chosen channels, frequency-capped.
- Chatbot itself is in-app (no push); VA is the push surface.

## 8. Open questions

(All built to launch recommendations per standing instruction.)
- **Q1 — VA proactive frequency.** Rec: one morning digest + event-driven urgent nudges (probability drop, revision due), capped at a sane daily max; snoozable. **Adopted.**
- **Q2 — VA action autonomy.** **Resolved: suggest-and-confirm only**, never autonomous (CXO rule).
- **Q3 — chatbot scope for admins.** Rec: scoped to the data their role can already access. **Adopted.**

## 9. Out of scope (for now)

- **Any new RAG/retrieval** — chatbot reuses the existing stack.
- **Any new intelligence/prediction** — VA composes Flow 9/7/8/11 outputs; it owns none.
- **Autonomous actions** — explicitly excluded; suggest-and-confirm only.
- **Cross-user data access** — chatbot/VA never widen a user's existing scope.

## 10. Related ARCHITECTURE sections

§7 / §7.21 (RAG retrieval patterns + curriculum overlay the chatbot reuses), §8.6 (chatbot + VA typed prompts), §8.22 (vision for image questions), §9 (`assistant` namespace; `mode=chatbot` events), §10 (Celery VA triggers: morning digest, revision-due, probability-drop), §4 (`va_memory`, `chatbot_conversations`), §6.19 (role-scoped access), §12 (#12 inbox; hybrid widget #57), §13 (i18n), Flow 9/7/8/11 (signal sources).

## 11. Data model sketch

```
# Both schemas (tenant-routed):
chatbot_conversations  id, tenant_type, user_id, started_at
chatbot_messages       id, conversation_id, sender[user,ai], body, source_refs_jsonb, created_at
va_memory              user_id, key, value, updated_at        # prefs/state/snooze (per #108)
va_surfaced_log        id, user_id, signal_type, surfaced_at, acted[bool], action_ref  # frequency cap + no-repeat
# VA reads existing tables (Flow 9 predictions/cognitive_dna, Flow 7 reviews, Flow 8 plans) — no new signal tables
```

## 12. Acceptance criteria

1. Floating chatbot on every screen; any user, any subject, any time; hybrid widget #57 (text/voice/image) (#107).
2. Chatbot answers from the user's accessible scope only (role+tenant), with source badges; continuous conversation; never out-of-scope content.
3. Chatbot interactions feed Flow 9 (`mode=chatbot`), respecting #72.
4. VA proactively surfaces composed signals — revision due, probability drop + 3 actions (students), at-risk + pending reviews (teachers) (#108).
5. VA personalises via `va_memory`; frequency-capped + snoozable; respects notification prefs.
6. VA drafts actions but executes only after explicit user confirmation, routed through the owning flow — never autonomous.
7. Both tenants (teacher-facing VA school-only); independent users scoped to own data; i18n (en/ur/sd/ps, RTL).

---

## Milestone split (M-21 family)

- **M-21a — AI Chatbot** (#107). Self-contained RAG surface reusing the existing retrieval stack + widget #57. Depends on the RAG stack (Flow 5/6 — M-09/M-12) + §7.21 overlay.
- **M-21b — Virtual Assistant** (#108). Proactive aggregator + `va_memory` + suggest-and-confirm action drafting. Depends on M-18 (Flow 9 signals), Flow 7/8/11 outputs, and M-21a (reuses the conversational surface).

Order a → b. Ticket ranges assigned off M-20b's last ticket at draft time.

## Drafting completeness ledger

**v2 features covered (2):** #107, #108. **This completes the full v2 feature set** (1-108 minus retired #19/#20/#22; #50 label-fixed onto Flow 6).

**BLOCKED-HOOKs consumed:** none — no flow or milestone ever deferred work to Flow 12 (it is a pure downstream surface).

**Cross-flow assertions honored:** Flow 11's note that the VA surfaces dashboard/group output (Flow 12 reads Flow 11, not vice-versa) — honored as a read-only composition; the chatbot reuses the RAG stack; the VA composes Flow 9/7/8/11 signals without owning any.

**New BLOCKED-HOOKs deferred onward:** none. Flow 12 is the terminal flow — all dependencies are on drafted/done flows; it defers nothing.

**CXO rule anchored:** VA actions are suggest-and-confirm only, never autonomous (§3.2, §6, Q2).
