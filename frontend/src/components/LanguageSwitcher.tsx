"use client";

import { useTranslations } from "next-intl";
import { locales, type Locale } from "@/i18n/config";

const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  ur: "اردو",
  sd: "سنڌي",
  ps: "پښتو",
};

export default function LanguageSwitcher() {
  const t = useTranslations("landing");

  function handleLocaleChange(locale: Locale) {
    document.cookie = `locale=${locale};path=/;max-age=${60 * 60 * 24 * 365}`;
    window.location.reload();
  }

  return (
    <div className="flex flex-wrap gap-2 justify-center" aria-label={t("language_switcher")}>
      {locales.map((locale) => (
        <button
          key={locale}
          onClick={() => handleLocaleChange(locale)}
          className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 transition-colors min-h-[44px] min-w-[44px]"
          aria-label={`Switch to ${LOCALE_LABELS[locale]}`}
        >
          {LOCALE_LABELS[locale]}
        </button>
      ))}
    </div>
  );
}
