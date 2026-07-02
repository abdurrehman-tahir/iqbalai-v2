"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Target, Plus, Pencil, Trash2 } from "lucide-react";
import { frameworksApi, ApiError, type Framework } from "@/lib/api";
import type { ExamFrameworkCreate, ExamFrameworkUpdate } from "@/lib/api/types";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

// Grade band bounds mirror the backend validator (schemas._MIN_GRADE/_MAX_GRADE).
const MIN_GRADE = 1;
const MAX_GRADE = 14;

function parseGrades(raw: string): number[] {
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map(Number);
}

function gradesValid(raw: string): boolean {
  const grades = parseGrades(raw);
  return (
    grades.length > 0 &&
    grades.every((g) => Number.isInteger(g) && g >= MIN_GRADE && g <= MAX_GRADE)
  );
}

const frameworkSchema = z.object({
  name: z.string().min(1).max(255),
  exam_target: z.string().min(1).max(255),
  region: z.string().min(1).max(100),
  grades: z.string().min(1).refine(gradesValid, { message: "grades" }),
});

type FrameworkFormValues = z.infer<typeof frameworkSchema>;

function toCreatePayload(values: FrameworkFormValues): ExamFrameworkCreate {
  return {
    name: values.name,
    exam_target: values.exam_target,
    region: values.region,
    target_grade_range: parseGrades(values.grades),
    language: "en",
  };
}

function toUpdatePayload(values: FrameworkFormValues): ExamFrameworkUpdate {
  return {
    name: values.name,
    exam_target: values.exam_target,
    region: values.region,
    target_grade_range: parseGrades(values.grades),
  };
}

// Only DRAFT frameworks are visually badged as neutral; published/live are success.
const STATUS_VARIANT: Record<string, "secondary" | "success" | "warning"> = {
  draft: "secondary",
  researching: "warning",
  pending_approval: "warning",
  published: "success",
  refreshing: "warning",
  deprecated: "secondary",
};

export function FrameworksClient() {
  const t = useTranslations("admin.exam_frameworks");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [editTarget, setEditTarget] = useState<Framework | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Framework | null>(null);
  const [formError, setFormError] = useState("");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["exam-frameworks", "list"],
    queryFn: () => frameworksApi.list(token!),
    enabled: mounted && !!token,
  });

  const createMutation = useMutation({
    mutationFn: (values: FrameworkFormValues) =>
      frameworksApi.create(token ?? "", toCreatePayload(values)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-frameworks"] });
      setShowCreate(false);
      setFormError("");
    },
    onError: (err: Error) => {
      setFormError(err instanceof ApiError ? err.message : err.message);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: FrameworkFormValues }) =>
      frameworksApi.update(token ?? "", id, toUpdatePayload(values)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-frameworks"] });
      setEditTarget(null);
      setFormError("");
    },
    onError: (err: Error) => {
      setFormError(err instanceof ApiError ? err.message : err.message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => frameworksApi.delete(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-frameworks"] });
      setDeleteTarget(null);
    },
    onError: (err: Error) => {
      setFormError(err instanceof ApiError ? err.message : err.message);
    },
  });

  const form = useForm<FrameworkFormValues>({
    resolver: zodResolver(frameworkSchema),
    defaultValues: { name: "", exam_target: "", region: "", grades: "" },
  });

  function openEdit(framework: Framework) {
    setFormError("");
    setEditTarget(framework);
    form.reset({
      name: framework.name,
      exam_target: framework.exam_target,
      region: framework.region,
      grades: framework.target_grade_range.join(", "),
    });
  }

  function openCreate() {
    setFormError("");
    setShowCreate(true);
    form.reset({ name: "", exam_target: "", region: "", grades: "" });
  }

  function closeFormModal() {
    setShowCreate(false);
    setEditTarget(null);
    setFormError("");
  }

  async function handleSubmit(values: FrameworkFormValues) {
    setFormError("");
    if (editTarget) {
      await updateMutation.mutateAsync({ id: editTarget.id, values });
    } else {
      await createMutation.mutateAsync(values);
    }
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-32 ms-auto" aria-hidden="true" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <ErrorState description={t("error")} onRetry={() => refetch()} retryLabel={t("retry")} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <Button variant="primary" size="md" className="gap-2" onClick={openCreate}>
          <Plus className="size-4" aria-hidden="true" />
          {t("add_button")}
        </Button>
      </div>

      {!data || data.length === 0 ? (
        <EmptyState
          icon={Target}
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
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.exam_target")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden sm:table-cell">
                  {t("col.region")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden lg:table-cell">
                  {t("col.grades")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.status")}
                </th>
                <th className="px-4 py-3 text-end font-medium text-gray-500">{t("col.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((framework) => (
                <tr key={framework.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{framework.name}</td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell max-w-xs truncate">
                    {framework.exam_target}
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden sm:table-cell">
                    {framework.region}
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden lg:table-cell">
                    {framework.target_grade_range.join(", ")}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANT[framework.status] ?? "secondary"}>
                      {t(`status.${framework.status}`)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(framework)}
                        aria-label={t("actions.edit", { name: framework.name })}
                      >
                        <Pencil className="size-4" aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(framework)}
                        aria-label={t("actions.delete", { name: framework.name })}
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="size-4" aria-hidden="true" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={showCreate || !!editTarget}
        onClose={closeFormModal}
        title={editTarget ? t("modal.edit_title") : t("modal.create_title")}
        size="md"
        closeLabel={t("modal.close")}
      >
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="fw-name" required>
              {t("modal.name_label")}
            </Label>
            <Input
              id="fw-name"
              {...form.register("name")}
              placeholder={t("modal.name_placeholder")}
            />
            {form.formState.errors.name && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="fw-exam-target" required>
              {t("modal.exam_target_label")}
            </Label>
            <Input
              id="fw-exam-target"
              {...form.register("exam_target")}
              placeholder={t("modal.exam_target_placeholder")}
            />
            {form.formState.errors.exam_target && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {form.formState.errors.exam_target.message}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="fw-region" required>
              {t("modal.region_label")}
            </Label>
            <Input
              id="fw-region"
              {...form.register("region")}
              placeholder={t("modal.region_placeholder")}
            />
            {form.formState.errors.region && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {form.formState.errors.region.message}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="fw-grades" required>
              {t("modal.grades_label")}
            </Label>
            <Input
              id="fw-grades"
              {...form.register("grades")}
              placeholder={t("modal.grades_placeholder")}
              inputMode="numeric"
            />
            <p className="text-xs text-gray-500 mt-1">{t("modal.grades_hint")}</p>
            {form.formState.errors.grades && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {t("modal.grades_error")}
              </p>
            )}
          </div>

          {formError && (
            <p className="text-sm text-red-600" role="alert">
              {formError}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" size="md" onClick={closeFormModal}>
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

      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t("delete_modal.title")}
        description={t("delete_modal.description", { name: deleteTarget?.name ?? "" })}
        size="sm"
        closeLabel={t("delete_modal.cancel")}
      >
        <div className="flex justify-end gap-3">
          <Button variant="outline" size="md" onClick={() => setDeleteTarget(null)}>
            {t("delete_modal.cancel")}
          </Button>
          <Button
            variant="destructive"
            size="md"
            loading={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
          >
            {t("delete_modal.confirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
