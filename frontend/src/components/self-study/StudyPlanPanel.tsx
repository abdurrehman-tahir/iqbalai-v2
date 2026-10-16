"use client";

/**
 * Conversational study-plan wizard + FullCalendar + .ics export (T-215–T-217).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { HybridInputWidget, type SubmitPayload } from "@/components/shared/HybridInputWidget";
import { Button } from "@/components/ui/button";
import { selfStudyApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function StudyPlanPanel() {
  const t = useTranslations("self_study.plan");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [gateError, setGateError] = useState<string | null>(null);
  const [refineOpen, setRefineOpen] = useState(false);

  const gateQuery = useQuery({
    queryKey: ["self-study", "prep-gate"],
    queryFn: () => selfStudyApi.prepBookGate(token!),
    enabled: mounted && !!token,
  });

  const convoQuery = useQuery({
    queryKey: ["self-study", "plan-convo"],
    queryFn: () => selfStudyApi.planConversationState(token!),
    enabled: mounted && !!token && gateQuery.data?.allowed === true,
    retry: false,
  });

  const activeQuery = useQuery({
    queryKey: ["self-study", "active-plan"],
    queryFn: () => selfStudyApi.getActivePlan(token!),
    enabled: mounted && !!token,
  });

  const googleQuery = useQuery({
    queryKey: ["self-study", "google-calendar"],
    queryFn: () => selfStudyApi.googleCalendarConfig(token!),
    enabled: mounted && !!token,
  });

  const answerMutation = useMutation({
    mutationFn: (answer: string) =>
      selfStudyApi.planConversationAnswer(token!, { answer }),
    onSuccess: () => {
      setGateError(null);
      void qc.invalidateQueries({ queryKey: ["self-study", "plan-convo"] });
    },
    onError: (err) => {
      setGateError(err instanceof Error ? err.message : t("error"));
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => selfStudyApi.generatePlan(token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["self-study", "active-plan"] });
      void qc.invalidateQueries({ queryKey: ["self-study", "plan-convo"] });
    },
    onError: (err) => {
      setGateError(err instanceof Error ? err.message : t("error"));
    },
  });

  const refineMutation = useMutation({
    mutationFn: (refinement_request: string) => {
      const planId = activeQuery.data?.plan?.id;
      if (!planId) throw new Error(t("no_plan"));
      return selfStudyApi.refinePlan(token!, planId, { refinement_request });
    },
    onSuccess: () => {
      setRefineOpen(false);
      void qc.invalidateQueries({ queryKey: ["self-study", "active-plan"] });
    },
    onError: (err) => {
      setGateError(err instanceof Error ? err.message : t("error"));
    },
  });

  const onConvoSubmit = async (payload: SubmitPayload): Promise<void> => {
    const text = payload.text.trim();
    if (!text) return;
    answerMutation.mutate(text);
  };

  const onRefineSubmit = async (payload: SubmitPayload): Promise<void> => {
    const text = payload.text.trim();
    if (!text) return;
    refineMutation.mutate(text);
  };

  const plan = activeQuery.data?.plan ?? null;
  const events = useMemo(() => {
    if (!plan) return [];
    return plan.items.map((item) => ({
      id: item.id,
      title: Array.isArray(item.tasks) && item.tasks[0] && typeof item.tasks[0] === "object"
        ? String((item.tasks[0] as { title?: string }).title ?? t("task_fallback"))
        : t("task_fallback"),
      start: item.start_date,
      end: item.end_date,
      backgroundColor: item.subject_color,
      borderColor: item.subject_color,
      extendedProps: { est_minutes: item.est_minutes },
    }));
  }, [plan, t]);

  const downloadIcs = () => {
    if (!plan || !token) return;
    void selfStudyApi.downloadPlanIcs(token, plan.id);
  };

  if (gateQuery.isLoading || activeQuery.isLoading) {
    return (
      <p className="text-sm text-gray-500" data-testid="study-plan-loading">
        {t("loading")}
      </p>
    );
  }

  if (gateQuery.isError) {
    return (
      <p className="text-sm text-red-600" role="alert" data-testid="study-plan-error">
        {t("error")}
      </p>
    );
  }

  const gate = gateQuery.data;
  const convo = convoQuery.data;

  return (
    <section
      className="rounded-lg border border-gray-200 bg-white p-4 space-y-4"
      data-testid="study-plan-panel"
      aria-label={t("title")}
    >
      <div>
        <h3 className="text-lg font-medium text-gray-900">{t("title")}</h3>
        <p className="text-xs text-gray-500">{t("help")}</p>
      </div>

      {gate && !gate.allowed && (
        <p className="text-sm text-amber-800" role="alert" data-testid="prep-book-gate-blocked">
          {gate.error_message ?? t("gate_blocked")}
        </p>
      )}

      {gate?.allowed && !plan && convo && !convo.complete && (
        <div className="space-y-2" data-testid="study-plan-conversation">
          <p className="text-sm text-gray-800">
            {t("step", { step: convo.step + 1, total: convo.total_steps })}
          </p>
          <p className="text-sm font-medium text-gray-900" data-testid="study-plan-question">
            {convo.question}
          </p>
          <HybridInputWidget
            onSubmit={onConvoSubmit}
            disabled={answerMutation.isPending}
            placeholder={t("answer_placeholder")}
          />
        </div>
      )}

      {gate?.allowed && convo?.complete && !plan && (
        <Button
          type="button"
          variant="primary"
          size="sm"
          loading={generateMutation.isPending}
          onClick={() => generateMutation.mutate()}
          data-testid="study-plan-generate"
        >
          {t("generate")}
        </Button>
      )}

      {gateError && (
        <p className="text-sm text-red-600" role="alert">
          {gateError}
        </p>
      )}

      {!plan && gate?.allowed && !convoQuery.isFetching && !convo && (
        <p className="text-sm text-gray-600" data-testid="study-plan-empty">
          {t("empty")}
        </p>
      )}

      {plan && (
        <div className="space-y-3" data-testid="study-plan-calendar">
          <p className="text-sm text-gray-700">
            {t("active_label", {
              granularity: plan.granularity_current,
              hours: plan.daily_hours,
            })}
          </p>
          <div className="overflow-x-auto" data-testid="fullcalendar-root">
            <FullCalendar
              plugins={[dayGridPlugin, timeGridPlugin]}
              initialView="dayGridMonth"
              headerToolbar={{
                left: "prev,next today",
                center: "title",
                right: "dayGridMonth,timeGridWeek",
              }}
              events={events}
              height="auto"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={downloadIcs}
              data-testid="study-plan-ics"
            >
              {t("export_ics")}
            </Button>
            {googleQuery.data?.enabled && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                data-testid="study-plan-google"
                disabled
              >
                {t("google_calendar")}
              </Button>
            )}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setRefineOpen((v) => !v)}
              data-testid="study-plan-refine-toggle"
            >
              {t("refine")}
            </Button>
          </div>
          {refineOpen && (
            <div data-testid="study-plan-refine">
              <HybridInputWidget
                onSubmit={onRefineSubmit}
                disabled={refineMutation.isPending}
                placeholder={t("refine_placeholder")}
              />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
