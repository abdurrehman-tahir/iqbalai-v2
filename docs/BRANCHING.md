# BRANCHING.md

**Status:** Locked
**Owner:** @abdurrehman
**Last reviewed:** 2026-05-11

This document defines how branches, PRs, and merges work in this repo. Read it before opening your first PR.

---

## Branch roles

### `main`
- **What it represents:** Production. What's deployed to users.
- **Who can push:** Nobody directly. Force-push disabled.
- **How code reaches it:** A single release PR from `staging` → `main`, approved by @abdurrehman.
- **Protection rules** (set on GitHub once via Settings → Branches):
  - Require pull request before merging
  - Require approval from @abdurrehman
  - Require status checks to pass before merging
  - Do not allow force pushes
  - Do not allow deletions

### `staging`
- **What it represents:** Integration branch. The next release candidate.
- **Who can push:** Nobody directly. All changes via PR.
- **Base branch for:** Every feature, fix, and hotfix branch.
- **CI:** Full test suite runs on every PR targeting `staging`.
- **Protection rules:** Same as `main`.

### Feature, fix, and hotfix branches
- **Created from:** `staging`
- **Merged into:** `staging` via squash merge
- **Naming convention:**
  - `feature/phase<N>-<short-name>` — new features (e.g., `feature/phase1-rbac-roles`)
  - `fix/<short-name>` — bug fixes (e.g., `fix/lecture-version-rollback`)
  - `hotfix/<short-name>` — urgent fixes to production (rare; cherry-picked back to `staging` after)
- **Lifetime:** Delete after merge.

---

## Merge strategy

| From | To | Strategy | Why |
|---|---|---|---|
| `feature/*` → `staging` | Squash merge | Clean linear history on `staging`. One commit per feature. |
| `fix/*` → `staging` | Squash merge | Same. |
| `hotfix/*` → `staging` | Squash merge | Same. |
| `staging` → `main` | Merge commit | Preserves the release boundary as a visible commit in `main`'s history. |

GitHub UI: set "Allow squash merging" and "Allow merge commits" to **enabled**, set "Allow rebase merging" to **disabled** to keep things consistent.

---

## PR rules

1. **One PR = one logical change.** Don't bundle unrelated features.
2. **Every PR targets `staging`** (never `main`, except the release PR).
3. **PR title** follows Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`. Examples:
   - `feat(rbac): add 6-level permission hierarchy`
   - `fix(rag): handle empty curriculum index`
   - `docs(specs): finalize flow-7 next-day review spec`
   - `docs(backlog): add M-08 to M-12 tickets`
4. **PR body** is auto-filled by the `phase-complete-review` Claude Code skill (when that ships) using the template at `.github/PULL_REQUEST_TEMPLATE.md`. Empty fields = blocked merge.
5. **CI must be green** before merge.
6. **@abdurrehman must approve** before merge.
7. **No self-merge** even after approval if you're the author and not @abdurrehman.
8. **Squash merge commit message** should be the PR title + a one-line summary. Don't carry junk commit messages forward.

### 8.1 Docs-only PRs — fast track

PRs that touch ONLY `docs/` (no code changes) follow a lighter path:

- **Author:** typically @abdurrehman-tahir (chat sessions with Claude produce updated specs / backlog / ARCH updates → he commits + pushes)
- **PR title prefix:** `docs(specs):`, `docs(backlog):`, `docs(arch):`, `docs(amendments):` depending on what's touched
- **CI:** skipped for `docs/`-only changes (no tests to run; only markdown linting + link checks)
- **Review:** @abdurrehman self-approves docs-only PRs (he's the sole author of doc content; co-review by Awais happens at chat-session time, not PR time)
- **Merge cadence:** can merge same-day; doesn't block on Hamza's review
- **Backlog touched:** if the PR adds/changes tickets in `docs/backlog/`, Hamza must `git pull` before starting his next session (per WORKFLOW.md §0)

**Why fast-track:** doc updates are the bottleneck for keeping Hamza unblocked. Treating them like code PRs (full CI + multi-reviewer) wastes time on changes that have already been chat-reviewed by Abd. + Awais.

**What's NOT docs-only:** any PR that touches both `docs/` AND code follows the full review path (Hamza review + Abd. review + CI). Mixed PRs are discouraged — split them.

---

## Workflow for Hamza (typical day)

```bash
# Start of day: sync staging
git checkout staging
git pull origin staging

# Start a new feature
git checkout -b feature/phase2-curriculum-parser

# Tell Claude Code what to build (Claude reads CLAUDE.md + STACK_LOCK.md automatically)
# Claude writes code, runs pre-commit locally, commits

# Push and open PR
git push -u origin feature/phase2-curriculum-parser
gh pr create --base staging --title "feat(curriculum): structured parsing of curriculum PDFs"

# Wait for CI + @abdurrehman approval
# After approval, squash merge via GitHub UI

# Delete the local branch
git checkout staging
git pull
git branch -d feature/phase2-curriculum-parser
```

---

## Release flow (when staging is ready to ship)

```bash
# @abdurrehman triggers the release
git checkout staging
git pull origin staging

# Open a release PR
gh pr create --base main --head staging --title "release: vX.Y.Z"

# Tag the release after merge
git checkout main
git pull
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z
```

CI on `main` runs a deployment workflow (added later when deploy targets are decided in `ARCHITECTURE.md`).

---

## Hotfix flow (production bug needs immediate fix)

Rare. Only @abdurrehman triggers this.

```bash
# Branch from main, not staging
git checkout main
git pull
git checkout -b hotfix/critical-auth-bug

# Fix, PR to main, get approval, merge
gh pr create --base main --title "hotfix(auth): patch JWT validation bug"

# After merge to main, cherry-pick into staging
git checkout staging
git pull
git cherry-pick <hotfix-commit-sha>
git push
```

---

## One-time setup (already done for this repo, documented for reference)

```bash
# Create staging from main (run once at repo creation)
git checkout main
git checkout -b staging
git push -u origin staging
```

### Branch protection: free-tier reality

**GitHub Branch Protection Rules and Rulesets are paywalled on free private repos** as of 2026. Both pop up "Move to GitHub Team" messages on this repo. We accept that and enforce process via the layers below instead. The day this repo moves to a Team/Org account, we enable the real protections from Settings → Rules → Rulesets.

What we use instead (all free, all already configured):

1. **CI workflows** (`.github/workflows/ci.yml`) run on every PR. Red CI = visible signal not to merge.
2. **PR template check** (`.github/workflows/pr-template-check.yml`) fails PRs with empty required sections.
3. **CODEOWNERS** (`.github/CODEOWNERS`) auto-assigns @abdurrehman-tahir as reviewer on every PR.
4. **Bypass audit** (`.github/workflows/bypass-audit.yml`) detects direct pushes to `main`/`staging` and files a GitHub issue automatically. Also runs a weekly summary every Monday.
5. **Process rules in this file + `.claude/CLAUDE.md`** — Claude Code reads these and enforces them on Hamza's behalf during code generation.

This means: GitHub itself won't *block* a direct push, but you'll know about it within minutes (audit workflow files an issue), and the social/process layer keeps Hamza on the rails for normal work. For a 2-person team, this is sufficient.

---

## Things that are forbidden

- Pushing directly to `main` or `staging`
- Force-pushing to any branch except your own feature branch (and only when nobody else is on it)
- Long-running feature branches (>1 week without sync to `staging`) — rebase or merge `staging` in frequently
- Merging without CI green
- Merging without @abdurrehman approval
- Renaming `main` or `staging`
- Deleting `main` or `staging`

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-11 | Initial branching rules | @abdurrehman (with Claude) |
| 2026-05-11 | Free-tier reality: replaced "configure branch protection" with audit-workflow + CODEOWNERS approach. Real protection enabled when repo moves to Team/Org account. | @abdurrehman (with Claude) |
