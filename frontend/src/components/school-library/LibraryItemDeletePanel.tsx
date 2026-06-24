"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { schoolLibraryApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";

interface LibraryItemDeletePanelProps {
  itemId: string;
  libraryHref: string;
  canDelete: boolean;
}

export function LibraryItemDeletePanel({
  itemId,
  libraryHref,
  canDelete,
}: LibraryItemDeletePanelProps) {
  const t = useTranslations("school_library.lifecycle");
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token } = useClientAuth();

  const deleteMutation = useMutation({
    mutationFn: () => schoolLibraryApi.deleteItem(token!, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["school-library", "list"] });
      router.push(libraryHref);
    },
  });

  if (!canDelete) {
    return null;
  }

  return (
    <section className="rounded-lg border border-red-200 bg-red-50 p-4">
      <h3 className="text-lg font-semibold text-red-900">{t("delete_section_title")}</h3>
      <p className="mt-2 text-sm text-red-800">{t("delete_section_help")}</p>
      <Button
        type="button"
        variant="destructive"
        className="mt-4"
        disabled={deleteMutation.isPending}
        onClick={() => deleteMutation.mutate()}
      >
        {deleteMutation.isPending ? t("deleting") : t("delete_button")}
      </Button>
      {deleteMutation.isError && (
        <p className="mt-2 text-sm text-red-700" role="alert">
          {deleteMutation.error instanceof ApiError
            ? deleteMutation.error.message
            : t("delete_error")}
        </p>
      )}
    </section>
  );
}
