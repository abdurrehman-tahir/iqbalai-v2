"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { studentOnboardingApi, parentChildLinksApi } from "@/lib/api";
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

  const { data: linkRequests } = useQuery({
    queryKey: ["student", "link-requests"],
    queryFn: () => parentChildLinksApi.listStudentPending(token!),
    enabled: mounted && !!token,
  });

  const dismissMutation = useMutation({
    mutationFn: () => studentOnboardingApi.dismissBanner(token ?? ""),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student"] }),
  });

  const approveMutation = useMutation({
    mutationFn: (linkId: string) => parentChildLinksApi.approveLinkRequest(token ?? "", linkId),
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

      <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
        <h3 className="text-lg font-medium text-gray-900">{t("link_requests_title")}</h3>
        {!linkRequests?.pending.length ? (
          <p className="text-sm text-gray-500">{t("link_requests_empty")}</p>
        ) : (
          <ul className="space-y-3">
            {linkRequests.pending.map((link) => (
              <li
                key={link.id}
                className="flex flex-wrap items-center justify-between gap-3 border border-gray-100 rounded-md p-3"
              >
                <p className="text-sm text-gray-800">
                  {t("link_request_from", { name: link.parent_name ?? "A parent" })}
                </p>
                <Button
                  variant="primary"
                  size="sm"
                  loading={approveMutation.isPending}
                  onClick={() => approveMutation.mutate(link.id)}
                >
                  {t("link_request_approve")}
                </Button>
              </li>
            ))}
          </ul>
        )}
        {approveMutation.isError && (
          <p className="text-sm text-red-600">{t("link_request_error")}</p>
        )}
      </section>
    </div>
  );
}
