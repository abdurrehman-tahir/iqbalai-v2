"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Target,
  Plus,
  Pencil,
  Trash2,
  FlaskConical,
  Loader2,
  ClipboardCheck,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { frameworksApi, ApiError, type Framework } from "@/lib/api";
import type {
  ExamFrameworkCreate,
  ExamFrameworkUpdate,
  FrameworkResearchJobRead,
  FrameworkStudyPlanRead,
} from "@/lib/api/types";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  const [researchTarget, setResearchTarget] = useState<Framework | null>(null);
  const [reviewTarget, setReviewTarget] = useState<Framework | null>(null);
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

  // T-093: kick off the AI research run; the framework flips DRAFT -> RESEARCHING.
  const researchMutation = useMutation({
    mutationFn: (id: string) => frameworksApi.triggerResearch(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-frameworks"] });
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
                      {framework.status === "draft" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => researchMutation.mutate(framework.id)}
                          loading={
                            researchMutation.isPending &&
                            researchMutation.variables === framework.id
                          }
                          aria-label={t("actions.research", { name: framework.name })}
                          className="text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50"
                        >
                          <FlaskConical className="size-4" aria-hidden="true" />
                        </Button>
                      )}
                      {framework.status === "pending_approval" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setReviewTarget(framework)}
                          aria-label={t("actions.review", { name: framework.name })}
                          className="text-amber-600 hover:text-amber-800 hover:bg-amber-50"
                        >
                          <ClipboardCheck className="size-4" aria-hidden="true" />
                        </Button>
                      )}
                      {framework.status !== "draft" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setResearchTarget(framework)}
                          aria-label={t("actions.view_research", { name: framework.name })}
                        >
                          {framework.status === "researching" ? (
                            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                          ) : (
                            <FlaskConical className="size-4" aria-hidden="true" />
                          )}
                        </Button>
                      )}
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

      <Modal
        open={!!researchTarget}
        onClose={() => setResearchTarget(null)}
        title={t("research_modal.title")}
        description={t("research_modal.description", { name: researchTarget?.name ?? "" })}
        size="md"
        closeLabel={t("research_modal.close")}
      >
        {researchTarget && <ResearchJobPanel frameworkId={researchTarget.id} token={token ?? ""} />}
      </Modal>

      <Modal
        open={!!reviewTarget}
        onClose={() => setReviewTarget(null)}
        title={t("review_modal.title")}
        description={t("review_modal.description", { name: reviewTarget?.name ?? "" })}
        size="xl"
        closeLabel={t("review_modal.close")}
      >
        {reviewTarget && (
          <ReviewPlanPanel
            frameworkId={reviewTarget.id}
            token={token ?? ""}
            onDecided={() => {
              qc.invalidateQueries({ queryKey: ["exam-frameworks"] });
              setReviewTarget(null);
            }}
          />
        )}
      </Modal>
    </div>
  );
}

const reviewSchema = z.object({
  notes: z.string().min(1).max(4000),
});
type ReviewFormValues = z.infer<typeof reviewSchema>;

/** Platform-Admin review surface (T-094): reads the PENDING_APPROVAL plan (content
 * + cited sources) and approves (-> PUBLISHED) or rejects (-> DRAFT with notes).
 * Renders all four states: loading / empty (no pending plan) / error / success. */
function ReviewPlanPanel({
  frameworkId,
  token,
  onDecided,
}: {
  frameworkId: string;
  token: string;
  onDecided: () => void;
}) {
  const t = useTranslations("admin.exam_frameworks");
  const [showReject, setShowReject] = useState(false);
  const [actionError, setActionError] = useState("");

  const { data, isLoading, isError, refetch } = useQuery<FrameworkStudyPlanRead>({
    queryKey: ["exam-frameworks", "plan", frameworkId],
    queryFn: () => frameworksApi.reviewPlan(token, frameworkId),
    enabled: !!token,
    retry: false,
  });

  const approveMutation = useMutation({
    mutationFn: () => frameworksApi.approve(token, frameworkId),
    onSuccess: onDecided,
    onError: (err: Error) =>
      setActionError(err instanceof ApiError ? err.message : err.message),
  });

  const rejectForm = useForm<ReviewFormValues>({
    resolver: zodResolver(reviewSchema),
    defaultValues: { notes: "" },
  });

  const rejectMutation = useMutation({
    mutationFn: (values: ReviewFormValues) =>
      frameworksApi.reject(token, frameworkId, { notes: values.notes }),
    onSuccess: onDecided,
    onError: (err: Error) =>
      setActionError(err instanceof ApiError ? err.message : err.message),
  });

  if (isLoading) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  // The endpoint 404s when the framework isn't pending approval -> empty state.
  if (isError || !data) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title={t("review_modal.empty_title")}
        description={t("review_modal.empty_description")}
      />
    );
  }

  const content = data.content_jsonb as {
    topics?: { topic_name?: string }[];
    weekly_pacing?: unknown[];
  };
  const sources = data.sources_cited_jsonb as { url?: string; title?: string }[];
  const topics = content.topics ?? [];

  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-gray-500">{t("review_modal.version")}</dt>
        <dd className="font-medium text-gray-900">{data.version}</dd>
        <dt className="text-gray-500">{t("review_modal.topics")}</dt>
        <dd className="font-medium text-gray-900">{topics.length}</dd>
        <dt className="text-gray-500">{t("review_modal.weeks")}</dt>
        <dd className="font-medium text-gray-900">{(content.weekly_pacing ?? []).length}</dd>
      </dl>

      <section>
        <h3 className="text-sm font-semibold text-gray-900 mb-2">
          {t("review_modal.topics_heading")}
        </h3>
        {topics.length === 0 ? (
          <p className="text-sm text-gray-500">{t("review_modal.no_topics")}</p>
        ) : (
          <ul className="list-disc space-y-1 ps-5 text-sm text-gray-700 max-h-40 overflow-y-auto">
            {topics.map((topic, i) => (
              <li key={i}>{topic.topic_name ?? "—"}</li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-900 mb-2">
          {t("review_modal.sources_heading")}
        </h3>
        {sources.length === 0 ? (
          <p className="text-sm text-gray-500">{t("review_modal.no_sources")}</p>
        ) : (
          <ul className="space-y-1 text-sm max-h-40 overflow-y-auto">
            {sources.map((source, i) => (
              <li key={i} className="truncate">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-indigo-600 hover:underline"
                  dir="ltr"
                >
                  {source.title || source.url}
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      {actionError && (
        <p className="text-sm text-red-600" role="alert">
          {actionError}
        </p>
      )}

      {showReject ? (
        <form
          onSubmit={rejectForm.handleSubmit((values) => rejectMutation.mutate(values))}
          className="space-y-3 border-t border-gray-100 pt-4"
        >
          <div>
            <Label htmlFor="reject-notes" required>
              {t("review_modal.notes_label")}
            </Label>
            <Textarea
              id="reject-notes"
              rows={3}
              {...rejectForm.register("notes")}
              placeholder={t("review_modal.notes_placeholder")}
            />
            {rejectForm.formState.errors.notes && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {t("review_modal.notes_error")}
              </p>
            )}
          </div>
          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => setShowReject(false)}
            >
              {t("review_modal.cancel")}
            </Button>
            <Button
              type="submit"
              variant="destructive"
              size="md"
              loading={rejectMutation.isPending}
            >
              {t("review_modal.confirm_reject")}
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex justify-end gap-3 border-t border-gray-100 pt-4">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            {t("review_modal.refresh")}
          </Button>
          <Button
            variant="outline"
            size="md"
            className="gap-2 text-red-600"
            onClick={() => {
              setActionError("");
              setShowReject(true);
            }}
          >
            <XCircle className="size-4" aria-hidden="true" />
            {t("review_modal.reject")}
          </Button>
          <Button
            variant="primary"
            size="md"
            className="gap-2"
            loading={approveMutation.isPending}
            onClick={() => {
              setActionError("");
              approveMutation.mutate();
            }}
          >
            <CheckCircle2 className="size-4" aria-hidden="true" />
            {t("review_modal.approve")}
          </Button>
        </div>
      )}
    </div>
  );
}

/** Fetches and renders the latest research job for a framework — all four UI
 * states (loading / empty=no run yet / error / success). */
function ResearchJobPanel({ frameworkId, token }: { frameworkId: string; token: string }) {
  const t = useTranslations("admin.exam_frameworks");
  const { data, isLoading, isError, refetch } = useQuery<FrameworkResearchJobRead>({
    queryKey: ["exam-frameworks", "research", frameworkId],
    queryFn: () => frameworksApi.latestResearch(token, frameworkId),
    enabled: !!token,
    retry: false,
    // A running job progresses server-side; poll while it's in flight.
    refetchInterval: (query) => (query.state.data?.status === "running" ? 4000 : false),
  });

  if (isLoading) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  // The endpoint 404s when no run has ever been triggered -> empty state.
  if (isError || !data) {
    return (
      <EmptyState
        icon={FlaskConical}
        title={t("research_modal.empty_title")}
        description={t("research_modal.empty_description")}
      />
    );
  }

  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
      <dt className="text-gray-500">{t("research_modal.status")}</dt>
      <dd className="font-medium text-gray-900">
        <span className="inline-flex items-center gap-2">
          {data.status === "running" && (
            <Loader2 className="size-4 animate-spin text-indigo-600" aria-hidden="true" />
          )}
          {t(`research_status.${data.status}`)}
        </span>
      </dd>
      <dt className="text-gray-500">{t("research_modal.cost")}</dt>
      <dd className="font-medium text-gray-900">${data.cost_usd.toFixed(2)}</dd>
      <dt className="text-gray-500">{t("research_modal.sources")}</dt>
      <dd className="font-medium text-gray-900">{data.sources_count}</dd>
      {data.error && (
        <>
          <dt className="text-gray-500">{t("research_modal.error")}</dt>
          <dd className="text-red-600" role="alert">
            {data.error}
          </dd>
        </>
      )}
      <div className="col-span-2 pt-2">
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          {t("research_modal.refresh")}
        </Button>
      </div>
    </dl>
  );
}
