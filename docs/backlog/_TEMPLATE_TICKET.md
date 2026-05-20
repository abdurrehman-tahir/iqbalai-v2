# Ticket template

Copy this when creating a new ticket. Replace placeholders. Delete this paragraph.

---

## T-NNN — Short descriptive title (one line)

**Layer:** Foundation | 1 (auth) | 2 (school structure) | 3 (content) | 4 (lecture creation) | 5 (lecture consumption) | 6 (cross-cutting)
**Milestone:** M-NN
**Estimate:** 1-5 days
**Status:** todo

### Spec source
- `flow-N-*.md` §X.Y (subsection title)
- `flow-N-*.md` §A.B (subsection title)
*(If no spec exists yet, write `BLOCKED: requires flow-N-XYZ.md to be drafted` and set Status to `blocked`)*

### ARCH source
- `ARCHITECTURE.md` §X.Y (subsection title)
- `ARCHITECTURE.md` §A.B (subsection title)

### Depends on
- T-XXX (one-line description)
- T-YYY (one-line description)

### What this ticket builds

(1-2 short paragraphs. What does the USER see? What does the CODE create? Mention frontend AND backend if both.)

### Acceptance (demo script — must be runnable)

The reviewer + Awais should be able to follow these steps and check each box. Aim for 3-6 steps.

1. [ ] Step 1 (concrete user action or system observable)
2. [ ] Step 2
3. [ ] Step 3
4. [ ] Step 4 (final state confirms ticket done)

### Out of scope for this ticket

- [Thing 1] (goes in T-ZZZ — link)
- [Thing 2] (deferred to Phase 2 per TODO.md entry "X")

### Notes / known gotchas (optional)

(Edge cases the implementer should know. Spec references for tricky behaviors. Anti-patterns to avoid.)
