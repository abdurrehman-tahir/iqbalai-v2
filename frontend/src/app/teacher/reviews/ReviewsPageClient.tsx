"use client";

import { useTranslations } from "next-intl";
import { ReviewsList } from "@/components/reviews/ReviewsList";

export function ReviewsPageClient() {
  const t = useTranslations("teacher.reviews.list");
  return (
    <main className="mx-auto w-full max-w-4xl space-y-6 px-4 py-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-gray-900 sm:text-3xl">{t("title")}</h1>
        <p className="text-sm text-gray-600 sm:text-base">{t("subtitle")}</p>
      </header>
      <ReviewsList />
    </main>
  );
}
