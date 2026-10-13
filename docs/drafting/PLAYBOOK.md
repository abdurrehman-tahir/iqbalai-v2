# Drafting mode — playbook

You are here because the first row in `docs/backlog/ROADMAP.md` that is not `done` has no backlog file yet (status `drafted-spec`), or it is a placeholder row (`Deferred work`, `Rollout N`).

**Your job in this session:** draft that one milestone, open a docs-only PR, and stop. Do not write product code.

---

## 0. Ground rules

- **One milestone per session, one docs-only PR.** Implementation happens later, in its own session and PR, after this one merges.
- **Never mark anything as built without checking the code.** Search `api/` and `frontend/` and cite the file paths you found.
- **Never guess at scope.** If a spec is ambiguous, draft the clear part and list the question under "Open questions" in the PR description. Whoever merges decides.
- **Do not edit files outside what this drafting step needs** (the new milestone file, `ROADMAP.md`, `docs/feature-specs/_CHANGE_LOG.md`, and where relevant `docs/TODO.md` or `DEFERRED_REGISTER.md`).

## 1. Identify what to draft

Read `ROADMAP.md` from the top. The first row whose Status is not `done` is your target. It will be one of three kinds:

| Row | What to do |
|---|---|
| A milestone row (`M-NN`) with status `drafted-spec` | Draft it: §2, then §3, then §4 |
| The `Deferred work` placeholder | Build the deferred-work register: §5 |
| A `Rollout N` placeholder | Draft that rollout: §6 |

If the first not-`done` row already has a backlog file (status `drafted` or `in-progress`), you are not in drafting mode. Implement its next ticket instead.

## 2. Checks before drafting

Run the **mandatory pre-draft audit** in `docs/backlog/README.md` (section "Mandatory pre-draft audit"): sources exist, harvest `BLOCKED-HOOK` markers that target this milestone, stale-reference pass, dependency sanity, open-item gate. Then add these two checks, which were added at handover:

**a. Dependencies must already be done.** Every milestone or ticket this one depends on must be `done`. If any is not, do not draft. Report which dependency is missing in your reply and stop. Do not skip ahead to a different milestone on your own.

**b. Built-or-not check.** For every feature or spec item in scope, search the code for an existing implementation. Draft tickets only for what is missing. In the milestone file, add a short "Already built" list with the file paths you found.

- If **everything** in scope is already built, draft no tickets. Set the ROADMAP row to `done`, explain why in the row and in `_CHANGE_LOG.md`, and open the docs-only PR with that change.
- **M-22 and M-23 are known to be largely built.** Graduation and migration of graduates to the independent tenant shipped in M-06 (`api/app/features/graduation/`), and promotion fields exist in `api/app/features/grades/`. The subscription tier schema and Platform Admin CRUD shipped in M-01 (`api/app/features/subscriptions/`, `frontend/src/app/admin/subscription-tiers/`). Check each spec item against this code before drafting anything.

## 3. Draft a milestone

- **File:** `docs/backlog/M-NN-short-name.md`, or `M-NN` plus one letter for a split (`M-18b-…`). Any other naming breaks the CI ledger's file-to-row mapping.
- **Header:** copy the shape of an existing milestone file, for example `M-17-self-study-mode.md`: title, `**Status:** drafted`, estimated duration, `**Tickets:** T-AAA through T-BBB`.
- **Tickets:** follow `docs/backlog/_TEMPLATE_TICKET.md` and "Ticket structure" in `docs/backlog/README.md`. Every ticket cites its spec section and ARCH sections, lists its dependencies, its required tests, acceptance steps, and what is out of scope.
- **Size:** 7 to 16 tickets. If it is bigger, split it into `a`/`b` milestones and add the extra row to `ROADMAP.md` directly after.
- **Last ticket:** `M-NN PR + demo`.
- **Numbering:** the first ticket is the highest `T-NNN` that exists anywhere in `docs/backlog/`, plus one. Number contiguously. Never reuse a number.
- **Harvested markers:** each `BLOCKED-HOOK` that targets this milestone becomes a ticket, or is re-deferred with a new marker pointing further out. Never drop one silently.

## 4. Register the draft and open the PR

1. **ROADMAP row:** status `drafted-spec` → `drafted`; ticket cell → the real range.
2. **`docs/feature-specs/_CHANGE_LOG.md`:** add one row, dated today.
3. If you consumed an item listed in `docs/TODO.md` or `DEFERRED_REGISTER.md`, mark it there as moved to this milestone.
4. **Commit message:** `docs(M-NN): draft <milestone name>`. **Do not put ticket IDs in the commit message.** The CI ledger reads commit messages and would demand those tickets be done.
5. **Open the docs-only PR.** In the description: what is in scope, what was found already built, anything re-deferred, any open questions.
6. **Stop.**

## 5. Deferred work — building the register

This runs when the `Deferred work` row is the first not-`done` row. It can also be run earlier on request (see `PROMPTS.md`), for estimating.

**Sources — collect every item from:**
- The `## 9. Out of scope (for now)` section of every flow spec in `docs/feature-specs/` (flow 1 to flow 13, including flow 7)
- `docs/TODO.md`
- `BLOCKED-HOOK` markers anywhere in `docs/` whose target milestone is done or does not exist
- `docs/STACK_LOCK.md` items tagged `resolve-before pilot`

**Classify each item** into exactly one of these:

| Class | Where it goes |
|---|---|
| Dev work, not built | Into the deferred-work series. **This includes items tagged `phase-2-*` or `phase-3-*`** — the decision is to build everything before deciding next steps. |
| Dev work, already built | Recorded as built, with file paths. Not drafted. |
| Non-dev work (legal, translations, procedures, business, launch tasks) | Into a Rollout (§6) |
| Never build, by design (for example "never via UI", "out per policy") | Excluded. Record it as excluded. These are decisions, not unbuilt work. |
| A pointer to another flow that already owns it | Skip. That flow's milestone covers it. |

**Then:**
1. Write `docs/drafting/DEFERRED_REGISTER.md`: one row per item with its source (file and section), the item, its class, whether it is built (with evidence), and its target milestone.
2. Group the dev items into milestones by flow or theme, 7 to 16 tickets each, in dependency order.
3. In `ROADMAP.md`, replace the `Deferred work` row with one row per new milestone (status `drafted-spec`), numbered after the highest existing milestone number, placed before the Rollout rows.
4. Open the docs-only PR with the register and the roadmap change. Stop. Each new milestone is then drafted in its own session using §2 to §4.

## 6. Rollouts

- **The word is "Rollout", not "phase".** "Phase" already means three different things in these docs: old branch names, the strategic doc's build phases, and the `phase-2`/`phase-3` deferral tags.
- **Four stages:** Rollout 1 Pilot readiness, Rollout 2 Pilot, Rollout 3 Production launch, Rollout 4 Post-launch.
- **Draft them only after every build milestone, including the deferred series, is on the roadmap.**
- **Each Rollout is a milestone:** it gets an `M-NN` number at draft time and tickets numbered like any other. Keep "Rollout N" in its title. Its tickets are non-dev tasks: the register's non-dev items, plus whatever that stage needs.
- **Name an owner on each rollout ticket.** These are business decisions.
- **Rollout tickets have no code commits.** Close them by setting `**Status:** done` and adding one line saying what shows it is done.

**Items already known to belong here:**

| Item | Rollout | Note |
|---|---|---|
| Legal review of the ToS (`pre-pilot-full-legal-review` in `TODO.md`) | 1 | |
| Disclaimer translations into ur/sd/ps | 1 | Must land before predictions (M-18c) reach real users. Until then predictions show the English fallback. |
| Backup and restore procedures | 1 | Flagged as a launch blocker in `TODO.md` and `resolve-before pilot` in `STACK_LOCK.md` |
| PII handling for PDPB 2025 | 1 | The legal part goes here; any code change goes into the deferred series |
| Connection pooling sizing, embedding cache, rate limiting per role | — | These are dev work: they go into the deferred series, before Rollout 1 |

## 7. Known traps

- **Flow 7's spec was missing from the repo until the handover.** The committed version was restored from an earlier draft and judged good enough: it resolves every section M-16 cites.
- **M-22 and M-23 are largely built.** Do §2b properly before drafting a single ticket.
- **The CI ledger only sees ticket IDs named in commit messages.** A milestone whose commits never name their tickets leaves every ticket at `todo`. That happened to M-12 and had to be fixed by hand at handover.
- **Mentioning a ticket ID in a commit message counts as referencing it.** A message like "T-NNN stays open" makes the ledger demand that ticket be done.
- **Milestone file names must be `M-NN` or `M-NN` plus one letter.**
