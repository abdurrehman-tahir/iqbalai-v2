import { IndependentStudentShell } from "./IndependentStudentShell";

export default function IndependentStudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <IndependentStudentShell>{children}</IndependentStudentShell>;
}
