"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { studentOnboardingApi, tosApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const LANGUAGES = ["en", "ur", "sd", "ps"] as const;

const profileSchema = z.object({
  display_name: z.string().min(1).max(255),
  language_preference: z.enum(LANGUAGES),
  accept_tos: z.boolean().refine((v) => v, { message: "tos_required" }),
});

const modeSchema = z
  .object({
    lecture_mode: z.boolean(),
    self_study_mode: z.boolean(),
  })
  .refine((d) => d.lecture_mode || d.self_study_mode, { message: "mode_required" });

type ProfileFormValues = z.infer<typeof profileSchema>;
type ModeFormValues = z.infer<typeof modeSchema>;

export function StudentOnboardingClient() {
  const t = useTranslations("student.onboarding");
  const router = useRouter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const { data: onboarding, isLoading } = useQuery({
    queryKey: ["student", "onboarding"],
    queryFn: () => studentOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  const { data: tos } = useQuery({
    queryKey: ["tos", "current"],
    queryFn: () => tosApi.getCurrent(token ?? ""),
    enabled: mounted && !!token,
  });

  const profileForm = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      display_name: onboarding?.profile?.display_name ?? "",
      language_preference: "en",
      accept_tos: false,
    },
  });

  const modeForm = useForm<ModeFormValues>({
    resolver: zodResolver(modeSchema),
    defaultValues: { lecture_mode: true, self_study_mode: false },
  });

  const profileMutation = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      studentOnboardingApi.completeProfileBasic(token ?? "", {
        display_name: values.display_name,
        language_preference: values.language_preference,
        tos_version_id: tos!.id,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["student"] });
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError ? err.message : t("error_generic"));
    },
  });

  const modeMutation = useMutation({
    mutationFn: (values: ModeFormValues) =>
      studentOnboardingApi.selectModes(token ?? "", values),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["student"] });
      router.replace("/student");
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError ? err.message : t("error_generic"));
    },
  });

  if (isLoading || !onboarding) {
    return <Skeleton className="mx-auto h-64 max-w-lg w-full" />;
  }

  if (onboarding.ready_to_study) {
    router.replace("/student");
    return null;
  }

  const showModes = onboarding.profile_basic_complete;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">
          {showModes ? t("modes_title") : t("title")}
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          {showModes ? t("modes_subtitle") : t("subtitle")}
        </p>
      </div>

      {formError && (
        <p className="text-sm text-red-600 rounded-md bg-red-50 border border-red-200 p-3" role="alert">
          {formError}
        </p>
      )}

      {!showModes ? (
        <form
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-6"
          onSubmit={profileForm.handleSubmit((values) => {
            setFormError(null);
            profileMutation.mutate(values);
          })}
        >
          <div>
            <Label htmlFor="student-name" required>{t("name_label")}</Label>
            <Input id="student-name" {...profileForm.register("display_name")} />
          </div>
          <div>
            <Label htmlFor="student-language" required>{t("language_label")}</Label>
            <select
              id="student-language"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              {...profileForm.register("language_preference")}
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>{t(`language_${lang}`)}</option>
              ))}
            </select>
          </div>
          <label className="flex items-start gap-2 text-sm text-gray-700">
            <input type="checkbox" {...profileForm.register("accept_tos")} className="mt-1" />
            <span>{t("tos_label")}</span>
          </label>
          <Button type="submit" variant="primary" loading={profileMutation.isPending}>
            {t("profile_submit")}
          </Button>
        </form>
      ) : (
        <form
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-6"
          onSubmit={modeForm.handleSubmit((values) => {
            setFormError(null);
            modeMutation.mutate(values);
          })}
        >
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...modeForm.register("lecture_mode")} />
            {t("lecture_mode")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...modeForm.register("self_study_mode")} />
            {t("self_study_mode")}
          </label>
          <Button type="submit" variant="primary" loading={modeMutation.isPending}>
            {t("modes_submit")}
          </Button>
        </form>
      )}
    </div>
  );
}
