"use client";

/**
 * Admin comparative teacher metrics table (T-139, Flow 5 §3.11 #38).
 * Shared across all three admin shells (Platform/District/School) — the
 * backend already scopes rows by the caller's role/claims, so this
 * component doesn't need to know which shell it's mounted under.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { BarChart3 } from "lucide-react";
import { adminMetricsApi, type TeacherMetricsRead } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type SortKey =
  | "teacher_name"
  | "subject_name"
  | "grade_range"
  | "school_name"
  | "lecture_count"
  | "avg_total"
  | "avg_topic_relevance_pct";

const DEFAULT_SORT: SortKey = "avg_total";

function sortRows(
  rows: TeacherMetricsRead[],
  key: SortKey,
  direction: "asc" | "desc"
): TeacherMetricsRead[] {
  const sorted = [...rows].sort((a, b) => {
    const av = a[key];
    const bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "number" && typeof bv === "number") return av - bv;
    return String(av).localeCompare(String(bv));
  });
  return direction === "asc" ? sorted : sorted.reverse();
}

export function TeacherMetricsClient() {
  const t = useTranslations("admin.metrics");
  const { mounted, token } = useClientAuth();
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>(DEFAULT_SORT);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [exporting, setExporting] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["admin-metrics", "teacher-metrics"],
    queryFn: () => adminMetricsApi.listTeacherMetrics(token!),
    enabled: mounted && !!token,
  });

  const rows = useMemo(() => {
    const all = data ?? [];
    const query = search.trim().toLowerCase();
    const filtered = query
      ? all.filter(
          (row) =>
            row.teacher_name.toLowerCase().includes(query) ||
            row.subject_name.toLowerCase().includes(query) ||
            row.school_name.toLowerCase().includes(query)
        )
      : all;
    return sortRows(filtered, sortKey, sortDir);
  }, [data, search, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  async function handleExport() {
    if (!token) return;
    setExporting(true);
    try {
      const blob = await adminMetricsApi.exportTeacherMetricsCsv(token);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "teacher-metrics.csv";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState description={t("error")} onRetry={() => refetch()} retryLabel={t("retry")} />
    );
  }

  const columns: { key: SortKey; label: string }[] = [
    { key: "teacher_name", label: t("col.teacher") },
    { key: "subject_name", label: t("col.subject") },
    { key: "grade_range", label: t("col.grade") },
    { key: "school_name", label: t("col.school") },
    { key: "lecture_count", label: t("col.lecture_count") },
    { key: "avg_total", label: t("col.avg_total") },
    { key: "avg_topic_relevance_pct", label: t("col.avg_topic_relevance") },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <Button type="button" variant="outline" onClick={() => void handleExport()} loading={exporting}>
          {t("export_csv")}
        </Button>
      </div>

      <Input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder={t("search_placeholder")}
        aria-label={t("search_placeholder")}
        className="max-w-sm"
      />

      {rows.length === 0 ? (
        <EmptyState
          icon={BarChart3}
          title={t("empty.title")}
          description={t("empty.description")}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" role="table" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-start">
                {columns.map((col) => (
                  <th key={col.key} className="px-4 py-3 text-start font-medium text-gray-500">
                    <button
                      type="button"
                      className="flex items-center gap-1"
                      onClick={() => toggleSort(col.key)}
                      aria-label={t("sort_by", { column: col.label })}
                    >
                      {col.label}
                      {sortKey === col.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => (
                <tr
                  key={`${row.teacher_user_id}-${row.subject_id}-${row.grade_range}`}
                  className="hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">{row.teacher_name}</td>
                  <td className="px-4 py-3 text-gray-600">{row.subject_name}</td>
                  <td className="px-4 py-3 text-gray-600">{row.grade_range}</td>
                  <td className="px-4 py-3 text-gray-600">{row.school_name}</td>
                  <td className="px-4 py-3 text-gray-600">{row.lecture_count}</td>
                  <td className="px-4 py-3 text-gray-600">{row.avg_total}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {row.avg_topic_relevance_pct != null
                      ? `${row.avg_topic_relevance_pct}%`
                      : t("col.na")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
