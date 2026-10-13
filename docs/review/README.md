# Checking the developers' work — start here

This is for Awais, or anyone who needs to check the developers' work without reading code.

You give an AI assistant (Claude Code) the number of a pull request, and it gives you back a plain-language report: what the developers were supposed to do, what they did, what they skipped, and what to ask them.

## A few words you'll see

- **Pull request (PR):** a package of changes the developers want to add to the project. Each one has a number, like #38.
- **Merge:** adding that package to the project for real.
- **Milestone:** one stage of the build plan, such as "M-22". Each milestone is a list of tickets.
- **Ticket:** one small piece of work inside a milestone.
- **Automatic checks:** tests and checks that run by themselves on every PR and show pass or fail.

## Setting up (once)

You need a Claude Code account connected to this project on GitHub, the same setup the developers use. Ask the developers to help you connect it the first time.

## How to use it

1. Find the PR number. It's in the link the developers send you, e.g. `.../pull/38` means PR #38.
2. Open a Claude Code session on this project.
3. Type this, with your PR number:

   `Review PR #38 in plain language, per docs/review/PLAYBOOK.md.`

That's all. It reads everything itself and replies with the report.

## What you get back

Always the same eight parts, in plain words:

1. What this PR was supposed to deliver
2. What was done, and what wasn't
3. Automatic checks: what passed and what failed
4. Boxes the developers left unticked
5. Tests
6. Changes from the agreed plan
7. Open questions still waiting for an answer
8. Questions to ask the developers, ready to copy and send

Each item is marked **Fine**, **Worth asking** or **Needs fixing**, with a one-line verdict at the top.

## Good to know

- **It never changes anything.** It only reads and reports. It won't edit, comment on, approve or merge anything.
- **Some things can't be confirmed by anyone.** For example, whether a developer ran tests on their own computer leaves no trace. The report will say "the developers say so, but this can't be confirmed" instead of guessing.
- **If it can't read something,** such as the automatic check results, it will say so plainly.
- **Your review doesn't block anything by itself.** Anyone can merge. If you want to see PRs before they're merged, agree with the developers that they send you the link and wait for your OK.

## What to do with the report

Copy part 8, "Questions to ask the developers", and send it to them. If anything is marked **Needs fixing**, ask them not to merge until it's sorted.
