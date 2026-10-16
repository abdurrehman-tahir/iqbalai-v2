"use client";

/**
 * Reminder channel preferences — T-218 (push / email / SMS).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { selfStudyApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function ReminderPreferencesPanel() {
  const t = useTranslations("self_study.reminders");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const prefsQuery = useQuery({
    queryKey: ["self-study", "reminder-prefs"],
    queryFn: () => selfStudyApi.getReminderPreferences(token!),
    enabled: mounted && !!token,
  });

  const mutation = useMutation({
    mutationFn: (patch: {
      push_enabled?: boolean;
      email_enabled?: boolean;
      sms_enabled?: boolean;
    }) => selfStudyApi.putReminderPreferences(token!, patch),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["self-study", "reminder-prefs"] });
    },
  });

  if (prefsQuery.isLoading) {
    return (
      <p className="text-sm text-gray-500" data-testid="reminders-loading">
        {t("loading")}
      </p>
    );
  }

  if (prefsQuery.isError || !prefsQuery.data) {
    return (
      <p className="text-sm text-red-600" role="alert" data-testid="reminders-error">
        {t("error")}
      </p>
    );
  }

  const prefs = prefsQuery.data;

  return (
    <section
      className="rounded-lg border border-gray-200 bg-white p-4 space-y-3"
      data-testid="reminder-preferences"
      aria-label={t("title")}
    >
      <div>
        <h3 className="text-lg font-medium text-gray-900">{t("title")}</h3>
        <p className="text-xs text-gray-500">{t("help")}</p>
      </div>
      {(
        [
          ["push_enabled", "push"] as const,
          ["email_enabled", "email"] as const,
          ["sms_enabled", "sms"] as const,
        ] as const
      ).map(([key, labelKey]) => (
        <label key={key} className="flex items-center gap-2 text-sm text-gray-800">
          <input
            type="checkbox"
            checked={prefs[key]}
            disabled={mutation.isPending}
            data-testid={`reminder-${labelKey}`}
            onChange={(e) => mutation.mutate({ [key]: e.target.checked })}
          />
          {t(labelKey)}
        </label>
      ))}
    </section>
  );
}
