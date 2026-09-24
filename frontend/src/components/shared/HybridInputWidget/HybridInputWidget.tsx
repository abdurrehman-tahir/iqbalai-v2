"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImagePlusIcon, SendIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useClientAuth } from "@/hooks/use-client-auth";
import { studentVoiceApi } from "@/lib/api";
import { cn } from "@/lib/utils";

import { ImageAttachmentChip } from "./ImageAttachmentChip";
import { VoiceRecorder } from "./VoiceRecorder";
import { useImageUpload } from "./hooks/useImageUpload";
import { useVoiceTranscription } from "./hooks/useVoiceTranscription";
import type { HybridInputWidgetProps, VoiceLanguage } from "./types";

/**
 * Canonical hybrid text/voice/image input widget (#57 / T-155).
 * M-12: text + voice. M-13 extends image attach via allowImages.
 */
export function HybridInputWidget({
  onSubmit,
  placeholder,
  disabled = false,
  initialText = "",
  maxImages = 3,
  allowVoice = true,
  allowImages = false,
  voiceLanguage,
  autoSendCountdownSeconds = 0,
  onAutoSendCancel,
  onRecordingStart,
  onRecordingStop,
  onImageAttached,
  transcribeAudio: transcribeAudioProp,
}: HybridInputWidgetProps) {
  const t = useTranslations("widgets.hybrid_input");
  const { token } = useClientAuth();

  const [text, setText] = useState(initialText);
  const [submitting, setSubmitting] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);

  const prefixBeforeVoiceRef = useRef("");
  const textRef = useRef(text);
  const cancelledAutoSendRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const handleSubmitRef = useRef<() => Promise<void>>(async () => undefined);

  useEffect(() => {
    textRef.current = text;
  }, [text]);

  useEffect(() => {
    setText(initialText);
  }, [initialText]);

  const {
    images,
    error: imageError,
    uploading: imageUploading,
    uploadImage,
    removeImage,
    clearImages,
    clearError: clearImageError,
    maxImages: imageCap,
  } = useImageUpload({
    maxImages,
    enabled: allowImages,
    onAttached: onImageAttached,
  });

  const defaultTranscribe = useCallback(
    async (audio: Blob, language?: VoiceLanguage) => {
      return studentVoiceApi.transcribe(token ?? "cookie-session", audio, language);
    },
    [token]
  );

  const transcribeAudio = transcribeAudioProp ?? defaultTranscribe;

  const mergeVoiceIntoText = useCallback((sessionTranscript: string) => {
    const prefix = prefixBeforeVoiceRef.current.trimEnd();
    const next = prefix
      ? `${prefix}${prefix.endsWith(" ") ? "" : " "}${sessionTranscript}`
      : sessionTranscript;
    setText(next);
  }, []);

  const cancelAutoSend = useCallback(() => {
    cancelledAutoSendRef.current = true;
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    if (countdown !== null) {
      setCountdown(null);
      onAutoSendCancel?.();
    }
  }, [countdown, onAutoSendCancel]);

  const {
    isRecording,
    isTranscribing,
    permission,
    toggle: toggleRecording,
  } = useVoiceTranscription({
    language: voiceLanguage,
    enabled: allowVoice && !disabled && !submitting,
    transcribeAudio,
    onPartialTranscript: mergeVoiceIntoText,
    onFinalTranscript: mergeVoiceIntoText,
    onRecordingStart: () => {
      cancelAutoSend();
      prefixBeforeVoiceRef.current = textRef.current;
      onRecordingStart?.();
    },
    onRecordingStop,
    onError: (code) => {
      if (code === "mic_permission_denied") {
        setInlineError(t("mic_permission_denied"));
      } else if (code === "voice_unavailable") {
        setInlineError(
          t("voice_unavailable", { language: voiceLanguage ?? "en" })
        );
      } else {
        setInlineError(t("voice_error"));
      }
    },
  });

  const handleSubmit = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed && images.length === 0) return;
    if (submitting || disabled || isRecording) return;
    cancelAutoSend();
    setSubmitting(true);
    setInlineError(null);
    try {
      await onSubmit({ text: trimmed, attached_images: images });
      setText("");
      clearImages();
    } catch {
      setInlineError(t("send_error"));
    } finally {
      setSubmitting(false);
    }
  }, [
    cancelAutoSend,
    clearImages,
    disabled,
    images,
    isRecording,
    onSubmit,
    submitting,
    t,
    text,
  ]);

  handleSubmitRef.current = handleSubmit;

  // T-156: auto-send countdown when initialText is set with seconds > 0.
  useEffect(() => {
    cancelledAutoSendRef.current = false;
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    if (!autoSendCountdownSeconds || autoSendCountdownSeconds <= 0 || !initialText.trim()) {
      setCountdown(null);
      return;
    }
    setCountdown(autoSendCountdownSeconds);
    let remaining = autoSendCountdownSeconds;
    countdownIntervalRef.current = setInterval(() => {
      remaining -= 1;
      if (cancelledAutoSendRef.current) {
        if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
        return;
      }
      if (remaining <= 0) {
        if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
        setCountdown(null);
        void handleSubmitRef.current();
        return;
      }
      setCountdown(remaining);
    }, 1000);
    return () => {
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    };
  }, [autoSendCountdownSeconds, initialText]);

  const onTextChange = (value: string) => {
    cancelAutoSend();
    setText(value);
    setInlineError(null);
  };

  const imageErrorMessage = (() => {
    if (!imageError) return null;
    if (imageError === "too_large") return t("image_too_large");
    if (imageError === "format_unsupported") return t("image_format_unsupported");
    if (imageError === "max_reached") return t("image_max_reached", { count: imageCap });
    return t("image_not_ready");
  })();

  const busy = disabled || submitting || isTranscribing || imageUploading;
  const canSend = (text.trim().length > 0 || images.length > 0) && !busy && !isRecording;

  return (
    <div className="w-full space-y-2" data-testid="hybrid-input-widget">
      {allowImages && images.length > 0 ? (
        <div className="flex flex-wrap gap-2" data-testid="hybrid-image-row">
          {images.map((img) => (
            <ImageAttachmentChip
              key={img.storage_key}
              image={img}
              disabled={busy}
              removeLabel={t("image_remove")}
              onRemove={removeImage}
            />
          ))}
        </div>
      ) : null}

      <div
        className={cn(
          "flex items-end gap-1 rounded-lg border border-gray-300 bg-white p-2",
          "focus-within:border-brand-600 focus-within:ring-2 focus-within:ring-brand-600/30",
          isRecording && "border-red-300 ring-2 ring-red-200"
        )}
      >
        <textarea
          data-testid="hybrid-text-input"
          className={cn(
            "max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-900",
            "placeholder:text-gray-400 focus:outline-none disabled:opacity-50",
            "text-start"
          )}
          rows={2}
          value={text}
          disabled={busy}
          placeholder={placeholder ?? t("placeholder_default")}
          aria-label={placeholder ?? t("placeholder_default")}
          onChange={(e) => onTextChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSubmit();
            }
          }}
        />

        {allowVoice ? (
          <VoiceRecorder
            isRecording={isRecording}
            disabled={busy}
            permissionDenied={permission === "denied"}
            startLabel={t("mic_start")}
            stopLabel={t("mic_stop")}
            permissionDeniedLabel={t("mic_permission_denied")}
            onToggle={() => {
              cancelAutoSend();
              void toggleRecording();
            }}
          />
        ) : null}

        {allowImages ? (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              data-testid="hybrid-image-input"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) {
                  cancelAutoSend();
                  clearImageError();
                  void uploadImage(file);
                }
              }}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={busy || images.length >= imageCap}
              aria-label={t("image_attach")}
              title={t("image_attach")}
              data-testid="hybrid-image-button"
              onClick={() => fileInputRef.current?.click()}
            >
              <ImagePlusIcon className="size-5" aria-hidden="true" />
            </Button>
          </>
        ) : null}

        <Button
          type="button"
          variant="primary"
          size="icon"
          loading={submitting}
          disabled={!canSend}
          aria-label={t("send")}
          data-testid="hybrid-send-button"
          onClick={() => void handleSubmit()}
        >
          {!submitting ? <SendIcon className="size-5" aria-hidden="true" /> : null}
        </Button>
      </div>

      {isRecording ? (
        <p className="text-xs text-red-600" role="status" data-testid="hybrid-recording-hint">
          {t("mic_stop")}
        </p>
      ) : null}

      {countdown !== null && countdown > 0 ? (
        <button
          type="button"
          className="text-start text-xs text-amber-700 underline-offset-2 hover:underline"
          data-testid="hybrid-auto-send-countdown"
          onClick={cancelAutoSend}
        >
          {t("auto_send_countdown", { seconds: countdown })}
        </button>
      ) : null}

      {(inlineError || imageErrorMessage) && (
        <p className="text-xs text-red-600" role="alert" data-testid="hybrid-error">
          {inlineError ?? imageErrorMessage}
        </p>
      )}
    </div>
  );
}
