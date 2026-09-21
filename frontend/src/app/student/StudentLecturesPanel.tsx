"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { studentLecturesApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function StudentLecturesPanel() {
  const t = useTranslations("student.lectures");
  const { mounted, token } = useClientAuth();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["student", "lectures"],
    queryFn: () => studentLecturesApi.list(token!),
    enabled: mounted && !!token,
  });

  const lectures = Array.isArray(data) ? data : [];

  return (
    <section
      className="rounded-lg border border-gray-200 bg-white p-4 space-y-3"
      data-testid="student-lectures"
      aria-label={t("title")}
    >
      <div>
        <h3 className="text-lg font-medium text-gray-900">{t("title")}</h3>
        <p className="text-sm text-gray-600">{t("subtitle")}</p>
      </div>
      {isLoading ? <p className="text-sm text-gray-500">{t("loading")}</p> : null}
      {isError ? <p className="text-sm text-red-600">{t("error")}</p> : null}
      {!isLoading && !isError && lectures.length === 0 ? (
        <p className="text-sm text-gray-500">{t("empty")}</p>
      ) : null}
      {lectures.length > 0 ? (
        <ul className="space-y-2">
          {lectures.map((lecture) => (
            <li
              key={lecture.lecture_id}
              className="flex items-center justify-between gap-3 rounded-md border border-gray-100 px-3 py-2"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">{lecture.title}</p>
                <p className="text-xs text-gray-500">{lecture.topic}</p>
              </div>
              <a
                href={`/student/lectures/${lecture.lecture_id}`}
                className="shrink-0 text-sm font-medium text-blue-600 hover:underline"
              >
                {t("open")}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
