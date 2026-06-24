import { CurriculumItemDetail } from "@/components/school-library/CurriculumItemDetail";

export default async function CoordinatorCurriculumDetailPage({
  params,
}: {
  params: Promise<{ itemId: string }>;
}) {
  const { itemId } = await params;
  return (
    <CurriculumItemDetail
      itemId={itemId}
      uploadHref="/coordinator/library/curriculum/upload"
      libraryHref="/coordinator/curriculum"
    />
  );
}
