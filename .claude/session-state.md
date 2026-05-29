# Session state (live — Claude Code updates this)

**Purpose:** Survive context compaction without re-reading the milestone, flow spec, or ARCH from scratch. Claude Code updates this file after each meaningful step (dossier loaded, file edited, tests written, commit made). Post-compaction, read THIS file first.

Keep it short — ≤30 lines. Replace the whole content each time; do not append history.

---

**Current milestone:** _none_
**Current ticket:** _none_
**Ticket dossier loaded:** _no_
**Dossier source files:** _none_

**Done this session:** _none_

**In progress:**
- Step: _idle_
- Last file edited: _none_
- Tests written: _none_

**Next intended step:** _wait for Hamza's first instruction_

**Format-gate run for current changes:** _no_
**Commits this session:** _none_

---

**Update protocol:**
- After `ticket-loader` returns: fill in Current ticket + dossier-loaded + dossier source files + In progress = "implementing".
- After each file edit: update "Last file edited".
- After tests pass locally: set "Tests written".
- After commit: append commit SHA + message to "Commits this session" (keep last 5 only).
- After ticket close: move ticket to "Done this session", clear In progress, set Next = "load next ticket".