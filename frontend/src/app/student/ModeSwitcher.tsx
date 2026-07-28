"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { studentModeApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { StudyModeLiteral } from "@/lib/api/types";

/**
 * School-student Lecture ⇄ Self-Study switcher (T-101 / flow-4 §3.4).
 * Independent shells must not render this component.
 */
export function ModeSwitcher() {
  const t = useTranslations("student.mode");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["student", "mode"],
    queryFn: () => studentModeApi.getMode(token!),
    enabled: mounted && !!token,
  });

  const switchMutation = useMutation({
    mutationFn: (active_mode: StudyModeLiteral) => {
      const leaving =
        data?.active_mode === "lecture"
          ? data.mode_state.lecture
          : data?.mode_state.self_study;
      return studentModeApi.setMode(token ?? "", {
        active_mode,
        leaving_mode_state: leaving ?? {},
      });
    },
    onSuccess: (next) => {
      qc.setQueryData(["student", "mode"], next);
      void qc.invalidateQueries({ queryKey: ["student"] });
    },
  });

  if (!mounted || isLoading) {
    return (
      <div
        className="h-10 w-56 animate-pulse rounded-md bg-gray-100"
        role="status"
        aria-label={t("loading")}
      />
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center gap-2" role="alert">
        <p className="text-sm text-red-600">{t("error")}</p>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void refetch()}
          disabled={isFetching}
        >
          {t("retry")}
        </Button>
      </div>
    );
  }

  const active = data.active_mode;
  const busy = switchMutation.isPending;

  return (
    <div className="flex flex-col items-end gap-1">
      <div
        role="radiogroup"
        aria-label={t("label")}
        className="inline-flex rounded-md border border-gray-200 bg-gray-50 p-1"
      >
        {(["lecture", "self_study"] as const).map((mode) => {
          const selected = active === mode;
          return (
            <button
              key={mode}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={busy || selected}
              className={cn(
                "min-h-11 min-w-[6.5rem] rounded px-3 py-2 text-sm font-medium transition-colors",
                selected
                  ? "bg-white text-brand-700 shadow-sm"
                  : "text-gray-600 hover:bg-white/60",
              )}
              onClick={() => switchMutation.mutate(mode)}
            >
              {t(mode)}
            </button>
          );
        })}
      </div>
      {switchMutation.isError && (
        <p className="text-xs text-red-600" role="alert">
          {t("switch_error")}
        </p>
      )}
    </div>
  );
}
