import { SchoolAdminShell } from "./SchoolAdminShell";

export default function SchoolAdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SchoolAdminShell>{children}</SchoolAdminShell>;
}
