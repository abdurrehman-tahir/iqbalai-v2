import { IndependentLectureRedirect } from "./IndependentLectureRedirect";
import { StudentShell } from "./StudentShell";

export default function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <IndependentLectureRedirect>
      <StudentShell>{children}</StudentShell>
    </IndependentLectureRedirect>
  );
}
