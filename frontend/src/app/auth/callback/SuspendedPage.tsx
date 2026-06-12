"use client";

import { useTranslations } from "next-intl";

export function SuspendedPage() {
  const t = useTranslations("auth.suspended");

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-md text-center space-y-4">
        <h1 className="text-xl font-semibold text-gray-900">{t("title")}</h1>
        <p className="text-sm text-gray-600">{t("description")}</p>
        <a href="/login" className="text-sm text-brand-600 underline">
          {t("back_to_login")}
        </a>
      </div>
    </main>
  );
}
