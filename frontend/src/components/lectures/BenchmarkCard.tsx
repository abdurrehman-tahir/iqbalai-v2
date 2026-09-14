"use client";

/**
 * Teacher-facing anonymized benchmark card (T-139, #37) — "Top X% of
 * {subject} teachers in {region}", never a raw score (Flow 5 §3.11 locked
 * rule). School tenant only — no independent counterpart (one-person
 * tenants have no peer cohort). Renders nothing before the first result
 * arrives, matching TeachingInnovationCard's "quiet when there's nothing
 * to say" pattern, but always keeps the opt-out control visible once
 * loaded so a teacher can manage the setting proactively.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { teacherBenchmarksApi } from "@/lib/api";
import type { TeacherBenchmarkRead } from "@/lib/api/types";

interface BenchmarkCardProps {
  token: string;
  t: ReturnType<typeof useTranslations>;
  queryKeyPrefix: string;
}

export function BenchmarkCard({ token, t, queryKeyPrefix }: BenchmarkCardProps) {
  const queryClient = useQueryClient();
  // The list endpoint only ever returns non-opted-out rows (backend §37 rule),
  // so an empty list doesn't distinguish "opted out" from "not yet computed" —
  // this local toggle tracks the session's own action rather than re-deriving
  // it from the list response. A documented, low-stakes UX gap: it resets to
  // the opt-out label on a fresh page load even if the teacher opted out
  // earlier, but the underlying rows stay correctly cleared server-side.
  const [optedOut, setOptedOut] = useState(false);
  const queryKey = [queryKeyPrefix, "benchmarks"];

  const query = useQuery({
    queryKey,
    queryFn: () => teacherBenchmarksApi.list(token),
  });

  const optOutMutation = useMutation({
    mutationFn: (value: boolean) => teacherBenchmarksApi.setOptOut(token, { opted_out: value }),
    onSuccess: (_result, value) => {
      setOptedOut(value);
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  if (query.isLoading) {
    return (
      <section className="space-y-2" aria-busy="true">
        <Skeleton className="h-16 w-full" />
      </section>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        title={t("benchmark_error")}
        description={t("benchmark_error")}
        onRetry={() => void query.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  const rows: TeacherBenchmarkRead[] = query.data ?? [];

  return (
    <section
      className="space-y-2 rounded-md border border-indigo-200 bg-indigo-50 p-3"
      aria-labelledby="benchmark-heading"
    >
      <h3 id="benchmark-heading" className="text-sm font-medium text-indigo-900">
        {t("benchmark_title")}
      </h3>
      {rows.length === 0 ? (
        <p className="text-sm text-indigo-800">{t("benchmark_empty")}</p>
      ) : (
        <ul className="space-y-1">
          {rows.map((row) => (
            <li key={row.id} className="text-sm text-indigo-900">
              {t("benchmark_line", {
                percent: row.top_percent,
                subject: row.subject_name,
                region: row.region,
              })}
            </li>
          ))}
        </ul>
      )}
      <Button
        type="button"
        size="sm"
        variant="ghost"
        disabled={optOutMutation.isPending}
        onClick={() => optOutMutation.mutate(!optedOut)}
      >
        {optedOut ? t("benchmark_opt_in") : t("benchmark_opt_out")}
      </Button>
    </section>
  );
}
