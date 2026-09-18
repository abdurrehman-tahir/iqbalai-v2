"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { studentQuizzesApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function StudentQuizzesPanel() {
  const t = useTranslations("student.quizzes");
  const { mounted, token } = useClientAuth();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["student", "quizzes"],
    queryFn: () => studentQuizzesApi.list(token!),
    enabled: mounted && !!token,
  });

  return (
    <section
      className="rounded-lg border border-gray-200 bg-white p-4 space-y-3"
      data-testid="student-quizzes"
      aria-label={t("title")}
    >
      <div>
        <h3 className="text-lg font-medium text-gray-900">{t("title")}</h3>
        <p className="text-sm text-gray-600">{t("subtitle")}</p>
      </div>

      {isLoading ? <p className="text-sm text-gray-500">{t("loading")}</p> : null}
      {isError ? (
        <p className="text-sm text-red-600" role="alert">
          {t("error")}
        </p>
      ) : null}
      {!isLoading && !isError && (data?.length ?? 0) === 0 ? (
        <p className="text-sm text-gray-500">{t("empty")}</p>
      ) : null}

      <ul className="space-y-2">
        {(data ?? []).map((quiz) => (
          <li
            key={quiz.assignment_id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-gray-100 px-3 py-2"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">{quiz.lecture_topic}</p>
              <p className="text-xs text-gray-500">
                {t("question_count", { count: quiz.question_count })} · {t(`status_${quiz.status}`)}
              </p>
            </div>
            <a
              href={`/student/quizzes/${quiz.assignment_id}`}
              className="text-sm text-blue-600 hover:underline"
            >
              {quiz.status === "completed" ? t("view_results") : t("take_quiz")}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
