import { useTranslations } from "next-intl";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { AuthTopBar } from "@/components/auth/AuthTopBar";
import { LoginButton } from "./LoginButton";
import { LoginForm } from "./LoginForm";
import { JoinPanel } from "./JoinPanel";

export default function LoginPage() {
  const t = useTranslations("auth.login");
  // BFF branded form is the default (M-07b / A-003); `oidc_redirect` restores the
  // legacy "Sign in with Authentik" button for dev/SSO debugging.
  const mode = process.env.NEXT_PUBLIC_AUTH_LOGIN_MODE ?? "bff";

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <AuthTopBar />

      <main className="mx-auto grid w-full max-w-6xl flex-1 gap-6 px-4 py-10 sm:px-6 lg:grid-cols-2 lg:gap-8 lg:py-16">
        {/* Left — branded sign-in card */}
        <section className="rounded-3xl border border-brand-100 bg-gradient-to-b from-brand-50 to-white p-8 sm:p-10">
          <div className="mb-8 space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              {t("title")}
            </h1>
            <p className="text-sm text-gray-500">{t("subtitle")}</p>
          </div>

          {mode === "oidc_redirect" ? <LoginButton label={t("cta")} /> : <LoginForm />}
        </section>

        {/* Right — join / create-account promo */}
        <JoinPanel />
      </main>

      <footer className="flex justify-center pb-8">
        <LanguageSwitcher />
      </footer>
    </div>
  );
}
