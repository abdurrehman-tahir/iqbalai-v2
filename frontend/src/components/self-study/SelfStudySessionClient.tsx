"use client";

/**
 * Self-study session — reuses Flow 6 HybridInputWidget + LiveFeedbackPanel (T-210).
 * No re-implementation of widget / panel / adaptation / pipeline.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { HybridInputWidget, type SubmitPayload } from "@/components/shared/HybridInputWidget";
import {
  LiveFeedbackPanel,
  type LiveFeedbackMetrics,
} from "@/app/student/lectures/[lectureId]/LiveFeedbackPanel";
import { selfStudyApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";

type Props = {
  /** Shared UI for school + independent (Flow 8 §3.11). */
  homeHref: string;
};

export function SelfStudySessionClient({ homeHref }: Props) {
  const t = useTranslations("self_study.session");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [lastAnswer, setLastAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const metrics: LiveFeedbackMetrics | null = sessionId
    ? {
        session_id: sessionId,
        time_on_topic_seconds: 0,
        questions_asked_this_session: lastAnswer ? 1 : 0,
        panel_visible: true,
      }
    : null;

  const {
    data: dueDeck,
    isLoading: dueLoading,
    isError: dueError,
  } = useQuery({
    queryKey: ["self-study", "due-flashcards"],
    queryFn: () => selfStudyApi.listDueFlashcards(token!),
    enabled: mounted && !!token,
  });

  const startMutation = useMutation({
    mutationFn: () => selfStudyApi.startSession(token!, {}),
    onSuccess: (data) => {
      setSessionId(data.id);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["self-study"] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("start_error"));
    },
  });

  const endMutation = useMutation({
    mutationFn: () => selfStudyApi.endSession(token!, sessionId!),
    onSuccess: () => {
      setSessionId(null);
      setLastAnswer(null);
    },
  });

  const onSubmit = async (payload: SubmitPayload): Promise<void> => {
    // Full Pattern A Q&A lands in later tickets — widget reuse is the T-210 gate.
    setLastAnswer(payload.text.trim() || t("submitted_voice_or_image"));
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6" data-testid="self-study-session">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
          <p className="mt-1 text-sm text-gray-600">{t("subtitle")}</p>
        </div>
        <a href={homeHref} className="text-sm text-blue-600 hover:underline">
          {t("back_home")}
        </a>
      </div>

      {!sessionId ? (
        <Button
          variant="primary"
          size="md"
          loading={startMutation.isPending}
          onClick={() => startMutation.mutate()}
          data-testid="self-study-start-session"
        >
          {t("start")}
        </Button>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          loading={endMutation.isPending}
          onClick={() => endMutation.mutate()}
          data-testid="self-study-end-session"
        >
          {t("end")}
        </Button>
      )}

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      {sessionId && (
        <section
          className="rounded-lg border border-gray-200 bg-white p-4 space-y-3"
          aria-label={t("widget_label")}
          data-testid="self-study-hybrid-widget"
        >
          <HybridInputWidget
            onSubmit={onSubmit}
            disabled={false}
            placeholder={t("ask_placeholder")}
          />
          {lastAnswer && (
            <p className="text-sm text-gray-700" data-testid="self-study-last-submit">
              {t("last_submit", { text: lastAnswer })}
            </p>
          )}
        </section>
      )}

      <LiveFeedbackPanel
        sessionId={sessionId}
        metrics={metrics}
        collapsed={panelCollapsed}
        onToggleCollapsed={() => setPanelCollapsed((v) => !v)}
      />

      <section
        className="rounded-lg border border-gray-200 bg-white p-4 space-y-2"
        data-testid="due-flashcards-section"
        aria-label={t("due_title")}
      >
        <h3 className="text-lg font-medium text-gray-900">{t("due_title")}</h3>
        <p className="text-xs text-gray-500">{t("due_schedule_note")}</p>
        {dueLoading && <p className="text-sm text-gray-500">{t("due_loading")}</p>}
        {dueError && (
          <p className="text-sm text-red-600" role="alert">
            {t("due_error")}
          </p>
        )}
        {dueDeck && dueDeck.items.length === 0 && (
          <p className="text-sm text-gray-600" data-testid="due-flashcards-empty">
            {t("due_empty")}
          </p>
        )}
        {dueDeck && dueDeck.items.length > 0 && (
          <ul className="space-y-2" data-testid="due-flashcards-list">
            {dueDeck.items.map((card) => (
              <li
                key={card.id}
                className="rounded border border-gray-100 p-3 text-sm"
                data-testid="due-flashcard-item"
              >
                <p className="font-medium text-gray-900">{card.front_text}</p>
                <p className="mt-1 text-gray-600">{card.back_text}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
