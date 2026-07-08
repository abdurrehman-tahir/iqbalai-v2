"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FileText, Plus } from "lucide-react";
import { useFormatter } from "next-intl";
import { tosApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

const TOS_CHAR_LIMIT = 50_000;
const DISCLAIMER_CHAR_LIMIT = 500;

interface TosVersion {
  id: string;
  version: number;
  content: string;
  effective_at: string;
}

interface TosAdminClientProps {
  type: "tos" | "disclaimer";
}

export function TosAdminClient({ type }: TosAdminClientProps) {
  const t = useTranslations(type === "tos" ? "admin.tos" : "admin.disclaimer");
  const format = useFormatter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [showPublish, setShowPublish] = useState(false);

  const charLimit = type === "tos" ? TOS_CHAR_LIMIT : DISCLAIMER_CHAR_LIMIT;

  const publishSchema = z.object({
    content: z
      .string()
      .min(1, t("modal.content_required"))
      .max(charLimit, t("modal.content_too_long", { limit: charLimit })),
  });

  type PublishValues = z.infer<typeof publishSchema>;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [type, "list"],
    queryFn: () => (type === "tos" ? tosApi.list(token!) : tosApi.listDisclaimer(token!)),
    enabled: mounted && !!token,
  });

  const publishMutation = useMutation({
    mutationFn: (values: PublishValues) =>
      type === "tos"
        ? tosApi.publish(token ?? "", values.content)
        : tosApi.publishDisclaimer(token ?? "", values.content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [type] });
      setShowPublish(false);
    },
  });

  const form = useForm<PublishValues>({
    resolver: zodResolver(publishSchema),
    defaultValues: { content: "" },
  });

  function openPublish() {
    const latest = data?.[0];
    form.reset({ content: latest?.content ?? "" });
    setShowPublish(true);
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-36 ms-auto" aria-hidden="true" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <ErrorState description={t("error")} onRetry={() => refetch()} retryLabel={t("retry")} />
      </div>
    );
  }

  const versions = (data ?? []) as TosVersion[];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <Button variant="primary" size="md" className="gap-2" onClick={openPublish}>
          <Plus className="size-4" aria-hidden="true" />
          {t("publish_button")}
        </Button>
      </div>

      {/* Disclaimer char limit info */}
      {type === "disclaimer" && (
        <div className="rounded-lg border border-brand-200 bg-brand-50 p-4">
          <p className="text-sm text-brand-800">
            {t("char_limit_info", { limit: DISCLAIMER_CHAR_LIMIT })}
          </p>
        </div>
      )}

      {/* Version history */}
      {versions.length === 0 ? (
        <EmptyState
          icon={FileText}
          title={t("empty.title")}
          description={t("empty.description")}
          action={{ label: t("publish_button"), onClick: openPublish }}
        />
      ) : (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-gray-700">{t("history_label")}</h2>
          <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
            {versions.map((v, idx) => (
              <div
                key={v.id}
                className="flex items-start justify-between gap-4 p-4 hover:bg-gray-50"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-900">
                      {t("version_label", { version: v.version })}
                    </span>
                    {idx === 0 && <Badge variant="success">{t("current_badge")}</Badge>}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {format.dateTime(new Date(v.effective_at), {
                      dateStyle: "long",
                      timeStyle: "short",
                    })}
                  </p>
                  <p className="text-sm text-gray-600 mt-2 line-clamp-3 whitespace-pre-wrap">
                    {v.content}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Publish modal */}
      <Modal
        open={showPublish}
        onClose={() => setShowPublish(false)}
        title={t("modal.title")}
        description={t("modal.description", {
          current: versions[0]?.version ?? 0,
          next: (versions[0]?.version ?? 0) + 1,
        })}
        size="xl"
        closeLabel={t("modal.close")}
      >
        <form
          onSubmit={form.handleSubmit(async (v) => {
            await publishMutation.mutateAsync(v);
          })}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="tos-content" required>
              {t("modal.content_label")}
            </Label>
            <Textarea
              id="tos-content"
              {...form.register("content")}
              rows={type === "disclaimer" ? 6 : 16}
              maxLength={charLimit}
              placeholder={t("modal.content_placeholder")}
            />
            <div className="flex justify-between mt-1">
              {form.formState.errors.content && (
                <p className="text-xs text-red-600" role="alert">
                  {form.formState.errors.content.message}
                </p>
              )}
              <span className="text-xs text-gray-400 ms-auto">
                {form.watch("content")?.length ?? 0} / {charLimit}
              </span>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" size="md" onClick={() => setShowPublish(false)}>
              {t("modal.cancel")}
            </Button>
            <Button type="submit" variant="primary" size="md" loading={publishMutation.isPending}>
              {t("modal.publish")}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
