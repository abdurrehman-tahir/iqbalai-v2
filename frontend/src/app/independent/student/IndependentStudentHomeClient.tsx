"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { independentStudentOnboardingApi } from "@/lib/api";
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

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-green-200 bg-green-50 p-4">
        <p className="text-sm font-medium text-green-800">{t("ready_banner")}</p>
      </div>
      <p className="text-sm text-gray-600">{t("self_study_only")}</p>

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

      <a href="/independent/student/diagnostics" className="text-sm text-blue-600 hover:underline">
        {t("diagnostics_link")}
      </a>
    </div>
  );
}
