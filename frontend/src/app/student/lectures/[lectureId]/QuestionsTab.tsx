"use client";

import { useTranslations } from "next-intl";
import type { StudentQuestionRead } from "@/lib/api";

type Props = {
  questions: StudentQuestionRead[];
  loading?: boolean;
  onOpen: (question: StudentQuestionRead) => void;
};

export function QuestionsTab({ questions, loading, onOpen }: Props) {
  const t = useTranslations("student.lecture_viewer");

  return (
    <section className="mx-auto w-full max-w-3xl px-4 pb-8" data-testid="questions-tab">
      <h2 className="mb-3 text-sm font-semibold text-gray-900">{t("questions_tab")}</h2>
      {loading ? (
        <p className="text-sm text-gray-500">{t("loading")}</p>
      ) : questions.length === 0 ? (
        <p className="text-sm text-gray-500" data-testid="questions-empty">
          {t("questions_empty")}
        </p>
      ) : (
        <ul className="space-y-2">
          {questions.map((q) => (
            <li key={q.id}>
              <button
                type="button"
                className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-start text-sm hover:bg-gray-50"
                onClick={() => onOpen(q)}
                data-testid="question-history-item"
              >
                <span className="line-clamp-2 text-gray-900">{q.question_text}</span>
                <span className="mt-1 block text-[11px] text-gray-500">
                  {new Date(q.asked_at).toLocaleString()}
                  {q.answered_at ? ` · ${t("answered")}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
