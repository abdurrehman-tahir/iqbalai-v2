"use client";

/**
 * Review card action row (T-205, Flow 7 §3.6). Multiple actions are allowed
 * per review (recorded server-side in ``acted_actions``):
 * - Publish Mini-Lecture → targeted distribution (T-204)
 * - Edit Main Lecture → Flow 5 edit mode with a context banner
 * - Schedule Group Study → present but disabled until Flow 11 ships
 * - Dismiss without action → recoverable (Reopen)
 */

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { CalendarClock, Pencil, Send, Undo2, X } from "lucide-react";
import { ApiError, nextDayReviewApi, type ReviewDetailRead } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";

type Action = "publishMini" | "editMain" | "dismiss" | "reopen";

export function ReviewActions({ review }: { review: ReviewDetailRead }) {
  const t = useTranslations("teacher.reviews.actions");
  const { token } = useClientAuth();
  const qc = useQueryClient();
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: (action: Action) => nextDayReviewApi[action](token!, review.id),
    onSuccess: (updated, action) => {
      qc.setQueryData(["reviews", "detail", review.id], updated);
      void qc.invalidateQueries({ queryKey: ["reviews", "list"] });
      if (action === "editMain") {
        router.push(`/teacher/lectures/${review.lecture_id}?from_review=${review.id}`);
      }
    },
  });

  if (!review.can_act) return null;

  const dismissed = review.status === "dismissed";
  const busy = mutation.isPending;
  const pendingAction = busy ? mutation.variables : undefined;
  const errorMessage =
    mutation.error instanceof ApiError && mutation.error.code === "PRECONDITION_FAILED"
      ? t("publish_no_recipients")
      : t("error");

  return (
    <section aria-label={t("aria_label")} className="space-y-2" data-testid="review-actions">
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => mutation.mutate("publishMini")}
          disabled={busy || !review.mini_lecture_id || review.mini_published || dismissed}
          loading={pendingAction === "publishMini"}
        >
          <Send className="me-1 size-4" aria-hidden="true" />
          {review.mini_published ? t("published") : t("publish")}
        </Button>
        <Button
          variant="outline"
          onClick={() => mutation.mutate("editMain")}
          disabled={busy}
          loading={pendingAction === "editMain"}
        >
          <Pencil className="me-1 size-4" aria-hidden="true" />
          {t("edit_main")}
        </Button>
        {/* BLOCKED-HOOK: Flow 11 / M-20 group-study scheduler — disabled until it exists. */}
        <Button variant="outline" disabled aria-describedby="group-study-note">
          <CalendarClock className="me-1 size-4" aria-hidden="true" />
          {t("group_study")}
        </Button>
        {dismissed ? (
          <Button
            variant="ghost"
            onClick={() => mutation.mutate("reopen")}
            disabled={busy}
            loading={pendingAction === "reopen"}
          >
            <Undo2 className="me-1 size-4" aria-hidden="true" />
            {t("reopen")}
          </Button>
        ) : (
          <Button
            variant="ghost"
            onClick={() => mutation.mutate("dismiss")}
            disabled={busy}
            loading={pendingAction === "dismiss"}
          >
            <X className="me-1 size-4" aria-hidden="true" />
            {t("dismiss")}
          </Button>
        )}
      </div>
      <p id="group-study-note" className="text-xs text-gray-500">
        {t("group_study_soon")}
      </p>
      {mutation.isError && (
        <p className="text-sm text-red-700" role="alert">
          {errorMessage}
        </p>
      )}
    </section>
  );
}
