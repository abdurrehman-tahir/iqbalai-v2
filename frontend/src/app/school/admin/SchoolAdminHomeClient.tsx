"use client";

import { useTranslations } from "next-intl";

export function SchoolAdminHomeClient() {
  const t = useTranslations("school_admin.dashboard");
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center">
      <p className="text-lg font-medium text-gray-900">{t("title")}</p>
      <p className="mt-2 text-sm text-gray-500">{t("subtitle")}</p>
    </div>
  );
}
