"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Pencil, Users2 } from "lucide-react";
import { personasApi, type Persona } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

const editSchema = z.object({
  system_prompt: z.string().min(1).max(8000),
});

type EditValues = z.infer<typeof editSchema>;

export function PersonasClient() {
  const t = useTranslations("admin.personas");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [editTarget, setEditTarget] = useState<Persona | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["personas", "list"],
    queryFn: () => personasApi.list(token!),
    enabled: mounted && !!token,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: EditValues }) =>
      personasApi.update(token ?? "", id, values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["personas"] });
      setEditTarget(null);
    },
  });

  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: { system_prompt: "" },
  });

  function openEdit(persona: Persona) {
    setEditTarget(persona);
    form.reset({ system_prompt: persona.system_prompt });
  }

  async function handleSubmit(values: EditValues) {
    if (!editTarget) return;
    await updateMutation.mutateAsync({ id: editTarget.id, values });
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <Skeleton className="h-8 w-48 hidden" aria-hidden="true" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <ErrorState
          description={t("error")}
          onRetry={() => refetch()}
          retryLabel={t("retry")}
        />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <EmptyState
          icon={Users2}
          title={t("empty.title")}
          description={t("empty.description")}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((persona) => (
          <div
            key={persona.id}
            className={cn(
              "rounded-lg border bg-white p-5 shadow-sm flex flex-col gap-3",
              persona.is_custom
                ? "border-purple-200 bg-purple-50/30"
                : "border-gray-200",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-gray-900">
                  {persona.name}
                </h2>
                {persona.description && (
                  <p className="text-sm text-gray-500">{persona.description}</p>
                )}
              </div>
              <div className="flex gap-1 shrink-0">
                {persona.is_custom && (
                  <Badge variant="default">{t("custom_badge")}</Badge>
                )}
                {!persona.is_active && (
                  <Badge variant="secondary">{t("inactive_badge")}</Badge>
                )}
              </div>
            </div>

            {persona.is_custom ? (
              <p className="text-xs text-purple-700 bg-purple-50 rounded p-2 leading-relaxed">
                {t("custom_info")}
              </p>
            ) : (
              <p className="text-xs text-gray-400 line-clamp-3 font-mono">
                {persona.system_prompt}
              </p>
            )}

            <Button
              variant="outline"
              size="sm"
              className="mt-auto self-start gap-2"
              onClick={() => openEdit(persona)}
            >
              <Pencil className="size-3.5" aria-hidden="true" />
              {t("edit_button")}
            </Button>
          </div>
        ))}
      </div>

      {/* Edit modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t("modal.title", { name: editTarget?.name ?? "" })}
        description={t("modal.description")}
        size="lg"
        closeLabel={t("modal.close")}
      >
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="system_prompt" required>
              {t("modal.prompt_label")}
            </Label>
            <Textarea
              id="system_prompt"
              {...form.register("system_prompt")}
              rows={10}
              maxLength={8000}
              placeholder={t("modal.prompt_placeholder")}
              className="font-mono text-xs"
            />
            <div className="flex justify-between mt-1">
              {form.formState.errors.system_prompt && (
                <p className="text-xs text-red-600" role="alert">
                  {form.formState.errors.system_prompt.message}
                </p>
              )}
              <span className="text-xs text-gray-400 ms-auto">
                {form.watch("system_prompt")?.length ?? 0} / 8000
              </span>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => setEditTarget(null)}
            >
              {t("modal.cancel")}
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={updateMutation.isPending}
            >
              {t("modal.save")}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
