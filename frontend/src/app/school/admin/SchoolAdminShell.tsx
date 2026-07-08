"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Users,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  UserCog,
  ClipboardList,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { performLogout, getUser } from "@/lib/auth";
import { useEffect, useState } from "react";
import type { StoredUser } from "@/lib/auth";
import { useQuery } from "@tanstack/react-query";
import { schoolAdminApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { IqbalLogo } from "@/components/IqbalLogo";

const NAV = [
  { key: "dashboard", href: "/school/admin", icon: LayoutDashboard },
  { key: "users", href: "/school/admin/users", icon: Users },
  { key: "coordinators", href: "/school/admin/coordinators", icon: UserCog },
  { key: "teachers", href: "/school/admin/teachers", icon: GraduationCap },
  { key: "audit_log", href: "/school/admin/audit-log", icon: ClipboardList },
] as const;

export function SchoolAdminShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("school_admin");
  const pathname = usePathname();
  const { mounted, token } = useClientAuth();
  const [user, setUser] = useState<StoredUser | null>(null);

  const { data: school } = useQuery({
    queryKey: ["school-admin", "my-school"],
    queryFn: () => schoolAdminApi.getMySchool(token!),
    enabled: mounted && !!token,
  });

  useEffect(() => {
    setUser(getUser());
  }, []);

  function handleLogout() {
    void performLogout();
  }

  const headerTitle = school?.name ?? t("header_title");

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="hidden md:flex md:w-64 md:flex-col border-e border-gray-200 bg-white">
        <div className="flex h-16 items-center px-6 border-b border-gray-100">
          <IqbalLogo size="sm" />
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
        <header className="h-16 border-b border-gray-200 bg-white px-6 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">{headerTitle}</h1>
          <span className="text-sm text-gray-500">{user?.email}</span>
        </header>
        <main className="flex-1 p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
