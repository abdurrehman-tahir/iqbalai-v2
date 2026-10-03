"use client";

/**
 * "My Highlights" tab (T-188, flow-6 §3.6): the student's own highlights,
 * newest first, each with lecture + concept tags, a link back to the lecture
 * position, and its paired flashcard.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Highlighter } from "lucide-react";
import { studentHighlightsApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { HighlightCard } from "./HighlightCard";

export const MY_HIGHLIGHTS_PAGE_SIZE = 20;

export function MyHighlightsClient() {
  const t = useTranslations("student.highlights");
  const { mounted, token } = useClientAuth();
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["student", "my-highlights", page],
    queryFn: () =>
      studentHighlightsApi.listMine(token!, page, MY_HIGHLIGHTS_PAGE_SIZE),
    enabled: mounted && !!token,
  });

  const items = query.data?.items ?? [];
  const pages = query.data?.pages ?? 1;

  return (
    <section
      className="mx-auto w-full max-w-3xl space-y-4"
      data-testid="my-highlights"
      aria-labelledby="my-highlights-title"
    >
      <header className="space-y-1">
        <h2
          id="my-highlights-title"
          className="text-xl font-semibold text-gray-900 sm:text-2xl"
        >
          {t("title")}
        </h2>
        <p className="text-sm text-gray-600">{t("subtitle")}</p>
      </header>

      {query.isLoading || !mounted ? (
        <div
          className="space-y-3"
          data-testid="my-highlights-loading"
          aria-busy="true"
        >
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState
          description={t("error")}
          retryLabel={t("retry")}
          onRetry={() => void query.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Highlighter}
          title={t("empty_title")}
          description={t("empty_description")}
          action={{ label: t("empty_cta"), href: "/student" }}
        />
      ) : (
        <>
          <ol className="space-y-3" aria-label={t("list_label")}>
            {items.map((item) => (
              <li key={item.id}>
                <HighlightCard item={item} />
              </li>
            ))}
          </ol>
          {pages > 1 ? (
            <nav
              className="flex items-center justify-between gap-2"
              aria-label={t("pagination_label")}
            >
              <Button
                variant="outline"
                size="md"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                {t("prev_page")}
              </Button>
              <span className="text-sm text-gray-600">
                {t("page_of", { page, pages })}
              </span>
              <Button
                variant="outline"
                size="md"
                disabled={page >= pages}
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
              >
                {t("next_page")}
              </Button>
            </nav>
          ) : null}
        </>
      )}
    </section>
  );
}
