"use client";

import { useTranslations } from "next-intl";
import { ReferenceUploadForm } from "./ReferenceUploadForm";

export function ReferenceUploadPage({ detailBasePath }: { detailBasePath: string }) {
  const t = useTranslations("school_library.reference.upload");

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("page_title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("page_subtitle")}</p>
      </div>
      <ReferenceUploadForm detailBasePath={detailBasePath} />
    </div>
  );
}
