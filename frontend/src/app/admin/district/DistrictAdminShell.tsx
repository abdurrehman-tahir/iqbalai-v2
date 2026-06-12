"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { School, Menu, X, LogOut, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { clearToken, getLogoutUrl, getUser, type StoredUser } from "@/lib/auth";
import LanguageSwitcher from "@/components/LanguageSwitcher";

const NAV_ITEMS = [
  { key: "schools", href: "/admin/district/schools", icon: School },
  { key: "users", href: "/admin/district/users", icon: Users },
] as const;

export function DistrictAdminShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [user, setUser] = useState<StoredUser | null>(null);
  const pathname = usePathname();
  const t = useTranslations("district_admin");
  const tNav = useTranslations("district_admin.nav");

  useEffect(() => {
    setUser(getUser());
  }, []);

  function handleLogout() {
    clearToken();
    window.location.href = getLogoutUrl();
  }

  function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
    return (
      <nav aria-label={tNav("aria_label")}>
        <ul className="space-y-1 px-3 py-4">
          {NAV_ITEMS.map(({ key, href, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <li key={key}>
                <Link
                  href={href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-brand-50 text-brand-700"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
                  )}
                >
                  <Icon className="size-5 shrink-0" aria-hidden="true" />
                  <span>{tNav(key)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="hidden md:flex md:w-64 md:flex-col border-e border-gray-200 bg-white">
        <div className="flex h-16 items-center px-6 border-b border-gray-100">
          <span className="text-xl font-bold text-brand-700">IqbalAI</span>
          <span className="ms-2 text-xs text-gray-400 font-medium">{t("badge")}</span>
        </div>
        <div className="flex flex-1 flex-col justify-between overflow-y-auto">
          <NavLinks />
          <div className="px-3 py-4 border-t border-gray-100 space-y-1">
            <LanguageSwitcher />
            <Button
              variant="ghost"
              size="md"
              className="w-full justify-start gap-3 text-gray-600"
              onClick={handleLogout}
            >
              <LogOut className="size-5" aria-hidden="true" />
              {t("logout")}
            </Button>
          </div>
        </div>
      </aside>

      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 start-0 z-50 w-64 bg-white border-e border-gray-200 flex flex-col md:hidden transition-transform",
          drawerOpen ? "translate-x-0" : "-translate-x-full rtl:translate-x-full",
        )}
        aria-hidden={!drawerOpen}
      >
        <div className="flex h-16 items-center justify-between px-6 border-b border-gray-100">
          <span className="text-xl font-bold text-brand-700">IqbalAI</span>
          <Button variant="ghost" size="icon" onClick={() => setDrawerOpen(false)}>
            <X className="size-5" aria-hidden="true" />
          </Button>
        </div>
        <NavLinks onNavigate={() => setDrawerOpen(false)} />
      </aside>

      <div className="flex flex-1 flex-col min-w-0">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-gray-200 bg-white px-4 md:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label={tNav("open_menu")}
          >
            <Menu className="size-5" aria-hidden="true" />
          </Button>
          <div className="flex-1" />
          <div className="flex flex-col items-end">
            <span className="text-sm font-medium text-gray-900">{user?.email ?? t("role")}</span>
            <span className="text-xs text-gray-400">{t("role")}</span>
          </div>
        </header>
        <main className="flex-1 container mx-auto max-w-screen-xl px-4 py-8 md:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
