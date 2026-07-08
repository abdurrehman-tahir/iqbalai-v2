import Link from "next/link";
import { useTranslations } from "next-intl";
import { IqbalLogo } from "@/components/IqbalLogo";

/**
 * Dark banner at the top of the auth surface: brand lockup on the left,
 * login / create-account actions on the right (matches the login mockup).
 */
export function AuthTopBar() {
  const t = useTranslations("auth.top_bar");

  return (
    <header className="relative isolate overflow-hidden bg-gray-900">
      {/* Subtle green glow so the dark bar reads as branded, not flat black. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-gradient-to-r from-brand-900/40 via-transparent to-brand-800/30"
      />
      <div className="relative mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 backdrop-blur-sm">
          <Link href="/" aria-label={t("home_aria")}>
            <IqbalLogo size="md" tagline={t("tagline")} inverted />
          </Link>
        </div>

        <nav className="flex items-center gap-2 sm:gap-3" aria-label={t("aria_label")}>
          <Link
            href="/login"
            className="rounded-lg bg-brand-500 px-4 py-2 text-xs font-bold uppercase tracking-wide text-white shadow-sm transition-colors hover:bg-brand-600 sm:px-6 sm:text-sm"
          >
            {t("login")}
          </Link>
          <Link
            href="/signup"
            className="rounded-lg bg-brand-700 px-4 py-2 text-xs font-bold uppercase tracking-wide text-white shadow-sm transition-colors hover:bg-brand-800 sm:px-6 sm:text-sm"
          >
            {t("create_account")}
          </Link>
        </nav>
      </div>
    </header>
  );
}
