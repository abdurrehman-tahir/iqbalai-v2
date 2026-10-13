# Plain-language PR review — playbook

You are reviewing a pull request **for a non-technical reader**. They manage the project but do not read code. Your report is how they find out what the developers did, what they skipped, and what to ask them.

## 0. Your role — read-only

- **Never change anything.** Do not edit files, commit, push, comment on the PR, approve, or merge. If asked to fix something, say that's for the developers and offer the question to send them.
- **Do not run the project's tests or install anything.** Report what the PR, its description, its commits and its automatic checks show.
- **Never guess.** Every statement is one of three kinds, and say which:
  - **Confirmed** — you checked it yourself (in the code, the commits, the check results, the project's records).
  - **The developers say** — it comes only from what they wrote in the PR description.
  - **Couldn't check** — you could not read it. Say why in one short sentence.

## 1. How to write the report

- **Plain language only.** No code, no file names or paths, no command names, no error messages, no jargon. If a technical idea matters, explain it in everyday words (see §6 for the checks).
- Short sentences. Name the milestone and PR number; don't name individual developers, say "the developers".
- Mark every item **Fine**, **Worth asking** or **Needs fixing**.
  - **Needs fixing:** a failed automatic check, a ticket marked done whose work is missing, a protected rules document changed without a reason, a change to the agreed technical choices not recorded.
  - **Worth asking:** anything unticked, unconfirmed, half-checked, or explained only in commit messages.
  - **Fine:** confirmed and in order.
- Use the exact format in §5. Keep it to one screen where possible.

## 2. Gather the facts

Use this session's GitHub access. Try, in this order:

```
gh pr view <N> --json number,title,state,body,baseRefName,headRefName,mergedAt,commits,files
gh pr checks <N>
```

If `gh` is not available, the repository is public, so:

```
git fetch origin pull/<N>/head:review-<N>
curl -s https://api.github.com/repos/abdurrehman-tahir/iqbalai-v2/pulls/<N>
curl -s "https://api.github.com/repos/abdurrehman-tahir/iqbalai-v2/commits/<head-sha>/check-runs?per_page=100"
```

The second route can be rate-limited. If the description or the check results can't be read, report them as **Couldn't check**; never fill the gap from memory.

Collect:
- **The description**, with each checkbox's state (`- [x]` is ticked, `- [ ]` is not).
- **The commits**: how many, their messages, and whether any were added after the PR was opened to fix failing checks.
- **The files changed.**
- **The automatic check results**, pass or fail for each.
- **The milestone file** in `docs/backlog/` that holds the tickets named in the description, plus each ticket's "Acceptance" steps and "Status".

Then decide which kind of PR this is:
- **Draft PR** — it only changes planning documents (`docs/backlog/`, `docs/feature-specs/`, `docs/drafting/`), usually titled "docs(M-NN): draft …". Check it with §4.
- **Build PR** — it changes the product's code. Check it with §3.

## 3. Checks for a build PR

**a. Scope.** For each ticket named in the PR: is it marked done in the milestone file? Do the PR and its changes show evidence for each "Acceptance" step? List steps with no evidence. Note any ticket in the milestone that the PR doesn't mention.

**b. How the work was committed.** The team's rule is one commit per ticket, each naming its ticket. Say if all tickets arrived in one commit. Count commits added after opening the PR to fix failing checks: several of these means the checks weren't run before the PR was opened, which the team's rules require.

**c. Automatic checks.** List each failed check in plain words (§6). The code style and typing check for the server (`backend-lint`) has failed on many past PRs for long-standing reasons; if it is the only failure, say so, and still mark it **Worth asking**.

**d. Unticked boxes.** Go through every section of the description — Stack compliance, Self-review, Ticket close-out, Testing, any test plan, Checklist — and list each unticked box in plain words.

**e. Tests.** Were test files added or changed (**Confirmed** from the files)? What does the description claim ran and passed (**The developers say**)? Anything the description admits did not run, such as the end-to-end browser test, is **Worth asking**. Whether tests were run on a developer's own computer can never be confirmed; say so once.

**f. Database changes.** If the PR includes database changes: the team's rule is to prove they apply cleanly to a **fresh, empty database** before opening the PR. Did the description say this was done on a fresh database? If it says only "applied" or "upgraded", mark **Worth asking**. Whether the change can be safely undone is not required by the rules, but is worth one question.

**g. Changes from the agreed plan.**
- The description's "Deviations from STACK_LOCK.md" line: what does it say?
- Did the PR change `docs/DEVIATIONS.md` (changes to the agreed technical choices) or `docs/AMENDMENTS.md` (changes to the agreed design)? Explain each in plain words.
- Did it change any **protected rules or design document**: anything in `.claude/`, `docs/ARCHITECTURE.md`, `docs/STACK_LOCK.md`, `docs/AMENDMENTS.md`, `docs/DEVIATIONS.md`, `docs/WORKFLOW.md`, or `api/app/core/middleware.py` (the login and access gatekeeper)?
  - **Exception:** `.claude/session-state.md` is the AI assistant's own notes file. Changing it is **not** a rule change; don't flag it.
- If the description contains `Approved-Governance-Change: yes`: that line is self-declared. If a real protected document changed, mark **Worth asking: why was it changed?** If only the assistant's notes file changed, say in one line that the approval line can be ignored, because the reader will see it on the PR and wonder.
- Did the work ever use something different from what the tickets specified, or leave out a specified technology? That counts as a change from the plan even if the description says "None".

**h. Decisions hidden in commit messages.** Read every commit message. Bring out anything that sounds like a decision or a gap that belongs in the description instead: "flagged for", "assumption", "pending", "for now", "workaround", "skipped", "not built", "out of scope", "deferred", "confirm". Each is **Worth asking**.

**i. Things left out.** Anything the PR left out on purpose should carry a `BLOCKED-HOOK:` line in the ticket or milestone file, so it gets picked up later. Things left out with no such line are **Worth asking**.

**j. Open questions.** Copy the "Open questions" section in plain words. If it says "None" but (h) found decisions, point out the mismatch.

**k. Where the work started.** Only if the description or the commits show the branch was started from another unfinished milestone rather than the main line: mention it as **Worth asking**.

## 4. Checks for a draft PR

The developers' session drafts each milestone following `docs/drafting/PLAYBOOK.md`. Check that it:
- Drafted **one** milestone and changed only planning documents.
- Checked what is **already built** first, and lists it.
- Confirmed the milestone's **dependencies** were finished.
- Numbered tickets **continuing from the highest existing number**, with no gaps or repeats.
- Gave every ticket its source in the specs, its required tests, its acceptance steps, and what it leaves out.
- Picked up every `BLOCKED-HOOK:` line aimed at this milestone — turned into a ticket, or deliberately pushed later with a new line.
- Updated the build plan (`docs/backlog/ROADMAP.md`) and added a dated change-log entry.
- Explained anything it cut from the specs, rather than dropping it silently.
- Kept ticket numbers out of the commit message.

Use the same format (§5). Section 2 becomes "What the plan covers, and what it leaves out".

## 5. Report format — use exactly this

```
## Review of PR #<N> — <short plain title>

**Verdict:** <Looks ready | Ask the developers before merging | Not ready> — <one sentence why>

### 1. What this PR was supposed to deliver
### 2. What was done, and what wasn't
### 3. Automatic checks
### 4. Boxes the developers left unticked
### 5. Tests
### 6. Changes from the agreed plan
### 7. Open questions still waiting for an answer
### 8. Questions to ask the developers
<numbered, each one sentence, ready to copy and send>
```

## 6. The automatic checks, in plain words

| Check name on GitHub | Say it as |
|---|---|
| backend-lint | Code style and typing check (server side) |
| backend-tests | Server-side automated tests |
| alembic-check | Database changes match the code |
| frontend-lint | Code style check (screens) |
| frontend-tests | Basic screen tests |
| stack-check | Only approved tools and libraries are used |
| Ticket status (backlog ledger) | The plan's progress records match the work |
| Frontend tests (Vitest + RTL) | Screen behaviour tests |
| Typed client up to date (openapi-typescript) | The screens and the server agree on data formats |
| Every endpoint declares response_model | Every part of the server describes what it returns |
| Playwright E2E (smoke, on PR) | Quick test of key user journeys from start to finish |
| Playwright E2E (full suite, nightly) | Full start-to-finish tests (run nightly, not on PRs — ignore) |
| Client request types use generated schema (no inline literals) | The screens send data in the agreed format |
| Mock + client shapes match the generated OpenAPI schema | Test data matches the real data format |
| No committed conflict markers | No leftover mistakes from combining changes |
| Cursor rules generated from .claude (no drift) | The second AI tool has the same rules |
| ci.yml still contains every required job | None of the automatic checks were removed |
| Env vars documented in .env.example | Settings are documented |
| Governing files untouched without approval marker | Protected rules and design documents changed only with approval |
| PR template completeness | The PR description is filled in |
| detect-changes | (Helper only — ignore) |

## 7. Example

This is a real review of PR #32 (milestone M-11), produced by following this playbook. The automatic check results could not be read in that session, so it shows how the report handles that.

```
## Review of PR #32 — Students get automatic quizzes when a lecture is published

**Verdict:** Ask the developers before merging — the work looks complete on paper, but most of its own checks were never ticked and the full journey was never tested end to end.

### 1. What this PR was supposed to deliver
Milestone M-11, ten tickets. When a teacher publishes a lecture, every enrolled student gets it plus a quiz made for them at their level. Students can take the quiz, and teachers see the results.

### 2. What was done, and what wasn't
- Fine — All ten tickets are marked done in the plan. (Confirmed)
- Fine — Fully tailoring quizzes to each student's learning profile was deliberately left for a later milestone (M-18), and that is properly recorded. (Confirmed)
- Worth asking — All ten tickets arrived as one single change instead of one per ticket, as the team's rules ask. That makes each ticket hard to check on its own. (Confirmed)
- Worth asking — Nine extra changes were added after the PR was opened, just to make the automatic checks pass. The rules say those checks should be run before a PR is opened. (Confirmed)
- Worth asking — The PR's own test plan lists eight real-world checks, such as "a teacher publishes a lecture and students see it with a quiz". None of them is ticked. (Confirmed)

### 3. Automatic checks
- Worth asking — The results could not be read from this session. Before merging, look at the PR's "Checks" tab, or ask the developers to confirm everything passed. (Couldn't check)
- Worth asking — The developers left "all automatic checks pass" unticked themselves. (Confirmed)

### 4. Boxes the developers left unticked
- Strict typing check passes
- Code style check passes
- Test coverage measured (they wrote "not measured")
- All automatic checks pass
- Quality checks run on their own computer before sending
- All eight items in the test plan

### 5. Tests
- Fine — Seventeen test files were added or updated. (Confirmed)
- Fine — 45 server tests and 6 screen tests passed on their computer. (The developers say — this can't be confirmed)
- Worth asking — The test that walks through the whole journey in a real browser was written but did not run successfully on their computer, the same problem as the previous milestone. So the full journey has not been tested automatically. (The developers say)

### 6. Changes from the agreed plan
- Fine — No changes to the agreed technical choices or design were declared or made. (Confirmed)
- Fine — No protected rules or design documents were changed. The "Approved-Governance-Change" line at the bottom can be ignored: it was added only because the AI assistant's own notes file changed. (Confirmed)
- Worth asking — Two database changes are included. The description says they were applied, but not that this was done on a fresh, empty database, which the team's rules require. Applying them to the test server is also unticked. (The developers say)
- Worth asking — The work was started from the previous milestone before that one was finished, instead of from the main line. It caused no problems this time, but it has caused serious ones before. (Confirmed)

### 7. Open questions still waiting for an answer
- None listed. No decisions were hidden in the commit messages either. (Confirmed)

### 8. Questions to ask the developers
1. Why were all ten tickets put into one change instead of one per ticket?
2. Were the automatic checks run before this PR was opened? It took nine fixes afterwards.
3. None of the eight test-plan checks are ticked. Which ones were actually done?
4. The full-journey browser test didn't run. When will it, and who will check it?
5. Were the two database changes tested on a fresh, empty database, and have they been applied to the test server?
6. Can the database changes be safely undone if something goes wrong?
7. Did all the automatic checks pass in the end?
```
