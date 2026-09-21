import { LectureViewerClient } from "./LectureViewerClient";

type Props = { params: Promise<{ lectureId: string }> };

export default async function StudentLecturePage({ params }: Props) {
  const { lectureId } = await params;
  return <LectureViewerClient lectureId={lectureId} />;
}
