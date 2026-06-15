"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useFormatter } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { Archive, GraduationCap, Plus } from "lucide-react";
import { gradesApi, ApiError, type Grade } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const gradeSchema = z.object({
  name: z.string().min(1).max(200),
});

type GradeFormValues = z.infer<typeof gradeSchema>;

export function GradesClient() {
  const t = useTranslations("coordinator.grades");
  const format = useFormatter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<Grade | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["grades", "list", { includeArchived }],
    queryFn: () => gradesApi.list(token!, includeArchived),
    enabled: mounted && !!token,
  });

  const form = useForm<GradeFormValues>({
    resolver: zodResolver(gradeSchema),
    defaultValues: { name: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: GradeFormValues) => gradesApi.create(token ?? "", values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grades"] });
      setShowCreate(false);
      form.reset();
    },
    onError: (err: unknown) => setFormError(errorMessage(err)),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => gradesApi.archive(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grades"] });
      setArchiveTarget(null);
    },
  });

  function errorMessage(err: unknown): string {
    if (err instanceof ApiError && err.code === "CONFLICT") return t("modal.duplicate_error");
    if (err instanceof ApiError && err.status === 403) return t("modal.scope_error");
    return t("modal.generic_error");
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError) {
    return <ErrorState message={t("error")} onRetry={() => refetch()} retryLabel={t("retry")} />;
  }

  const grades = data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t("title")}</h2>
          <p className="text-sm text-gray-500 mt-1">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
              className="rounded border-gray-300"
            />
            {t("show_archived")}
          </label>
          <Button onClick={() => { setShowCreate(true); setFormError(null); form.reset(); }}>
            <Plus className="size-4 me-2" aria-hidden="true" />
            {t("add_button")}
          </Button>
        </div>
      </div>

      {grades.length === 0 ? (
        <EmptyState
          icon={GraduationCap}
          title={t("empty.title")}
          description={t("empty.description")}
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="size-4 me-2" aria-hidden="true" />
              {t("empty.cta")}
            </Button>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200" aria-label={t("table_label")}>
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-start text-xs font-medium text-gray-500 uppercase">{t("col.name")}</th>
                <th className="px-4 py-3 text-start text-xs font-medium text-gray-500 uppercase">{t("col.session")}</th>
                <th className="px-4 py-3 text-start text-xs font-medium text-gray-500 uppercase">{t("col.status")}</th>
                <th className="px-4 py-3 text-start text-xs font-medium text-gray-500 uppercase">{t("col.created")}</th>
                <th className="px-4 py-3 text-end text-xs font-medium text-gray-500 uppercase">{t("col.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {grades.map((grade) => (
                <tr key={grade.id}>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    <Link href={`/coordinator/grades/${grade.id}`} className="text-brand-700 hover:underline">
                      {grade.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{grade.academic_session}</td>
                  <td className="px-4 py-3">
                    <Badge variant={grade.status === "active" ? "success" : "secondary"}>
                      {t(`status.${grade.status}`)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {format.dateTime(new Date(grade.created_at))}
                  </td>
                  <td className="px-4 py-3 text-end">
                    {grade.status === "active" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setArchiveTarget(grade)}
                        aria-label={t("actions.archive", { name: grade.name })}
                      >
                        <Archive className="size-4" aria-hidden="true" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title={t("modal.create_title")}>
        <form
          onSubmit={form.handleSubmit((values) => {
            setFormError(null);
            createMutation.mutate(values);
          })}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="grade-name">{t("modal.name_label")}</Label>
            <Input id="grade-name" placeholder={t("modal.name_placeholder")} {...form.register("name")} />
          </div>
          {formError && <p className="text-sm text-red-600">{formError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>{t("modal.cancel")}</Button>
            <Button type="submit" disabled={createMutation.isPending}>{t("modal.create")}</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={!!archiveTarget}
        onClose={() => setArchiveTarget(null)}
        title={t("archive_modal.title")}
      >
        <p className="text-sm text-gray-600 mb-4">
          {t("archive_modal.description", { name: archiveTarget?.name ?? "" })}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setArchiveTarget(null)}>{t("archive_modal.cancel")}</Button>
          <Button
            variant="danger"
            onClick={() => archiveTarget && archiveMutation.mutate(archiveTarget.id)}
            disabled={archiveMutation.isPending}
          >
            {t("archive_modal.confirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
