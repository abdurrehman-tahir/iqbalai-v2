"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { independentTeacherOnboardingApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function IndependentTeacherHomeClient() {
  const t = useTranslations("independent.teacher.home");
  const { mounted, token } = useClientAuth();

  const { data: onboarding } = useQuery({
    queryKey: ["independent-teacher", "onboarding"],
    queryFn: () => independentTeacherOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  if (!onboarding?.ready_to_use) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-green-200 bg-green-50 p-4">
        <p className="text-sm font-medium text-green-800">{t("ready_banner")}</p>
      </div>
      <p className="text-sm text-gray-600">{t("welcome", { name: onboarding.profile?.name ?? "" })}</p>
    </div>
  );
}
