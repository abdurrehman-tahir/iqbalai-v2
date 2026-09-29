"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

export type LiveFeedbackMetrics = {
  session_id?: string;
  time_on_topic_seconds?: number;
  questions_asked_this_session?: number;
  mastery_estimate?: number | null;
  daily_goal_status?: string | null;
  panel_visible?: boolean;
  stuck_nudge?: {
    should_show?: boolean;
    seconds_on_page?: number;
    already_fired?: boolean;
  };
};

type Props = {
  sessionId: string | null;
  metrics: LiveFeedbackMetrics | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
};

function formatDuration(seconds: number, locale: string): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return new Intl.NumberFormat(locale).format(m) + ":" + String(s).padStart(2, "0");
}

export function LiveFeedbackPanel({
  sessionId,
  metrics,
  collapsed,
  onToggleCollapsed,
}: Props) {
  const t = useTranslations("student.lecture_viewer.live_feedback");
  const locale = useLocale();
  const dir = locale === "ur" || locale === "sd" || locale === "ps" ? "rtl" : "ltr";

  const visible = Boolean(metrics?.panel_visible && sessionId);
  if (!visible || !metrics) return null;

  const timeOnTopic = metrics.time_on_topic_seconds ?? 0;
  const questions = metrics.questions_asked_this_session ?? 0;

  return (
    <aside
      className="fixed bottom-4 z-40 max-w-sm rounded-lg border border-gray-200 bg-white/95 p-3 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-white/90 end-4"
      data-testid="live-feedback-panel"
      dir={dir}
      aria-live="polite"
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-gray-900">{t("title")}</h2>
        <button
          type="button"
          className="text-xs text-gray-600 underline"
          onClick={onToggleCollapsed}
          data-testid="live-feedback-collapse"
          aria-expanded={!collapsed}
        >
          {collapsed ? t("expand") : t("collapse")}
        </button>
      </div>
      {!collapsed ? (
        <dl className="space-y-2 text-sm text-gray-700">
          <div className="flex justify-between gap-4">
            <dt>{t("time_on_topic")}</dt>
            <dd data-testid="live-feedback-time">
              {formatDuration(timeOnTopic, locale)}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>{t("questions_asked")}</dt>
            <dd data-testid="live-feedback-questions">{questions}</dd>
          </div>
          {/* mastery / daily_goal remain hidden until Flow 9 / Flow 8 ship */}
        </dl>
      ) : null}
    </aside>
  );
}

type StuckProps = {
  open: boolean;
  onDismiss: () => void;
  onRephrase: () => void;
  onListConcepts: () => void;
  onSwitchVoice: () => void;
};

export function StuckNudge({
  open,
  onDismiss,
  onRephrase,
  onListConcepts,
  onSwitchVoice,
}: StuckProps) {
  const t = useTranslations("student.lecture_viewer.stuck_nudge");
  const locale = useLocale();
  const dir = locale === "ur" || locale === "sd" || locale === "ps" ? "rtl" : "ltr";
  const [shownOnce, setShownOnce] = useState(false);

  useEffect(() => {
    if (open) setShownOnce(true);
  }, [open]);

  const shouldRender = open || shownOnce;
  if (!shouldRender || !open) return null;

  return (
    <div
      className="fixed bottom-24 z-50 max-w-sm rounded-lg border border-amber-200 bg-amber-50 p-3 shadow-md end-4"
      data-testid="stuck-nudge"
      role="status"
      dir={dir}
    >
      <p className="mb-2 text-sm text-amber-950">{t("message")}</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded bg-amber-700 px-2 py-1 text-xs text-white"
          data-testid="stuck-nudge-rephrase"
          onClick={() => {
            onRephrase();
            onDismiss();
          }}
        >
          {t("rephrase")}
        </button>
        <button
          type="button"
          className="rounded bg-amber-700 px-2 py-1 text-xs text-white"
          data-testid="stuck-nudge-concepts"
          onClick={() => {
            onListConcepts();
            onDismiss();
          }}
        >
          {t("list_concepts")}
        </button>
        <button
          type="button"
          className="rounded bg-amber-700 px-2 py-1 text-xs text-white"
          data-testid="stuck-nudge-voice"
          onClick={() => {
            onSwitchVoice();
            onDismiss();
          }}
        >
          {t("switch_voice")}
        </button>
        <button
          type="button"
          className="rounded px-2 py-1 text-xs text-amber-900 underline"
          data-testid="stuck-nudge-dismiss"
          onClick={onDismiss}
        >
          {t("dismiss")}
        </button>
      </div>
    </div>
  );
}

export function useLiveFeedbackSocket(
  enabled: boolean,
  onMetrics: (m: LiveFeedbackMetrics) => void,
): void {
  const wsBase = useMemo(() => {
    const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
    try {
      const u = new URL(api);
      u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
      u.pathname = "/ws/v1/live-feedback";
      u.search = "";
      return u.toString();
    } catch {
      return "ws://localhost:8000/ws/v1/live-feedback";
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(wsBase);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as {
            type?: string;
            event?: string;
            payload?: LiveFeedbackMetrics;
          };
          const type = msg.type || msg.event;
          if (type === "live_feedback_update" && msg.payload) {
            onMetrics(msg.payload);
          }
        } catch {
          /* ignore malformed */
        }
      };
      ws.onclose = () => {
        if (!closed) retry = setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, [enabled, onMetrics, wsBase]);
}
