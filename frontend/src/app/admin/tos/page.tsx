"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { TosAdminClient } from "./TosAdminClient";

export default function TosPage() {
  const [tab, setTab] = useState<"tos" | "disclaimer">("tos");
  const t = useTranslations("admin.nav");

  return (
    <div className="space-y-6">
      {/* Tab switcher */}
      <div className="flex gap-1 border-b border-gray-200">
        <button
          type="button"
          onClick={() => setTab("tos")}
          className={[
            "px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px",
            tab === "tos"
              ? "border-brand-600 text-brand-700"
              : "border-transparent text-gray-500 hover:text-gray-700",
          ].join(" ")}
        >
          {t("tos_tab_tos")}
        </button>
        <button
          type="button"
          onClick={() => setTab("disclaimer")}
          className={[
            "px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px",
            tab === "disclaimer"
              ? "border-brand-600 text-brand-700"
              : "border-transparent text-gray-500 hover:text-gray-700",
          ].join(" ")}
        >
          {t("tos_tab_disclaimer")}
        </button>
      </div>

      <TosAdminClient key={tab} type={tab} />
    </div>
  );
}
