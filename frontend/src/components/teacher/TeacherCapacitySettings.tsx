"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { teacherOnboardingApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TeacherOnboardingRead } from "@/lib/api/types";

const MIN_CAPACITY = 1;
const MAX_CAPACITY = 20;

interface TeacherCapacitySettingsProps {
  onboarding: TeacherOnboardingRead;
}

export function TeacherCapacitySettings({ onboarding }: TeacherCapacitySettingsProps) {
  const t = useTranslations("teacher.capacity");
  const { token } = useClientAuth();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(String(onboarding.teacher_capacity));

  useEffect(() => {
    setValue(String(onboarding.teacher_capacity));
  }, [onboarding.teacher_capacity]);

  const updateMutation = useMutation({
    mutationFn: (teacherCapacity: number) =>
      teacherOnboardingApi.updateCapacity(token!, { teacher_capacity: teacherCapacity }),
    onSuccess: (result) => {
      queryClient.setQueryData<TeacherOnboardingRead>(["teacher", "onboarding"], (prev) =>
        prev
          ? {
              ...prev,
              teacher_capacity: result.teacher_capacity,
              capacity_below_assignments: result.capacity_below_assignments,
            }
          : prev,
      );
    },
  });

  const parsed = Number.parseInt(value, 10);
  const outOfRange =
    Number.isNaN(parsed) || parsed < MIN_CAPACITY || parsed > MAX_CAPACITY;
  const belowAssignments =
    !Number.isNaN(parsed) && parsed < onboarding.assignment_count;

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-6">
      <h2 className="text-lg font-semibold text-gray-900">{t("title")}</h2>
      <p className="mt-1 text-sm text-gray-600">{t("subtitle")}</p>

      <form
        className="mt-4 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (outOfRange) return;
          updateMutation.mutate(parsed);
        }}
      >
        <div className="max-w-xs space-y-2">
          <Label htmlFor="teacher-capacity">{t("field_label")}</Label>
          <Input
            id="teacher-capacity"
            type="number"
            min={MIN_CAPACITY}
            max={MAX_CAPACITY}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            aria-describedby="teacher-capacity-help"
          />
          <p id="teacher-capacity-help" className="text-xs text-gray-500">
            {t("field_help", {
              min: MIN_CAPACITY,
              max: MAX_CAPACITY,
              count: onboarding.assignment_count,
            })}
          </p>
        </div>

        {belowAssignments && (
          <div
            className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            role="status"
          >
            {t("below_assignments_warning", {
              capacity: parsed,
              count: onboarding.assignment_count,
            })}
          </div>
        )}

        {onboarding.capacity_below_assignments && !belowAssignments && (
          <div
            className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            role="status"
          >
            {t("currently_below_assignments", { count: onboarding.assignment_count })}
          </div>
        )}

        <p className="text-xs text-gray-500">{t("admin_override_help")}</p>

        <Button type="submit" disabled={updateMutation.isPending || outOfRange}>
          {updateMutation.isPending ? t("saving") : t("save")}
        </Button>

        {updateMutation.isError && (
          <p className="text-sm text-red-700" role="alert">
            {updateMutation.error instanceof ApiError
              ? updateMutation.error.message
              : t("error_generic")}
          </p>
        )}

        {updateMutation.isSuccess && (
          <p className="text-sm text-green-700" role="status">
            {t("saved")}
          </p>
        )}
      </form>
    </section>
  );
}
