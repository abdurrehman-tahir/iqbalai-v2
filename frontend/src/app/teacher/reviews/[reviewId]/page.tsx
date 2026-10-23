import { ReviewCardClient } from "./ReviewCardClient";

type Props = { params: Promise<{ reviewId: string }> };

export default async function TeacherReviewPage({ params }: Props) {
  const { reviewId } = await params;
  return <ReviewCardClient reviewId={reviewId} />;
}
