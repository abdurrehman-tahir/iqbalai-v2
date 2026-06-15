"use client";

import { usePathname } from "next/navigation";
import { AdminShell } from "./AdminShell";

/** Platform Admin shell — skipped under /admin/district (District Admin has its own shell). */
export function AdminLayoutSwitch({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname.startsWith("/admin/district/")) {
    return <>{children}</>;
  }
  return <AdminShell>{children}</AdminShell>;
}
