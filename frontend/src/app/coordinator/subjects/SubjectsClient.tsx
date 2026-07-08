"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useFormatter } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Archive, BookOpen, Pencil, Plus } from "lucide-react";
import { subjectsApi, ApiError, type Subject } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// The four platform locales (ARCH §13) — the only languages a subject may take.
const LANGUAGES = ["en", "ur", "sd", "ps"] as const;

const subjectSchema = z.object({
  name: z.string().min(1).max(200),
  language: z.enum(LANGUAGES),
});

type SubjectFormValues = z.infer<typeof subjectSchema>;

export function SubjectsClient() {
  const t = useTranslations("coordinator.subjects");
  const format = useFormatter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<Subject | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<Subject | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["subjects", "list", { includeArchived }],
    queryFn: () => subjectsApi.list(token!, includeArchived),
    enabled: mounted && !!token,
  });

  const form = useForm<SubjectFormValues>({
    resolver: zodResolver(subjectSchema),
    defaultValues: { name: "", language: "en" },
  });

  const createMutation = useMutation({
    mutationFn: (values: SubjectFormValues) => subjectsApi.create(token ?? "", values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subjects"] });
      setShowCreate(false);
    },
    onError: (err: unknown) => setFormError(errorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: SubjectFormValues }) =>
      subjectsApi.update(token ?? "", id, values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subjects"] });
      setEditTarget(null);
    },
    onError: (err: unknown) => setFormError(errorMessage(err)),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => subjectsApi.archive(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subjects"] });
      setArchiveTarget(null);
    },
  });

  function errorMessage(err: unknown): string {
    if (err instanceof ApiError && err.code === "CONFLICT") {
      return t("modal.duplicate_error");
    }
    return t("modal.generic_error");
  }

  function openCreate() {
    setFormError(null);
    form.reset({ name: "", language: "en" });
    setShowCreate(true);
  }

  function openEdit(subject: Subject) {
    setFormError(null);
    form.reset({ name: subject.name, language: languageOf(subject) });
    setEditTarget(subject);
  }

  /** Narrow the stored free-text language to a known locale; fall back to en. */
  function languageOf(subject: Subject): (typeof LANGUAGES)[number] {
    return (LANGUAGES as readonly string[]).includes(subject.language)
      ? (subject.language as (typeof LANGUAGES)[number])
      : "en";
  }

  function handleSubmit(values: SubjectFormValues) {
    setFormError(null);
    // Fire-and-forget: onSuccess closes the modal, onError surfaces formError.
    if (editTarget) {
      updateMutation.mutate({ id: editTarget.id, values });
    } else {
      createMutation.mutate(values);
    }
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState description={t("error")} onRetry={() => refetch()} retryLabel={t("retry")} />
    );
  }

  const modalOpen = showCreate || !!editTarget;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <Button variant="primary" size="md" className="gap-2" onClick={openCreate}>
          <Plus className="size-4" aria-hidden="true" />
          {t("add_button")}
        </Button>
      </div>

      {/* Archived toggle */}
      <label className="inline-flex items-center gap-2 text-sm text-gray-600">
        <input
          type="checkbox"
          className="size-4 rounded border-gray-300"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        {t("show_archived")}
      </label>

      {/* Empty state */}
      {!data || data.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title={t("empty.title")}
          description={t("empty.description")}
          action={{ label: t("empty.cta"), onClick: openCreate }}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" role="table" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-start">
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.name")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.language")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.status")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.created")}
                </th>
                <th className="px-4 py-3 text-end font-medium text-gray-500">{t("col.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((subject) => (
                <tr key={subject.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{subject.name}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {t(`languages.${languageOf(subject)}`)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={subject.status === "active" ? "success" : "secondary"}>
                      {t(`status.${subject.status}`)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">
                    {format.dateTime(new Date(subject.created_at))}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(subject)}
                        aria-label={t("actions.edit", { name: subject.name })}
                        className="text-brand-600 hover:text-brand-800 hover:bg-brand-50"
                      >
                        <Pencil className="size-4" aria-hidden="true" />
                      </Button>
                      {subject.status === "active" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setArchiveTarget(subject)}
                          aria-label={t("actions.archive", { name: subject.name })}
                          className="text-amber-600 hover:text-amber-800 hover:bg-amber-50"
                        >
                          <Archive className="size-4" aria-hidden="true" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => {
          setShowCreate(false);
          setEditTarget(null);
        }}
        title={editTarget ? t("modal.edit_title") : t("modal.create_title")}
        size="md"
        closeLabel={t("modal.close")}
      >
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="subject-name" required>
              {t("modal.name_label")}
            </Label>
            <Input
              id="subject-name"
              {...form.register("name")}
              placeholder={t("modal.name_placeholder")}
            />
            {form.formState.errors.name && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {t("modal.name_required")}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="subject-language" required>
              {t("modal.language_label")}
            </Label>
            <select
              id="subject-language"
              {...form.register("language")}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {t(`languages.${lang}`)}
                </option>
              ))}
            </select>
          </div>

          {formError && (
            <p className="text-sm text-red-600" role="alert">
              {formError}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => {
                setShowCreate(false);
                setEditTarget(null);
              }}
            >
              {t("modal.cancel")}
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={createMutation.isPending || updateMutation.isPending}
            >
              {editTarget ? t("modal.save") : t("modal.create")}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Archive confirmation modal */}
      <Modal
        open={!!archiveTarget}
        onClose={() => setArchiveTarget(null)}
        title={t("archive_modal.title")}
        description={t("archive_modal.description", { name: archiveTarget?.name ?? "" })}
        size="sm"
        closeLabel={t("archive_modal.cancel")}
      >
        <div className="flex justify-end gap-3">
          <Button variant="outline" size="md" onClick={() => setArchiveTarget(null)}>
            {t("archive_modal.cancel")}
          </Button>
          <Button
            variant="primary"
            size="md"
            loading={archiveMutation.isPending}
            onClick={() => archiveTarget && archiveMutation.mutate(archiveTarget.id)}
          >
            {t("archive_modal.confirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
