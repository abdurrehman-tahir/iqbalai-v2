import Link from "next/link";
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
        {/* Navigation, so a Link — this was a bare <button> with no handler and no href,
            which left the landing page's only CTA inert (QA E03/E05). /login is the one
            sanctioned entry point; never link Authentik directly. */}
        <Link
          href="/login"
          className="mt-6 inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg bg-brand-600 px-8 py-3 font-medium text-white transition-colors hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
        >
          {t("cta_button")}
        </Link>
        <div className="mt-8">
          <LanguageSwitcher />
        </div>
      </div>
    </main>
  );
}
