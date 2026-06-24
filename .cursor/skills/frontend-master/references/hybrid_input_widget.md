# Hybrid input widget (text + voice + image) — canonical pattern

**Status:** Locked component pattern per Flow 6 v2 (#57) + ARCH §8.22.

This is the **single canonical input widget** used by every student-facing AI surface. Applies to:

- Lecture Q&A panel (Flow 6)
- Wizard chat sidebar during lecture creation (Flow 5 #26)
- Group study room chat (Flow 11, future)
- Self-Study mode chat (Flow 8, future)
- Study plan creation (Flow 8, future)
- Virtual Assistant chat (Flow 12, future)

**Frontend reuse is mandatory.** If a feature needs text/voice/image input, it MUST use this widget. No duplicate implementations.

---

## What the widget supports

Three input modes that compose freely in a single send:

1. **Text** — typed into the input box
2. **Voice** — mic icon → faster-whisper STT (per STACK_LOCK §4) → live transcription appears in input box
3. **Image** — drag-drop, paste (Ctrl/Cmd+V), or image-attach icon → up to 3 images attached as chips below input

A single message can carry text + voice transcript + 0-3 images all together.

---

## Component location

```
frontend/src/components/shared/HybridInputWidget/
├── index.tsx                       # main component export
├── HybridInputWidget.tsx           # the widget
├── ImageAttachmentChip.tsx         # thumbnail with X-to-remove
├── VoiceRecorder.tsx               # mic button + recording state
├── hooks/
│   ├── useImageUpload.ts           # client-side: upload via student_question_image profile
│   └── useVoiceTranscription.ts    # client-side: faster-whisper streaming
└── types.ts                        # shared types
```

**Single source of truth.** Don't reimplement in feature folders. Import from `@/components/shared/HybridInputWidget`.

---

## Public API

```tsx
import { HybridInputWidget } from "@/components/shared/HybridInputWidget";

<HybridInputWidget
  // Required
  onSubmit={(payload: SubmitPayload) => Promise<void>}
  
  // Optional
  placeholder?: string                    // i18n key for empty-state placeholder
  disabled?: boolean
  initialText?: string                    // e.g., "Explain: [highlighted text]" prefill
  maxImages?: number                      // default 3
  allowVoice?: boolean                    // default true
  allowImages?: boolean                   // default true
  voiceLanguage?: 'en' | 'ur' | 'sd' | 'ps'   // for STT model selection
  
  // Auto-send countdown (per Flow 6 §3.3)
  autoSendCountdownSeconds?: number       // default 0 (no countdown); 3 for highlight->question flow
  onAutoSendCancel?: () => void

  // Telemetry hooks
  onRecordingStart?: () => void
  onRecordingStop?: () => void
  onImageAttached?: (count: number) => void
/>
```

```ts
type SubmitPayload = {
  text: string;                                  // typed + transcribed combined
  attached_images: ImageRef[];                   // 0-3 images
};

type ImageRef = {
  storage_key: string;                           // MinIO key from upload pipeline
  mime_type: 'image/jpeg' | 'image/png' | 'image/webp';
  size_bytes: number;
  thumbnail_data_url: string;                    // small base64 for instant render
};
```

---

## Four UI states

Per frontend-master `four_ui_states.md`:

| State | Trigger | UI |
|---|---|---|
| **Idle** | initial / after submit | Text input + mic icon + image-attach icon, all enabled |
| **Recording** | mic clicked | Red pulse indicator, live transcription appearing in input, "Tap to stop" |
| **Image attached** | image dropped/pasted/picked | Thumbnail chip below input with X-to-remove; can attach more (up to 3); other input modes still active |
| **Submitting** | send clicked OR auto-send fired | Spinner; inputs disabled until onSubmit resolves |
| **Error** | upload failed / STT failed / send failed | Inline error toast with retry; idle state restored |

Loading states use the shared `<LoadingSpinner />` component. Errors use `<ErrorToast />` with i18n keys per `i18n_keys.md`.

---

## Image upload flow

```
1. User drops/pastes/picks image
2. useImageUpload.uploadImage(file):
   - Client-side validate (size ≤ 5 MB, format ∈ JPEG/PNG/WEBP)
   - POST to /api/v1/uploads (student_question_image profile per ARCH §11.19)
   - Response: { storage_key, thumbnail_url } when ingested
3. ImageAttachmentChip renders with thumbnail_data_url
4. On submit: ImageRef[] passed to onSubmit
5. Parent component calls /api/v1/{feature}/questions with text + attached_images[]
6. Backend routes to vision-LLM if attached_images is non-empty (per ARCH §8.22)
```

**Locked rules:**
- EXIF stripped at ingest pipeline (server-side). Client doesn't preprocess.
- Max 3 images per send (enforced at UI + server).
- Drag-drop on mobile falls back to picker (unreliable).
- HEIC / BMP / TIFF rejected with toast "Format not supported — use JPEG, PNG, or WEBP."

---

## Voice flow

```
1. User taps mic icon
2. useVoiceTranscription.start():
   - Request mic permission (if denied → graceful degrade to text-only with toast)
   - Begin WebSocket to /api/v1/voice/stt
   - Server runs faster-whisper streaming; emits partial transcripts
3. Partial transcripts append to input.value in real time
4. User taps mic again OR 30s silence OR ESC → stop
5. Final transcript settles in input.value (user can edit before send)
```

**Locked rules:**
- Recording max 60 seconds per turn
- 30-second silence auto-stop
- Mic permission denied → graceful degrade to text-only mode with "permission needed" tooltip on mic icon
- Latency target: < 1s after stop; sustained > 3s alerts Platform Admin

---

## i18n keys (per `i18n_keys.md`)

All visible strings via next-intl. Keys live in `messages/<locale>/widgets.json`:

```json
{
  "hybrid_input": {
    "placeholder_default": "Ask a question...",
    "placeholder_highlight": "Explain: {text}",
    "mic_start": "Tap to record",
    "mic_stop": "Tap to stop",
    "image_attach": "Attach image",
    "image_too_large": "Image too large; max 5 MB",
    "image_format_unsupported": "Format not supported — use JPEG, PNG, or WEBP",
    "image_max_reached": "Max {count} images per question",
    "mic_permission_denied": "Permission needed to record",
    "send": "Send",
    "auto_send_countdown": "Sending in {seconds}s — tap to cancel",
    "voice_unavailable": "Voice not yet available in {language}"
  }
}
```

Available in all 4 launch languages (en, ur, sd, ps). RTL handled via Tailwind logical utilities (`me-`, `ms-`, `text-start`).

---

## What features CONSUME the widget

```tsx
// frontend/src/features/lectures/StudyMode/QuestionPanel.tsx
import { HybridInputWidget } from "@/components/shared/HybridInputWidget";

export function QuestionPanel({ lectureId, highlightedText }: Props) {
  const askQuestion = useMutation(/* ... */);
  
  return (
    <div>
      <HybridInputWidget
        initialText={highlightedText ? `Explain: ${highlightedText}` : ""}
        autoSendCountdownSeconds={highlightedText ? 3 : 0}
        voiceLanguage={userLocale}
        onSubmit={async (payload) => {
          await askQuestion.mutateAsync({
            lecture_id: lectureId,
            text: payload.text,
            attached_images: payload.attached_images,
          });
        }}
      />
      {/* answer stream below */}
    </div>
  );
}
```

The widget itself stays UI-only. Business logic (which API to call, how to interpret responses, source-badge rendering) belongs in the consuming feature component.

---

## Anti-patterns (DO NOT do these)

- ❌ Implementing voice transcription or image upload in a feature folder. Use this widget.
- ❌ Adding a fourth input mode (e.g., file upload, video). Image-only at launch; future extensions go through ARCHITECTURE.md amendment.
- ❌ Bypassing `useImageUpload` to hit MinIO directly. Always go through `/api/v1/uploads` per ARCH §11.
- ❌ Hardcoded English strings anywhere in the widget. All via next-intl.
- ❌ Inline styles. Tailwind utility classes only, per `component_template.md`.
- ❌ Buffering audio in memory for offline transcription. Always stream via WebSocket.

---

## Related

- ARCH §8.22 — Vision-LLM routing (where the backend decides text vs vision model)
- ARCH §11.19 — `student_question_image` upload profile
- Flow 6 v2 §3.5 — widget lifecycle spec
- Flow 5 §3.2/§3.5 — wizard chat sidebar consumer
- frontend-master/references/four_ui_states.md
- frontend-master/references/i18n_keys.md
