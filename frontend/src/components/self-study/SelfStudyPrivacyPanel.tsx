"use client";

/**
 * #72 Share self-study activity with teacher — T-220 (school only; hidden for independent).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { studentPrivacyApi, selfStudyApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function SelfStudyPrivacyPanel() {
  const t = useTranslations("self_study.privacy");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const entryQuery = useQuery({
    queryKey: ["self-study", "entry"],
    queryFn: () => selfStudyApi.getEntry(token!),
    enabled: mounted && !!token,
  });

  const isSchool = entryQuery.data?.tenant_type === "school";

  const shareQuery = useQuery({
    queryKey: ["self-study", "teacher-share"],
    queryFn: () => studentPrivacyApi.getTeacherShare(token!),
    enabled: mounted && !!token && isSchool,
  });

  const mutation = useMutation({
    mutationFn: (share: boolean) =>
      studentPrivacyApi.setTeacherShare(token!, share ? "share" : "private"),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["self-study", "teacher-share"] });
    },
  });

  if (entryQuery.isLoading) {
    return (
      <p className="text-sm text-gray-500" data-testid="privacy-loading">
        {t("loading")}
      </p>
    );
  }

  if (!isSchool) {
    return null;
  }

  if (shareQuery.isError) {
    return (
      <p className="text-sm text-red-600" role="alert" data-testid="privacy-error">
        {t("error")}
      </p>
    );
  }

  const shared = shareQuery.data?.teacher_activity_share !== "private";

  return (
    <section
      className="rounded-lg border border-gray-200 bg-white p-4 space-y-2"
      data-testid="self-study-privacy"
      aria-label={t("title")}
    >
      <h3 className="text-lg font-medium text-gray-900">{t("title")}</h3>
      <p className="text-xs text-gray-500">{t("help")}</p>
      <p className="text-xs text-gray-500">{t("aggregate_note")}</p>
      {shareQuery.isLoading ? (
        <p className="text-sm text-gray-500">{t("loading")}</p>
      ) : (
        <label className="flex items-center gap-2 text-sm text-gray-800">
          <input
            type="checkbox"
            checked={shared}
            disabled={mutation.isPending}
            data-testid="privacy-share-toggle"
            onChange={(e) => mutation.mutate(e.target.checked)}
          />
          {t("share_label")}
        </label>
      )}
    </section>
  );
}
