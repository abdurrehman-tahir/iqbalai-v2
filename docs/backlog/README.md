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
[Any data-model shapes shown are **design intent, NOT literal migration DDL**. Write the SQLAlchemy model, then `alembic revision --autogenerate` → review the diff → one concern per migration (ARCH §4.12). The model layer is the source of truth; never hand-write a migration from a ticket sketch.]

### API contract (any ticket with endpoints)
- **Endpoint(s):** `METHOD /api/v1/...`
- **Request / Response models:** Pydantic `XxxCreate` / `response_model=XxxRead` — **every endpoint declares `response_model=`**
- **FE type:** generated via openapi-typescript (`schema.d.ts`) — never hand-mirrored

### Tests (required — not "as the ticket specifies")
- **Backend:** pytest unit + API contract test (FastAPI TestClient) per endpoint
- **Frontend (if a Frontend section exists):** Vitest + RTL for components/hooks **and** a Playwright E2E step proving the acceptance path renders + works

### Acceptance (demo script)
1. [ ] Step 1 of demo
2. [ ] Step 2 of demo
3. [ ] Step 3 of demo

**UX acceptance (any ticket with a Frontend section — each machine-checked by the Playwright step):**
- [ ] Reachable from the app nav (not an orphan route)
- [ ] Renders real content (no blank shell); all four UI states handled (loading / empty / error / success)
- [ ] Overflowing content scrolls; primary action enabled/disabled correctly
- [ ] Responsive (mobile + desktop), RTL-safe, all strings via i18n keys

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
2. **Pull inherited hooks.** `grep -rn "BLOCKED-HOOK" docs/backlog/ docs/feature-specs/_CHANGE_LOG.md` and read every hit whose target milestone is the one being drafted. **Each matching hook MUST be folded into this milestone as a real ticket** (or, if consciously re-deferred, re-marked with a new `BLOCKED-HOOK` line pointing at the later milestone — never silently dropped). **Also** `grep -rn "Flow <N>" docs/backlog/` for the flow this milestone implements, to catch forward hooks deferred *before* that flow was drafted (these were never `BLOCKED-HOOK`-tagged because their target was draftable, not blocked — e.g. a "→ Flow 8" hook planted while Flow 8 was still unwritten). Fold those in too.
3. **Stale-reference pass** — confirm every cited ARCH §/flow § still resolves to the right content (T0-renumbering and post-amendment drift happen); fix or flag mismatches.
4. **Dependency sanity** — confirm `Depends on:` tickets all exist and precede this milestone; no forward references to unborn tickets.
5. **Open-item + modernization gate.** `grep -n "resolve-before" docs/STACK_LOCK.md` — any open item tagged `resolve-before` **this** milestone MUST be decided + locked first; never draft over an open foundational decision. Then run the **ticket-modernization pass**: confirm the milestone's tickets carry the current template fields (API contract, Tests, UX acceptance) and that all data-model content reads as *intent, not migration DDL*; add missing fields before drafting/implementing.
6. Only then draft the tickets, append the `_CHANGE_LOG` entry, and flip the ROADMAP status to `drafted`.

### Milestone-boundary audit-log distillation (run AFTER a milestone merges)

The improvement loop's distillation pass — a ~5-minute pass at each milestone boundary, the counterpart to phase-complete-review's per-PR capture into `docs/AUDIT_LOG.md`:

1. **Scan** `docs/AUDIT_LOG.md` for classes with ≥2 occurrences (or any high-severity single hit).
2. **Promote** each into the carrier CC reads at authoring time — a `data-modeling` / `frontend-master` skill rule, a `CLAUDE.md` gate, or a CI lint — choosing the *bindingness* the class needs (prose for judgment calls, a lint for mechanical checks). Set the entry's status to `promoted (→carrier, date)` and record the generalized rule text.
3. **Verify** against later audits: a class that stops recurring = the rule worked; a class that **recurs after its rule existed** = the carrier was too weak (e.g. prose that needed a CI lint) → harden it, don't re-add it.

Owner: Abd. (with Claude) — it edits governing artifacts, so it's a drafting-side judgment call, not CC's. CC only *generates* the findings (via phase-complete-review at PR time) and *consumes* the promoted rules next milestone.

### Mandatory flow-spec audit (run BEFORE drafting any flow spec)

Flow specs are the **source** the milestones derive from, so an error here propagates everywhere. Drafting a flow spec (Flows 9-12 remain) is not allowed to start until this audit has run. It is the mechanism that stops a deferred hook, an uncovered v2 feature, or a cross-flow assertion from being lost. Steps, in order:

1. **Verify sources exist on disk** — the v2 doc (`/mnt/user-data/uploads/9_IqbalAI_Final_v6.docx`), ARCHITECTURE.md, STACK_LOCK.md. Confirm the target flow spec is **not** already drafted. (The v2 doc has 108 features; #19/#20/#22 are retired.)
2. **Feature-coverage reconciliation.** Extract the v2 feature numbers this flow owns from the v2 doc, then diff against every other flow's `**v2 doc features covered:**` header. The **union of all flow headers must equal the full 1-108 set minus retired** — this diff catches BOTH gaps (a feature assigned to no flow) AND overlaps (a feature claimed by two). Resolve every gap/overlap before drafting; the new spec's header must list **exactly** its set. Record the decision for any feature that moves or is dual-referenced.
3. **BLOCKED-HOOK harvest (inverse of the milestone "pull inherited hooks" step).** `grep -rn "BLOCKED-HOOK:" docs/backlog/ | grep "→ Flow <N>"` — enumerate **every** hook targeting this flow. **Each one MUST become a real lifecycle section / explicit acceptance contract in the spec** (or be consciously re-deferred with a fresh `BLOCKED-HOOK` line to a later flow — never silently dropped). A flow with zero hooks (e.g. Flow 12) is scoped purely from the v2 doc; note that explicitly.
4. **Cross-reference consistency.** `grep -rhnE "[Ff]low <N>\b" docs/feature-specs/flow-*.md` across all **finalized** specs to collect every assertion others make about this flow ("read-only per Flow N", "Flow N owns X"). The spec must honor each. Any "TODO confirm placement" / ambiguous ownership (e.g. #73 between Flow 9/11) must be **explicitly resolved** here, not left floating.
5. **Dependency + stack sanity.** Confirm upstream flows this one consumes are already drafted (enforce drafting order 9 → 10 → 11 → 12; no forward flow dependency). Check whether any feature needs a new STACK_LOCK entry or a `DEVIATIONS.md` note (e.g. Yjs/CRDT for #103) — decide before drafting, not after.
6. **Milestone-split + ROADMAP plan.** Decide whether the flow is too large for one milestone (Flow 9 ≈ 29 features) and pre-record the split so the ROADMAP row(s) + future ticket ranges stay coherent and contiguous.
7. **Draft + register.** Write the spec to house style (Purpose → Personas → Lifecycle §3.x → Permissions matrix → Edge cases → Limits → Notifications → Open questions → Out of scope → Related ARCHITECTURE sections → Data-model sketch → Acceptance criteria; header lists v2 features covered + related specs). Then flip ROADMAP `blocked` → `drafted`, append the `_CHANGE_LOG` entry, and add any **new** `BLOCKED-HOOK` lines for work this flow defers to still-undrafted flows.

**Completeness ledger (per drafted flow).** Close every flow spec with a `## Drafting completeness ledger` section recording: the v2 features it covers (matching the header), each BLOCKED-HOOK it consumed (with source ticket), each cross-flow assertion it honored, and any feature/hook re-deferred onward. This makes the full 1-108 coverage + the hook registry auditable at a glance and lets the next flow's step-2/step-3 diff run cleanly.

### Standardized deferral marker (so the audit's grep is reliable)

Whenever a ticket **or flow spec** defers work that belongs to a not-yet-draftable milestone/flow, write **exactly** this greppable line — in a ticket's `Notes / known gotchas` and the milestone's soft-dependency block, or (for a flow spec) in the relevant lifecycle section and the spec's completeness ledger:

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
