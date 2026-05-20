# `<feature name>` — feature spec

**Status:** draft | in-review | approved | deprecated
**Owners (product):** @<github-handle> (Awais usually)
**Owners (technical):** @abdurrehman-tahir
**Last reviewed:** YYYY-MM-DD
**Related ARCHITECTURE sections:** §X, §Y
**Related feature specs:** `other-feature.md`, ...

> **Reading order:** new contributors read `docs/feature-specs/README.md` first to understand the role of this document, then this file, then the related ARCHITECTURE sections.

---

## 1. Purpose

One paragraph. What is this feature, and why does it exist?

- What user problem does it solve?
- Why now (vs. defer to Phase 2)?
- What's the one-sentence pitch a teacher/student/parent would understand?

**Example:**
> *Lecture generation lets a teacher upload a chapter of their textbook and a reference book, then generate an AI lecture in their teaching style (lecture / Socratic / story / applied). It exists because Pakistani government-school teachers spend hours preparing lecture notes that could be drafted in minutes. We do this now because it's IqbalAI's primary product USP — "upload your textbook, get a lecture plan in 5 minutes."*

---

## 2. Personas

Which users does this feature serve, and what's each one trying to do?

**Always identify the tenant type(s)** this feature serves: `school`, `independent`, or both. Per ARCH §3.16, these are two distinct schemas. Most features are school-tenant only; some (typically content surfaces) work in both; very few are independent-only.

| Persona | What they want to do | Permissions needed | Tenant |
|---|---|---|---|
| Teacher | Generate, edit, publish lectures | Create + modify own lectures | school |
| Student | Read published lectures, ask questions | Read lectures from enrolled Grade-Sections | school |
| Independent Teacher | Generate own lecture plans, no student distribution | Own private content only | independent |
| Independent Student | Self-study with own materials + exam framework | Own private content + Platform Library read-only | independent |
| Parent | (Read-only if linked) view child's activity | Read via opt-in ParentChildLink (school only at launch) | school |
| School admin | Audit, suspend problem content | Read all in school + soft-delete + override capacity | school |
| Coordinator | Manage Grade-Subject assignments within scope | CRUD within scope (per §6.19 inheritance) | school |
| District Admin / Platform Admin | Inherit all lower-role permissions within their scope (§6.19) | varies | varies |

**Locked rules:**
- Every interactive surface must work for every persona listed. If a persona is excluded, say so explicitly in "Out of scope."
- **Permission inheritance** (ARCH §6.19): every action available to a role is also available to all roles above it within scope. Don't list "School Admin can do everything Coordinator can" — that's implied by inheritance. Only spell out exceptions or scope bounds.
- **Custom Persona awareness** (ARCH §8.20): if this feature surfaces per-student AI responses, note how Custom Persona interacts. Persona = STYLE (tone, structure); other features may set STRATEGY (e.g., Flow 6 §3.9 angle adaptation). Both compatible.
- **Tenant column is mandatory** for every persona row.

---

## 3. Lifecycle

What states does the primary entity move through, and what triggers each transition?

Draw it as a state machine. ASCII art is fine — it forces clarity.

**Example:**

```
            ┌────────────┐
            │   DRAFT    │  ← teacher creates, AI generates content
            └─────┬──────┘
              edit│ (teacher edits the content)
                  ▼
            ┌────────────┐
            │  REVIEWED  │  ← teacher marks as reviewed
            └─────┬──────┘
            publish│ (teacher publishes)
                  ▼
            ┌────────────┐                ┌─────────────┐
            │ PUBLISHED  │── unpublish ──▶│ UNPUBLISHED │
            └─────┬──────┘                └──────┬──────┘
            archive│                        archive│
                  ▼                              ▼
            ┌─────────────────────────────────────┐
            │              ARCHIVED               │
            └─────────────────────────────────────┘
```

For each transition, document:
- Who can trigger it (which roles)
- What conditions must hold
- What side effects fire (NATS events, notifications, downstream state changes)
- Whether the transition is reversible

**Locked rule:** every state in the diagram must appear as a value in the relevant ORM enum.

---

## 4. Permissions matrix

Who can do what?

Per ARCH §6.19 inheritance: every action available to a role is also available to all roles above it within scope. Don't repeat lower-role rows for upper roles — just note inheritance once. Spell out only exceptions, scope bounds, and cross-tenant restrictions.

For features that span both tenants (school + independent), provide two matrices OR a single matrix with a Tenant column. For tenant-specific features, note tenant at the top.

| Action | Teacher (owner) | Teacher (other in same school) | Student | Parent | School admin | Platform admin |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Create | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Read draft | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Read published | ✅ | ✅ (within school) | ✅ (if in class) | ✅ (if linked, if in class) | ✅ | ✅ |
| Edit | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Publish | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Unpublish | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Soft-delete | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Hard-delete | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

**Locked rules:**
- Any cell different from "❌" must map to a `require_*` dependency in the corresponding router endpoint. If the cell says "✅ (if linked)", the dependency uses `require_parent_of(...)` or similar scope check.
- Per §6.19 inheritance: District Admin inherits ALL School Admin permissions within own district; Platform Admin inherits everything. Matrix rows show specific scope bounds, not the inheritance ladder.
- **Cross-tenant operations forbidden** except for Platform Admin (per §6.10). School users cannot access independent-tenant data; vice versa. Return 404 per §3.13.

---

## 5. Edge cases

What happens at the boundaries? List every one you can think of. Better to list a case and resolve it as "behavior X" than miss it and discover the gap in production.

**Categories to think through:**

- **Concurrent edits.** Two teachers (or the same teacher in two tabs) editing the same resource. What's the resolution? Optimistic concurrency (If-Match)? Last-writer-wins?
- **Soft-deleted parents.** Lecture references curriculum X. Curriculum X is soft-deleted. Can the lecture still be read? Can a new generation reference it?
- **Cross-tenant attempts.** User from school A requests a resource owned by school B. Per ARCHITECTURE.md §3.13, this returns 404 (not 403). Confirm here.
- **Permission downgrades.** A teacher is demoted to student mid-session. What happens to their open lecture editor?
- **Rate-limit hits.** User hits the LLM rate limit during a streaming generation. What's the UX? Resume? Show the partial result and offer retry?
- **External service outage.** Groq is down; OpenAI fallback fails too. What's the user-facing message? Can they retry?
- **Empty inputs.** What if the curriculum has zero chunks (PDF couldn't be parsed)? What's the error code?
- **Excessive inputs.** What if a teacher tries to generate a lecture from a curriculum that has 10,000+ chunks? Is there a limit?
- **Language mismatches.** Teacher selects content language Urdu, but uploaded curriculum is English. Translate at retrieval time? Show the English content with an Urdu summary? Refuse?
- **Partial failures.** A bulk operation half-completes. What's the rollback / retry story?

For each edge case, document:
- **The scenario** — one sentence
- **The behavior** — what happens
- **The error code** (if applicable) — from the §5.5 locked list

**Example:**
> **Scenario:** Teacher A and Teacher B both edit the same lecture's body simultaneously.
> **Behavior:** Optimistic concurrency via `If-Match` header. Second writer gets 412 PRECONDITION_FAILED. Frontend shows "Someone else updated this lecture — refresh to see the latest version." User can refresh or copy their changes elsewhere first.
> **Error code:** `PRECONDITION_FAILED`

---

## 6. Limits

Numerical bounds. Be specific.

- **Per-user limits:** how many of this resource can a single user have? Per day? Total?
- **Per-school limits:** total resources per school? Concurrent operations?
- **Per-request limits:** max payload size? Max items in a bulk operation?
- **Time limits:** how long until an idle session expires? How long do generated resources stay before auto-archive?
- **Rate limits:** at the nginx zone level (general / llm / auth)
- **Cost limits:** if an operation costs LLM tokens, what's the cap?

**Example:**
> - Max lectures per teacher per day: 50 (soft limit; nginx rate-limit `api_llm` zone enforces 10r/s)
> - Max lectures per teacher total: 10,000 (database soft check; rejects beyond this with `LIMIT_EXCEEDED`)
> - Max curriculum file size: 100 MB (enforced by upload pipeline; profile `curriculum`)
> - Lecture body max size: 200 KB markdown (enforced at API)
> - Per-LLM-call cost ceiling: $0.50 per generation (estimated from token count; aborts before completion if exceeded)
> - Generated lecture content TTL: none (lectures persist until archived; archived lectures auto-purged after 1 year)

---

## 7. Notifications

When does the system notify someone? Who gets notified, by what channel, with what message?

**Notification namespaces (locked, per ARCH §9.21):** every notification carries a `feature_namespace` field — one of 7 LOCKED values:
- `lectures` — lecture lifecycle, generation, publish, edits, access changes, enrollments
- `self_study` — study plan, reminders, plan adherence, flashcards
- `quiz` — quiz generation and attempt results
- `connections` — teacher-student assignments, parent-child links, capacity overrides
- `content_library` — library ingestion, version bumps, deprecation
- `system` — Platform Admin alerts, ToS updates, security
- `account` — suspensions, exports, deletions, profile milestones

**Template key convention:** `{namespace}.{event_name}` (e.g., `lectures.generation_complete`, `system.plagiarism_flagged`).

For each notification, group by namespace and use the format below:

### Namespace: `<namespace>`

| Trigger | Recipient | Channel(s) | Template key |
|---|---|---|---|
| Lecture published | Students in Grade-Section | In-app + push | `lectures.published` |
| Lecture generation failed | Teacher (owner) | In-app | `lectures.generation_failed` |
| Daily generation count > 80% of limit | Teacher (owner) | In-app | `lectures.usage_warning` |

**Locked rules:**
- Every notification has a `template key` resolved through next-intl per ARCH §13. Hardcoded English in notification templates is forbidden.
- Every notification MUST belong to one of the 7 namespaces. Adding a new namespace requires platform-wide decision + migration; do not invent ad-hoc namespaces.
- **Notifications cannot be turned off** per Flow 1 Q13 lock. Don't add opt-out toggles.
- **Push notifications are mode-agnostic** per Q17 — they fire regardless of student's Mode (Lecture / Self-Study).
- 90-day inbox retention; 7-year audit log retention per §14.10.

If no notifications are sent: say "None" explicitly. The empty section is meaningful — it tells reviewers "we thought about it and chose silence."

---

## 8. Open questions

Things we know we don't know. List every one.

The rule: **a feature spec cannot be merged with open questions.** Either you answer them, or you scope them out, or you defer to a future spec amendment with explicit reasoning.

**Example (pre-resolution):**
> - [ ] What happens when the teacher unpublishes a lecture students have already started reading? Do their in-progress reads get cut off?
> - [ ] Should parents be able to see lectures their child hasn't read yet? Or only ones they've engaged with?
> - [ ] Is "school admin can unpublish" really right, or should it require teacher consent first?

**Example (post-resolution):**
> - ~~Q: What happens when the teacher unpublishes...~~ → Resolved: students mid-read continue with the version they fetched (cached on the client). New reads return 404.
> - ~~Q: Should parents see unread lectures?~~ → Resolved: yes, parents see the same scope their child sees.
> - ~~Q: School admin unpublish without teacher consent?~~ → Resolved: yes for problem content, but it triggers a notification to the teacher and an audit log entry.

---

## 9. Out of scope (for now)

Features we considered and explicitly deferred. This section prevents scope creep and documents the reasoning.

**Locked rule:** anything in this section gets a TODO.md entry too.

**Example:**
- **Multi-author lectures.** Considered, but Phase 1 ships single-author only. Phase 2 reviews multi-author after we see usage patterns. (TODO.md: phase-2-multi-author-lectures)
- **AI-assisted editing during the review state.** Teacher edits manually in Phase 1. AI-assisted "improve this paragraph" is Phase 2. (TODO.md: phase-2-ai-edit-assist)
- **Real-time co-editing.** Out of scope entirely until at least Phase 3. Requires CRDT-class complexity. (TODO.md: never, unless re-evaluated)

---

## 10. Related ARCHITECTURE sections

When implementing this feature, Claude Code reads these sections (in addition to §0):

- §<X.Y> — <reason>
- §<X.Y> — <reason>

**Example:**
- §3 (entire) — multi-tenancy is critical; this feature owns lectures, a tenant-scoped resource
- §4.18 — lecture versioning pattern (immutable LectureVersion records)
- §5 (entire) — API design
- §6.7 — access dependencies
- §7.10 — Pattern S RAG for lecture generation
- §8.6 — typed prompts (`lecture_generation_v1.py`)
- §9.3 — `lecture.created`, `lecture.scored`, `lecture.published` events
- §11.16 — curriculum file upload profile

---

## 11. Acceptance criteria

For each persona × major action, what's the success criterion?

These are also the test cases. The implementation is "done" when these all pass.

**Example:**
- ✅ A teacher in school A can generate a lecture from one of their curricula
- ✅ A teacher in school B receives 404 when trying to access school A's lecture (per §3.13)
- ✅ A student in a class enrolled in the lecture can see it after the teacher publishes
- ✅ A student in a different class cannot see the lecture (per §3.6)
- ✅ A parent linked to a student in the lecture's class can see it
- ✅ A parent NOT linked to any student cannot see the lecture
- ✅ When the teacher unpublishes, students in the class see the lecture disappear within 60 seconds (via WS event)
- ✅ Concurrent edit by two teachers produces 412 PRECONDITION_FAILED for the second writer
- ✅ Bulk lecture generation in Urdu produces Urdu content (verified by post-generation language detection)
- ✅ All UI text is translated in en/ur/sd/ps; no `__TODO__` markers in production

---

**Last reviewed:** YYYY-MM-DD
**Reviewers:** @<github-handle>, @abdurrehman-tahir
