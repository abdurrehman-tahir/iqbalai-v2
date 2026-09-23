import { QuizAttemptClient } from "./QuizAttemptClient";

type Props = { params: Promise<{ assignmentId: string }> };

export default async function StudentQuizPage({ params }: Props) {
  const { assignmentId } = await params;
  return <QuizAttemptClient assignmentId={assignmentId} />;
}
