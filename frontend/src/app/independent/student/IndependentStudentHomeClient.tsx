"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { independentStudentOnboardingApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function IndependentStudentHomeClient() {
  const t = useTranslations("independent.student.home");
  const { mounted, token } = useClientAuth();

  const { data: onboarding } = useQuery({
    queryKey: ["independent-student", "onboarding"],
    queryFn: () => independentStudentOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  if (!onboarding?.ready_to_study) return null;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-green-200 bg-green-50 p-4">
        <p className="text-sm font-medium text-green-800">{t("ready_banner")}</p>
      </div>
      <p className="text-sm text-gray-600">{t("self_study_only")}</p>
      <a href="/independent/student/diagnostics" className="text-sm text-blue-600 hover:underline">
        {t("diagnostics_link")}
      </a>
    </div>
  );
}
