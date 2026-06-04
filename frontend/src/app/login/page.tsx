import { useTranslations } from "next-intl";
import { LoginButton } from "./LoginButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";

export default function LoginPage() {
  const t = useTranslations("auth.login");
  const tApp = useTranslations("app");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="w-full max-w-sm space-y-8">
        {/* Brand */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-brand-700">{tApp("name")}</h1>
          <p className="mt-2 text-sm text-gray-500">{tApp("tagline")}</p>
        </div>

        {/* Login card */}
        <div className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm space-y-6">
          <div className="text-center space-y-1">
            <h2 className="text-xl font-semibold text-gray-900">{t("title")}</h2>
            <p className="text-sm text-gray-500">{t("subtitle")}</p>
          </div>

          <LoginButton label={t("cta")} />
        </div>

        {/* Language switcher */}
        <div className="flex justify-center">
          <LanguageSwitcher />
        </div>
      </div>
    </main>
  );
}
