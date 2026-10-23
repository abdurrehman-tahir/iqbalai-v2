"use client";

/**
 * Per-cluster drill-down (T-203, Flow 7 §3.6): aggregated wording, each
 * student's exact question and a link to the content element. Student names
 * come from the API for the owning teacher only (§6.19) — Coordinator/Admin
 * get the wording without identities. The teacher may reply to a student
 * (canonical hybrid widget, #57) or skip the cluster so regeneration ignores it.
 */

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { Reply } from "lucide-react";
import {
  lectureWizardApi,
  nextDayReviewApi,
  type ReviewClusterView,
  type ReviewDetailRead,
} from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Modal } from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HybridInputWidget, type VoiceLanguage } from "@/components/shared/HybridInputWidget";

const VOICE_LANGUAGES: readonly VoiceLanguage[] = ["en", "ur", "sd", "ps"];

export function ClusterDrillDown({
  review,
  cluster,
  onClose,
}: {
  review: ReviewDetailRead;
  cluster: ReviewClusterView;
  onClose: () => void;
}) {
  const t = useTranslations("teacher.reviews.drilldown");
  const locale = useLocale();
  const { token } = useClientAuth();
  const qc = useQueryClient();
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const voiceLanguage = VOICE_LANGUAGES.find((l) => l === locale) ?? "en";
  const canTeacherAct = review.is_owner && review.can_act;

  const onUpdated = (updated: ReviewDetailRead) =>
    qc.setQueryData(["reviews", "detail", review.id], updated);

  const replyMutation = useMutation({
    mutationFn: (vars: { studentUserId: string; body: string }) =>
      nextDayReviewApi.reply(token!, review.id, {
        cluster_ref: cluster.cluster_ref,
        student_user_id: vars.studentUserId,
        body: vars.body,
      }),
    onSuccess: (updated) => {
      onUpdated(updated);
      setReplyTo(null);
    },
  });

  const skipMutation = useMutation({
    mutationFn: () =>
      nextDayReviewApi.skipCluster(token!, review.id, { cluster_ref: cluster.cluster_ref }),
    onSuccess: onUpdated,
  });

  const replies = (review.replies ?? []).filter((r) => r.cluster_id === cluster.cluster_ref);

  return (
    <Modal open onClose={onClose} title={t("title")} size="xl" closeLabel={t("close")}>
      <div className="max-h-[70vh] space-y-4 overflow-y-auto" data-testid="cluster-drilldown">
        <div className="space-y-1">
          <p className="font-medium text-gray-900">{cluster.representative_question}</p>
          <p className="text-xs text-gray-500">
            {t("meta", {
              questions: cluster.question_count,
              students: cluster.unique_student_count,
            })}
          </p>
          {cluster.skipped && <Badge variant="secondary">{t("skipped")}</Badge>}
        </div>

        <ul className="space-y-3">
          {(cluster.questions ?? []).map((q) => (
            <li key={q.question_id} className="space-y-2 rounded-md border border-gray-200 p-3">
              {q.student_name && (
                <p className="text-xs font-medium text-gray-700" data-testid="drilldown-student">
                  {q.student_name}
                </p>
              )}
              <p className="text-sm text-gray-900">{q.question_text}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/teacher/lectures/${cluster.lecture_id}${
                    q.paragraph_id ? `?paragraph=${encodeURIComponent(q.paragraph_id)}` : ""
                  }`}
                  className="inline-flex min-h-11 items-center text-sm text-brand-700 hover:underline"
                >
                  {t("open_content")}
                </Link>
                {canTeacherAct && q.student_user_id && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setReplyTo(q.student_user_id ?? null)}
                    aria-expanded={replyTo === q.student_user_id}
                  >
                    <Reply className="me-1 size-4" aria-hidden="true" />
                    {t("reply")}
                  </Button>
                )}
              </div>
              {replies
                .filter((r) => r.student_user_id === q.student_user_id)
                .map((r) => (
                  <p
                    key={r.id}
                    className="rounded bg-brand-50 p-2 text-sm text-gray-800"
                    data-testid="drilldown-reply"
                  >
                    {r.body}
                  </p>
                ))}
              {canTeacherAct && replyTo === q.student_user_id && q.student_user_id && (
                <HybridInputWidget
                  placeholder={t("reply_placeholder")}
                  allowImages={false}
                  allowVoice
                  voiceLanguage={voiceLanguage}
                  disabled={replyMutation.isPending}
                  transcribeAudio={(audio, language) =>
                    lectureWizardApi.transcribeVoice(token!, review.lecture_id, audio, language)
                  }
                  onSubmit={async ({ text }) => {
                    if (!text.trim() || !q.student_user_id) return;
                    await replyMutation.mutateAsync({
                      studentUserId: q.student_user_id,
                      body: text.trim(),
                    });
                  }}
                />
              )}
            </li>
          ))}
        </ul>

        {(replyMutation.isError || skipMutation.isError) && (
          <p className="text-sm text-red-700" role="alert">
            {t("error")}
          </p>
        )}

        {canTeacherAct && !cluster.skipped && (
          <div className="flex justify-end border-t border-gray-100 pt-3">
            <Button
              variant="outline"
              onClick={() => skipMutation.mutate()}
              loading={skipMutation.isPending}
            >
              {t("skip")}
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
}
