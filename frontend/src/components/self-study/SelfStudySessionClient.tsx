"use client";

/**
 * Self-study session — Flow 6 HybridInputWidget + LiveFeedbackPanel (T-210)
 * + daily goal #69 via widget / panel / EOD check (T-211).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { HybridInputWidget, type SubmitPayload } from "@/components/shared/HybridInputWidget";
import {
  LiveFeedbackPanel,
  type LiveFeedbackMetrics,
} from "@/app/student/lectures/[lectureId]/LiveFeedbackPanel";
import { ApiError, selfStudyApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { MaterialUploadPanel } from "@/components/self-study/MaterialUploadPanel";
import { StudyPlanPanel } from "@/components/self-study/StudyPlanPanel";
import { ReminderPreferencesPanel } from "@/components/self-study/ReminderPreferencesPanel";
import { SelfStudyPrivacyPanel } from "@/components/self-study/SelfStudyPrivacyPanel";

type Props = {
  /** Shared UI for school + independent (Flow 8 §3.11). */
  homeHref: string;
};

const FIVE_MINUTES_SECONDS = 5 * 60;

export function SelfStudySessionClient({ homeHref }: Props) {
  const t = useTranslations("self_study.session");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStartedAt, setSessionStartedAt] = useState<number | null>(null);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [lastAnswer, setLastAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingGoalText, setPendingGoalText] = useState<string | null>(null);
  const [showReplaceConfirm, setShowReplaceConfirm] = useState(false);
  const [showAchievementCheck, setShowAchievementCheck] = useState(false);

  const {
    data: goalToday,
    isLoading: goalLoading,
    isError: goalError,
  } = useQuery({
    queryKey: ["self-study", "goal"],
    queryFn: () => selfStudyApi.getTodayGoal(token!),
    enabled: mounted && !!token,
  });

  const goal = goalToday?.goal ?? null;

  const metrics: LiveFeedbackMetrics | null = sessionId
    ? {
        session_id: sessionId,
        time_on_topic_seconds: sessionStartedAt
          ? Math.max(0, Math.floor((Date.now() - sessionStartedAt) / 1000))
          : 0,
        questions_asked_this_session: lastAnswer ? 1 : 0,
        daily_goal_text: goal?.goal_text ?? null,
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

  const setGoalMutation = useMutation({
    mutationFn: (args: { goal_text: string; confirm_replace: boolean }) =>
      selfStudyApi.setGoal(token!, args),
    onSuccess: () => {
      setPendingGoalText(null);
      setShowReplaceConfirm(false);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["self-study", "goal"] });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409 && pendingGoalText) {
        setShowReplaceConfirm(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("goal_error"));
    },
  });

  const achievementMutation = useMutation({
    mutationFn: (args: {
      achieved?: boolean | null;
      skip: boolean;
      session_duration_seconds: number;
    }) => selfStudyApi.respondGoalAchievement(token!, args),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["self-study", "goal"] });
    },
  });

  const startMutation = useMutation({
    mutationFn: () => selfStudyApi.startSession(token!, {}),
    onSuccess: (data) => {
      setSessionId(data.id);
      setSessionStartedAt(Date.now());
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
      setSessionStartedAt(null);
      setLastAnswer(null);
      setShowAchievementCheck(false);
    },
  });

  const sessionDurationSeconds = (): number => {
    if (!sessionStartedAt) return 0;
    return Math.max(0, Math.floor((Date.now() - sessionStartedAt) / 1000));
  };

  const requestEndSession = () => {
    const duration = sessionDurationSeconds();
    if (
      goal &&
      goal.achievement_check_pending &&
      duration >= FIVE_MINUTES_SECONDS
    ) {
      setShowAchievementCheck(true);
      return;
    }
    endMutation.mutate();
  };

  const finishWithAchievement = (choice: "yes" | "no" | "skip") => {
    const duration = sessionDurationSeconds();
    achievementMutation.mutate(
      {
        achieved: choice === "skip" ? null : choice === "yes",
        skip: choice === "skip",
        session_duration_seconds: duration,
      },
      {
        onSettled: () => {
          endMutation.mutate();
        },
      },
    );
  };

  const onGoalSubmit = async (payload: SubmitPayload): Promise<void> => {
    const text = payload.text.trim();
    if (!text) return;
    setPendingGoalText(text);
    setGoalMutation.mutate({ goal_text: text, confirm_replace: false });
  };

  const confirmReplace = () => {
    if (!pendingGoalText) return;
    setGoalMutation.mutate({ goal_text: pendingGoalText, confirm_replace: true });
  };

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

      <section
        className="rounded-lg border border-gray-200 bg-white p-4 space-y-3"
        data-testid="self-study-goal-section"
        aria-label={t("goal_title")}
      >
        <h3 className="text-lg font-medium text-gray-900">{t("goal_title")}</h3>
        <p className="text-xs text-gray-500">{t("goal_help")}</p>
        {goalLoading && <p className="text-sm text-gray-500">{t("goal_loading")}</p>}
        {goalError && (
          <p className="text-sm text-red-600" role="alert">
            {t("goal_error")}
          </p>
        )}
        {!goalLoading && !goalError && goal && (
          <p className="text-sm text-gray-900" data-testid="self-study-goal-text">
            {t("goal_current", { text: goal.goal_text })}
          </p>
        )}
        {!goalLoading && !goalError && !goal && (
          <p className="text-sm text-gray-600" data-testid="self-study-goal-empty">
            {t("goal_empty")}
          </p>
        )}
        <HybridInputWidget
          onSubmit={onGoalSubmit}
          disabled={setGoalMutation.isPending}
          placeholder={t("goal_placeholder")}
        />
        {showReplaceConfirm && pendingGoalText && (
          <div
            className="rounded border border-amber-200 bg-amber-50 p-3 space-y-2"
            role="alertdialog"
            aria-labelledby="goal-replace-title"
            data-testid="self-study-goal-replace-confirm"
          >
            <p id="goal-replace-title" className="text-sm text-amber-900">
              {t("goal_replace_confirm")}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="sm"
                loading={setGoalMutation.isPending}
                onClick={confirmReplace}
                data-testid="self-study-goal-replace-yes"
              >
                {t("goal_replace_yes")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowReplaceConfirm(false);
                  setPendingGoalText(null);
                }}
                data-testid="self-study-goal-replace-no"
              >
                {t("goal_replace_no")}
              </Button>
            </div>
          </div>
        )}
      </section>

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
          loading={endMutation.isPending || achievementMutation.isPending}
          onClick={requestEndSession}
          data-testid="self-study-end-session"
        >
          {t("end")}
        </Button>
      )}

      {showAchievementCheck && (
        <div
          className="rounded-lg border border-gray-200 bg-white p-4 space-y-3"
          role="dialog"
          aria-labelledby="goal-achieve-title"
          data-testid="self-study-goal-achievement"
        >
          <p id="goal-achieve-title" className="text-sm font-medium text-gray-900">
            {t("goal_achieve_prompt")}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              size="sm"
              loading={achievementMutation.isPending}
              onClick={() => finishWithAchievement("yes")}
              data-testid="self-study-goal-achieve-yes"
            >
              {t("goal_achieve_yes")}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={achievementMutation.isPending}
              onClick={() => finishWithAchievement("no")}
              data-testid="self-study-goal-achieve-no"
            >
              {t("goal_achieve_no")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              loading={achievementMutation.isPending}
              onClick={() => finishWithAchievement("skip")}
              data-testid="self-study-goal-achieve-skip"
            >
              {t("goal_achieve_skip")}
            </Button>
          </div>
        </div>
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

      <MaterialUploadPanel />
      <StudyPlanPanel />
      <ReminderPreferencesPanel />
      <SelfStudyPrivacyPanel />

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
