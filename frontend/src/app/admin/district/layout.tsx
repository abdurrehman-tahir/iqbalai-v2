import { DistrictAdminShell } from "./DistrictAdminShell";

export default function DistrictAdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DistrictAdminShell>{children}</DistrictAdminShell>;
}
