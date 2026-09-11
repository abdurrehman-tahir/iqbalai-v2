# Session state (live)

**Milestone:** M-10 Lecture Edit + Versions + 7-Dim Scoring
**Branch:** milestone/M-10-lecture-edit-scoring (forked from M-09 tip — M-09 PR #30
still OPEN/unmerged at branch-creation time; flagged in PR description, retarget
to staging once #30 merges)
**Done:**
- T-129 (commits fbba2bb, fe88afa) — edit/scoring data model.
- T-130 (backend done, commit pending) — TipTap save endpoint (school +
  independent): `content_jsonb` column, `tiptap.py` plain-text extraction,
  `edit_summary.py` heuristic, `save_lecture_version`/`get_current_lecture_version`
  service+router methods, idempotency-keyed POST, `lecture.version.created` emitted.
  206 backend tests passing (42 new). Frontend TipTap editor page/hooks/i18n/tests
  still TODO before T-130 can be marked fully done.
**Current ticket:** T-130 frontend (TipTap editor page + autosave hook + tests)
**Next:** build the editor route, wire save/autosave, then T-131 (voice edits)
**Tooling note:** ruff via `uvx ruff==0.6.9` (fast, works). pytest/mypy needed
`uv pip install --python /usr/local/bin/python <pkg>` run as root inside the
api container (plain `uv run`/`uv sync` and `uv pip install` as non-root both
hit slow-network/permission issues — root install worked, ~5-10 min due to
throttled bandwidth). mypy --strict full-tree run still in progress in
background task bqttpghwv — check it before the PR; tiptap.py/edit_summary.py
already verified clean individually.
**api/uv.lock:** grew +283 lines from an abandoned `uv run ruff format` (dev-group
resolution) — NOT yet committed, decide whether to keep before the PR.
**Out of scope reminder:** M-11 (publish/quiz) and M-12 (viewer) — do not implement.
**Pre-existing untouched changes on disk (not mine, leave alone):** api/app/features/
student_onboarding/service.py, api/app/features/tos/service.py,
frontend/src/lib/__tests__/auth.test.ts, frontend/src/lib/auth.ts, ./Untitled,
infrastructure/authentik/apply_login_branding.py
