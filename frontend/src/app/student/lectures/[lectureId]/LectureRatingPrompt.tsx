"use client";

/**
 * Optional, dismissable 1–5 star rating shown once the lecture is completed
 * (T-192, flow-6 §3.11). Non-blocking: rendered inline at the end of the
 * lecture, never as a modal. Ratings are anonymous coaching for the teacher —
 * the prompt says so — and are never shown to other students.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Star, X } from "lucide-react";
import { lectureRatingApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";

type Props = { lectureId: string; completed: boolean };

const STARS = [1, 2, 3, 4, 5] as const;

export function dismissKey(lectureId: string): string {
  return `lecture-rating-dismissed:${lectureId}`;
}

function readDismissed(lectureId: string): boolean {
  try {
    return sessionStorage.getItem(dismissKey(lectureId)) === "1";
  } catch {
    return false;
  }
}

export function LectureRatingPrompt({ lectureId, completed }: Props) {
  const t = useTranslations("student.lecture_rating");
  const { mounted, token } = useClientAuth();
  const queryClient = useQueryClient();
  const [dismissed, setDismissed] = useState(() => readDismissed(lectureId));
  const [selected, setSelected] = useState<number | null>(null);

  const mine = useQuery({
    queryKey: ["student", "lecture-rating", lectureId],
    queryFn: () => lectureRatingApi.getMine(token!, lectureId),
    enabled: mounted && !!token && completed && !dismissed,
  });

  const submit = useMutation({
    mutationFn: (rating: number) =>
      lectureRatingApi.submit(token!, lectureId, { rating }),
    onSuccess: (data) => {
      queryClient.setQueryData(["student", "lecture-rating", lectureId], data);
    },
  });

  const dismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem(dismissKey(lectureId), "1");
    } catch {
      // storage unavailable — dismissal still holds for this view
    }
  };

  // Only after completion; never once dismissed; never if already rated
  // (unless the student just rated here — then show the thanks state).
  if (!completed || dismissed || !mine.data) return null;
  if (mine.data.rating != null && !submit.isSuccess) return null;

  return (
    <section
      className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
      aria-labelledby="lecture-rating-title"
      data-testid="lecture-rating-prompt"
      dir="auto"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2
            id="lecture-rating-title"
            className="text-base font-semibold text-gray-900"
          >
            {submit.isSuccess ? t("thanks_title") : t("title")}
          </h2>
          <p className="text-sm text-gray-600">
            {submit.isSuccess ? t("thanks_body") : t("subtitle")}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("dismiss")}
          onClick={dismiss}
          data-testid="lecture-rating-dismiss"
          className="size-11"
        >
          <X className="size-5" aria-hidden="true" />
        </Button>
      </div>

      {!submit.isSuccess ? (
        <>
          <div
            role="radiogroup"
            aria-label={t("stars_label")}
            className="flex flex-wrap gap-1"
          >
            {STARS.map((value) => {
              const active = selected !== null && value <= selected;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selected === value}
                  aria-label={t("star_label", { count: value })}
                  onClick={() => setSelected(value)}
                  className="inline-flex size-11 items-center justify-center rounded-md hover:bg-amber-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                  data-testid={`lecture-rating-star-${value}`}
                >
                  <Star
                    className={`size-7 ${active ? "fill-amber-400 text-amber-500" : "text-gray-400"}`}
                    aria-hidden="true"
                  />
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="md"
              disabled={selected === null || submit.isPending}
              onClick={() => selected !== null && submit.mutate(selected)}
              data-testid="lecture-rating-submit"
            >
              {submit.isPending ? t("submitting") : t("submit")}
            </Button>
            <span className="text-xs text-gray-500">{t("privacy_note")}</span>
          </div>
          {submit.isError ? (
            <p className="text-sm text-red-600" role="alert">
              {t("error")}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
