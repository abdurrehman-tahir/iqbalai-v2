"use client";

/**
 * Highlight → auto-prompt question box (T-156).
 * Prefills "Explain: …", 3s auto-send unless the student interacts.
 */

import { useCallback, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  HybridInputWidget,
  type SubmitPayload,
} from "@/components/shared/HybridInputWidget";

export type HighlightSelection = {
  text: string;
  paragraphId: string | null;
  sourceChunkId: string | null;
};

type Props = {
  selection: HighlightSelection;
  onCancel: () => void;
  onSubmit: (payload: {
    question_text: string;
    highlight_text: string;
    paragraph_id: string | null;
    source_chunk_id: string | null;
    question_language: "en" | "ur" | "sd" | "ps";
  }) => Promise<void>;
};

function localeLang(locale: string): "en" | "ur" | "sd" | "ps" {
  if (locale === "ur" || locale === "sd" || locale === "ps") return locale;
  return "en";
}

export function HighlightQuestionBox({ selection, onCancel, onSubmit }: Props) {
  const t = useTranslations("student.lecture_viewer");
  const locale = useLocale();
  const language = localeLang(locale);
  const [busy, setBusy] = useState(false);

  const initialText = useMemo(
    () => t("explain_prefix", { text: selection.text }),
    [selection.text, t]
  );

  const handleSubmit = useCallback(
    async (payload: SubmitPayload) => {
      setBusy(true);
      try {
        await onSubmit({
          question_text: payload.text,
          highlight_text: selection.text,
          paragraph_id: selection.paragraphId,
          source_chunk_id: selection.sourceChunkId,
          question_language: language,
        });
      } finally {
        setBusy(false);
      }
    },
    [language, onSubmit, selection]
  );

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-30 border-t border-amber-200 bg-amber-50/95 p-3 shadow-lg backdrop-blur sm:inset-x-auto sm:bottom-4 sm:start-1/2 sm:w-full sm:max-w-xl sm:-translate-x-1/2 sm:rounded-lg sm:border"
      data-testid="highlight-question-box"
      dir="auto"
      role="dialog"
      aria-label={t("ask_question")}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-amber-900">{t("highlight_prompt")}</p>
        <button
          type="button"
          className="text-xs text-gray-600 hover:underline"
          onClick={onCancel}
          data-testid="highlight-question-cancel"
        >
          {t("cancel")}
        </button>
      </div>
      <HybridInputWidget
        initialText={initialText}
        autoSendCountdownSeconds={3}
        onAutoSendCancel={() => undefined}
        onSubmit={handleSubmit}
        disabled={busy}
        allowVoice
        allowImages={false}
        voiceLanguage={language}
        placeholder={t("question_placeholder")}
      />
    </div>
  );
}
