import { AdminLayoutSwitch } from "./AdminLayoutSwitch";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AdminLayoutSwitch>{children}</AdminLayoutSwitch>;
}
