"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { schoolLibraryApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { getUser } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";

const STATUS_VARIANT: Record<
  string,
  "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  pending: "warning",
  ingesting: "warning",
  available: "success",
  failed: "destructive",
};

interface ReferenceItemDetailProps {
  itemId: string;
  uploadHref: string;
}

export function ReferenceItemDetail({ itemId, uploadHref }: ReferenceItemDetailProps) {
  const t = useTranslations("school_library.reference");
  const router = useRouter();
  const queryClient = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [userId, setUserId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    setUserId(getUser()?.user_id ?? null);
  }, []);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["school-library", "item", itemId],
    queryFn: () => schoolLibraryApi.get(token!, itemId),
    enabled: mounted && !!token,
    refetchInterval: (query) => {
      const status = query.state.data?.ingestion_status;
      return status === "pending" || status === "ingesting" ? 3000 : false;
    },
  });

  const publishMutation = useMutation({
    mutationFn: () => schoolLibraryApi.publish(token!, itemId),
    onSuccess: (item) => {
      setActionError(null);
      setActionMessage(t("detail.publish_success"));
      queryClient.setQueryData(["school-library", "item", itemId], item);
    },
    onError: (err: unknown) => {
      setActionMessage(null);
      setActionError(err instanceof ApiError ? err.message : t("detail.publish_error"));
    },
  });

  const removeSelectionMutation = useMutation({
    mutationFn: () => schoolLibraryApi.removeSelection(token!, itemId),
    onSuccess: () => {
      router.push(uploadHref);
    },
    onError: (err: unknown) => {
      setActionMessage(null);
      setActionError(err instanceof ApiError ? err.message : t("detail.remove_selection_error"));
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return <ErrorState message={t("detail.error")} onRetry={() => refetch()} />;
  }

  const statusKey = data.ingestion_status as keyof typeof STATUS_VARIANT;
  const isPublic = data.visibility === "school_public";
  const isOwner = userId !== null && data.created_by === userId;
  const visibilityLabel = isPublic ? t("detail.visibility_public") : t("detail.visibility_private");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">{data.title}</h2>
          <p className="mt-1 text-sm text-gray-600">{t("detail.subtitle")}</p>
        </div>
        <Badge variant={STATUS_VARIANT[statusKey] ?? "secondary"} role="status">
          {t(`detail.status.${data.ingestion_status}`)}
        </Badge>
      </div>

      <dl className="grid gap-3 rounded-lg border border-gray-200 bg-white p-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="font-medium text-gray-500">{t("detail.visibility_label")}</dt>
          <dd className="text-gray-900">{visibilityLabel}</dd>
        </div>
        <div>
          <dt className="font-medium text-gray-500">{t("detail.language_label")}</dt>
          <dd className="text-gray-900">{data.language.toUpperCase()}</dd>
        </div>
        <div>
          <dt className="font-medium text-gray-500">{t("detail.grade_label")}</dt>
          <dd className="text-gray-900">
            {data.grade_level_ordinal ?? t("detail.grade_unknown")}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-gray-500">{t("detail.content_type_label")}</dt>
          <dd className="text-gray-900">{t("detail.content_type_reference")}</dd>
        </div>
      </dl>

      {isPublic ? (
        <p className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-700" role="note">
          {t("detail.unpublish_blocked")}
        </p>
      ) : isOwner ? (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="text-lg font-semibold text-gray-900">{t("detail.publish_section_title")}</h3>
          <p className="mt-2 text-sm text-gray-600">{t("detail.publish_section_help")}</p>
          <Button
            type="button"
            className="mt-4"
            disabled={publishMutation.isPending}
            onClick={() => {
              setActionError(null);
              setActionMessage(null);
              publishMutation.mutate();
            }}
          >
            {publishMutation.isPending ? t("detail.publishing") : t("detail.publish_button")}
          </Button>
        </div>
      ) : null}

      {isPublic && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="text-lg font-semibold text-gray-900">
            {t("detail.remove_selection_section_title")}
          </h3>
          <p className="mt-2 text-sm text-gray-600">{t("detail.remove_selection_help")}</p>
          <Button
            type="button"
            variant="outline"
            className="mt-4"
            disabled={removeSelectionMutation.isPending}
            onClick={() => {
              setActionError(null);
              setActionMessage(null);
              removeSelectionMutation.mutate();
            }}
          >
            {removeSelectionMutation.isPending
              ? t("detail.removing_selection")
              : t("detail.remove_selection_button")}
          </Button>
        </div>
      )}

      {actionMessage && (
        <p className="text-sm text-green-700" role="status">
          {actionMessage}
        </p>
      )}
      {actionError && (
        <p className="text-sm text-red-600" role="alert">
          {actionError}
        </p>
      )}

      <Link href={uploadHref} className="text-sm font-medium text-brand-700 hover:underline">
        {t("detail.upload_another")}
      </Link>
    </div>
  );
}
