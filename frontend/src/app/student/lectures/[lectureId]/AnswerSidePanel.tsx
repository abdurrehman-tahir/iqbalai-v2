"use client";

/**
 * AI answer side panel (T-159) + follow-ups (T-160).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  HybridInputWidget,
  type SubmitPayload,
} from "@/components/shared/HybridInputWidget";
import type { StudentQuestionRead } from "@/lib/api";

type Props = {
  question: StudentQuestionRead | null;
  streamingText?: string;
  open: boolean;
  onClose: () => void;
  onFollowUp: (content: string) => Promise<void>;
  onSourceBadgeClick?: (chunkId: string | null) => void;
};

function localeLang(locale: string): "en" | "ur" | "sd" | "ps" {
  if (locale === "ur" || locale === "sd" || locale === "ps") return locale;
  return "en";
}

export function AnswerSidePanel({
  question,
  streamingText,
  open,
  onClose,
  onFollowUp,
  onSourceBadgeClick,
}: Props) {
  const t = useTranslations("student.lecture_viewer");
  const locale = useLocale();
  const language = localeLang(locale);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [question?.conversations, streamingText, question?.answer_text]);

  const handleFollowUp = useCallback(
    async (payload: SubmitPayload) => {
      setBusy(true);
      try {
        await onFollowUp(payload.text);
      } finally {
        setBusy(false);
      }
    },
    [onFollowUp]
  );

  if (!open || !question) return null;

  const answerBody = streamingText ?? question.answer_text ?? null;
  const tagsPayload = question.answer_source_tags_jsonb;
  const spans = Array.isArray(tagsPayload)
    ? tagsPayload
    : tagsPayload && typeof tagsPayload === "object" && Array.isArray((tagsPayload as { spans?: unknown }).spans)
      ? ((tagsPayload as { spans: object[] }).spans as object[])
      : [];

  return (
    <aside
      className="fixed inset-y-0 end-0 z-40 flex w-full max-w-md flex-col border-s border-gray-200 bg-white shadow-xl"
      data-testid="answer-side-panel"
      dir="auto"
      aria-label={t("answer_panel_title")}
    >
      <header className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-900">{t("answer_panel_title")}</h2>
        <button
          type="button"
          className="text-sm text-gray-600 hover:underline"
          onClick={onClose}
          data-testid="answer-panel-close"
        >
          {t("close")}
        </button>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
        <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-800">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
            {t("your_question")}
          </p>
          <p>{question.question_text}</p>
          {question.classification ? (
            <p className="mt-2 text-xs text-gray-500" data-testid="question-classification">
              {t(`classification_${question.classification}`)}
            </p>
          ) : null}
        </div>

        {question.conversations.map((turn) => (
          <div
            key={turn.id}
            className={`rounded-md p-3 text-sm ${
              turn.role === "user" ? "bg-blue-50 text-blue-950" : "bg-emerald-50 text-emerald-950"
            }`}
            data-testid={`conversation-turn-${turn.role}`}
          >
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide opacity-70">
              {turn.role === "user" ? t("you") : t("ai_tutor")}
            </p>
            <p className="whitespace-pre-wrap">{turn.content}</p>
          </div>
        ))}

        {answerBody && question.conversations.every((c) => c.role !== "assistant") ? (
          <div
            className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-950"
            data-testid="answer-body"
          >
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide opacity-70">
              {t("ai_tutor")}
            </p>
            <p className="whitespace-pre-wrap">
              {answerBody}
              {streamingText ? <span className="animate-pulse">▍</span> : null}
            </p>
          </div>
        ) : null}

        {!answerBody && !streamingText ? (
          <p className="text-sm text-gray-500" data-testid="answer-waiting">
            {t("answer_preparing")}
          </p>
        ) : null}

        {spans.length > 0 ? (
          <div className="space-y-1" data-testid="answer-source-spans">
            <p className="text-xs font-medium text-gray-500">{t("sources")}</p>
            <ul className="flex flex-wrap gap-1">
              {spans.map((raw, i) => {
                const span = raw as {
                  badge?: string;
                  chunk_id?: string | null;
                  tier?: string;
                };
                return (
                  <li key={i}>
                    <button
                      type="button"
                      className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[11px] text-gray-700 hover:bg-gray-100"
                      data-testid="answer-source-badge"
                      data-tier={span.tier}
                      onClick={() => onSourceBadgeClick?.(span.chunk_id ?? null)}
                    >
                      {span.badge ?? span.tier ?? "source"}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      <footer className="border-t border-gray-200 p-3">
        <HybridInputWidget
          onSubmit={handleFollowUp}
          disabled={busy}
          allowVoice
          allowImages={false}
          voiceLanguage={language}
          placeholder={t("follow_up_placeholder")}
        />
      </footer>
    </aside>
  );
}
