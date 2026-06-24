"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { gradesApi, schoolLibraryApi, subjectsApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const LANGUAGES = ["en", "ur", "sd", "ps"] as const;
const CONTENT_TYPES = ["curriculum", "reference"] as const;

const STATUS_VARIANT: Record<
  string,
  "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  pending: "warning",
  ingesting: "warning",
  available: "success",
  failed: "destructive",
};

function detailHref(contentType: string, itemId: string): string {
  if (contentType === "curriculum") {
    return `/teacher/library/curriculum/${itemId}`;
  }
  return `/teacher/library/reference/${itemId}`;
}

export function SchoolLibraryBrowse() {
  const t = useTranslations("school_library.browse");
  const { mounted, token } = useClientAuth();
  const [titleSearch, setTitleSearch] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [gradeOrdinal, setGradeOrdinal] = useState("");
  const [language, setLanguage] = useState("");
  const [contentType, setContentType] = useState("");

  const filters = useMemo(
    () => ({
      title: titleSearch.trim() || undefined,
      subject_id: subjectId || undefined,
      grade_level_ordinal: gradeOrdinal ? Number(gradeOrdinal) : undefined,
      language: language || undefined,
      content_type: contentType || undefined,
    }),
    [titleSearch, subjectId, gradeOrdinal, language, contentType],
  );

  const { data: subjects } = useQuery({
    queryKey: ["subjects", "list"],
    queryFn: () => subjectsApi.list(token!),
    enabled: mounted && !!token,
  });

  const { data: grades } = useQuery({
    queryKey: ["grades", "list"],
    queryFn: () => gradesApi.list(token!),
    enabled: mounted && !!token,
  });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["school-library", "list", filters],
    queryFn: () => schoolLibraryApi.list(token!, filters),
    enabled: mounted && !!token,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some(
        (item) => item.ingestion_status === "pending" || item.ingestion_status === "ingesting",
      )
        ? 10_000
        : false;
    },
  });

  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("page_title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("page_subtitle")}</p>
      </div>

      <div className="grid gap-4 rounded-lg border border-gray-200 bg-white p-4 md:grid-cols-2 xl:grid-cols-3">
        <div>
          <Label htmlFor="library-search">{t("search_label")}</Label>
          <Input
            id="library-search"
            value={titleSearch}
            onChange={(event) => setTitleSearch(event.target.value)}
            placeholder={t("search_placeholder")}
          />
        </div>
        <div>
          <Label htmlFor="library-subject">{t("subject_label")}</Label>
          <select
            id="library-subject"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={subjectId}
            onChange={(event) => setSubjectId(event.target.value)}
          >
            <option value="">{t("all_subjects")}</option>
            {(subjects ?? []).map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="library-grade">{t("grade_label")}</Label>
          <select
            id="library-grade"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={gradeOrdinal}
            onChange={(event) => setGradeOrdinal(event.target.value)}
          >
            <option value="">{t("all_grades")}</option>
            {(grades ?? []).map((grade) => (
              <option key={grade.id} value={String(grade.level_ordinal)}>
                {grade.name}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-gray-500">{t("grade_help")}</p>
        </div>
        <div>
          <Label htmlFor="library-language">{t("language_label")}</Label>
          <select
            id="library-language"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
          >
            <option value="">{t("all_languages")}</option>
            {LANGUAGES.map((code) => (
              <option key={code} value={code}>
                {t(`language_${code}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="library-content-type">{t("content_type_label")}</Label>
          <select
            id="library-content-type"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={contentType}
            onChange={(event) => setContentType(event.target.value)}
          >
            <option value="">{t("all_content_types")}</option>
            {CONTENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`content_type_${type}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              setTitleSearch("");
              setSubjectId("");
              setGradeOrdinal("");
              setLanguage("");
              setContentType("");
            }}
          >
            {t("clear_filters")}
          </Button>
        </div>
      </div>

      {isError ? (
        <ErrorState description={t("error")} onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : items.length === 0 ? (
        <EmptyState title={t("empty_title")} description={t("empty_description")} />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-start font-medium text-gray-600">{t("column_title")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-600">{t("column_type")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-600">{t("column_visibility")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-600">{t("column_status")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-600">{t("column_language")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => {
                const statusKey = item.ingestion_status as keyof typeof STATUS_VARIANT;
                const visibilityKey =
                  item.visibility === "school_public" ? "visibility_public" : "visibility_private";
                return (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        href={detailHref(item.content_type, item.id)}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        {item.title}
                      </Link>
                      {item.grade_level_ordinal != null && (
                        <p className="mt-1 text-xs text-gray-500">
                          {t("grade_tag", { grade: item.grade_level_ordinal })}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {t(`content_type_${item.content_type}`)}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{t(visibilityKey)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[statusKey] ?? "secondary"} role="status">
                        {t(`status.${item.ingestion_status}`)}
                      </Badge>
                      {item.ingestion_status === "failed" && item.ingestion_error && (
                        <p className="mt-1 max-w-xs text-xs text-red-700">{item.ingestion_error}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{item.language.toUpperCase()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
