"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { gradesApi, schoolLibraryApi, subjectsApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const LANGUAGES = ["en", "ur", "sd", "ps"] as const;

interface CurriculumUploadFormProps {
  detailBasePath: string;
}

export function CurriculumUploadForm({ detailBasePath }: CurriculumUploadFormProps) {
  const t = useTranslations("school_library.curriculum");
  const router = useRouter();
  const { mounted, token } = useClientAuth();
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState<(typeof LANGUAGES)[number]>("en");
  const [subjectId, setSubjectId] = useState("");
  const [gradeOrdinal, setGradeOrdinal] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: subjects, isLoading: subjectsLoading } = useQuery({
    queryKey: ["subjects", "list"],
    queryFn: () => subjectsApi.list(token!),
    enabled: mounted && !!token,
  });

  const { data: grades, isLoading: gradesLoading } = useQuery({
    queryKey: ["grades", "list"],
    queryFn: () => gradesApi.list(token!),
    enabled: mounted && !!token,
  });

  const uploadMutation = useMutation({
    mutationFn: () =>
      schoolLibraryApi.upload(token ?? "", {
        file: file!,
        title,
        content_type: "curriculum",
        language,
        subject_id: subjectId || null,
        grade_level_ordinal: gradeOrdinal ? Number(gradeOrdinal) : null,
      }),
    onSuccess: (result) => {
      router.push(`${detailBasePath}/${result.item.id}`);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : t("upload.error_generic"));
    },
  });

  const formReady =
    mounted &&
    !!token &&
    !!file &&
    title.trim().length > 0 &&
    subjectId &&
    gradeOrdinal &&
    !uploadMutation.isPending;

  return (
    <form
      className="space-y-4 rounded-lg border border-gray-200 bg-white p-6"
      onSubmit={(event) => {
        event.preventDefault();
        if (!formReady) return;
        setError(null);
        uploadMutation.mutate();
      }}
    >
      <p className="rounded-md bg-brand-50 px-3 py-2 text-sm text-brand-800" role="note">
        {t("upload.public_notice")}
      </p>

      <div>
        <Label htmlFor="curriculum-title" required>
          {t("upload.title_label")}
        </Label>
        <Input
          id="curriculum-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder={t("upload.title_placeholder")}
        />
      </div>

      <div>
        <Label htmlFor="curriculum-subject" required>
          {t("upload.subject_label")}
        </Label>
        {subjectsLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <select
            id="curriculum-subject"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={subjectId}
            onChange={(event) => setSubjectId(event.target.value)}
          >
            <option value="">{t("upload.subject_placeholder")}</option>
            {(subjects ?? []).map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div>
        <Label htmlFor="curriculum-grade" required>
          {t("upload.grade_label")}
        </Label>
        {gradesLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <select
            id="curriculum-grade"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={gradeOrdinal}
            onChange={(event) => setGradeOrdinal(event.target.value)}
          >
            <option value="">{t("upload.grade_placeholder")}</option>
            {(grades ?? []).map((grade) => (
              <option key={grade.id} value={String(grade.level_ordinal)}>
                {grade.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div>
        <Label htmlFor="curriculum-language" required>
          {t("upload.language_label")}
        </Label>
        <select
          id="curriculum-language"
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={language}
          onChange={(event) => setLanguage(event.target.value as (typeof LANGUAGES)[number])}
        >
          {LANGUAGES.map((code) => (
            <option key={code} value={code}>
              {t(`upload.language_${code}`)}
            </option>
          ))}
        </select>
      </div>

      <div>
        <Label htmlFor="curriculum-file" required>
          {t("upload.file_label")}
        </Label>
        <Input
          id="curriculum-file"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <p className="mt-1 text-xs text-gray-500">{t("upload.file_help")}</p>
      </div>

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <Button type="submit" disabled={!formReady}>
        {uploadMutation.isPending ? t("upload.submitting") : t("upload.submit")}
      </Button>
    </form>
  );
}
