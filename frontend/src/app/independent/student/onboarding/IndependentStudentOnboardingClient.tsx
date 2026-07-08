"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { independentStudentOnboardingApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const profileSchema = z.object({
  exam_date: z.string().min(1),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

export function IndependentStudentOnboardingClient() {
  const t = useTranslations("independent.student.onboarding");
  const router = useRouter();
  const qc = useQueryClient();
  const { token } = useClientAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { exam_date: "" },
  });

  const completeMutation = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      independentStudentOnboardingApi.completeProfile(token ?? "", values),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["independent-student"] });
      router.replace("/independent/student");
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError ? err.message : t("error_generic"));
    },
  });

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      <p className="text-sm text-gray-600 rounded-md bg-brand-50 border border-brand-100 p-3">
        {t("diagnostic_deferred")}
      </p>

      {formError && (
        <p
          className="text-sm text-red-600 rounded-md bg-red-50 border border-red-200 p-3"
          role="alert"
        >
          {formError}
        </p>
      )}

      <form
        onSubmit={form.handleSubmit((values) => completeMutation.mutate(values))}
        className="space-y-4"
      >
        <div>
          <Label htmlFor="exam-date" required>
            {t("exam_date_label")}
          </Label>
          <Input id="exam-date" type="date" {...form.register("exam_date")} />
        </div>
        <Button type="submit" variant="primary" size="md" loading={completeMutation.isPending}>
          {t("submit")}
        </Button>
      </form>
    </div>
  );
}
