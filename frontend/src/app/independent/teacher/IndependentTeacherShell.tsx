"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, LogOut, NotebookPen } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { performLogout } from "@/lib/auth";
import { useCurrentUser } from "@/hooks/use-current-user";
import { IndependentTeacherOnboardingGate } from "./IndependentTeacherOnboardingGate";

const NAV = [
  { key: "dashboard", href: "/independent/teacher", icon: LayoutDashboard },
  { key: "lectures", href: "/independent/teacher/lectures/new", icon: NotebookPen },
] as const;

export function IndependentTeacherShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("independent.teacher");
  const pathname = usePathname();
  const { user } = useCurrentUser();
  const onOnboardingPage = pathname.startsWith("/independent/teacher/onboarding");

  function handleLogout() {
    void performLogout();
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {!onOnboardingPage && (
        <aside className="hidden md:flex md:w-64 md:flex-col border-e border-gray-200 bg-white">
          <div className="flex h-16 items-center px-6 border-b border-gray-100">
            <span className="text-xl font-bold text-brand-700">IqbalAI</span>
          </div>
          <nav className="px-3 py-4" aria-label={t("nav.aria_label")}>
            <ul className="space-y-1">
              {NAV.map(({ key, href, icon: Icon }) => (
                <li key={key}>
                  <Link
                    href={href}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium",
                      pathname === href
                        ? "bg-brand-50 text-brand-700"
                        : "text-gray-600 hover:bg-gray-100",
                    )}
                  >
                    <Icon className="size-5" aria-hidden="true" />
                    {t(`nav.${key}`)}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="mt-auto px-3 py-4 border-t border-gray-100">
            <Button variant="ghost" size="md" className="w-full justify-start gap-3" onClick={handleLogout}>
              <LogOut className="size-5" aria-hidden="true" />
              {t("logout")}
            </Button>
          </div>
        </aside>
      )}
      <div className="flex flex-1 flex-col">
        <header className="h-16 border-b border-gray-200 bg-white px-6 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">
            {onOnboardingPage ? t("onboarding.header_title") : t("header_title")}
          </h1>
          <span className="text-sm text-gray-500">{user?.email}</span>
        </header>
        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          <IndependentTeacherOnboardingGate>{children}</IndependentTeacherOnboardingGate>
        </main>
      </div>
    </div>
  );
}
