# Feature specs

**Status:** Locked process. Append-only directory of permanent business-rule documents.
**Owner:** @abdurrehman-tahir
**Purpose:** Capture the **business rules** of each flow — the WHAT and WHY, separate from the HOW (which lives in `docs/ARCHITECTURE.md`) and the WHEN (which lives in `docs/backlog/`).

---

## What lives here vs. what doesn't

| Doc | Concern | Lifetime | Reviewer |
|---|---|---|---|
| **`docs/feature-specs/<feature>.md`** (here) | Business rules — lifecycle, permissions, edge cases, limits, notifications | Permanent (lives forever, updated as rules evolve) | Abd. + Awais |
| `docs/backlog/M-NN-*.md` | Execution sequencing — which tickets land in which milestone, what depends on what | Living (updated as flow specs finalize) | Abd. |
| `docs/ARCHITECTURE.md` | Technical patterns — how the stack fits together | Permanent (changed via AMENDMENTS.md) | Abd. |
| `docs/STACK_LOCK.md` | Locked tools | Permanent (changed via PR) | Abd. |
| The v2 product doc (Awais's doc) | Product intent at a high level | Long-lived (the strategic source) | Awais + Abd. |

If you're about to write "what happens when X" into either ARCHITECTURE.md or a backlog ticket, **stop** — that's a business rule. It belongs here.

---

## Specs are organized by FLOW, not by individual feature

The v2 product doc lists ~109 features. Writing 109 separate spec files would create fragmentation — most features tightly couple (a lecture wizard + auto-quiz + scoring + originality + benchmarking all happen in one teacher workflow). Instead, the spec set is organized into **13 flows**, each covering a coherent end-to-end user workflow that spans multiple features.

Current spec set (post-T0):

| Flow | Spec file | Features covered |
|---|---|---|
| 1. Platform Setup | `flow-1-platform-setup.md` (v2) | #1, #6, #7, #8, #9, #12, #13, #14 |
| 2. Admin & Coordinator Setup | `flow-2-admin-coordinator-setup.md` (v3) | #2, #3, #4, #5 + Grade/Section/Subject model + promotion workflow |
| 3. Teacher Onboarding | `flow-3-teacher-onboarding.md` (v3) | #11, #16, #17, #18 |
| 4. Student Onboarding | `flow-4-student-onboarding.md` (v3) | #10, #15, #51, #52, #53 + Exam Framework + graduation |
| 5. Teacher Creates a Lecture | `flow-5-teacher-creates-lecture.md` (v1) | #21, #23, #23b, #24-38, #41 (19 features) |
| 6. Student Studies a Lecture | `flow-6-student-studies-lecture.md` (v2) | #54-61, #71 (9 features) |
| 7-12 | (to be drafted in parallel with Phase 1 development) | TBD |
| 13. Subscriptions (thin) | `flow-13-subscriptions.md` (v1) | Schema-only at launch; full module deferred to Phase 2 |

**Rules for flows:**
- One spec per coherent flow. A flow can cover 1-20 features depending on coupling.
- A feature MUST appear in exactly one spec. Don't duplicate. If a feature touches multiple flows (e.g., notifications fire from many places), document it in its primary flow and reference from others.
- Flow specs follow the same `_TEMPLATE.md` structure (Personas, Lifecycle, Permissions, Edge cases, Limits, Notifications, Open Questions, Out of Scope, Related ARCH sections, Acceptance criteria).
- A spec's `v2 doc features covered:` header MUST list every feature it owns. CI may grep for orphan features in the future.

---

## Why this exists as its own folder

Three reasons:

1. **Business rules are reviewed by Awais and Abd. for product intent and feasibility.** That's a different review than implementation tickets. Different reviewer mindset, different cadence. Mixing them with ticket sequencing means one of the two reviews gets skimmed.
2. **Tickets are short-lived** (a milestone is 2-3 weeks; the ticket is "done" once merged). **Business rules are permanent** (the rule "students can't see lectures before scheduled release" outlives a hundred tickets). Mixing throwaway tickets with permanent rules is structurally wrong.
3. **Tickets are too small to carry business rules.** A ticket says "implement T-XXX." The flow spec answers "what behavior is correct?" Keeping them separate forces both to be read.

---

## The lifecycle of a feature spec

```
1. DRAFT
   Either: Awais drafts a flow spec from the v2 doc.
   Or:     Abd. drafts a flow spec.
   Or:     Claude (in a chat session with Abd.) drafts a flow spec from the v2 doc,
           the relevant ARCHITECTURE sections, and asks Abd. the open questions.
   Result: docs/feature-specs/flow-N-<name>.md on a docs branch.

2. REVIEW
   - Awais reads the spec for product intent ("yes, that's how teachers actually work")
   - Abd. reads it for feasibility ("does this play with the multi-tenant model?
     does it touch any unlocked decisions in ARCHITECTURE.md?")
   - Comments resolved on the PR.

3. APPROVE & MERGE
   When both approve, the spec merges to `staging`. It's now the permanent record
   for how this workflow is supposed to behave.

4. BACKLOG TICKETS UNBLOCK
   Tickets in `docs/backlog/M-NN-*.md` that were marked `BLOCKED: requires flow-N`
   are unblocked. Their `Spec source:` lines can now resolve. Abd. + Claude may
   draft additional tickets that this flow enables.

5. IMPLEMENT (via backlog tickets)
   Hamza picks a milestone. Tells Claude Code "Implement T-NNN."
   Claude reads:
   - The ticket file (docs/backlog/M-NN-*.md, the T-NNN section)
   - The ticket's `Spec source:` — line-range reads from this flow spec
   - The ticket's `ARCH source:` — line-range reads from ARCHITECTURE.md
   - Relevant skills
   and writes code that satisfies all three.

6. AMEND
   When reality changes the business rule (e.g., teachers need a "draft" state we
   didn't anticipate), the change is a PR to docs/feature-specs/<feature>.md.
   Same review track as the original (Awais + Abd. approval).
   If the change also requires an architecture change, it ALSO goes through AMENDMENTS.md.

7. RETIRE
   Features are deprecated, not deleted. The spec gets a "Status: deprecated"
   header and stays in the repo. Future contributors can read why a feature
   existed and why it was retired.
```

---

## What a feature spec contains

See `_TEMPLATE.md` for the canonical structure. Every spec has these sections:

1. **Purpose** — one paragraph, what this feature exists to do
2. **Personas** — which users this feature is for (teacher, student, parent, school admin, etc.)
3. **Lifecycle** — the states the feature's primary entity moves through, and what triggers each transition
4. **Permissions matrix** — who can do what
5. **Edge cases** — what happens at boundaries (concurrent edits, soft-deleted parents, cross-tenant access attempts, etc.)
6. **Limits** — rate limits, count limits, size limits
7. **Notifications** — who gets notified when (email, push, SMS, in-app)
8. **Open questions** — things we know we don't know yet; flagged for resolution before implementation
9. **Out of scope (for now)** — features we considered and explicitly deferred; helps prevent scope drift
10. **Related ARCHITECTURE sections** — pointers to which §X sections are relevant

The spec is **prose, not code**. No SQL schemas, no API endpoints, no Pydantic models. Those go in ARCHITECTURE.md (patterns) or in the implementation. The spec answers "what should happen?" not "how do we build it?"

---

## Mandatory before implementation

A feature cannot be implemented until its flow spec has been merged. WORKFLOW.md enforces this:

- Each backlog ticket has a `Spec source:` line citing the flow spec sections it depends on.
- If a ticket's `Spec source:` references a flow file that doesn't exist or isn't merged, the ticket is marked `BLOCKED: requires flow-N spec finalized`. Hamza skips it and moves to the next unblocked ticket.
- `phase-complete-review` skill's Checklist M verifies that the implemented behavior matches the cited spec sections.

If you find yourself implementing a feature and discovering ambiguity that the spec doesn't resolve: stop. Message Abd. Don't guess and silently lock in an interpretation.

---

## Naming conventions

- **One file per flow.** Filename follows `flow-NN-<kebab-name>.md` where NN matches the flow's position in the v2 product doc.
  - Example: `flow-5-teacher-creates-lecture.md` covers v2 features #21, #23, #23b, #24-38, #41 (19 features in one flow).
- **A flow can cover 4-19 v2 features** depending on coupling. Don't fragment specs per individual feature.
- Within a flow file: group related sub-features under one §3 Lifecycle when they share permissions and state transitions.
- The full flow → feature mapping lives in `feature-specs/README.md` top-of-file table.

---

## What gets a feature spec

Every user-facing feature with non-trivial business logic. Examples:

- Auth (signup, login, password reset, MFA, SSO callback) → `auth.md`
- Schools, classes, enrollments → `schools.md`
- Lectures (the whole lifecycle) → `lectures.md`
- VA (virtual assistant) → `va.md`
- Quizzes, scoring, feedback → `quizzes.md`
- Originality scoring → `originality.md`

What doesn't:

- Pure infrastructure (`infrastructure/llm/`, `infrastructure/rag/`) — patterns are in ARCHITECTURE.md
- Pure plumbing (Celery tasks, NATS consumers) — they implement something for a feature; the spec belongs to the feature
- One-off scripts (`scripts/`)
- Devops (`docker/`, `nginx/`)

---

## Drafting a feature spec — practical guide

If you (Abd. or Awais) are about to draft a spec:

1. **Copy `_TEMPLATE.md`** as `<feature>.md`
2. **Read the relevant section in the v2 doc** to capture original product intent
3. **Read ARCHITECTURE.md §0** and follow it to the technical sections relevant to this feature
4. **Fill in the spec section by section.** When you hit a question you can't answer, add it to "Open questions" — don't skip it.
5. **Open a PR.** Request review from Awais (product) and yourself (feasibility).
6. **Iterate on PR comments.** Resolve every "Open question" before merge — that's the point.
7. **Merge.** The spec is now permanent.

If Claude (in a chat session with Abd.) is drafting the spec:

1. Read the v2 doc section for the feature
2. Read ARCHITECTURE.md §0 + the sections it points to for this feature type
3. Read related feature specs (e.g., if drafting `quizzes.md`, read `lectures.md` for context)
4. Fill in the template, asking Abd. the questions that require human judgment (limits, notification preferences, edge-case product intent)
5. Output the draft for Abd. to review before committing

---

## When a spec gets out of sync with reality

If you discover that the code does something different from the spec:

- If the spec was right and the code is wrong: that's a bug. Fix the code.
- If the code is right and the spec was wrong: open a spec PR to fix the spec. Get Awais + Abd. to re-approve.
- If both are wrong because reality is different from what we planned: open a spec PR with the new reality. Approve. THEN fix the code in a follow-up PR.

Never silently let the code drift from the spec. The spec is the source of truth for what the feature is supposed to do.

---

**Last updated:** 2026-05-14
**Owner:** @abdurrehman-tahir
