"use client";

/**
 * Teacher lecture detail — Flow 5 edit mode (T-130 ``LectureEditorPanel``) plus
 * the lecture's Reviews tab (T-206). Reached from a review card's "Edit Main
 * Lecture" / "Open full draft" and from the drill-down's content links; when
 * opened from a review, a context banner links back to that card (T-205).
 */

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { ArrowLeft, ClipboardList, Info, Pencil } from "lucide-react";
import { lectureWizardApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { LectureEditorPanel } from "@/components/lectures/LectureEditorPanel";
import { ReviewsList } from "@/components/reviews/ReviewsList";

export type LectureTab = "edit" | "reviews";

export function LectureDetailClient({
  lectureId,
  fromReviewId,
  initialTab,
}: {
  lectureId: string;
  fromReviewId: string | null;
  initialTab: LectureTab;
}) {
  const t = useTranslations("teacher.lecture_detail");
  const tWizard = useTranslations("teacher.lectures.wizard");
  const { mounted, token } = useClientAuth();
  const [tab, setTab] = useState<LectureTab>(initialTab);

  const tabs: { key: LectureTab; icon: typeof Pencil }[] = [
    { key: "edit", icon: Pencil },
    { key: "reviews", icon: ClipboardList },
  ];

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-4 py-8" data-testid="lecture-detail">
      <Link
        href="/teacher/reviews"
        className="inline-flex min-h-11 items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="size-4 rtl:rotate-180" aria-hidden="true" />
        {t("back")}
      </Link>
      <h1 className="text-2xl font-semibold text-gray-900 sm:text-3xl">{t("title")}</h1>

      {fromReviewId && (
        <div
          className="flex flex-wrap items-center gap-2 rounded-md border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800"
          role="note"
          data-testid="from-review-banner"
        >
          <Info className="size-4 shrink-0" aria-hidden="true" />
          <span>{t("from_review")}</span>
          <Link
            href={`/teacher/reviews/${fromReviewId}`}
            className="font-medium underline-offset-2 hover:underline"
          >
            {t("back_to_review")}
          </Link>
        </div>
      )}

      <div role="tablist" aria-label={t("tabs_label")} className="flex gap-2 border-b border-gray-200">
        {tabs.map(({ key, icon: Icon }) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`lecture-tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`lecture-panel-${key}`}
            onClick={() => setTab(key)}
            className={cn(
              "-mb-px inline-flex min-h-11 items-center gap-2 border-b-2 px-3 text-sm font-medium",
              tab === key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-gray-600 hover:text-gray-900",
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {t(`tab_${key}`)}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`lecture-panel-${tab}`} aria-labelledby={`lecture-tab-${tab}`}>
        {tab === "edit" ? (
          mounted && token ? (
            <LectureEditorPanel
              token={token}
              lectureId={lectureId}
              api={lectureWizardApi}
              t={tWizard}
              queryKeyPrefix="teacher"
            />
          ) : (
            <Skeleton className="h-96 w-full" />
          )
        ) : (
          <ReviewsList lectureId={lectureId} />
        )}
      </div>
    </main>
  );
}
