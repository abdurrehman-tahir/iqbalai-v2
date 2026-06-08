"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CreditCard, Plus, Pencil, Trash2 } from "lucide-react";
import { subscriptionsApi, type SubscriptionTier } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

const tierSchema = z.object({
  name: z.string().min(1).max(100),
  pricing_monthly_pkr: z.coerce.number().min(0),
  applies_to_role: z.string().min(1),
  caps: z.string().min(2), // JSON string
});

type TierFormValues = z.infer<typeof tierSchema>;

export function SubscriptionTiersClient() {
  const t = useTranslations("admin.subscription_tiers");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [editTarget, setEditTarget] = useState<SubscriptionTier | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SubscriptionTier | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["subscription-tiers", "list"],
    queryFn: () => subscriptionsApi.list(token!),
    enabled: mounted && !!token,
  });

  const createMutation = useMutation({
    mutationFn: (values: TierFormValues) =>
      subscriptionsApi.create(token ?? "", {
        name: values.name,
        pricing_monthly_pkr: values.pricing_monthly_pkr,
        applies_to_role: values.applies_to_role,
        caps: JSON.parse(values.caps) as Record<string, unknown>,
        is_active: true,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscription-tiers"] });
      setShowCreate(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: TierFormValues }) =>
      subscriptionsApi.update(token ?? "", id, {
        name: values.name,
        pricing_monthly_pkr: values.pricing_monthly_pkr,
        applies_to_role: values.applies_to_role,
        caps: JSON.parse(values.caps) as Record<string, unknown>,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscription-tiers"] });
      setEditTarget(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => subscriptionsApi.delete(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscription-tiers"] });
      setDeleteTarget(null);
    },
  });

  const form = useForm<TierFormValues>({
    resolver: zodResolver(tierSchema),
    defaultValues: {
      name: "",
      pricing_monthly_pkr: 0,
      applies_to_role: "school",
      caps: "{}",
    },
  });

  function openEdit(tier: SubscriptionTier) {
    setEditTarget(tier);
    form.reset({
      name: tier.name,
      pricing_monthly_pkr: tier.pricing_monthly_pkr,
      applies_to_role: tier.applies_to_role,
      caps: JSON.stringify(tier.caps, null, 2),
    });
  }

  function openCreate() {
    setShowCreate(true);
    form.reset({
      name: "",
      pricing_monthly_pkr: 0,
      applies_to_role: "school",
      caps: "{}",
    });
  }

  async function handleSubmit(values: TierFormValues) {
    try {
      JSON.parse(values.caps);
    } catch {
      form.setError("caps", { message: t("modal.caps_invalid_json") });
      return;
    }

    if (editTarget) {
      await updateMutation.mutateAsync({ id: editTarget.id, values });
    } else {
      await createMutation.mutateAsync(values);
    }
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-32 ms-auto" aria-hidden="true" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Array.from({ length: 3 }).map((_, i) => (
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

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <Button variant="primary" size="md" className="gap-2" onClick={openCreate}>
          <Plus className="size-4" aria-hidden="true" />
          {t("add_button")}
        </Button>
      </div>

      {/* Schema-only banner */}
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
        <p className="text-sm text-yellow-800">{t("schema_only_banner")}</p>
      </div>

      {/* Tiers grid / empty state */}
      {!data || data.length === 0 ? (
        <EmptyState
          icon={CreditCard}
          title={t("empty.title")}
          description={t("empty.description")}
          action={{ label: t("empty.cta"), onClick: openCreate }}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((tier) => (
            <div
              key={tier.id}
              className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm flex flex-col gap-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold text-gray-900">
                    {tier.name}
                  </h2>
                  <p className="text-sm text-gray-500">
                    PKR {tier.pricing_monthly_pkr.toLocaleString()} / {t("month")}
                  </p>
                </div>
                <Badge variant={tier.is_active ? "success" : "secondary"}>
                  {tier.is_active ? t("status.active") : t("status.deprecated")}
                </Badge>
              </div>

              <p className="text-xs text-gray-500">
                {t("role_label")}: <span className="font-medium">{tier.applies_to_role}</span>
              </p>

              <pre className="text-xs bg-gray-50 rounded p-2 overflow-x-auto text-gray-600">
                {JSON.stringify(tier.caps, null, 2)}
              </pre>

              <div className="flex gap-2 mt-auto">
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => openEdit(tier)}
                >
                  <Pencil className="size-3.5" aria-hidden="true" />
                  {t("actions.edit")}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1.5 text-red-500 hover:text-red-700 hover:bg-red-50"
                  onClick={() => setDeleteTarget(tier)}
                >
                  <Trash2 className="size-3.5" aria-hidden="true" />
                  {t("actions.delete")}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal
        open={showCreate || !!editTarget}
        onClose={() => {
          setShowCreate(false);
          setEditTarget(null);
        }}
        title={editTarget ? t("modal.edit_title") : t("modal.create_title")}
        size="md"
        closeLabel={t("modal.close")}
      >
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="tier-name" required>
              {t("modal.name_label")}
            </Label>
            <Input
              id="tier-name"
              {...form.register("name")}
              placeholder={t("modal.name_placeholder")}
            />
            {form.formState.errors.name && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="tier-price" required>
              {t("modal.price_label")}
            </Label>
            <Input
              id="tier-price"
              type="number"
              min={0}
              {...form.register("pricing_monthly_pkr")}
            />
            {form.formState.errors.pricing_monthly_pkr && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {form.formState.errors.pricing_monthly_pkr.message}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="tier-role" required>
              {t("modal.role_label")}
            </Label>
            <Input
              id="tier-role"
              {...form.register("applies_to_role")}
              placeholder={t("modal.role_placeholder")}
            />
          </div>

          <div>
            <Label htmlFor="tier-caps">{t("modal.caps_label")}</Label>
            <Textarea
              id="tier-caps"
              {...form.register("caps")}
              placeholder="{}"
              rows={4}
              className="font-mono text-xs"
            />
            {form.formState.errors.caps && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {form.formState.errors.caps.message}
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => {
                setShowCreate(false);
                setEditTarget(null);
              }}
            >
              {t("modal.cancel")}
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={createMutation.isPending || updateMutation.isPending}
            >
              {editTarget ? t("modal.save") : t("modal.create")}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete confirmation modal */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t("delete_modal.title")}
        description={t("delete_modal.description", {
          name: deleteTarget?.name ?? "",
        })}
        size="sm"
        closeLabel={t("delete_modal.cancel")}
      >
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            size="md"
            onClick={() => setDeleteTarget(null)}
          >
            {t("delete_modal.cancel")}
          </Button>
          <Button
            variant="destructive"
            size="md"
            loading={deleteMutation.isPending}
            onClick={() =>
              deleteTarget && deleteMutation.mutate(deleteTarget.id)
            }
          >
            {t("delete_modal.confirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
