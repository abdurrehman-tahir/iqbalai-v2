# Roadmap — Milestone Overview

**Status:** Living document
**Owner:** @abdurrehman-tahir
**Purpose:** High-level milestone sequence with status. Hamza checks here first to know what to work on. Stakeholder communication (Mufti, Awais, CXO layer) happens at milestone granularity.

---

## Milestone summary table

**Status vocabulary** (implementation lifecycle): `blocked` (no spec) -> `drafted-spec` (flow spec only) -> `drafted` (backlog tickets written, not started) -> `in-progress` (some tickets done) -> `done` (all tickets done). The `in-progress`/`done` end is **auto-verified** by `scripts/check_ticket_status.py` rolling ticket states up to this column on every PR — do not hand-edit it out of sync with tickets.

| ID | Milestone | Layer | Tickets | Est. duration | Status | Demo deliverable |
|---|---|---|---|---|---|---|
| M-00 | Foundation: infra + containers + base code | 0 | T-001 to T-015 | ~1.5 weeks | done | All services run locally; smoke-test API returns 200 |
| M-01 | Platform Setup: Platform Admin + ToS + personas + langs | 1 | T-016 to T-027 | ~3-4 days | in-progress | Platform Admin logs in, configures personas, exam syllabi, languages |
| M-01a | Foundation Remediation + FE/Integration Enforcement | 1 | T-223 to T-237 | ~1 week | drafted | Nav reaches every page; ToS renders/scrolls; FE tests + typed client + model-first migrations enforced in CI |
| M-02 | School Onboarding: District + School + role hierarchy | 1 | T-028 to T-040 | ~3-4 days | drafted | Platform Admin creates a District, then School, then School Admin who logs in |
| M-03 | Subjects + Grade/Section/Subject offerings | 2 | T-041 to T-052 | ~2-3 days | drafted | School Admin creates Coordinator, Coordinator creates Grade/Section/Subjects, assigns Teacher |
| M-04 | Teacher Onboarding + Content Library (school-tier) | 2 | T-053 to T-068 | ~3-4 days | drafted | Teacher logs in, uploads curriculum, sees it ingest + appear in their library |
| M-05 | Independent Users: signup + Platform Library | 2 | T-069 to T-076 | ~2-3 days | drafted | Independent teacher self-signs up, accesses Platform Library |
| M-06 | Student Onboarding (school) + Parent Linking | 2 | T-077 to T-090 | ~3-4 days | drafted | Coordinator enrolls students into Grade-Section; parents link to children |
| M-07 | Exam Framework Engine (platform-tier) | 3 | T-091 to T-100 | ~3-4 days | drafted | Platform Admin triggers AI research; approves; students can select framework |
| M-08 | Student Mode + Diagnostic + Cognitive DNA seed | 3 | T-101 to T-112 | ~3-4 days | drafted | Student picks mode, takes diagnostic, cognitive DNA initialized |
| M-09 | Lecture Wizard + AI Generation (Pattern S RAG) | 4 | T-113 to T-128 | ~1.5 weeks | drafted | Teacher generates first lecture; sees streaming output with source badges |
| M-10 | Lecture Edit + Versions + 7-Dim Scoring | 4 | T-129 to T-140 | ~3-4 days | drafted | Teacher edits lecture; sees score timeline + Innovation Record suggestions |
| M-11 | Auto-quiz Per Student + Publish Lecture | 4 | T-141 to T-150 | ~2-3 days | drafted | Lecture publishes; auto-quizzes generate per student; students see quizzes |
| M-12 | Lecture Mode Viewer + Highlight + Q&A + Voice | 5 | T-151 to T-165 | ~1.5 weeks | drafted | Student opens lecture; voice-reads; highlights; asks questions w/ AI answers |
| M-13 | Hybrid Widget + Multimodal Image + Vision LLM | 5 | T-166 to T-172 | ~2-3 days | drafted | Student attaches image to question; gets vision-LLM answer |
| M-14 | Live Feedback Panel + NATS Event Pipeline + Adaptation | 5 | T-173 to T-184 | ~1 week | drafted | Live feedback updates; stuck nudge fires; AI adapts angle on repeat |
| M-15 | Flashcards + Concept Enrichment + Lecture Rating | 5 | T-185 to T-194 | ~2-3 days | drafted | Highlights become flashcards; concepts have career links; ratings flow to teacher |
| M-16 | Next-Day Review (Flow 7) | 6 | T-195 to T-208 | ~3-4 days | drafted | Teacher gets next-day review; publishes targeted mini-lecture |
| M-17 | Self-Study Mode (Flow 8) | 6 | T-209 to T-222 | ~3-4 days | drafted | Student builds study plan from prep book; adherence tracked |
| M-18a | AI Intelligence — Question Bank + Collection (Flow 9: #42,#43,#74-#76) | 6 | TBD (off T-222) | ~1 week | drafted-spec | Build-first foundation: bank, Bloom tags, unified queue |
| M-18b | AI Intelligence — Cognitive DNA engine (Flow 9: #77-#84) | 6 | TBD | ~1 week | drafted-spec | Signals, mistake tracking, DNA profile + role visibility |
| M-18c | AI Intelligence — Prediction + recommendations (Flow 9: #85-#93) | 6 | TBD | ~1 week | drafted-spec | Pass-prob, nightly recalc, 2-future, recovery (heuristic-first) |
| M-18d | AI Intelligence — Spaced repetition + pedagogy (Flow 9: #94-#99) | 6 | TBD | ~1 week | drafted-spec | FSRS scheduling, micro-revision, retention, weekly pedagogy |
| M-19 | Parent Monitoring (Flow 10: #100 + #105 parent-view) | 6 | TBD (off M-18d; deps M-18b/c + M-06 T-082) | ~2-3 days | drafted-spec | Read-only parent dashboard + proactive/mini-lecture/adherence alerts |
| M-20a | Group Study (Flow 11: #101,#102,#103 + Schedule-Group-Study) | 6 | TBD (off M-19; deps M-18b/c + Flow 6/8) | ~3-4 days | drafted-spec | AI-suggested + student groups; shared/private threads; Yjs collaborative notes |
| M-20b | Dashboards (Flow 11: #73,#104,#105-student,#106) | 6 | TBD (off M-20a; deps M-18b/c + M-10 T-139) | ~2-3 days | drafted-spec | Teacher/admin/coordinator dashboards + class comparison + learning record (compose, no #38 rebuild) |
| M-21a | AI Chatbot (Flow 12: #107) | 6 | TBD (off M-20b; deps RAG stack M-09/M-12 + §7.21) | ~2-3 days | drafted-spec | Floating always-available subject Q&A, role-scoped, source badges |
| M-21b | Virtual Assistant (Flow 12: #108) | 6 | TBD (off M-21a; deps M-18 + Flow 7/8/11 + M-21a) | ~3-4 days | drafted-spec | Proactive guide composing Flow 9/7/8/11 signals; suggest-and-confirm actions |
| M-22 | Promotion Workflow + Graduation Lifecycle | 6 | T-200 to T-208 | ~2-3 days | drafted | Coordinator initiates promotion; School Admin approves; Grade 12 student migrates |
| M-23 | Subscriptions schema-only + Platform Admin CRUD | 6 | T-209 to T-213 | ~1-2 days | drafted | Platform Admin creates tier definitions; District/School see "Coming soon" |

---

## Timeline view

**Estimate basis — Claude-Code velocity (tiered):** Hamza implements each ticket via Claude Code; his time = review + targeted debug/reimplement, not authoring. Heavy RAG/voice/ML milestones (M-00, M-09, M-12, M-14, M-18a-d) compressed ~2-3×; all other CRUD/UI milestones ~4×, vs the original hand-coding baseline. Re-tune as real throughput lands.

```
Q3 2026                                                            Q4 2026                                       Q1 2027
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
M-00 ████████████████ Foundation (~1.5w)
                      M-01 ████████████ Platform Setup (~3-4d)
                        M-01a ███████████ Foundation Remediation (~1w)
                                         M-02 ████████████ School Onboarding (~3-4d)
                                                            M-03 ████████ Subjects + GSO (~2-3d)
                                                                           M-04 ████████████ Teacher + Library (~3-4d)
                                                                                              M-05 ████████ Independent (~2-3d)
                                                                                                             M-06 ████████████ Students + Parents (~3-4d)
                                                                                                                                M-07 ████████████ Exam Framework (~3-4d)
                                                                                                                                                   M-08 ████████████ Mode + Diagnostic (~3-4d)
                                                                                                                                                                      M-09 ████████████████ Lecture Wizard + Gen (~1.5w)
                                                                                                                                                                                            M-10 ████████████ Edit + Versions (~3-4d)
                                                                                                                                                                                                              M-11 ████████ Quiz + Publish (~2-3d)
                                                                                                                                                                                                                             M-12 ████████████████ Mode Viewer + Q&A (~1.5w)
                                                                                                                                                                                                                                                    M-13 ████████ Multimodal (~2-3d)
                                                                                                                                                                                                                                                                   M-14 ████████████ Live Feedback (~1w)
                                                                                                                                                                                                                                                                                      M-15 ████████ Flashcards + Concepts (~2-3d)
                                                                                                                                                                                                                                                                                                     M-22 ████████ Promotion (~2-3d)
                                                                                                                                                                                                                                                                                                                    M-23 ████ Subscriptions (~1-2d)

(All 12 flows drafted. M-18a-d / M-19 / M-20a-b / M-21a-b are spec-ready (status drafted-spec) — milestone backlogs not yet written; ticket ranges assigned off T-222 at milestone-draft time, family order preserved.)
```

**Approximate total to launch-ready core:** ~2-3 months for M-00 through M-15 + M-22 + M-23 (Claude-Code velocity, tiered; was 7-9 months hand-coding).
**Milestones M-16 to M-21** add ~1-1.5 months → **full v2 launch ~3-4.5 months total** (was ~10-14 months hand-coding).

---

## Critical path

The longest dependency chain that gates demo-able product:

```
M-00 → M-01 → M-01a → M-02 → M-03 → M-04 → M-06 → M-08 → M-09 → M-11 → M-12
```

Everything else either layers atop this chain OR depends on it indirectly. Targeting M-12 (student studies a lecture) as the **first end-to-end demo milestone** — ~5-6 months in if Hamza maintains pace.

---

## Working order — what Hamza picks next

1. Pull latest `staging`
2. Read this ROADMAP — find current milestone (Status: in-progress) OR first todo milestone
3. Open that milestone file → tickets in order
4. Implement T-NNN → next → next
5. After all milestone tickets done → open ONE PR for entire milestone branch

If multiple milestones say `todo`, pick the lowest M-NN number unless blocked. Never skip a milestone for a later one unless the earlier one is BLOCKED.

---

## Blocked milestones — what unblocks them

| Milestone | Blocked on | How to unblock |
|---|---|---|
| M-16 Next-Day Review | flow-7-next-day-review.md DRAFTED (v1) | Unblocked — ready for backlog ticket drafting |
| M-17 Self-Study | flow-8-self-study.md DRAFTED (v1) | Unblocked — ready for backlog ticket drafting |
| M-18 Cognitive DNA | flow-9-ai-intelligence.md DRAFTED → split into M-18a/b/c/d | Draft milestone family a→d; ML heuristic-first (trained models Phase 2) |
| M-19 Parent Monitoring | flow-10-parent-monitoring.md DRAFTED | Draft + merge M-19 (single milestone; school-tenant at launch) |
| M-20 Group Study + Dashboards | flow-11-group-study-dashboards.md DRAFTED → M-20a (group study) + M-20b (dashboards) | Draft family a→b; Yjs deviation for #103 notes |
| M-21 Chatbot + VA | flow-12-chatbot-va.md DRAFTED → M-21a (chatbot) + M-21b (VA) | Draft family a→b; VA actions suggest-and-confirm only |

**Recommended parallel work:** While Hamza implements M-00 through M-09, Abd. + Awais draft Flows 7-12 in chat sessions. By the time M-15 ships (month ~6-7), Flows 7-12 are spec'd and M-16+ can begin.

---

## Update cadence

- **Per-ticket completion:** mark ticket status `done` in its milestone file (Hamza updates)
- **Per-milestone completion:** Hamza updates this ROADMAP table row (Status `done`, demo URL, merged PR)
- **Spec changes:** Abd. updates affected ticket cite refs + adjusts dependencies; Hamza pulls latest
- **New flow drafted:** Abd. + Claude unblock the corresponding milestone; backlog file populated

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-14 | Initial roadmap. 24 milestones defined; M-00 to M-15 + M-22 + M-23 ticket-ready; M-16 to M-21 blocked on flows 7-12. | @abdurrehman (with Claude) |
| 2026-05-29 | Inserted M-01a (Foundation Remediation + FE/Integration Enforcement) after M-01; M-02 depends on M-01a. Closes the FE-test / typed-client / migration-model-first / UX-acceptance enforcement gap that let M-00/M-01 ship broken nav + ToS. Gates land in CLAUDE.md + CI (inherited by M-02→M-17 without rewrite). | @abdurrehman (with Claude) |