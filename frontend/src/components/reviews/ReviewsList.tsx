"use client";

/**
 * Chronological list of next-day review cards (Flow 7 §3.2 / §3.8).
 * Used by the teacher's Reviews page (all lectures) and a lecture's Reviews
 * tab (``lectureId`` set). Reviews never expire, so the full history renders.
 */

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { ChevronRight, ClipboardList } from "lucide-react";
import { nextDayReviewApi, type ReviewSummaryRead } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export function reviewStatusKey(
  review: Pick<ReviewSummaryRead, "status" | "read_only">,
): "pending" | "completed" | "dismissed" | "read_only" {
  if (review.read_only) return "read_only";
  switch (review.status) {
    case "pending":
      return "pending";
    case "completed":
      return "completed";
    case "dismissed":
      return "dismissed";
    default: {
      const _exhaustive: never = review.status;
      throw new Error(`unhandled review status: ${String(_exhaustive)}`);
    }
  }
}

const STATUS_VARIANT = {
  pending: "warning",
  completed: "success",
  dismissed: "secondary",
  read_only: "outline",
} as const;

export function ReviewsList({ lectureId }: { lectureId?: string }) {
  const t = useTranslations("teacher.reviews");
  const format = useFormatter();
  const { mounted, token } = useClientAuth();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reviews", "list", lectureId ?? "all"],
    queryFn: () => nextDayReviewApi.list(token!, lectureId),
    enabled: mounted && !!token,
  });

  if (!mounted || isLoading) {
    return (
      <div className="space-y-3" data-testid="reviews-loading">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        description={t("list.error")}
        onRetry={() => void refetch()}
        retryLabel={t("list.retry")}
      />
    );
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={ClipboardList}
        title={t("list.empty_title")}
        description={t("list.empty_description")}
      />
    );
  }

  return (
    <ul className="space-y-3" data-testid="reviews-list">
      {data.map((review) => {
        const statusKey = reviewStatusKey(review);
        return (
          <li key={review.id}>
            <Link
              href={`/teacher/reviews/${review.id}`}
              className="flex min-h-11 items-center gap-4 rounded-lg border border-gray-200 bg-white p-4 hover:border-brand-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              aria-label={`${t("list.open")}: ${review.offering_label} — ${review.lecture_title}`}
            >
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-gray-900">{review.offering_label}</span>
                  <Badge variant={STATUS_VARIANT[statusKey]}>{t(`status.${statusKey}`)}</Badge>
                </div>
                <p className="truncate text-sm text-gray-600">{review.lecture_title}</p>
                <p className="text-xs text-gray-500">
                  {format.dateTime(new Date(`${review.review_date}T00:00:00`), {
                    dateStyle: "medium",
                  })}{" "}
                  · {t("list.critical_count", { count: review.critical_count })} ·{" "}
                  {t("list.frequent_count", { count: review.high_frequency_count })}
                </p>
              </div>
              <ChevronRight className="size-5 shrink-0 text-gray-400 rtl:rotate-180" aria-hidden="true" />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
