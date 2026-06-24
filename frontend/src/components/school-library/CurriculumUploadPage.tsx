"use client";

import { useTranslations } from "next-intl";
import { CurriculumUploadForm } from "@/components/school-library/CurriculumUploadForm";

export function CurriculumUploadPage({ detailBasePath }: { detailBasePath: string }) {
  const t = useTranslations("school_library.curriculum.upload");

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("page_title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("page_subtitle")}</p>
      </div>
      <CurriculumUploadForm detailBasePath={detailBasePath} />
    </div>
  );
}
