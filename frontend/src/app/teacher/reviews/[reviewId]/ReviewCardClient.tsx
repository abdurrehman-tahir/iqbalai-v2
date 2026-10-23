"use client";

/**
 * Next-day review card — locked layout (Flow 7 §3.3): header, AI summary,
 * reflective question, three columns (Critical / High Frequency / Mini-Lecture
 * Preview) and the action row. Leaving the card without acting keeps
 * ``pending_action`` set server-side (T-201 #5) — nothing is written on view.
 */

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { AlertTriangle, ArrowLeft, FileText, TrendingUp } from "lucide-react";
import { nextDayReviewApi, type ReviewClusterView, type ReviewDetailRead } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { reviewStatusKey } from "@/components/reviews/ReviewsList";

/** Flow 7 §6: top 10 clusters per column, overflow behind "and N more". */
export const COLUMN_LIMIT = 10;

export function reviewQueryKey(reviewId: string) {
  return ["reviews", "detail", reviewId] as const;
}

function ClusterColumn({
  title,
  icon: Icon,
  clusters,
  testId,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  clusters: ReviewClusterView[];
  testId: string;
}) {
  const t = useTranslations("teacher.reviews.card");
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? clusters : clusters.slice(0, COLUMN_LIMIT);
  const hidden = clusters.length - visible.length;

  return (
    <section aria-labelledby={`${testId}-title`} data-testid={testId} className="space-y-3">
      <h3 id={`${testId}-title`} className="flex items-center gap-2 font-semibold text-gray-900">
        <Icon className="size-4" aria-hidden="true" />
        {title}
        <Badge variant="secondary">{clusters.length}</Badge>
      </h3>
      {clusters.length === 0 ? (
        <p className="text-sm text-gray-500">{t("column_empty")}</p>
      ) : (
        <ul className="space-y-2">
          {visible.map((cluster) => (
            <li
              key={cluster.cluster_ref}
              className="rounded-md border border-gray-200 bg-white p-3"
              data-testid="review-cluster"
            >
              <p className="text-sm text-gray-900">{cluster.representative_question}</p>
              <p className="mt-1 text-xs text-gray-500">
                {t("cluster_meta", {
                  questions: cluster.question_count,
                  students: cluster.unique_student_count,
                })}
              </p>
            </li>
          ))}
        </ul>
      )}
      {hidden > 0 && (
        <Button variant="ghost" size="sm" onClick={() => setExpanded(true)}>
          {t("more", { count: hidden })}
        </Button>
      )}
    </section>
  );
}

function MiniPreview({ review }: { review: ReviewDetailRead }) {
  const t = useTranslations("teacher.reviews.card");
  return (
    <section aria-labelledby="mini-title" data-testid="review-mini" className="space-y-3">
      <h3 id="mini-title" className="flex items-center gap-2 font-semibold text-gray-900">
        <FileText className="size-4" aria-hidden="true" />
        {t("mini_title")}
      </h3>
      {review.mini_lecture_id && review.mini_preview ? (
        <div className="space-y-3 rounded-md border border-gray-200 bg-white p-3">
          <p className="text-sm text-gray-700">{review.mini_preview}</p>
          {review.mini_published && <Badge variant="success">{t("mini_published")}</Badge>}
          <Link
            href={`/teacher/lectures/${review.mini_lecture_id}`}
            className="inline-flex min-h-11 items-center text-sm font-medium text-brand-700 hover:underline"
          >
            {t("mini_open")}
          </Link>
        </div>
      ) : (
        <p className="text-sm text-gray-500">{t("mini_none")}</p>
      )}
    </section>
  );
}

export function ReviewCardClient({ reviewId }: { reviewId: string }) {
  const t = useTranslations("teacher.reviews");
  const format = useFormatter();
  const { mounted, token } = useClientAuth();

  const { data: review, isLoading, isError, refetch } = useQuery({
    queryKey: reviewQueryKey(reviewId),
    queryFn: () => nextDayReviewApi.get(token!, reviewId),
    enabled: mounted && !!token,
  });

  if (!mounted || isLoading) {
    return (
      <main className="mx-auto w-full max-w-6xl space-y-4 px-4 py-8" data-testid="review-loading">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </main>
    );
  }

  if (isError || !review) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-8">
        <ErrorState
          description={t("card.error")}
          onRetry={() => void refetch()}
          retryLabel={t("card.retry")}
        />
      </main>
    );
  }

  const statusKey = reviewStatusKey(review);

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-8" data-testid="review-card">
      <Link
        href="/teacher/reviews"
        className="inline-flex min-h-11 items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="size-4 rtl:rotate-180" aria-hidden="true" />
        {t("card.back")}
      </Link>

      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">
            {t("card.heading", { label: review.offering_label })}
          </h1>
          <Badge variant={statusKey === "pending" ? "warning" : "secondary"}>
            {t(`status.${statusKey}`)}
          </Badge>
        </div>
        <p className="text-sm text-gray-600">{t("card.topic", { title: review.lecture_title })}</p>
        <p className="text-xs text-gray-500">
          {t("card.generated", {
            date: format.dateTime(new Date(`${review.review_date}T00:00:00`), {
              dateStyle: "long",
            }),
          })}
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("card.summary_title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-700" data-testid="review-summary">
            {review.ai_summary || t("card.summary_empty")}
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <ClusterColumn
          title={t("card.critical_title")}
          icon={AlertTriangle}
          clusters={review.critical ?? []}
          testId="review-critical"
        />
        <ClusterColumn
          title={t("card.frequent_title")}
          icon={TrendingUp}
          clusters={review.high_frequency ?? []}
          testId="review-frequent"
        />
        <MiniPreview review={review} />
      </div>
    </main>
  );
}
