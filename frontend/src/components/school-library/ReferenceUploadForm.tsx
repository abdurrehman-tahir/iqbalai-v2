"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { gradesApi, schoolLibraryApi, subjectsApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { useCurrentUser } from "@/hooks/use-current-user";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { prepareUploadFile, UPLOAD_FILE_READ_ERROR, UPLOAD_NOT_A_PDF_ERROR } from "@/lib/upload-file";

const LANGUAGES = ["en", "ur", "sd", "ps"] as const;
const AUTO_PUBLIC_ROLES = new Set(["coordinator", "school_admin", "district_admin", "platform_admin"]);

interface ReferenceUploadFormProps {
  detailBasePath: string;
}

export function ReferenceUploadForm({ detailBasePath }: ReferenceUploadFormProps) {
  const t = useTranslations("school_library.reference");
  const router = useRouter();
  const { mounted, token } = useClientAuth();
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState<(typeof LANGUAGES)[number]>("en");
  const [subjectId, setSubjectId] = useState("");
  const [gradeOrdinal, setGradeOrdinal] = useState("");
  const [makePublic, setMakePublic] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user } = useCurrentUser();
  const userRole = user?.role ?? null;

  const autoPublic = userRole !== null && AUTO_PUBLIC_ROLES.has(userRole);

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
    mutationFn: async () => {
      const selected = file!;
      let uploadFile: File | Blob;
      try {
        uploadFile = await prepareUploadFile(selected);
      } catch (err) {
        if (err instanceof Error && err.message === UPLOAD_NOT_A_PDF_ERROR) {
          throw err;
        }
        throw new Error(UPLOAD_FILE_READ_ERROR);
      }
      return schoolLibraryApi.upload(token ?? "", {
        file: uploadFile,
        fileName: selected.name,
        title,
        content_type: "reference",
        language,
        subject_id: subjectId || null,
        grade_level_ordinal: gradeOrdinal ? Number(gradeOrdinal) : null,
        visibility: autoPublic || makePublic ? "school_public" : undefined,
      });
    },
    onSuccess: (result) => {
      router.push(`${detailBasePath}/${result.item.id}`);
    },
    onError: (err: unknown) => {
      if (err instanceof Error && err.message === UPLOAD_NOT_A_PDF_ERROR) {
        setError(t("upload.invalid_pdf"));
        return;
      }
      if (err instanceof Error && err.message === UPLOAD_FILE_READ_ERROR) {
        setError(t("upload.file_read_error"));
        return;
      }
      if (err instanceof ApiError && err.message.includes("school_library_content")) {
        setError(t("upload.invalid_pdf"));
        return;
      }
      setError(err instanceof ApiError ? err.message : t("upload.error_generic"));
    },
  });

  const formReady =
    mounted &&
    !!token &&
    !!file &&
    title.trim().length > 0 &&
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
      {autoPublic ? (
        <p className="rounded-md bg-brand-50 px-3 py-2 text-sm text-brand-800" role="note">
          {t("upload.admin_public_notice")}
        </p>
      ) : (
        <div className="rounded-md border border-gray-200 px-3 py-3">
          <label className="flex items-start gap-3 text-sm text-gray-800">
            <input
              id="reference-make-public"
              type="checkbox"
              className="mt-0.5 size-4 rounded border-gray-300"
              checked={makePublic}
              onChange={(event) => setMakePublic(event.target.checked)}
            />
            <span>
              <span className="font-medium">{t("upload.privacy_toggle_label")}</span>
              <span className="mt-1 block text-gray-600">{t("upload.privacy_toggle_help")}</span>
            </span>
          </label>
        </div>
      )}

      <div>
        <Label htmlFor="reference-title" required>
          {t("upload.title_label")}
        </Label>
        <Input
          id="reference-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder={t("upload.title_placeholder")}
        />
      </div>

      <div>
        <Label htmlFor="reference-subject">{t("upload.subject_label")}</Label>
        {subjectsLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <select
            id="reference-subject"
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
        <Label htmlFor="reference-grade">{t("upload.grade_label")}</Label>
        {gradesLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <select
            id="reference-grade"
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
        <Label htmlFor="reference-language" required>
          {t("upload.language_label")}
        </Label>
        <select
          id="reference-language"
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
        <Label htmlFor="reference-file" required>
          {t("upload.file_label")}
        </Label>
        <Input
          id="reference-file"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setError(null);
          }}
        />
        {file && (
          <p className="mt-1 text-xs text-gray-600">
            {t("upload.file_selected", { name: file.name })}
          </p>
        )}
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
