import { CoordinatorShell } from "./CoordinatorShell";

export default function CoordinatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <CoordinatorShell>{children}</CoordinatorShell>;
}
