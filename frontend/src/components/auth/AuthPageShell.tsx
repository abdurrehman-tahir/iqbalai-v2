import { useTranslations } from "next-intl";
import LanguageSwitcher from "@/components/LanguageSwitcher";

interface AuthPageShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

/** Shared layout for login, signup hub, and password-reset surfaces (M-07b). */
export function AuthPageShell({ title, subtitle, children }: AuthPageShellProps) {
  const tApp = useTranslations("app");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-brand-700">{tApp("name")}</h1>
          <p className="mt-2 text-sm text-gray-500">{tApp("tagline")}</p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm space-y-6">
          <div className="text-center space-y-1">
            <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
            {subtitle ? <p className="text-sm text-gray-500">{subtitle}</p> : null}
          </div>
          {children}
        </div>

        <div className="flex justify-center">
          <LanguageSwitcher />
        </div>
      </div>
    </main>
  );
}
