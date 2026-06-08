"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { BookOpen, Plus, Pencil, Trash2 } from "lucide-react";
import { syllabiApi, type Syllabus } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

const syllabusSchema = z.object({
  name: z.string().min(1).max(200),
  description: z.string().max(500).optional(),
});

type SyllabusFormValues = z.infer<typeof syllabusSchema>;

export function SyllabiClient() {
  const t = useTranslations("admin.exam_syllabi");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [editTarget, setEditTarget] = useState<Syllabus | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Syllabus | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["exam-syllabi", "list"],
    queryFn: () => syllabiApi.list(token!),
    enabled: mounted && !!token,
  });

  const createMutation = useMutation({
    mutationFn: (values: SyllabusFormValues) =>
      syllabiApi.create(token ?? "", values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-syllabi"] });
      setShowCreate(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: SyllabusFormValues }) =>
      syllabiApi.update(token ?? "", id, values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-syllabi"] });
      setEditTarget(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => syllabiApi.delete(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-syllabi"] });
      setDeleteTarget(null);
    },
  });

  const form = useForm<SyllabusFormValues>({
    resolver: zodResolver(syllabusSchema),
    defaultValues: { name: "", description: "" },
  });

  function openEdit(syllabus: Syllabus) {
    setEditTarget(syllabus);
    form.reset({ name: syllabus.name, description: syllabus.description ?? "" });
  }

  function openCreate() {
    setShowCreate(true);
    form.reset({ name: "", description: "" });
  }

  async function handleSubmit(values: SyllabusFormValues) {
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
        <ErrorState
          description={t("error")}
          onRetry={() => refetch()}
          retryLabel={t("retry")}
        />
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

      {/* Empty state */}
      {!data || data.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title={t("empty.title")}
          description={t("empty.description")}
          action={{ label: t("empty.cta"), onClick: openCreate }}
        />
      ) : (
        /* Table (scrollable on mobile) */
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" role="table" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-start">
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.name")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.description")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.version")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.status")}
                </th>
                <th className="px-4 py-3 text-end font-medium text-gray-500">
                  {t("col.actions")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((syllabus) => (
                <tr key={syllabus.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {syllabus.name}
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell max-w-xs truncate">
                    {syllabus.description ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    v{syllabus.version_number}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={syllabus.is_active ? "success" : "secondary"}>
                      {syllabus.is_active ? t("status.active") : t("status.inactive")}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(syllabus)}
                        aria-label={t("actions.edit", { name: syllabus.name })}
                      >
                        <Pencil className="size-4" aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(syllabus)}
                        aria-label={t("actions.delete", { name: syllabus.name })}
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

      {/* Create / Edit modal */}
      <Modal
        open={showCreate || !!editTarget}
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
            <Label htmlFor="syl-name" required>
              {t("modal.name_label")}
            </Label>
            <Input
              id="syl-name"
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
            <Label htmlFor="syl-desc">{t("modal.desc_label")}</Label>
            <Textarea
              id="syl-desc"
              {...form.register("description")}
              placeholder={t("modal.desc_placeholder")}
              rows={3}
            />
          </div>

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

      {/* Delete confirmation modal */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t("delete_modal.title")}
        description={t("delete_modal.description", {
          name: deleteTarget?.name ?? "",
        })}
        size="sm"
        closeLabel={t("delete_modal.cancel")}
      >
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            size="md"
            onClick={() => setDeleteTarget(null)}
          >
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
