"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useFormatter } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Building2, Plus, Trash2, UserPlus } from "lucide-react";
import { districtsApi, adminUsersApi, type District } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const districtSchema = z.object({
  name: z.string().min(1).max(200),
  region: z.string().max(200).optional(),
  language_preference: z.string().max(20).optional(),
});

type DistrictFormValues = z.infer<typeof districtSchema>;

const inviteSchema = z.object({
  email: z.string().email(),
  display_name: z.string().min(1).max(255),
});

type InviteFormValues = z.infer<typeof inviteSchema>;

export function DistrictsClient() {
  const t = useTranslations("admin.districts");
  const format = useFormatter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<District | null>(null);
  const [inviteTarget, setInviteTarget] = useState<District | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["districts", "list"],
    queryFn: () => districtsApi.list(token!),
    enabled: mounted && !!token,
  });

  const createMutation = useMutation({
    mutationFn: (values: DistrictFormValues) => districtsApi.create(token ?? "", values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["districts"] });
      setShowCreate(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => districtsApi.delete(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["districts"] });
      setDeleteTarget(null);
    },
  });

  const inviteMutation = useMutation({
    mutationFn: (values: InviteFormValues & { district_id: string }) =>
      adminUsersApi.invite(token ?? "", {
        ...values,
        role: "district_admin",
      }),
    onSuccess: (invite) => {
      setInviteSuccess(invite.email);
      inviteForm.reset();
    },
  });

  const form = useForm<DistrictFormValues>({
    resolver: zodResolver(districtSchema),
    defaultValues: { name: "", region: "", language_preference: "" },
  });

  const inviteForm = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", display_name: "" },
  });

  function openCreate() {
    setShowCreate(true);
    form.reset({ name: "", region: "", language_preference: "" });
  }

  function openInvite(district: District) {
    setInviteTarget(district);
    setInviteSuccess(null);
    inviteForm.reset({ email: "", display_name: "" });
  }

  async function handleInviteSubmit(values: InviteFormValues) {
    if (!inviteTarget) return;
    await inviteMutation.mutateAsync({ ...values, district_id: inviteTarget.id });
  }

  async function handleSubmit(values: DistrictFormValues) {
    await createMutation.mutateAsync(values);
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState description={t("error")} onRetry={() => refetch()} retryLabel={t("retry")} />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <Button variant="primary" size="md" className="gap-2" onClick={openCreate}>
          <Plus className="size-4" aria-hidden="true" />
          {t("add_button")}
        </Button>
      </div>

      {/* Empty state */}
      {!data || data.length === 0 ? (
        <EmptyState
          icon={Building2}
          title={t("empty.title")}
          description={t("empty.description")}
          action={{ label: t("empty.cta"), onClick: openCreate }}
        />
      ) : (
        /* Table (scrollable on mobile) */
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" role="table" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-start">
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.name")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.region")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.language")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.created")}
                </th>
                <th className="px-4 py-3 text-end font-medium text-gray-500">{t("col.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((district) => (
                <tr key={district.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{district.name}</td>
                  <td className="px-4 py-3 text-gray-500">{district.region ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">
                    {district.language_preference ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">
                    {format.dateTime(new Date(district.created_at))}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openInvite(district)}
                        aria-label={t("actions.invite", { name: district.name })}
                        className="text-brand-600 hover:text-brand-800 hover:bg-brand-50"
                      >
                        <UserPlus className="size-4" aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(district)}
                        aria-label={t("actions.delete", { name: district.name })}
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="size-4" aria-hidden="true" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create modal */}
      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title={t("modal.create_title")}
        size="md"
        closeLabel={t("modal.close")}
      >
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="district-name" required>
              {t("modal.name_label")}
            </Label>
            <Input
              id="district-name"
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
            <Label htmlFor="district-region">{t("modal.region_label")}</Label>
            <Input
              id="district-region"
              {...form.register("region")}
              placeholder={t("modal.region_placeholder")}
            />
          </div>

          <div>
            <Label htmlFor="district-language">{t("modal.language_label")}</Label>
            <Input
              id="district-language"
              {...form.register("language_preference")}
              placeholder={t("modal.language_placeholder")}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" size="md" onClick={() => setShowCreate(false)}>
              {t("modal.cancel")}
            </Button>
            <Button type="submit" variant="primary" size="md" loading={createMutation.isPending}>
              {t("modal.create")}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Invite district admin modal */}
      <Modal
        open={!!inviteTarget}
        onClose={() => {
          setInviteTarget(null);
          setInviteSuccess(null);
        }}
        title={t("invite_modal.title", { name: inviteTarget?.name ?? "" })}
        size="md"
        closeLabel={t("invite_modal.close")}
      >
        {inviteSuccess ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              {t("invite_modal.success", { email: inviteSuccess })}
            </p>
            <div className="flex justify-end">
              <Button
                variant="primary"
                size="md"
                onClick={() => {
                  setInviteTarget(null);
                  setInviteSuccess(null);
                }}
              >
                {t("invite_modal.done")}
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={inviteForm.handleSubmit(handleInviteSubmit)} className="space-y-4">
            <div>
              <Label htmlFor="invite-email" required>
                {t("invite_modal.email_label")}
              </Label>
              <Input
                id="invite-email"
                type="email"
                {...inviteForm.register("email")}
                placeholder={t("invite_modal.email_placeholder")}
              />
              {inviteForm.formState.errors.email && (
                <p className="text-xs text-red-600 mt-1" role="alert">
                  {inviteForm.formState.errors.email.message}
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="invite-name" required>
                {t("invite_modal.name_label")}
              </Label>
              <Input
                id="invite-name"
                {...inviteForm.register("display_name")}
                placeholder={t("invite_modal.name_placeholder")}
              />
              {inviteForm.formState.errors.display_name && (
                <p className="text-xs text-red-600 mt-1" role="alert">
                  {inviteForm.formState.errors.display_name.message}
                </p>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                size="md"
                onClick={() => setInviteTarget(null)}
              >
                {t("invite_modal.cancel")}
              </Button>
              <Button type="submit" variant="primary" size="md" loading={inviteMutation.isPending}>
                {t("invite_modal.send")}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* Delete confirmation modal */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t("delete_modal.title")}
        description={t("delete_modal.description", { name: deleteTarget?.name ?? "" })}
        size="sm"
        closeLabel={t("delete_modal.cancel")}
      >
        <div className="flex justify-end gap-3">
          <Button variant="outline" size="md" onClick={() => setDeleteTarget(null)}>
            {t("delete_modal.cancel")}
          </Button>
          <Button
            variant="destructive"
            size="md"
            loading={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
          >
            {t("delete_modal.confirm")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
