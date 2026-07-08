"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { AuthPageShell } from "@/components/auth/AuthPageShell";

const PATHS = [
  { key: "invite", href: "/accept-invite", actionable: true },
  { key: "independent", href: "/independent/signup", actionable: true },
  { key: "parent", href: "/parent/signup", actionable: true },
  { key: "school", href: null, actionable: false },
] as const;

/** Unified create-account hub (M-07b T-242). */
export function SignupHub() {
  const t = useTranslations("auth.signup_hub");

  return (
    <AuthPageShell title={t("title")} subtitle={t("subtitle")}>
      <div className="space-y-4">
        {PATHS.map(({ key, href, actionable }) => (
          <div
            key={key}
            className="rounded-lg border border-gray-200 p-4 space-y-2 hover:border-brand-200 transition-colors"
          >
            <h3 className="text-sm font-semibold text-gray-900">{t(`cards.${key}.title`)}</h3>
            <p className="text-sm text-gray-600">{t(`cards.${key}.description`)}</p>
            {actionable && href ? (
              <Link
                href={href}
                className="inline-flex text-sm font-medium text-brand-600 hover:text-brand-700"
              >
                {t(`cards.${key}.cta`)} →
              </Link>
            ) : (
              <p className="text-xs text-gray-500 italic">{t(`cards.${key}.note`)}</p>
            )}
          </div>
        ))}

        <p className="text-center text-sm text-gray-600 pt-2">
          {t("have_account")}{" "}
          <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
            {t("sign_in")}
          </Link>
        </p>
      </div>
    </AuthPageShell>
  );
}
