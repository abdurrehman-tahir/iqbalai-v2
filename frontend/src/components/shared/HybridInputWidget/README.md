# HybridInputWidget — reuse contract (T-155 / T-171, spec #57)

**There is exactly one hybrid text/voice/image input component in this codebase.**
It lives here, at `frontend/src/components/shared/HybridInputWidget/`, and is
exported canonically from `./index.tsx`:

```ts
import { HybridInputWidget, type SubmitPayload } from "@/components/shared/HybridInputWidget";
```

Built in M-12 (T-155, text + voice) and extended in M-13 (T-166–T-172, image
attach + vision-LLM routing). Per `flow-6-student-studies-lecture.md` §3.5,
this is the canonical input for **any** surface that needs text + optional
voice dictation + optional image attach (0-3 images, JPEG/PNG/WEBP, 5 MB
each) — not just the lecture Q&A flow it originated on.

## Do not fork this component

If you're building a new chat-like or question-input surface (Flow 5 lecture
creation chat, Flow 8, Flow 11, or anything else that needs text/voice/image
input), **import `HybridInputWidget` and wire your own `onSubmit`** — do not
write a new input component, even a small one. The M-12/M-13 hard constraint
("§3.5 — ONE reusable widget") applies repo-wide, not just to Flow 6.

### Current consumers (as of M-13)

- `frontend/src/app/student/lectures/[lectureId]/HighlightQuestionBox.tsx` —
  new question from a highlighted passage (`allowImages`, 3s auto-send
  countdown via `autoSendCountdownSeconds`).
- `frontend/src/app/student/lectures/[lectureId]/AnswerSidePanel.tsx` —
  multi-turn follow-up on an existing question (`allowImages`, no
  auto-send).

Both surfaces render the widget with `data-testid="hybrid-input-widget"`;
only one is ever mounted at a time (the highlight box unmounts itself via
`setSelection(null)` the moment a question is created — see
`LectureViewerClient.submitQuestion`). E2E coverage for this invariant lives
in `frontend/e2e/lecture-hybrid-vision-smoke.spec.ts` ("only one widget is
mounted").

### Tracked follow-up: Flow 5 creation-chat migration

Flow 5's lecture-creation chat currently has its own, older input
implementation (predates T-155/M-12). Migrating it onto this shared widget
is **explicitly out of scope for M-13** (to avoid destabilizing working M-09
code) but is tracked as a deferred follow-up — see the "Frontend" section of
`docs/TODO.md` ("Flow 5 creation-chat migration onto `HybridInputWidget`").

## Contract

```ts
type SubmitPayload = {
  text: string;                 // typed + voice-transcribed text, combined
  attached_images: ImageRef[];  // 0-3 uploaded images (empty pre-M-13 / allowImages=false)
};

type HybridInputWidgetProps = {
  onSubmit: (payload: SubmitPayload) => Promise<void>;
  placeholder?: string;
  disabled?: boolean;
  initialText?: string;             // e.g. "Explain: <highlighted text>" (T-156)
  maxImages?: number;               // default 3
  allowVoice?: boolean;             // default true
  allowImages?: boolean;            // default false — opt in per-surface (M-13)
  voiceLanguage?: "en" | "ur" | "sd" | "ps";
  autoSendCountdownSeconds?: number; // default 0 (off); T-156 highlight flow uses 3
  onAutoSendCancel?: () => void;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  onImageAttached?: (count: number) => void;
  transcribeAudio?: (audio: Blob, language?: VoiceLanguage) => Promise<{ transcript: string }>;
};
```

- **Images are opt-in per call site** via `allowImages` — set it `true` on
  any new consumer that should support image attach; the icon/thumbnail
  row/drag-drop/paste handlers are all gated behind this single prop, so
  turning it on is the entire integration cost.
- The widget owns image upload itself (`hooks/useImageUpload.ts`, backed by
  `studentQuestionImagesApi.upload` from `@/lib/api`) — callers only ever see
  the resulting `ImageRef[]` (MinIO storage key + mime + size + a
  client-side thumbnail data URL) in `SubmitPayload.attached_images`. Thread
  `img.storage_key` values into your own request payload's
  `attached_images: string[]` field; the backend vision router (T-168) picks
  up from there.
- `transcribeAudio` exists purely as a dependency-injection seam for tests —
  production call sites should omit it and let the widget call
  `studentVoiceApi.transcribe` itself.

## Test coverage

- Component: `__tests__/HybridInputWidget.test.tsx` (Vitest + RTL) — text,
  voice, and image attach/remove/max-3/drag/paste/upload-failure paths.
- E2E: `frontend/e2e/lecture-hybrid-vision-smoke.spec.ts` (Playwright,
  `@smoke @mock`) — exercises both current consumers end-to-end with the
  backend fully mocked.
