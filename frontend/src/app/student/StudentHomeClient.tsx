"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { studentOnboardingApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";

export function StudentHomeClient() {
  const t = useTranslations("student.dashboard");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const { data: onboarding } = useQuery({
    queryKey: ["student", "onboarding"],
    queryFn: () => studentOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  const dismissMutation = useMutation({
    mutationFn: () => studentOnboardingApi.dismissBanner(token ?? ""),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student"] }),
  });

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("subtitle")}</p>
      </div>

      {onboarding?.show_complete_profile_banner && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex items-start justify-between gap-4">
          <p className="text-sm text-amber-900">{t("profile_banner")}</p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => dismissMutation.mutate()}
            disabled={dismissMutation.isPending}
          >
            {t("profile_banner_dismiss")}
          </Button>
        </div>
      )}
    </div>
  );
}
