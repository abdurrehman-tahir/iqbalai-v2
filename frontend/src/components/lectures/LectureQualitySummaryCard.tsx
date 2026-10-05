"use client";

/**
 * Teacher view of the displayed lecture quality score (T-192, flow-6 §3.11):
 * M-10 AI score (95%) blended with the students' anonymous rating average (5%).
 * Only the aggregate is ever shown — no individual ratings, no student names —
 * and the average stays hidden until enough students have rated.
 */

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { Star } from "lucide-react";
import { lectureRatingApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type Props = { token: string; lectureId: string };

export function LectureQualitySummaryCard({ token, lectureId }: Props) {
  const t = useTranslations("teacher.lecture_quality");
  const format = useFormatter();
  const query = useQuery({
    queryKey: ["teacher", "lecture-rating-summary", lectureId],
    queryFn: () => lectureRatingApi.summary(token, lectureId),
    enabled: !!token && !!lectureId,
  });

  return (
    <section
      className="space-y-2 rounded-lg border border-gray-200 bg-white p-4"
      aria-labelledby="lecture-quality-title"
      data-testid="lecture-quality-summary"
    >
      <h3
        id="lecture-quality-title"
        className="text-base font-semibold text-gray-900"
      >
        {t("title")}
      </h3>
      {query.isLoading ? (
        <Skeleton
          className="h-16 w-full"
          data-testid="lecture-quality-loading"
        />
      ) : query.isError ? (
        <div role="alert" className="space-y-2">
          <p className="text-sm text-gray-700">{t("error")}</p>
          <Button
            variant="outline"
            size="md"
            onClick={() => void query.refetch()}
          >
            {t("retry")}
          </Button>
        </div>
      ) : query.data ? (
        <div className="space-y-2 text-sm text-gray-800">
          <p
            className="text-2xl font-semibold text-gray-900"
            data-testid="lecture-quality-score"
          >
            {query.data.quality_score === null ||
            query.data.quality_score === undefined
              ? t("score_pending")
              : t("score", { score: format.number(query.data.quality_score) })}
          </p>
          <p data-testid="lecture-quality-ai">
            {query.data.ai_score === null || query.data.ai_score === undefined
              ? t("ai_pending")
              : t("ai_line", {
                  score: query.data.ai_score,
                  max: query.data.ai_score_max,
                })}
          </p>
          <p
            className="flex items-center gap-1"
            data-testid="lecture-quality-rating"
          >
            <Star className="size-4 text-amber-500" aria-hidden="true" />
            {query.data.average_rating === null ||
            query.data.average_rating === undefined
              ? query.data.rating_count === 0
                ? t("no_ratings")
                : t("ratings_hidden", {
                    count: query.data.rating_count,
                    min: query.data.min_ratings_for_display,
                  })
              : t("rating_line", {
                  average: format.number(query.data.average_rating, {
                    maximumFractionDigits: 1,
                  }),
                  count: query.data.rating_count,
                })}
          </p>
          <p className="text-xs text-gray-500">
            {t("weighting_note", {
              weight: Math.round(query.data.rating_weight * 100),
            })}
          </p>
        </div>
      ) : null}
    </section>
  );
}
