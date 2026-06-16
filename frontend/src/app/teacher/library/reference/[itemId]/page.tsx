import { ReferenceItemDetail } from "@/components/school-library/ReferenceItemDetail";

export default async function TeacherReferenceDetailPage({
  params,
}: {
  params: Promise<{ itemId: string }>;
}) {
  const { itemId } = await params;
  return (
    <ReferenceItemDetail
      itemId={itemId}
      uploadHref="/teacher/library/reference/upload"
      libraryHref="/teacher/library"
    />
  );
}
