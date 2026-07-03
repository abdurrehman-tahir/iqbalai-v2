"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { independentTeacherOnboardingApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const LANGUAGES = ["en", "ur", "sd", "ps"] as const;

const profileSchema = z.object({
  name: z.string().min(1).max(255),
  language_preference: z.enum(LANGUAGES),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

export function IndependentTeacherOnboardingClient() {
  const t = useTranslations("independent.teacher.onboarding");
  const router = useRouter();
  const qc = useQueryClient();
  const { token } = useClientAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: "", language_preference: "en" },
  });

  const completeMutation = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      independentTeacherOnboardingApi.completeProfile(token ?? "", values),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["independent-teacher"] });
      router.replace("/independent/teacher");
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        setFormError(err.message);
        return;
      }
      setFormError(t("error_generic"));
    },
  });

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {formError && (
        <p className="text-sm text-red-600 rounded-md bg-red-50 border border-red-200 p-3" role="alert">
          {formError}
        </p>
      )}

      <form
        onSubmit={form.handleSubmit((values) => completeMutation.mutate(values))}
        className="space-y-4"
      >
        <div>
          <Label htmlFor="name" required>
            {t("name_label")}
          </Label>
          <Input id="name" {...form.register("name")} />
        </div>

        <div>
          <Label htmlFor="language" required>
            {t("language_label")}
          </Label>
          <select
            id="language"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            {...form.register("language_preference")}
          >
            {LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>
                {t(`language_${lang}` as "language_en")}
              </option>
            ))}
          </select>
        </div>

        <Button type="submit" variant="primary" size="md" loading={completeMutation.isPending}>
          {t("submit")}
        </Button>
      </form>
    </div>
  );
}
