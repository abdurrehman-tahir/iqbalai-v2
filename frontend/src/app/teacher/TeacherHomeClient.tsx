"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { teacherOnboardingApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { TeacherCapacitySettings } from "@/components/teacher/TeacherCapacitySettings";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";

export function TeacherHomeClient() {
  const t = useTranslations("teacher.dashboard");
  const { mounted, token } = useClientAuth();

  const { data: onboarding, isLoading } = useQuery({
    queryKey: ["teacher", "onboarding"],
    queryFn: () => teacherOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  return (
    <div className="space-y-6">
      <DashboardHeader title={t("title")} subtitle={t("subtitle")} />

      {isLoading && <Skeleton className="h-16 w-full" />}

      {!isLoading && onboarding?.profile_complete && !onboarding.ready_to_teach && (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          role="status"
        >
          {t("awaiting_assignment", { count: onboarding.assignment_count })}
        </div>
      )}

      {!isLoading && onboarding?.ready_to_teach && (
        <div
          className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900"
          role="status"
        >
          {t("ready_banner")}
        </div>
      )}

      {!isLoading && onboarding && <TeacherCapacitySettings onboarding={onboarding} />}

      <div className="rounded-2xl border border-dashed border-brand-200 bg-brand-50/40 p-12 text-center">
        <p className="text-lg font-medium text-gray-900">{t("title")}</p>
        <p className="mt-2 text-sm text-gray-500">{t("subtitle")}</p>
      </div>
    </div>
  );
}
