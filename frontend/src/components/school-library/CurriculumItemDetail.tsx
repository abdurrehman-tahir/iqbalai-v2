"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { schoolLibraryApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { useCurrentUser } from "@/hooks/use-current-user";
import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { parseTopicTree, TopicTreeView } from "./TopicTreeView";
import { LibraryIngestionPanel } from "./LibraryIngestionPanel";
import { LibraryItemDeletePanel } from "./LibraryItemDeletePanel";

const STATUS_VARIANT: Record<
  string,
  "secondary" | "warning" | "success" | "destructive" | "outline"
> = {
  pending: "warning",
  ingesting: "warning",
  available: "success",
  failed: "destructive",
};

interface CurriculumItemDetailProps {
  itemId: string;
  uploadHref: string;
  libraryHref: string;
}

export function CurriculumItemDetail({ itemId, uploadHref, libraryHref }: CurriculumItemDetailProps) {
  const t = useTranslations("school_library.curriculum");
  const { mounted, token } = useClientAuth();
  const { user } = useCurrentUser();
  const userId = user?.user_id ?? null;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["school-library", "item", itemId],
    queryFn: () => schoolLibraryApi.get(token!, itemId),
    enabled: mounted && !!token,
    refetchInterval: (query) => {
      const status = query.state.data?.ingestion_status;
      return status === "pending" || status === "ingesting" ? 3000 : false;
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
    return <ErrorState description={t("detail.error")} onRetry={() => refetch()} />;
  }

  const tree = parseTopicTree(data);
  const statusKey = data.ingestion_status as keyof typeof STATUS_VARIANT;
  const isOwner = userId !== null && data.created_by === userId;

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
          <dd className="text-gray-900">{t("detail.visibility_public")}</dd>
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
          <dd className="text-gray-900">{t("detail.content_type_curriculum")}</dd>
        </div>
      </dl>

      <LibraryIngestionPanel itemId={itemId} item={data} />

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-lg font-semibold text-gray-900">{t("detail.topic_tree_title")}</h3>
        <div className="mt-4">
          {data.ingestion_status === "available" ? (
            <TopicTreeView
              tree={tree}
              degradedLabel={t("detail.topic_tree_degraded")}
              emptyLabel={t("detail.topic_tree_empty")}
            />
          ) : (
            <p className="text-sm text-gray-600" role="status">
              {t("detail.topic_tree_pending")}
            </p>
          )}
        </div>
      </section>

      <LibraryItemDeletePanel
        itemId={itemId}
        libraryHref={libraryHref}
        canDelete={isOwner}
      />

      <Link href={uploadHref} className="text-sm font-medium text-brand-700 hover:underline">
        {t("detail.upload_another")}
      </Link>
    </div>
  );
}
