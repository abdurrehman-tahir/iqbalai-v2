"use client";

/**
 * T-018 — Languages page.
 * Deployment-level config — 4 locked languages, read-only cards.
 */
import { useTranslations } from "next-intl";

const LANGUAGES = [
  { code: "en", name: "English", nativeName: "English", rtl: false, ttsReady: true },
  { code: "ur", name: "Urdu", nativeName: "اردو", rtl: true, ttsReady: false },
  { code: "sd", name: "Sindhi", nativeName: "سنڌي", rtl: true, ttsReady: false },
  { code: "ps", name: "Pashto", nativeName: "پښتو", rtl: true, ttsReady: false },
] as const;

function LanguageCard({
  lang,
  ttsReadyLabel,
  ttsPendingLabel,
  rtlLabel,
  ltrLabel,
}: {
  lang: (typeof LANGUAGES)[number];
  ttsReadyLabel: string;
  ttsPendingLabel: string;
  rtlLabel: string;
  ltrLabel: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm flex flex-col gap-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-lg font-semibold text-gray-900" lang={lang.code}>
            {lang.nativeName}
          </p>
          <p className="text-sm text-gray-500">{lang.name}</p>
        </div>
        <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-1 rounded">
          {lang.code}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <span
          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
            lang.rtl
              ? "bg-purple-50 text-purple-700 border-purple-200"
              : "bg-brand-50 text-brand-700 border-brand-200"
          }`}
        >
          {lang.rtl ? rtlLabel : ltrLabel}
        </span>
        <span
          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
            lang.ttsReady
              ? "bg-green-50 text-green-700 border-green-200"
              : "bg-gray-50 text-gray-500 border-gray-200"
          }`}
        >
          {lang.ttsReady ? ttsReadyLabel : ttsPendingLabel}
        </span>
      </div>
    </div>
  );
}

export default function LanguagesPage() {
  const t = useTranslations("admin.languages");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {/* Info banner */}
      <div className="rounded-lg border border-brand-200 bg-brand-50 p-4">
        <p className="text-sm text-brand-800">{t("deployment_banner")}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {LANGUAGES.map((lang) => (
          <LanguageCard
            key={lang.code}
            lang={lang}
            ttsReadyLabel={t("tts_ready")}
            ttsPendingLabel={t("tts_pending")}
            rtlLabel={t("rtl")}
            ltrLabel={t("ltr")}
          />
        ))}
      </div>
    </div>
  );
}
