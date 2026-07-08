import Link from "next/link";
import { useTranslations } from "next-intl";
import { IqbalLogo } from "@/components/IqbalLogo";
import { SocialButtons } from "@/components/auth/SocialButtons";

/**
 * Right-hand promotional panel on the login screen (matches the mockup): brand
 * lockup, a "join us for free" pitch, the same SSO providers, and a primary
 * link into the create-account hub.
 */
export function JoinPanel() {
  const t = useTranslations("auth.join");

  return (
    <section className="flex flex-col overflow-hidden rounded-3xl border border-brand-100 bg-gradient-to-b from-brand-50 to-white p-8 sm:p-10">
      <div className="flex justify-center pb-8">
        <IqbalLogo size="xl" tagline={t("tagline")} />
      </div>

      <div className="relative flex flex-1 flex-col items-center justify-center rounded-2xl border border-brand-100/70 bg-white/40 p-8 text-center">
        {/* Faint dotted grid so the panel echoes the mockup's textured backdrop. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(circle,theme(colors.brand.200)_1px,transparent_1px)] [background-size:22px_22px] opacity-40"
        />

        <div className="relative flex w-full flex-col items-center gap-6">
          <div className="space-y-1">
            <h2 className="text-4xl font-bold tracking-tight text-gray-900">{t("title")}</h2>
            <p className="text-lg text-gray-600">{t("subtitle")}</p>
          </div>

          <SocialButtons className="w-full max-w-sm" />

          <div className="flex w-full max-w-sm items-center gap-3">
            <span className="h-px flex-1 bg-brand-200" />
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("or")}
            </span>
            <span className="h-px flex-1 bg-brand-200" />
          </div>

          <Link
            href="/signup"
            className="inline-flex items-center justify-center rounded-xl bg-brand-600 px-10 py-3 text-sm font-bold uppercase tracking-wide text-white shadow-md shadow-brand-600/20 transition-colors hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
          >
            {t("cta")}
          </Link>

          <p className="max-w-xs text-sm text-gray-500">{t("trial")}</p>
        </div>
      </div>
    </section>
  );
}
