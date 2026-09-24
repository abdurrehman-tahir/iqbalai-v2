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

### `yjs` (CRDT) — group collaborative notes

- **Approved by:** @abdurrehman
- **Date:** 2026-05-29
- **Reason:** STACK_LOCK §2 excludes CRDT/real-time co-editing "in v1" in the context of the TipTap lecture editor. Flow 11 #103 requires multiple students to edit shared group notes simultaneously; conflict-free real-time collaboration is exactly what a CRDT solves, and re-implementing merge logic over plain WebSocket broadcast would be fragile and lossy under concurrent edits/offline reconnect. Yjs (MIT) is the de facto OSS CRDT; it syncs over our existing FastAPI WebSocket + Redis pub/sub transport (no new managed service) and persists as a compact binary doc. Scope is deliberately narrow — group notes only.
- **PR:** #<TBD — Flow 11 / M-20a>
- **Scope:** group collaborative notes only (`group_notes.yjs_doc`; frontend group-notes component + its sync provider). **NOT** lecture editing — TipTap stays non-CRDT.
- **Revocation criteria:** If real-time collaborative group notes are cut from scope, or if a non-CRDT approach (e.g. operational-transform service) is later mandated, revoke and migrate group notes off Yjs. Must never expand to lecture editing without a separate deviation.

### `AI4Bharat Indic-TTS` (Sindhi voice synthesis) — PENDING RATIFICATION

- **Approved by:** *pending — @abdurrehman has not ratified this entry.* Recorded retroactively per M-09 pre-merge review; the PR (#30) originally stated "Deviations from STACK_LOCK.md: None," which was incorrect. Documented here so the gap is on the record before merge, not self-approved.
- **Date:** 2026-09-15 (retroactive — behavior shipped in T-121, milestone M-09)
- **Locked choice deviated from:** STACK_LOCK §4.4 — AI4Bharat Indic-TTS as the locked TTS provider for Sindhi (`sd`).
- **What / Scope:** Sindhi (`sd`) TTS synthesis only. STT for `sd` is unaffected (still faster-whisper, same as all languages). English, Urdu (Piper) and Pashto (Edge-TTS) TTS are unaffected. `app/infrastructure/voice/router.py` still calls `_synthesize_ai4bharat()` when `AI4BHARAT_TTS_URL` is configured — the abstraction and provider call are implemented — but no self-hostable AI4Bharat Indic-TTS package could be verified/provisioned as of M-09, so `AI4BHARAT_TTS_URL` is unset at launch and every `sd` TTS request raises `VoiceUnavailableError`. In practice, `sd` voice sessions run STT-only until a provider URL is provisioned.
- **Guardrails:** The gap is contained to the single `app/infrastructure/voice/router.py` chokepoint — no other module calls a TTS provider directly. `_synthesize_ai4bharat()` fails closed via `VoiceUnavailableError` (never silently returns empty/wrong-language audio). No other language falls back to this path; `en`/`ur`/`ps` are on separately-configured, working providers.
- **Parity risk:** A Sindhi-language user in a lecture voice session can speak and be transcribed (STT works), but receives no spoken audio response — text/visual output only — where an English, Urdu, or Pashto user gets full voice output. This is a concrete accessibility/parity gap for `sd` users specifically.
- **Exit condition:** Close this deviation once a verified self-hostable AI4Bharat Indic-TTS deployment exists and `AI4BHARAT_TTS_URL` is set in the relevant environment(s) — no code change required, only provisioning + config, since the call path already exists.
- **PR:** #30

---

## Revoked deviations

(none yet)

## Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-11 | Initial deviations file. Pre-approved `langchain.text_splitter` for chunker. | @abdurrehman (with Claude) |
| 2026-05-29 | Added `yjs` (CRDT) deviation for Flow 11 group collaborative notes (group_notes only; lecture editing stays non-CRDT TipTap). | @abdurrehman (with Claude) |
| 2026-09-15 | Recorded (pending ratification) the AI4Bharat Indic-TTS Sindhi-synthesis gap from M-09/T-121; PR #30's "Deviations: None" line was incorrect. | Claude (M-09 pre-merge review) |

### `fastembed` (dev-only local embedding provider)

- **Date:** 2026-07-13 (**retroactive** — code shipped 2026-06-11 in `e403bb8` during library-upload debugging, without this entry; recorded per AUDIT_LOG `[ungoverned-change]`)
- **Locked choice deviated from:** STACK_LOCK §4.3 — BGE-M3 via Infinity as the embedding provider
- **What:** `EMBEDDING_PROVIDER=local` path in `api/app/infrastructure/rag/embedder.py` using **fastembed** (ONNX, `paraphrase-multilingual-MiniLM-L12-v2`, **384-dim**) inside the celery-worker, with a **separate** Qdrant collection `platform_chunks_local` (prod: `platform_chunks`, 1024-dim).
- **Why:** Infinity (BGE-M3, ~2–4 GB RAM, amd64-emulation on Apple Silicon) is not viable on 8 GB dev machines; ingestion was undevelopable locally.
- **Scope + guardrails (binding):** `local` is **dev-only**. Staging and production run `EMBEDDING_PROVIDER=infinity` — staging is the parity proof, since 384-dim local vectors and 1024-dim prod vectors are **not interchangeable** and dev RAG relevance does not predict prod. Collections stay strictly separated by provider (`*_local` suffix); vector dim comes from config, never hardcoded; any RAG-quality evaluation runs against the Infinity path.
- **Exit:** revisit if a dev-viable BGE-M3 runtime appears; otherwise permanent as a dev convenience.