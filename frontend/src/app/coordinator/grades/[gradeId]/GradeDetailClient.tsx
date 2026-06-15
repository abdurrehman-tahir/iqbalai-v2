"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, Archive, Plus } from "lucide-react";
import Link from "next/link";
import { gradesApi, sectionsApi, ApiError, type Section } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";

const sectionSchema = z.object({ name: z.string().min(1).max(100) });
type SectionFormValues = z.infer<typeof sectionSchema>;

export function GradeDetailClient() {
  const params = useParams<{ gradeId: string }>();
  const gradeId = params.gradeId;
  const router = useRouter();
  const t = useTranslations("coordinator.grade_detail");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<Section | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: grade, isLoading: gradeLoading, isError: gradeError, refetch: refetchGrade } = useQuery({
    queryKey: ["grades", gradeId],
    queryFn: () => gradesApi.get(token!, gradeId),
    enabled: mounted && !!token,
  });

  const { data: sections, isLoading: sectionsLoading, isError: sectionsError, refetch: refetchSections } = useQuery({
    queryKey: ["sections", gradeId],
    queryFn: () => sectionsApi.list(token!, gradeId),
    enabled: mounted && !!token,
  });

  const form = useForm<SectionFormValues>({ resolver: zodResolver(sectionSchema), defaultValues: { name: "" } });

  const createMutation = useMutation({
    mutationFn: (values: SectionFormValues) => sectionsApi.create(token ?? "", gradeId, values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sections", gradeId] });
      setShowCreate(false);
      form.reset();
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError && err.status === 409 ? t("sections.duplicate_error") : t("sections.generic_error"));
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (sectionId: string) => sectionsApi.archive(token ?? "", gradeId, sectionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sections", gradeId] });
      setArchiveTarget(null);
    },
  });

  if (!mounted || gradeLoading) return <Skeleton className="h-64 w-full" />;
  if (gradeError || !grade) {
    return <ErrorState message={t("error")} onRetry={() => refetchGrade()} retryLabel={t("retry")} />;
  }

  return (
    <div className="space-y-8">
      <div>
        <Link href="/coordinator/grades" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4">
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t("back")}
        </Link>
        <h2 className="text-2xl font-bold text-gray-900">{grade.name}</h2>
        <p className="text-sm text-gray-500">{t("session_label", { session: grade.academic_session })}</p>
      </div>

      <section aria-labelledby="sections-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 id="sections-heading" className="text-lg font-semibold text-gray-900">{t("sections.title")}</h3>
          <Button size="sm" onClick={() => { setShowCreate(true); setFormError(null); form.reset(); }}>
            <Plus className="size-4 me-2" aria-hidden="true" />
            {t("sections.add_button")}
          </Button>
        </div>

        {sectionsLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : sectionsError ? (
          <ErrorState message={t("sections.error")} onRetry={() => refetchSections()} retryLabel={t("retry")} />
        ) : !sections?.length ? (
          <EmptyState title={t("sections.empty.title")} description={t("sections.empty.description")} />
        ) : (
          <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
            {sections.map((section) => (
              <li key={section.id} className="flex items-center justify-between px-4 py-3">
                <span className="text-sm font-medium text-gray-900">{section.name}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setArchiveTarget(section)}
                  aria-label={t("sections.archive", { name: section.name })}
                >
                  <Archive className="size-4" aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title={t("sections.modal.title")}>
        <form
          onSubmit={form.handleSubmit((v) => { setFormError(null); createMutation.mutate(v); })}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="section-name">{t("sections.modal.name_label")}</Label>
            <Input id="section-name" {...form.register("name")} placeholder={t("sections.modal.name_placeholder")} />
          </div>
          {formError && <p className="text-sm text-red-600">{formError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>{t("sections.modal.cancel")}</Button>
            <Button type="submit" disabled={createMutation.isPending}>{t("sections.modal.create")}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!archiveTarget} onClose={() => setArchiveTarget(null)} title={t("sections.archive_modal.title")}>
        <p className="text-sm text-gray-600 mb-4">{t("sections.archive_modal.description", { name: archiveTarget?.name ?? "" })}</p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setArchiveTarget(null)}>{t("sections.archive_modal.cancel")}</Button>
          <Button variant="danger" onClick={() => archiveTarget && archiveMutation.mutate(archiveTarget.id)} disabled={archiveMutation.isPending}>
            {t("sections.archive_modal.confirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
