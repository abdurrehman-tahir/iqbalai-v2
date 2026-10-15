"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { independentStudentOnboardingApi, selfStudyApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function IndependentStudentHomeClient() {
  const t = useTranslations("independent.student.home");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [examDate, setExamDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [futureWarning, setFutureWarning] = useState<string | null>(null);

  const { data: onboarding } = useQuery({
    queryKey: ["independent-student", "onboarding"],
    queryFn: () => independentStudentOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  const {
    data: entry,
    isLoading: entryLoading,
    isError: entryError,
  } = useQuery({
    queryKey: ["self-study", "entry"],
    queryFn: () => selfStudyApi.getEntry(token!),
    enabled: mounted && !!token && !!onboarding?.ready_to_study,
  });

  const examDateMutation = useMutation({
    mutationFn: (value: string) => independentStudentOnboardingApi.setExamDate(token ?? "", value),
    onSuccess: (data) => {
      setError(null);
      setFutureWarning(data.future_date_warning ?? null);
      void qc.invalidateQueries({ queryKey: ["independent-student"] });
    },
    onError: (err) => {
      setFutureWarning(null);
      setError(err instanceof Error ? err.message : t("exam_date_error"));
    },
  });

  if (!onboarding?.ready_to_study) return null;

  const hasResumedState =
    !!entry?.state.last_goal_id ||
    !!entry?.state.last_material_id ||
    !!entry?.state.last_plan_view;

  return (
    <div className="space-y-4" data-testid="independent-self-study-dashboard">
      <div className="rounded-lg border border-green-200 bg-green-50 p-4">
        <p className="text-sm font-medium text-green-800">{t("ready_banner")}</p>
      </div>
      <p className="text-sm text-gray-600">{t("self_study_only")}</p>

      <section
        className="rounded-lg border border-gray-200 bg-white p-4 space-y-2"
        data-testid="self-study-section"
        aria-label={t("self_study_section_title")}
      >
        <h3 className="text-lg font-medium text-gray-900">{t("self_study_section_title")}</h3>
        <p className="text-sm text-gray-600">{t("self_study_section_body")}</p>
        {entryLoading && (
          <p className="text-xs text-gray-500" data-testid="self-study-entry-loading">
            {t("loading_entry")}
          </p>
        )}
        {entryError && (
          <p className="text-xs text-red-600" data-testid="self-study-entry-error" role="alert">
            {t("entry_error")}
          </p>
        )}
        {entry && (
          <>
            {hasResumedState && (
              <p className="text-xs text-gray-500" data-testid="self-study-resumed-state">
                {t("resumed_state_label")}
              </p>
            )}
            {!entry.subscription_gate.enforced && (
              <p className="text-xs text-gray-400" data-testid="self-study-subscription-gate">
                {t("subscription_gate_noop")}
              </p>
            )}
          </>
        )}
      </section>

      {onboarding.exam_date_passed && (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-3"
          data-testid="exam-date-passed-banner"
        >
          <p className="text-sm text-amber-900">{t("exam_date_passed_prompt")}</p>
          <Label htmlFor="ind-exam-date">{t("exam_date_label")}</Label>
          <Input
            id="ind-exam-date"
            type="date"
            value={examDate}
            onChange={(e) => setExamDate(e.target.value)}
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          {futureWarning && <p className="text-sm text-amber-800">{t("exam_date_future_warning")}</p>}
          <Button
            variant="primary"
            size="sm"
            loading={examDateMutation.isPending}
            disabled={!examDate}
            onClick={() => examDateMutation.mutate(examDate)}
          >
            {t("exam_date_save")}
          </Button>
        </div>
      )}

      <p className="flex flex-wrap gap-4">
        <a href="/independent/student/diagnostics" className="text-sm text-blue-600 hover:underline">
          {t("diagnostics_link")}
        </a>
        <a
          href="/independent/student/self-study"
          className="text-sm text-blue-600 hover:underline"
          data-testid="self-study-session-link"
        >
          {t("session_link")}
        </a>
      </p>
    </div>
  );
}
