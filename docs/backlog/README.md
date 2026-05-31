# Backlog — Implementation Tickets

**Status:** Living document
**Owner:** @abdurrehman-tahir
**Purpose:** Sequenced list of small implementable tickets that reference flow specs (business rules) + ARCHITECTURE.md (technical patterns). Each ticket = the smallest unit a developer can build and demo.

---

## Why this exists

The v2 product doc is the strategic source (109 features in phases). The flow specs are the business-rule source (workflows). Neither is implementable directly — phases are too big, flows assume all their parts exist. The backlog **decomposes both into tickets** that:

1. Build atop foundational dependencies before user-facing features
2. Reference flow specs for business rules (don't copy — single source of truth)
3. Reference ARCHITECTURE.md subsections for technical patterns
4. Have clear acceptance criteria (= demo script)
5. Group into milestones (2-3 weeks each) for stakeholder communication + PR cadence

---

## Reading the backlog

### Files

```
docs/backlog/
├── README.md                       (this file)
├── ROADMAP.md                      milestone overview, sequencing, current state
├── M-00-foundation.md              Milestone 0: containers, infra, base code
├── M-01-platform-setup.md          Milestone 1: Platform Admin + base config
├── M-02-school-onboarding.md       Milestone 2: District + School + first admins
├── ...
└── _TEMPLATE_TICKET.md             how to write a ticket
```

### Ticket structure

Each ticket has this shape:

```markdown
## T-NNN — Short descriptive title

**Layer:** Foundation | 1 | 2 | 3 | ...
**Milestone:** M-NN
**Estimate:** 1-5 days
**Status:** todo | in-progress | done | blocked

### Spec source
- `flow-1-platform-setup.md` §3.5 (Custom persona lifecycle)
- `flow-1-platform-setup.md` §6 (Limits — 5 personas + 1 Custom slot)

### ARCH source
- `ARCHITECTURE.md` §8.20 (Custom Persona learning batch)
- `ARCHITECTURE.md` §10.6 (Beat schedule entry `persona.update_custom`)

### Depends on
- T-XXX (description of prerequisite)
- T-YYY

### What this ticket builds
[1-2 paragraphs: what the user sees + what the code creates]

### Acceptance (demo script)
1. [ ] Step 1 of demo
2. [ ] Step 2 of demo
3. [ ] Step 3 of demo

### Out of scope for this ticket
- [thing 1] (goes in T-ZZZ)
- [thing 2] (deferred to Phase 2 per TODO.md)
```

### Status semantics

- **todo** — not yet started
- **in-progress** — currently on a milestone branch
- **done** — merged to staging
- **blocked** — waiting on a missing dependency (usually an undrafted flow spec; see `BLOCKED:` reason)

---

## How Hamza uses the backlog

1. Pulls latest from `staging` (per WORKFLOW.md §0)
2. Opens `docs/backlog/ROADMAP.md` — sees current milestone
3. Opens the milestone file (e.g., `M-03-teacher-onboarding.md`) — sees ordered list of tickets
4. Tells Claude Code: **"Implement T-045"**
5. Claude Code reads:
   - The ticket itself (~50 lines)
   - The cited flow spec sections (via line-range `view`)
   - The cited ARCH subsections
   - The skill files relevant to the changes (frontend, backend, etc. per `.claude/skills/`)
6. Implements the ticket (typically 1-3 days of work)
7. Hamza reviews, commits with message `feat(scope): ... (T-045)`
8. Continues with next ticket on same milestone branch
9. After all milestone tickets done → opens ONE PR for the entire milestone branch

---

## Drafting cadence

- **Backlog is drafted incrementally** alongside flow specs
- Tickets exist only for features whose flow spec is finalized
- Tickets dependent on unfinalized flow specs are marked `BLOCKED: needs flow-N spec finalized`
- As Awais reviews + finalizes Flows 7-12, corresponding tickets unblock

### Mandatory pre-draft audit (run BEFORE drafting any milestone)

Drafting a milestone is not allowed to start until this audit has run. It is the mechanism that stops deferred cross-milestone work from being lost. Steps, in order:

1. **Verify sources exist on disk** — the milestone's anchoring flow spec + the ARCHITECTURE §§ its tickets will cite. If the flow spec isn't finalized, the milestone stays `blocked` — do not draft.
2. **Pull inherited hooks.** `grep -rn "BLOCKED-HOOK" docs/backlog/ docs/feature-specs/_CHANGE_LEDGER.md` and read every hit whose target milestone is the one being drafted. **Each matching hook MUST be folded into this milestone as a real ticket** (or, if consciously re-deferred, re-marked with a new `BLOCKED-HOOK` line pointing at the later milestone — never silently dropped). **Also** `grep -rn "Flow <N>" docs/backlog/` for the flow this milestone implements, to catch forward hooks deferred *before* that flow was drafted (these were never `BLOCKED-HOOK`-tagged because their target was draftable, not blocked — e.g. a "→ Flow 8" hook planted while Flow 8 was still unwritten). Fold those in too.
3. **Stale-reference pass** — confirm every cited ARCH §/flow § still resolves to the right content (T0-renumbering and post-amendment drift happen); fix or flag mismatches.
4. **Dependency sanity** — confirm `Depends on:` tickets all exist and precede this milestone; no forward references to unborn tickets.
5. Only then draft the tickets, append the `_CHANGE_LEDGER` entry, and flip the ROADMAP status to `drafted`.

### Standardized deferral marker (so the audit's grep is reliable)

Whenever a ticket defers work that belongs to a not-yet-draftable milestone, write **exactly** this greppable line in the ticket's `Notes / known gotchas` AND in the milestone's soft-dependency block:

```
BLOCKED-HOOK: <what is stubbed> → <target flow / milestone> (built against <interim source> for now)
```

Example (M-11 T-144): `BLOCKED-HOOK: full Cognitive DNA calibration → Flow 9 / M-18 (built against M-08 diagnostic seed for now)`. One consistent phrase means a single `grep -rn "BLOCKED-HOOK"` always finds the complete set — no dedicated index file required.

---

## Relationship to other docs

| Doc | What it owns | Updated when |
|---|---|---|
| **v2 doc** (Awais's doc) | Strategic intent, 109 features list, priorities | Rarely (strategic pivots) |
| **flow-N-*.md specs** | Business rules per workflow | When Awais decides product behavior changes |
| **ARCHITECTURE.md** | Technical patterns | When architectural decisions change (via AMENDMENTS.md) |
| **`docs/backlog/`** (here) | Implementation tickets, milestones, sequencing | Frequently — every spec update, every milestone completion |
| **`docs/plans/`** (legacy) | Original phase plans | Deprecated in favor of backlog-based ROADMAP |

---

## Status as of this writing

- Backlog draft Session 1: Layer 0 + Layer 1 + Layer 2 tickets (Milestones M-00 to ~M-06)
- Backlog draft Session 2 (planned): Layer 3+ tickets (M-07 onward)
- Flows 7-12 not yet drafted → tickets dependent on those are BLOCKED

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-14 | Backlog system initialized. README + ROADMAP + Milestones M-00 to M-06 created. | @abdurrehman (with Claude) |
