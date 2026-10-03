# Session state — M-15 Flashcards + Concept Enrichment + Lecture Rating

- **Branch:** `milestone/M-15-flashcards-concept-enrichment-rating` @ `d82dce4` (= origin/staging, M-14 merge PR #35)
- **Current ticket:** T-185 — dossier loaded (ticket-loader), no code written yet
- **Milestone file:** `docs/backlog/M-15-flashcards-enrichment-rating.md` — Status lines: T-185:47 T-186:80 T-187:113 T-188:149 T-189:182 T-190:215 T-191:248 T-192:281 T-193:314 T-194:347
- **Design decisions so far:**
  - Table names follow flow-6 §10 sketch: `student_highlights`, `student_flashcards`, `lecture_ratings`, `concept_applications`, `careers`, `student_simulation_progress`
  - Highlight/flashcard hook point: `student_questions/answer_pipeline.py::_persist_answer` (both stream + non-stream paths)
  - Highlight anchor = paragraph_id + offset/length within paragraph text; restore only if text still matches (§5.5 silent drop)
  - `flashcard.created` absent from ARCH §9.3 taxonomy — check `app/infrastructure/events/subjects.py` registry at T-187 (possible AMENDMENTS gate)
  - M-12 ledger shows T-152/156/159 `todo` but code exists (stale ledger) — flag in PR
- **Env blockers:** Windows Application Control blocks git https/ssh (fetch/push), `pytest.exe`, and native DLLs in api/.venv (pydantic_core). WSL Ubuntu has uv/node; Linux venv setup (`uv sync` w/ UV_PROJECT_ENVIRONMENT=~/.venvs/iqbalai-api) denied by permission classifier — awaiting user.
- **Next step:** once a test runner is available → implement T-185 (model → autogenerate migration school_0073 → service hook → GET highlights endpoint → viewer yellow-mark overlay → tests)
