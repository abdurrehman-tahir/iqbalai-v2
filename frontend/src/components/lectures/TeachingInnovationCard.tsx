"use client";

/**
 * Teaching Innovation Record card (T-138, #36) — coaching tips, never
 * grading (Flow 5 §3.10 locked rule: no score/number ever appears here).
 * Teacher-scoped (not lecture-scoped), shared between the school and
 * independent wizards like LectureEditorPanel/ScoreTimelineChart.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import type { CoachingResponseRequest, CoachingSuggestionRead } from "@/lib/api/types";

interface TeachingCoachingApi {
  listSuggestions: (token: string) => Promise<CoachingSuggestionRead[]>;
  respondToSuggestion: (
    token: string,
    memoryId: string,
    data: CoachingResponseRequest
  ) => Promise<CoachingSuggestionRead>;
}

interface TeachingInnovationCardProps {
  token: string;
  api: TeachingCoachingApi;
  t: ReturnType<typeof useTranslations>;
  queryKeyPrefix: string;
}

export function TeachingInnovationCard({
  token,
  api,
  t,
  queryKeyPrefix,
}: TeachingInnovationCardProps) {
  const queryClient = useQueryClient();
  const queryKey = [queryKeyPrefix, "coaching-suggestions"];

  const query = useQuery({
    queryKey,
    queryFn: () => api.listSuggestions(token),
  });

  const respondMutation = useMutation({
    mutationFn: ({ memoryId, response }: { memoryId: string; response: "acted" | "ignored" }) =>
      api.respondToSuggestion(token, memoryId, { response }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
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
        title={t("coaching_error")}
        description={t("coaching_error")}
        onRetry={() => void query.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  const suggestions = query.data ?? [];

  // No pending tip right now is the common case — a quiet mentor doesn't
  // nag every time there's nothing to say (matches the topic-relevance
  // gauge's own "render nothing when there's nothing to show" pattern).
  if (suggestions.length === 0) {
    return null;
  }

  return (
    <section
      className="space-y-2 rounded-md border border-emerald-200 bg-emerald-50 p-3"
      aria-labelledby="coaching-heading"
    >
      <h3 id="coaching-heading" className="text-sm font-medium text-emerald-900">
        {t("coaching_title")}
      </h3>
      <ul className="space-y-3">
        {suggestions.map((suggestion) => (
          <li key={suggestion.id} className="space-y-1.5">
            <p className="text-sm text-emerald-900" dir="auto">
              {suggestion.suggestion}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={respondMutation.isPending}
                onClick={() =>
                  respondMutation.mutate({ memoryId: suggestion.id, response: "acted" })
                }
              >
                {t("coaching_act")}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={respondMutation.isPending}
                onClick={() =>
                  respondMutation.mutate({ memoryId: suggestion.id, response: "ignored" })
                }
              >
                {t("coaching_dismiss")}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
