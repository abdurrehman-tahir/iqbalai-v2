import { CurriculumItemDetail } from "@/components/school-library/CurriculumItemDetail";

export default async function TeacherCurriculumDetailPage({
  params,
}: {
  params: Promise<{ itemId: string }>;
}) {
  const { itemId } = await params;
  return (
    <CurriculumItemDetail
      itemId={itemId}
      uploadHref="/teacher/library/curriculum/upload"
    />
  );
}
