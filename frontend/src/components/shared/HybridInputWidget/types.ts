/** Shared types for the hybrid text/voice/image input widget (T-155 / #57). */

export type VoiceLanguage = "en" | "ur" | "sd" | "ps";

export type ImageMimeType = "image/jpeg" | "image/png" | "image/webp";

export type ImageRef = {
  storage_key: string;
  mime_type: ImageMimeType;
  size_bytes: number;
  thumbnail_data_url: string;
};

export type SubmitPayload = {
  /** Typed + transcribed text combined. */
  text: string;
  /** 0–3 images (M-13). Empty in M-12. */
  attached_images: ImageRef[];
};

export type HybridInputWidgetProps = {
  onSubmit: (payload: SubmitPayload) => Promise<void>;
  placeholder?: string;
  disabled?: boolean;
  /** Prefill e.g. `Explain: [highlighted text]` for T-156. */
  initialText?: string;
  maxImages?: number;
  allowVoice?: boolean;
  /** M-12 default false; M-13 enables image attach. */
  allowImages?: boolean;
  voiceLanguage?: VoiceLanguage;
  /** Auto-send countdown for T-156 highlight→question (default 0 = off). */
  autoSendCountdownSeconds?: number;
  onAutoSendCancel?: () => void;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  onImageAttached?: (count: number) => void;
  /** Optional override for STT (tests / alternate tenants). */
  transcribeAudio?: (
    audio: Blob,
    language?: VoiceLanguage
  ) => Promise<{ transcript: string }>;
};
