import Link from "next/link";
import { useTranslations } from "next-intl";

interface AuthNavLinksProps {
  showSignupOptions?: boolean;
}

/** Consistent back-navigation on signup and invite flows (M-07b T-242). */
export function AuthNavLinks({ showSignupOptions = false }: AuthNavLinksProps) {
  const t = useTranslations("auth.nav");

  return (
    <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label={t("aria_label")}>
      <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
        {t("back_to_login")}
      </Link>
      {showSignupOptions ? (
        <Link href="/signup" className="font-medium text-gray-600 hover:text-gray-800">
          {t("back_to_signup")}
        </Link>
      ) : null}
    </nav>
  );
}
