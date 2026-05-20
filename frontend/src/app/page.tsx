import { useTranslations } from "next-intl";
import LanguageSwitcher from "@/components/LanguageSwitcher";

export default function HomePage() {
  const t = useTranslations("landing");
  const tApp = useTranslations("app");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center space-y-6">
        <h1 className="text-4xl font-bold text-brand-700">
          {tApp("name")}
        </h1>
        <p className="text-xl text-gray-600">
          {tApp("tagline")}
        </p>
        <h2 className="text-2xl font-semibold mt-8">
          {t("hero_title")}
        </h2>
        <p className="text-gray-500">
          {t("hero_subtitle")}
        </p>
        <button className="mt-6 px-8 py-3 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition-colors min-h-[44px] min-w-[44px]">
          {t("cta_button")}
        </button>
        <div className="mt-8">
          <LanguageSwitcher />
        </div>
      </div>
    </main>
  );
}
