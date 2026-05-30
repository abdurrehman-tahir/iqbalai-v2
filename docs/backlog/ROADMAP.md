# Roadmap — Milestone Overview

**Status:** Living document
**Owner:** @abdurrehman-tahir
**Purpose:** High-level milestone sequence with status. Hamza checks here first to know what to work on. Stakeholder communication (Mufti, Awais, CXO layer) happens at milestone granularity.

---

## Milestone summary table

| ID | Milestone | Layer | Tickets | Est. duration | Status | Demo deliverable |
|---|---|---|---|---|---|---|
| M-00 | Foundation: infra + containers + base code | 0 | T-001 to T-015 | 3-4 weeks | todo | All services run locally; smoke-test API returns 200 |
| M-01 | Platform Setup: Platform Admin + ToS + personas + langs | 1 | T-016 to T-027 | 2-3 weeks | todo | Platform Admin logs in, configures personas, exam syllabi, languages |
| M-02 | School Onboarding: District + School + role hierarchy | 1 | T-028 to T-040 | 2-3 weeks | todo | Platform Admin creates a District, then School, then School Admin who logs in |
| M-03 | Subjects + Grade/Section/Subject offerings | 2 | T-041 to T-052 | 2 weeks | drafted | School Admin creates Coordinator, Coordinator creates Grade/Section/Subjects, assigns Teacher |
| M-04 | Teacher Onboarding + Content Library (school-tier) | 2 | T-053 to T-068 | 2-3 weeks | drafted | Teacher logs in, uploads curriculum, sees it ingest + appear in their library |
| M-05 | Independent Users: signup + Platform Library | 2 | T-069 to T-076 | 2 weeks | drafted | Independent teacher self-signs up, accesses Platform Library |
| M-06 | Student Onboarding (school) + Parent Linking | 2 | T-077 to T-090 | 2-3 weeks | drafted | Coordinator enrolls students into Grade-Section; parents link to children |
| M-07 | Exam Framework Engine (platform-tier) | 3 | T-091 to T-100 | 2-3 weeks | drafted | Platform Admin triggers AI research; approves; students can select framework |
| M-08 | Student Mode + Diagnostic + Cognitive DNA seed | 3 | T-101 to T-112 | 2-3 weeks | drafted | Student picks mode, takes diagnostic, cognitive DNA initialized |
| M-09 | Lecture Wizard + AI Generation (Pattern S RAG) | 4 | T-113 to T-128 | 3-4 weeks | drafted | Teacher generates first lecture; sees streaming output with source badges |
| M-10 | Lecture Edit + Versions + 7-Dim Scoring | 4 | T-129 to T-140 | 2-3 weeks | drafted | Teacher edits lecture; sees score timeline + Innovation Record suggestions |
| M-11 | Auto-quiz Per Student + Publish Lecture | 4 | T-141 to T-150 | 2 weeks | drafted | Lecture publishes; auto-quizzes generate per student; students see quizzes |
| M-12 | Lecture Mode Viewer + Highlight + Q&A + Voice | 5 | T-151 to T-165 | 3-4 weeks | todo | Student opens lecture; voice-reads; highlights; asks questions w/ AI answers |
| M-13 | Hybrid Widget + Multimodal Image + Vision LLM | 5 | T-166 to T-172 | 2 weeks | todo | Student attaches image to question; gets vision-LLM answer |
| M-14 | Live Feedback Panel + NATS Event Pipeline + Adaptation | 5 | T-173 to T-184 | 2-3 weeks | todo | Live feedback updates; stuck nudge fires; AI adapts angle on repeat |
| M-15 | Flashcards + Concept Enrichment + Lecture Rating | 5 | T-185 to T-194 | 2 weeks | todo | Highlights become flashcards; concepts have career links; ratings flow to teacher |
| M-16 | Next-Day Review (Flow 7) | 6 | (unblocked — flow-7 drafted; tickets TBD) | ~2-3 weeks | todo | Teacher gets next-day review; publishes targeted mini-lecture |
| M-17 | Self-Study Mode (Flow 8) | 6 | (unblocked — flow-8 drafted; tickets TBD) | ~2-3 weeks | todo | Student builds study plan from prep book; adherence tracked |
| M-18 | AI Intelligence Layer / Cognitive DNA (Flow 9) | 6 | (BLOCKED — needs flow-9) | TBD | blocked | (TBD per flow-9 spec) |
| M-19 | Parent Monitoring (Flow 10) | 6 | (BLOCKED — needs flow-10) | TBD | blocked | (TBD per flow-10 spec) |
| M-20 | Group Study + Dashboards (Flow 11) | 6 | (BLOCKED — needs flow-11) | TBD | blocked | (TBD per flow-11 spec) |
| M-21 | Chatbot + Virtual Assistant (Flow 12) | 6 | (BLOCKED — needs flow-12) | TBD | blocked | (TBD per flow-12 spec) |
| M-22 | Promotion Workflow + Graduation Lifecycle | 6 | T-200 to T-208 | 2 weeks | todo | Coordinator initiates promotion; School Admin approves; Grade 12 student migrates |
| M-23 | Subscriptions schema-only + Platform Admin CRUD | 6 | T-209 to T-213 | 1 week | todo | Platform Admin creates tier definitions; District/School see "Coming soon" |

---

## Timeline view

```
Q3 2026                                                            Q4 2026                                       Q1 2027
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
M-00 ████████████████ Foundation (3-4w)
                      M-01 ████████████ Platform Setup (2-3w)
                                         M-02 ████████████ School Onboarding (2-3w)
                                                            M-03 ████████ Subjects + GSO (2w)
                                                                           M-04 ████████████ Teacher + Library (2-3w)
                                                                                              M-05 ████████ Independent (2w)
                                                                                                             M-06 ████████████ Students + Parents (2-3w)
                                                                                                                                M-07 ████████████ Exam Framework (2-3w)
                                                                                                                                                   M-08 ████████████ Mode + Diagnostic (2-3w)
                                                                                                                                                                      M-09 ████████████████ Lecture Wizard + Gen (3-4w)
                                                                                                                                                                                            M-10 ████████████ Edit + Versions (2-3w)
                                                                                                                                                                                                              M-11 ████████ Quiz + Publish (2w)
                                                                                                                                                                                                                             M-12 ████████████████ Mode Viewer + Q&A (3-4w)
                                                                                                                                                                                                                                                    M-13 ████████ Multimodal (2w)
                                                                                                                                                                                                                                                                   M-14 ████████████ Live Feedback (2-3w)
                                                                                                                                                                                                                                                                                      M-15 ████████ Flashcards + Concepts (2w)
                                                                                                                                                                                                                                                                                                     M-22 ████████ Promotion (2w)
                                                                                                                                                                                                                                                                                                                    M-23 ████ Subscriptions (1w)

(M-18 to M-21 unscheduled — blocked on flows 9-12 not yet drafted; M-16/M-17 now unblocked — flows 7/8 drafted)
```

**Approximate total to launch-ready core:** 7-9 months for M-00 through M-15 + M-22 + M-23.
**Additional milestones M-16 to M-21** added as Flows 7-12 finalize. Estimated 3-5 more months for full v2 coverage.

---

## Critical path

The longest dependency chain that gates demo-able product:

```
M-00 → M-01 → M-02 → M-03 → M-04 → M-06 → M-08 → M-09 → M-11 → M-12
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
| M-18 Cognitive DNA | flow-9-ai-intelligence.md not drafted | Same — draft + merge flow-9 |
| M-19 Parent Monitoring | flow-10-parent-monitoring.md not drafted | Same — draft + merge flow-10 |
| M-20 Group Study + Dashboards | flow-11-group-study-dashboards.md not drafted | Same |
| M-21 Chatbot + VA | flow-12-chatbot-va.md not drafted | Same |

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