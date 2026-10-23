"use client";

/**
 * Reflective coaching question on the review card (T-202, Flow 7 §3.3 #49).
 * Coaching, never grading — the question itself is filtered server-side; the
 * teacher answers by typing or by voice through the canonical hybrid widget
 * (#57), transcribed via the teacher voice-transcribe endpoint of the lecture.
 * Optional: the card works fine if the teacher never answers.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { CheckCircle2, MessageCircleQuestion } from "lucide-react";
import { lectureWizardApi, nextDayReviewApi, type ReviewDetailRead } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { HybridInputWidget, type VoiceLanguage } from "@/components/shared/HybridInputWidget";

const VOICE_LANGUAGES: readonly VoiceLanguage[] = ["en", "ur", "sd", "ps"];

export function ReflectivePrompt({ review }: { review: ReviewDetailRead }) {
  const t = useTranslations("teacher.reviews.reflection");
  const locale = useLocale();
  const { token } = useClientAuth();
  const qc = useQueryClient();
  const voiceLanguage = VOICE_LANGUAGES.find((l) => l === locale) ?? "en";

  const mutation = useMutation({
    mutationFn: (response: string) =>
      nextDayReviewApi.reflect(token!, review.id, { response }),
    onSuccess: (updated) => qc.setQueryData(["reviews", "detail", review.id], updated),
  });

  if (!review.reflective_prompt) return null;

  return (
    <Card data-testid="review-reflection">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageCircleQuestion className="size-4" aria-hidden="true" />
          {t("title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-gray-800">{review.reflective_prompt}</p>
        {review.reflected ? (
          <p className="flex items-center gap-2 text-sm text-green-700" role="status">
            <CheckCircle2 className="size-4" aria-hidden="true" />
            {t("saved")}
          </p>
        ) : review.is_owner && review.can_act ? (
          <div className="space-y-2">
            <p className="text-xs text-gray-500">{t("hint")}</p>
            <HybridInputWidget
              placeholder={t("placeholder")}
              allowImages={false}
              allowVoice
              voiceLanguage={voiceLanguage}
              disabled={mutation.isPending}
              transcribeAudio={(audio, language) =>
                lectureWizardApi.transcribeVoice(token!, review.lecture_id, audio, language)
              }
              onSubmit={async ({ text }) => {
                if (text.trim()) await mutation.mutateAsync(text.trim());
              }}
            />
            {mutation.isError && (
              <p className="text-sm text-red-700" role="alert">
                {t("error")}
              </p>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
