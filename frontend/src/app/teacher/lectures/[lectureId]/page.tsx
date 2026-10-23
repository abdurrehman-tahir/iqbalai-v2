import { LectureDetailClient } from "./LectureDetailClient";

type Props = {
  params: Promise<{ lectureId: string }>;
  searchParams: Promise<{ from_review?: string; tab?: string }>;
};

export default async function TeacherLecturePage({ params, searchParams }: Props) {
  const { lectureId } = await params;
  const { from_review: fromReview, tab } = await searchParams;
  return (
    <LectureDetailClient
      lectureId={lectureId}
      fromReviewId={fromReview ?? null}
      initialTab={tab === "reviews" ? "reviews" : "edit"}
    />
  );
}
