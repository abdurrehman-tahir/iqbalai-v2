"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, LayoutDashboard, LogOut, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { clearToken, getLogoutUrl, getUser } from "@/lib/auth";
import { useEffect, useState } from "react";
import type { StoredUser } from "@/lib/auth";
import { useQuery } from "@tanstack/react-query";
import { usersApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

const NAV = [
  { key: "dashboard", href: "/coordinator", icon: LayoutDashboard },
  { key: "subjects", href: "/coordinator/subjects", icon: BookOpen },
  { key: "bulk_import", href: "/coordinator/bulk-import", icon: Upload },
] as const;

export function CoordinatorShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("coordinator");
  const pathname = usePathname();
  const { mounted, token } = useClientAuth();
  const [user, setUser] = useState<StoredUser | null>(null);

  const { data: profile } = useQuery({
    queryKey: ["users", "me"],
    queryFn: () => usersApi.getMe(token!),
    enabled: mounted && !!token,
  });

  useEffect(() => {
    setUser(getUser());
  }, []);

  function handleLogout() {
    clearToken();
    window.location.href = getLogoutUrl();
  }

  const scopeLabel = profile?.scoped_ids?.split(",").join(", ") ?? null;

  return (
    <div className="flex min-h-screen bg-gray-50">
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
                      : "text-gray-600 hover:bg-gray-100"
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
          <Button
            variant="ghost"
            size="md"
            className="w-full justify-start gap-3"
            onClick={handleLogout}
          >
            <LogOut className="size-5" aria-hidden="true" />
            {t("logout")}
          </Button>
        </div>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="h-16 border-b border-gray-200 bg-white px-6 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">{t("header_title")}</h1>
            {scopeLabel && (
              <p className="text-xs text-gray-500">{t("scope_label", { scope: scopeLabel })}</p>
            )}
          </div>
          <span className="text-sm text-gray-500">{user?.email}</span>
        </header>
        <main className="flex-1 p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
