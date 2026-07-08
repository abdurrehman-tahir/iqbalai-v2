"use client";

import { useTranslations } from "next-intl";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";

export function CoordinatorHomeClient() {
  const t = useTranslations("coordinator.dashboard");
  return (
    <div className="space-y-6">
      <DashboardHeader title={t("title")} subtitle={t("subtitle")} />
      <div className="rounded-2xl border border-dashed border-brand-200 bg-brand-50/40 p-12 text-center">
        <p className="text-lg font-medium text-gray-900">{t("title")}</p>
        <p className="mt-2 text-sm text-gray-500">{t("subtitle")}</p>
      </div>
    </div>
  );
}
