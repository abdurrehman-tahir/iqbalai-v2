"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { schoolLibraryApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import type { SchoolLibraryItemRead } from "@/lib/api/types";

interface LibraryIngestionPanelProps {
  itemId: string;
  item: Pick<SchoolLibraryItemRead, "ingestion_status" | "ingestion_error">;
}

export function LibraryIngestionPanel({ itemId, item }: LibraryIngestionPanelProps) {
  const t = useTranslations("school_library.ingestion");
  const { token } = useClientAuth();
  const queryClient = useQueryClient();

  const retryMutation = useMutation({
    mutationFn: () => schoolLibraryApi.retryIngestion(token!, itemId),
    onSuccess: (updated) => {
      queryClient.setQueryData(["school-library", "item", itemId], updated);
      queryClient.invalidateQueries({ queryKey: ["school-library", "list"] });
    },
  });

  if (item.ingestion_status === "failed") {
    return (
      <section className="rounded-lg border border-red-200 bg-red-50 p-4">
        <h3 className="text-lg font-semibold text-red-900">{t("failed_title")}</h3>
        <p className="mt-2 text-sm text-red-800" role="alert">
          {item.ingestion_error ?? t("failed_unknown")}
        </p>
        <Button
          type="button"
          className="mt-4"
          disabled={retryMutation.isPending}
          onClick={() => retryMutation.mutate()}
        >
          {retryMutation.isPending ? t("retrying") : t("retry_button")}
        </Button>
        {retryMutation.isError && (
          <p className="mt-2 text-sm text-red-700" role="alert">
            {retryMutation.error instanceof ApiError
              ? retryMutation.error.message
              : t("retry_error")}
          </p>
        )}
      </section>
    );
  }

  if (item.ingestion_status === "pending" || item.ingestion_status === "ingesting") {
    return (
      <section className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
        <p className="text-sm text-yellow-900" role="status">
          {t(`status_help.${item.ingestion_status}`)}
        </p>
        {item.ingestion_status === "pending" && (
          <Button
            type="button"
            variant="outline"
            className="mt-4"
            disabled={retryMutation.isPending}
            onClick={() => retryMutation.mutate()}
          >
            {retryMutation.isPending ? t("retrying") : t("retry_button")}
          </Button>
        )}
      </section>
    );
  }

  return null;
}
