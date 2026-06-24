"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { teacherOnboardingApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";

const LANGUAGES = ["en", "ur", "sd", "ps"] as const;
const PROVINCES = [
  "Punjab",
  "Sindh",
  "Khyber Pakhtunkhwa",
  "Balochistan",
  "ICT",
  "GB",
  "AJK",
] as const;

const profileSchema = z.object({
  name: z.string().min(1).max(255),
  region_province: z.enum(PROVINCES),
  region_district: z.string().max(200).optional(),
  bio: z.string().max(500).optional(),
  language_preference: z.enum(LANGUAGES),
  subject_ids: z.array(z.string()).min(1),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

export function TeacherOnboardingClient() {
  const t = useTranslations("teacher.onboarding");
  const router = useRouter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const { data: subjects, isLoading, isError, refetch } = useQuery({
    queryKey: ["teacher", "subject-options"],
    queryFn: () => teacherOnboardingApi.listSubjectOptions(token!),
    enabled: mounted && !!token,
  });

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: "",
      region_province: "Punjab",
      region_district: "",
      bio: "",
      language_preference: "en",
      subject_ids: [],
    },
  });

  const completeMutation = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      teacherOnboardingApi.completeProfile(token ?? "", {
        name: values.name,
        region_province: values.region_province,
        region_district: values.region_district || null,
        bio: values.bio || null,
        language_preference: values.language_preference,
        subject_ids: values.subject_ids,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["teacher"] });
      router.replace("/teacher");
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        setFormError(err.message);
        return;
      }
      setFormError(t("error_generic"));
    },
  });

  function toggleSubject(subjectId: string) {
    const current = form.getValues("subject_ids");
    const next = current.includes(subjectId)
      ? current.filter((id) => id !== subjectId)
      : [...current, subjectId];
    form.setValue("subject_ids", next, { shouldValidate: true });
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError) {
    return <ErrorState description={t("load_error")} onRetry={() => refetch()} retryLabel={t("retry")} />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("subtitle")}</p>
      </div>

      <form
        className="space-y-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
        onSubmit={form.handleSubmit((values) => {
          setFormError(null);
          completeMutation.mutate(values);
        })}
      >
        <div>
          <Label htmlFor="name" required>
            {t("name_label")}
          </Label>
          <Input id="name" {...form.register("name")} />
          {form.formState.errors.name && (
            <p className="mt-1 text-sm text-red-600">{t("name_required")}</p>
          )}
        </div>

        <div>
          <Label htmlFor="region_province" required>
            {t("province_label")}
          </Label>
          <select
            id="region_province"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            {...form.register("region_province")}
          >
            {PROVINCES.map((province) => (
              <option key={province} value={province}>
                {province}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label htmlFor="region_district">{t("district_label")}</Label>
          <Input id="region_district" {...form.register("region_district")} />
        </div>

        <div>
          <Label htmlFor="language_preference" required>
            {t("language_label")}
          </Label>
          <select
            id="language_preference"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            {...form.register("language_preference")}
          >
            {LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>
                {t(`language_${lang}`)}
              </option>
            ))}
          </select>
        </div>

        <fieldset>
          <legend className="text-sm font-medium text-gray-900">{t("subjects_label")}</legend>
          <p className="mt-1 text-sm text-gray-500">{t("subjects_help")}</p>
          <ul className="mt-3 space-y-2">
            {(subjects ?? []).map((subject) => (
              <li key={subject.id}>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.watch("subject_ids").includes(subject.id)}
                    onChange={() => toggleSubject(subject.id)}
                  />
                  {subject.name}
                </label>
              </li>
            ))}
          </ul>
          {form.formState.errors.subject_ids && (
            <p className="mt-1 text-sm text-red-600">{t("subjects_required")}</p>
          )}
          {(subjects ?? []).length === 0 && (
            <p className="mt-2 text-sm text-amber-700">{t("subjects_empty")}</p>
          )}
        </fieldset>

        <div>
          <Label htmlFor="bio">{t("bio_label")}</Label>
          <textarea
            id="bio"
            rows={4}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            {...form.register("bio")}
          />
        </div>

        {formError && <p className="text-sm text-red-600">{formError}</p>}

        <Button type="submit" disabled={completeMutation.isPending}>
          {completeMutation.isPending ? t("saving") : t("submit")}
        </Button>
      </form>
    </div>
  );
}
