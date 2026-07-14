"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Target, Plus, RefreshCw, Trash2, BookOpen, ArrowUpCircle } from "lucide-react";
import { studentFrameworksApi, ApiError } from "@/lib/api";
import type { StudentStudyPlanRead } from "@/lib/api/types";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";

/**
 * Student exam-framework surface (T-096): browse published frameworks scoped by region +
 * grade, select (pins to current version), see the §3.5.2 plan rendered, opt in to a
 * refreshed version, or drop. Region + grade are entered here (a student's region is not
 * yet stored on the profile — the filtering engine is what this ticket ships).
 */
export function StudentFrameworksClient() {
  const t = useTranslations("student.frameworks");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [region, setRegion] = useState("");
  const [grade, setGrade] = useState("");
  const [applied, setApplied] = useState<{ region: string; grade: number } | null>(null);
  const [planTarget, setPlanTarget] = useState<{ id: string; name: string } | null>(null);
  const [actionError, setActionError] = useState("");

  const selectionsQuery = useQuery({
    queryKey: ["student-frameworks", "selections"],
    queryFn: () => studentFrameworksApi.selections(token!),
    enabled: mounted && !!token,
  });

  const availableQuery = useQuery({
    queryKey: ["student-frameworks", "available", applied?.region, applied?.grade],
    queryFn: () => studentFrameworksApi.available(token!, applied!.region, applied!.grade),
    enabled: mounted && !!token && applied !== null,
  });

  const selectMutation = useMutation({
    mutationFn: (frameworkId: string) => studentFrameworksApi.select(token ?? "", frameworkId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student-frameworks"] });
      setActionError("");
    },
    onError: (err: Error) =>
      setActionError(err instanceof ApiError ? err.message : err.message),
  });

  const switchMutation = useMutation({
    mutationFn: (selectionId: string) =>
      studentFrameworksApi.switchVersion(token ?? "", selectionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student-frameworks"] }),
    onError: (err: Error) =>
      setActionError(err instanceof ApiError ? err.message : err.message),
  });

  const dropMutation = useMutation({
    mutationFn: (selectionId: string) => studentFrameworksApi.drop(token ?? "", selectionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student-frameworks"] }),
    onError: (err: Error) =>
      setActionError(err instanceof ApiError ? err.message : err.message),
  });

  function applyFilter(event: React.FormEvent) {
    event.preventDefault();
    const g = Number(grade);
    if (!region.trim() || !Number.isInteger(g) || g < 1 || g > 14) return;
    setApplied({ region: region.trim(), grade: g });
  }

  if (!mounted) {
    return <Skeleton className="h-40 w-full" />;
  }

  const selections = selectionsQuery.data ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("subtitle")}</p>
      </header>

      {actionError && (
        <p className="text-sm text-red-600" role="alert">
          {actionError}
        </p>
      )}

      {/* ── My selections ─────────────────────────────────────────────── */}
      <section className="space-y-3">
        <h3 className="text-lg font-medium text-gray-900">{t("my_title")}</h3>
        {selectionsQuery.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : selectionsQuery.isError ? (
          <ErrorState
            description={t("error")}
            onRetry={() => selectionsQuery.refetch()}
            retryLabel={t("retry")}
          />
        ) : selections.length === 0 ? (
          <EmptyState
            icon={Target}
            title={t("my_empty_title")}
            description={t("my_empty_description")}
          />
        ) : (
          <ul className="space-y-3">
            {selections.map((sel) => (
              <li
                key={sel.id}
                className="rounded-lg border border-gray-200 bg-white p-4 space-y-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-gray-900">{sel.framework_name}</p>
                    <p className="text-sm text-gray-500">{sel.exam_target}</p>
                  </div>
                  <Badge variant={sel.status === "active" ? "success" : "secondary"}>
                    {t(`status.${sel.status}`)}
                  </Badge>
                </div>

                <p className="text-xs text-gray-500">
                  {t("version_label", { version: sel.pinned_version })}
                </p>

                {sel.update_available && (
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 bg-amber-50 p-3">
                    <p className="text-sm text-amber-900">
                      {t("update_available", { version: sel.latest_version })}
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      className="gap-2"
                      loading={switchMutation.isPending && switchMutation.variables === sel.id}
                      onClick={() => switchMutation.mutate(sel.id)}
                    >
                      <ArrowUpCircle className="size-4" aria-hidden="true" />
                      {t("switch")}
                    </Button>
                  </div>
                )}

                {sel.status === "active" && (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => setPlanTarget({ id: sel.id, name: sel.framework_name })}
                    >
                      <BookOpen className="size-4" aria-hidden="true" />
                      {t("view_plan")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="gap-2 text-red-600"
                      loading={dropMutation.isPending && dropMutation.variables === sel.id}
                      onClick={() => dropMutation.mutate(sel.id)}
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      {t("drop")}
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Browse + select ───────────────────────────────────────────── */}
      <section className="space-y-3">
        <h3 className="text-lg font-medium text-gray-900">{t("browse_title")}</h3>
        <form onSubmit={applyFilter} className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-40">
            <Label htmlFor="fw-region">{t("region_label")}</Label>
            <Input
              id="fw-region"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder={t("region_placeholder")}
            />
          </div>
          <div className="w-28">
            <Label htmlFor="fw-grade">{t("grade_label")}</Label>
            <Input
              id="fw-grade"
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              inputMode="numeric"
              placeholder="10"
            />
          </div>
          <Button type="submit" variant="primary" size="md">
            {t("browse_button")}
          </Button>
        </form>

        {applied === null ? (
          <p className="text-sm text-gray-500">{t("browse_hint")}</p>
        ) : availableQuery.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : availableQuery.isError ? (
          <ErrorState
            description={t("error")}
            onRetry={() => availableQuery.refetch()}
            retryLabel={t("retry")}
          />
        ) : (availableQuery.data ?? []).length === 0 ? (
          <EmptyState
            icon={Target}
            title={t("browse_empty_title")}
            description={t("browse_empty_description")}
          />
        ) : (
          <ul className="space-y-3">
            {(availableQuery.data ?? []).map((fw) => {
              const alreadyActive = selections.some(
                (s) => s.framework_id === fw.id && s.status === "active"
              );
              return (
                <li
                  key={fw.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white p-4"
                >
                  <div>
                    <p className="font-medium text-gray-900">{fw.name}</p>
                    <p className="text-sm text-gray-500">
                      {fw.exam_target} · {fw.region}
                    </p>
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    className="gap-2"
                    disabled={alreadyActive}
                    loading={selectMutation.isPending && selectMutation.variables === fw.id}
                    onClick={() => selectMutation.mutate(fw.id)}
                  >
                    <Plus className="size-4" aria-hidden="true" />
                    {alreadyActive ? t("selected") : t("select")}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <Modal
        open={!!planTarget}
        onClose={() => setPlanTarget(null)}
        title={t("plan_modal.title", { name: planTarget?.name ?? "" })}
        size="xl"
        closeLabel={t("plan_modal.close")}
      >
        {planTarget && <StudyPlanPanel selectionId={planTarget.id} token={token ?? ""} />}
      </Modal>
    </div>
  );
}

/** Renders the pinned study plan for a selection — all four UI states. */
function StudyPlanPanel({ selectionId, token }: { selectionId: string; token: string }) {
  const t = useTranslations("student.frameworks");
  const { data, isLoading, isError, refetch } = useQuery<StudentStudyPlanRead>({
    queryKey: ["student-frameworks", "plan", selectionId],
    queryFn: () => studentFrameworksApi.studyPlan(token, selectionId),
    enabled: !!token,
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <ErrorState description={t("plan_modal.error")} onRetry={() => refetch()} retryLabel={t("retry")} />
    );
  }

  const content = data.content_jsonb as {
    topics?: { topic_name?: string; priority_weight?: number }[];
    weekly_pacing?: unknown[];
    exam_strategy?: { scoring_strategy?: string };
  };
  const topics = content.topics ?? [];

  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-gray-500">{t("plan_modal.version")}</dt>
        <dd className="font-medium text-gray-900">{data.version}</dd>
        <dt className="text-gray-500">{t("plan_modal.topics")}</dt>
        <dd className="font-medium text-gray-900">{topics.length}</dd>
        <dt className="text-gray-500">{t("plan_modal.weeks")}</dt>
        <dd className="font-medium text-gray-900">{(content.weekly_pacing ?? []).length}</dd>
      </dl>

      <section>
        <h4 className="text-sm font-semibold text-gray-900 mb-2">{t("plan_modal.topics_heading")}</h4>
        {topics.length === 0 ? (
          <p className="text-sm text-gray-500">{t("plan_modal.no_topics")}</p>
        ) : (
          <ul className="space-y-1 text-sm text-gray-700 max-h-60 overflow-y-auto">
            {topics.map((topic, i) => (
              <li key={i} className="flex items-center justify-between gap-3">
                <span>{topic.topic_name ?? "—"}</span>
                {typeof topic.priority_weight === "number" && (
                  <span className="text-xs text-gray-400">
                    {Math.round(topic.priority_weight * 100)}%
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div>
        <Button variant="outline" size="sm" className="gap-2" onClick={() => refetch()}>
          <RefreshCw className="size-4" aria-hidden="true" />
          {t("retry")}
        </Button>
      </div>
    </div>
  );
}
