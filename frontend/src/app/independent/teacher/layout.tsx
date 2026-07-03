import { IndependentTeacherShell } from "./IndependentTeacherShell";

export default function IndependentTeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <IndependentTeacherShell>{children}</IndependentTeacherShell>;
}
