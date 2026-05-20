# DEVIATIONS.md

**Status:** Living document
**Owner:** @abdurrehman (sole approver)
**Last reviewed:** 2026-05-11

This is the **only** place where exceptions to `STACK_LOCK.md` can be authorized.

## How a deviation gets approved

1. Open a PR that adds a new entry to this file using the template below.
2. The PR title must be: `deviation: <package>.<module> in <file scope>`
3. The PR must be approved by @abdurrehman.
4. Only after merge can the deviation be used in subsequent feature PRs.
5. The `check_stack_lock.py` script parses this file and unlocks the exact import path + file scope listed.

## Rules

- One deviation per entry. Don't bundle.
- File scope must be exact. Wildcards are allowed (`app/services/ingestion/*`) but should be narrow.
- Reason must explain *why* the locked alternative doesn't work, not just *what* you want to use.
- Date and approver are mandatory.
- Deviations are **revoked** by removing the entry. Code that depended on it must be refactored.

---

## Entry template (copy this when adding a deviation)

```markdown
### `<package>.<module>`

- **Approved by:** @abdurrehman
- **Date:** YYYY-MM-DD
- **Reason:** <Why the locked alternative doesn't work for this use case>
- **PR:** #<PR number>
- **Scope:** `<exact file path or narrow glob>`
- **Revocation criteria:** <What would cause this deviation to be removed>
```

---

## Active deviations

### `langchain.text_splitter`

- **Approved by:** @abdurrehman
- **Date:** 2026-05-11
- **Reason:** `RecursiveCharacterTextSplitter` is the de facto standard chunking implementation in the OSS RAG ecosystem. Rewriting it for the sole purpose of avoiding a LangChain import wastes engineering time and produces a less-tested chunker. Importing only `langchain.text_splitter` (not `langchain.chains`, `langchain.agents`, `langchain.llms`, etc.) does not pull the wider LangChain orchestration surface area we intentionally banned.
- **PR:** #1 (bootstrap)
- **Scope:** `app/services/ingestion/chunker.py` only
- **Revocation criteria:** If `langchain.text_splitter` ever depends on a banned LangChain submodule (LLM wrappers, chains, agents), or if `semantic-text-splitter` (Rust binding) matures to feature parity, revoke and migrate.

---

## Revoked deviations

(none yet)

---

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-11 | Initial deviations file. Pre-approved `langchain.text_splitter` for chunker. | @abdurrehman (with Claude) |
