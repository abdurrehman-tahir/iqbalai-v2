"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getLogoutUrl } from "@/lib/auth";
import { useCurrentUser } from "@/hooks/use-current-user";

export function ParentShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("parent.home");
  const pathname = usePathname();
  const { user } = useCurrentUser();
  const onSignupPage = pathname.startsWith("/parent/signup");

  function handleLogout() {
    window.location.href = getLogoutUrl();
  }

  if (onSignupPage) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <header className="h-16 border-b border-gray-200 bg-white px-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">{t("header_title")}</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="size-4 me-2" aria-hidden="true" />
            {t("logout")}
          </Button>
        </div>
      </header>
      <main className="flex-1 p-6 md:p-8 overflow-y-auto">{children}</main>
    </div>
  );
}
