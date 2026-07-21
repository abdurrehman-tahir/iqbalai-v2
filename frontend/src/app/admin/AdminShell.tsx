"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Globe,
  Users,
  BookOpen,
  CreditCard,
  FileText,
  ClipboardList,
  Library,
  Building2,
  Target,
  Menu,
  X,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { NotificationBell } from "@/components/admin/NotificationBell";
import { getLogoutUrl } from "@/lib/auth";
import { useCurrentUser } from "@/hooks/use-current-user";
import LanguageSwitcher from "@/components/LanguageSwitcher";
// useRouter import removed — logout uses window.location directly

// Role-aware nav (T-227). Each entry declares the roles permitted to see it,
// mirroring the backend `require_role` guarding the matching routes
// (flow-1-platform-setup §4). The shell is the single source of reachability:
// every new page registers its nav entry + allowed roles here, so no page can
// become an orphan and no user sees a link to a route they cannot access.
const PLATFORM_ADMIN = "platform_admin";

interface NavItem {
  key: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: readonly string[];
}

const NAV_ITEMS: NavItem[] = [
  { key: "districts", href: "/admin/districts", icon: Building2, roles: [PLATFORM_ADMIN] },
  { key: "users", href: "/admin/users", icon: Users, roles: [PLATFORM_ADMIN] },
  { key: "languages", href: "/admin/languages", icon: Globe, roles: [PLATFORM_ADMIN] },
  { key: "personas", href: "/admin/personas", icon: BookOpen, roles: [PLATFORM_ADMIN] },
  { key: "exam_syllabi", href: "/admin/exam-syllabi", icon: BookOpen, roles: [PLATFORM_ADMIN] },
  {
    key: "exam_frameworks",
    href: "/admin/exam-frameworks",
    icon: Target,
    roles: [PLATFORM_ADMIN],
  },
  {
    key: "subscription_tiers",
    href: "/admin/subscription-tiers",
    icon: CreditCard,
    roles: [PLATFORM_ADMIN],
  },
  { key: "tos", href: "/admin/tos", icon: FileText, roles: [PLATFORM_ADMIN] },
  { key: "library", href: "/admin/library", icon: Library, roles: [PLATFORM_ADMIN] },
  { key: "audit_log", href: "/admin/audit-log", icon: ClipboardList, roles: [PLATFORM_ADMIN] },
];

/** Nav items the given role is permitted to see. `null` (no/unknown user) → none. */
function navItemsForRole(role: string | null): NavItem[] {
  if (role === null) return [];
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

function SidebarNav({ role, onNavigate }: { role: string | null; onNavigate?: () => void }) {
  const pathname = usePathname();
  const t = useTranslations("admin.nav");
  const items = navItemsForRole(role);

  return (
    <nav aria-label={t("aria_label")}>
      <ul className="space-y-1 px-3 py-4">
        {items.map(({ key, href, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <li key={key}>
              <Link
                href={href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600",
                  active
                    ? "bg-brand-50 text-brand-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <Icon className="size-5 shrink-0" aria-hidden="true" />
                <span>{t(key)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { user } = useCurrentUser();
  const t = useTranslations("admin");
  const tNav = useTranslations("admin.nav");

  function handleLogout() {
    window.location.href = getLogoutUrl();
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <aside
        className="hidden md:flex md:w-64 md:flex-col md:shrink-0 border-e border-gray-200 bg-white"
        aria-label={t("sidebar_label")}
      >
        {/* Logo */}
        <div className="flex h-16 items-center px-6 border-b border-gray-100">
          <span className="text-xl font-bold text-brand-700">IqbalAI</span>
          <span className="ms-2 text-xs text-gray-400 font-medium">{t("admin_badge")}</span>
        </div>

        <div className="flex flex-1 flex-col justify-between overflow-y-auto">
          <SidebarNav role={user?.role ?? null} />

          {/* Bottom actions */}
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

      {/* Mobile drawer overlay */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={cn(
          "fixed inset-y-0 start-0 z-50 w-64 bg-white border-e border-gray-200 flex flex-col",
          "transition-transform duration-200 ease-in-out md:hidden",
          drawerOpen ? "translate-x-0" : "-translate-x-full rtl:translate-x-full"
        )}
        aria-label={t("sidebar_label")}
        aria-hidden={!drawerOpen}
      >
        <div className="flex h-16 items-center justify-between px-6 border-b border-gray-100">
          <span className="text-xl font-bold text-brand-700">IqbalAI</span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDrawerOpen(false)}
            aria-label={tNav("close_menu")}
          >
            <X className="size-5" aria-hidden="true" />
          </Button>
        </div>
        <div className="flex flex-1 flex-col justify-between overflow-y-auto">
          <SidebarNav role={user?.role ?? null} onNavigate={() => setDrawerOpen(false)} />
          <div className="px-3 py-4 border-t border-gray-100">
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

      {/* Main column */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Top header */}
        <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-gray-200 bg-white px-4 md:px-6">
          {/* Mobile hamburger */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label={tNav("open_menu")}
          >
            <Menu className="size-5" aria-hidden="true" />
          </Button>

          {/* Title spacer */}
          <div className="flex-1" />

          {/* Header right: notifications + user */}
          <div className="flex items-center gap-3">
            <NotificationBell />
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-sm font-medium text-gray-900 leading-none">
                {user?.email ?? "Platform Admin"}
              </span>
              <span className="text-xs text-gray-400 mt-0.5">{t("admin_role")}</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 container mx-auto max-w-screen-xl px-4 py-8 md:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
