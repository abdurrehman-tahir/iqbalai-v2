"use client";

/**
 * Version-by-version score timeline (T-137, #35). Shared between the school
 * and independent wizards — same pattern as LectureEditorPanel.tsx (a
 * generic `api.listVersions` prop, not a tenant-specific import).
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { useTranslations } from "next-intl";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import type { LectureVersionListResponse, LectureVersionRead } from "@/lib/api/types";

const PAGE_SIZE = 6;
// Matches scoring.py's _DIMENSION_CAPS total (10+10+5+5+10+5+10).
const MAX_TOTAL_SCORE = 55;
const LINE_COLOR = "#2563eb"; // Recharts needs a real color value, not a Tailwind class.

const DIMENSION_KEYS = [
  "originality",
  "depth",
  "cultural_relevance",
  "engagement",
  "alignment",
  "voice_quality",
  "ai_learning",
] as const;

interface ScoreTimelineApi {
  listVersions: (
    token: string,
    lectureId: string,
    page?: number,
    pageSize?: number
  ) => Promise<LectureVersionListResponse>;
}

interface ScoreTimelineChartProps {
  token: string;
  lectureId: string;
  api: ScoreTimelineApi;
  t: ReturnType<typeof useTranslations>;
  queryKeyPrefix: string;
}

interface ChartPoint {
  version: number;
  total: number;
  dimensions: Record<(typeof DIMENSION_KEYS)[number], number | null>;
  annotations: string[];
}

function toChartPoint(v: LectureVersionRead): ChartPoint {
  const scores = (v.scores_jsonb ?? {}) as Record<string, unknown>;
  const total = typeof scores.total === "number" ? scores.total : 0;
  const dimensions = Object.fromEntries(
    DIMENSION_KEYS.map((key) => [
      key,
      typeof scores[key] === "number" ? (scores[key] as number) : null,
    ])
  ) as ChartPoint["dimensions"];
  return { version: v.version, total, dimensions, annotations: v.edit_summary ?? [] };
}

function TimelineTooltip({
  active,
  payload,
  t,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartPoint }>;
  t: ReturnType<typeof useTranslations>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]!.payload;

  return (
    <div className="rounded-md border border-gray-200 bg-white p-2 text-xs shadow-md" dir="ltr">
      <p className="font-medium text-gray-900">
        {t("editor_version_label", { version: point.version })} —{" "}
        {t("timeline_total_label", { total: point.total, max: MAX_TOTAL_SCORE })}
      </p>
      <ul className="mt-1 space-y-0.5 text-gray-700">
        {DIMENSION_KEYS.map((key) => (
          <li key={key}>
            {t(`timeline_dimension_${key}`)}: {point.dimensions[key] ?? t("timeline_dimension_na")}
          </li>
        ))}
      </ul>
      {point.annotations.length > 0 ? (
        <ul className="mt-1 space-y-0.5 border-t border-gray-100 pt-1 text-gray-500">
          {point.annotations.map((annotation, i) => (
            <li key={i}>• {annotation}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function ScoreTimelineChart({
  token,
  lectureId,
  api,
  t,
  queryKeyPrefix,
}: ScoreTimelineChartProps) {
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: [queryKeyPrefix, "lecture-score-timeline", lectureId, page],
    queryFn: () => api.listVersions(token, lectureId, page, PAGE_SIZE),
  });

  if (query.isLoading) {
    return (
      <section className="space-y-2" aria-busy="true">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-56 w-full" />
      </section>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        title={t("timeline_error")}
        description={t("timeline_error")}
        onRetry={() => void query.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  const items = query.data?.items ?? [];

  if (items.length === 0) {
    return (
      <section className="space-y-2" aria-labelledby="timeline-heading">
        <h3 id="timeline-heading" className="text-lg font-medium text-gray-900">
          {t("timeline_title")}
        </h3>
        <p className="text-sm text-gray-600">{t("timeline_empty")}</p>
      </section>
    );
  }

  // The API returns newest-first (pagination semantics); the chart's x-axis
  // must read left-to-right ascending by version number.
  const chartData = [...items].reverse().map(toChartPoint);
  const total = query.data?.total ?? items.length;
  const hasOlder = page * PAGE_SIZE < total;
  const hasNewer = page > 1;

  return (
    <section className="space-y-3" aria-labelledby="timeline-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="timeline-heading" className="text-lg font-medium text-gray-900">
          {t("timeline_title")}
        </h3>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasOlder}
          >
            {t("timeline_older")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={!hasNewer}
          >
            {t("timeline_newer")}
          </Button>
        </div>
      </div>

      {/* x-axis is a version-number time series: always left-to-right,
          regardless of the app's RTL locale (ARCH §13.12). */}
      <div dir="ltr" className="h-64 w-full rounded-md border border-gray-200 p-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="version" />
            <YAxis domain={[0, MAX_TOTAL_SCORE]} />
            <Tooltip content={<TimelineTooltip t={t} />} />
            <Line
              type="monotone"
              dataKey="total"
              stroke={LINE_COLOR}
              strokeWidth={2}
              dot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
