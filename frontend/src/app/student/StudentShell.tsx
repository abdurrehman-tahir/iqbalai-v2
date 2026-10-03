"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { performLogout } from "@/lib/auth";
import { useCurrentUser } from "@/hooks/use-current-user";
import { StudentOnboardingGate } from "./StudentOnboardingGate";
import { ModeSwitcher } from "./ModeSwitcher";
import Link from "next/link";

/** Student primary nav (frontend-master Rule 13: every page nav-reachable). */
export const STUDENT_NAV: {
  href: string;
  labelKey: "nav.home" | "nav.highlights";
  match: (path: string) => boolean;
}[] = [
  { href: "/student", labelKey: "nav.home", match: (p) => p === "/student" },
  {
    href: "/student/highlights",
    labelKey: "nav.highlights",
    match: (p) => p.startsWith("/student/highlights"),
  },
];

export function StudentShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("student");
  const pathname = usePathname();
  const { user } = useCurrentUser();
  const onOnboardingPage = pathname.startsWith("/student/onboarding");

  function handleLogout() {
    void performLogout();
  }

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      {/* Wraps below sm so the 360px floor never scrolls horizontally (Rule 11). */}
      <header className="flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-gray-200 bg-white px-4 py-2 sm:px-6">
        <h1 className="text-lg font-semibold text-gray-900">
          {onOnboardingPage ? t("onboarding.header_title") : t("header_title")}
        </h1>
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          {!onOnboardingPage && <ModeSwitcher />}
          <span className="hidden text-sm text-gray-500 sm:inline">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="size-4 me-2" aria-hidden="true" />
            {t("logout")}
          </Button>
        </div>
      </header>
      {!onOnboardingPage && (
        <nav
          className="flex flex-wrap gap-1 border-b border-gray-200 bg-white px-4 sm:px-6"
          aria-label={t("nav.label")}
          data-testid="student-nav"
        >
          {STUDENT_NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`inline-flex min-h-11 items-center border-b-2 px-3 text-sm font-medium ${
                  active
                    ? "border-brand-600 text-gray-900"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                }`}
              >
                {t(item.labelKey)}
              </Link>
            );
          })}
        </nav>
      )}
      <main className="flex-1 p-6 md:p-8 overflow-y-auto">
        <StudentOnboardingGate>{children}</StudentOnboardingGate>
      </main>
    </div>
  );
}
