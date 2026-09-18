"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { studentQuizzesApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import type { QuizAttemptResultRead } from "@/lib/api/types";

type Props = { assignmentId: string };

export function QuizAttemptClient({ assignmentId }: Props) {
  const t = useTranslations("student.quiz_attempt");
  const { mounted, token } = useClientAuth();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizAttemptResultRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const quizQuery = useQuery({
    queryKey: ["student", "quiz", assignmentId],
    queryFn: () => studentQuizzesApi.get(token!, assignmentId),
    enabled: mounted && !!token && !!assignmentId,
  });

  const submitMutation = useMutation({
    mutationFn: () => studentQuizzesApi.submit(token!, assignmentId, answers),
    onSuccess: (data) => {
      setResult(data);
      setError(null);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  const allAnswered = useMemo(() => {
    const questions = quizQuery.data?.questions ?? [];
    return questions.length > 0 && questions.every((q) => Boolean(answers[q.id]));
  }, [answers, quizQuery.data?.questions]);

  if (result) {
    return (
      <section className="mx-auto max-w-2xl space-y-4" data-testid="quiz-results">
        <h2 className="text-2xl font-semibold text-gray-900">{t("results_title")}</h2>
        <p className="text-sm text-gray-700">
          {t("score_line", { score: result.score, max: result.max_score })}
        </p>
        <p className="text-sm text-gray-600">{t("results_supportive")}</p>
        <ul className="space-y-3">
          {result.questions.map((q) => (
            <li key={q.question_id} className="rounded-md border border-gray-200 p-3">
              <p className="text-sm font-medium text-gray-900">
                {q.ordinal}. {q.stem}
              </p>
              <p
                className={
                  q.is_correct ? "mt-1 text-sm text-green-700" : "mt-1 text-sm text-amber-700"
                }
              >
                {q.is_correct ? t("correct") : t("review")}
              </p>
              {q.source_excerpt ? (
                <p className="mt-2 text-xs text-gray-500">
                  {t("source_label")}: {q.source_excerpt}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
        <a href="/student" className="text-sm text-blue-600 hover:underline">
          {t("back_dashboard")}
        </a>
      </section>
    );
  }

  const quiz = quizQuery.data;

  return (
    <section className="mx-auto max-w-2xl space-y-4" data-testid="quiz-attempt">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-1 text-sm text-gray-600">
          {quiz ? t("subtitle", { topic: quiz.lecture_topic }) : t("loading")}
        </p>
      </div>

      {quizQuery.isError ? (
        <p className="text-sm text-red-600" role="alert">
          {t("error_generic")}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}

      <ol className="space-y-4">
        {(quiz?.questions ?? []).map((q) => (
          <li key={q.id} className="rounded-md border border-gray-200 p-3 space-y-2">
            <p className="text-sm font-medium text-gray-900">
              {q.ordinal}. {q.stem}
            </p>
            <fieldset className="space-y-1">
              <legend className="sr-only">{t("options_legend", { n: q.ordinal })}</legend>
              {q.options.map((opt) => (
                <label key={opt.key} className="flex items-start gap-2 text-sm text-gray-800">
                  <input
                    type="radio"
                    name={`q-${q.id}`}
                    value={opt.key}
                    checked={answers[q.id] === opt.key}
                    onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: opt.key }))}
                  />
                  <span>
                    {opt.key}. {opt.text}
                  </span>
                </label>
              ))}
            </fieldset>
          </li>
        ))}
      </ol>

      <Button
        type="button"
        onClick={() => submitMutation.mutate()}
        disabled={!allAnswered || submitMutation.isPending || !quiz}
      >
        {submitMutation.isPending ? t("submitting") : t("submit")}
      </Button>
    </section>
  );
}
