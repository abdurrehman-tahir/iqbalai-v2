"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { performLogout } from "@/lib/auth";
import { useCurrentUser } from "@/hooks/use-current-user";
import { StudentOnboardingGate } from "./StudentOnboardingGate";
import { ModeSwitcher } from "./ModeSwitcher";

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
      <header className="h-16 border-b border-gray-200 bg-white px-6 flex items-center justify-between gap-4">
        <h1 className="text-lg font-semibold text-gray-900">
          {onOnboardingPage ? t("onboarding.header_title") : t("header_title")}
        </h1>
        <div className="flex items-center gap-4">
          {!onOnboardingPage && <ModeSwitcher />}
          <span className="text-sm text-gray-500">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="size-4 me-2" aria-hidden="true" />
            {t("logout")}
          </Button>
        </div>
      </header>
      <main className="flex-1 p-6 md:p-8 overflow-y-auto">
        <StudentOnboardingGate>{children}</StudentOnboardingGate>
      </main>
    </div>
  );
}
