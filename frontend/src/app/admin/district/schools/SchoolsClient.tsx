"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useFormatter } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { School as SchoolIcon, Plus, Trash2, UserPlus } from "lucide-react";
import { schoolsApi, districtsApi, adminUsersApi, type School, type District } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { useCurrentUser } from "@/hooks/use-current-user";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const schoolSchema = z.object({
  name: z.string().min(1).max(200),
  district_id: z.string().min(1).max(36),
});

type SchoolFormValues = z.infer<typeof schoolSchema>;

const inviteSchema = z.object({
  email: z.string().email(),
  display_name: z.string().min(1).max(200),
});

type InviteFormValues = z.infer<typeof inviteSchema>;

export function SchoolsClient() {
  const t = useTranslations("district_admin.schools");
  const format = useFormatter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const { user } = useCurrentUser();
  const isPlatformAdmin = user?.role === "platform_admin";

  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<School | null>(null);
  const [inviteTarget, setInviteTarget] = useState<School | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);
  const [filterDistrictId, setFilterDistrictId] = useState<string>("");

  const effectiveDistrictId = isPlatformAdmin
    ? filterDistrictId || undefined
    : user?.district_id ?? undefined;

  const { data: districts } = useQuery({
    queryKey: ["districts", "list"],
    queryFn: () => districtsApi.list(token!),
    enabled: mounted && !!token && isPlatformAdmin,
  });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["schools", "list", effectiveDistrictId],
    queryFn: () => schoolsApi.list(token!, effectiveDistrictId),
    enabled: mounted && !!token && (!isPlatformAdmin || !!effectiveDistrictId),
  });

  const createMutation = useMutation({
    mutationFn: (values: SchoolFormValues) => schoolsApi.create(token ?? "", values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schools"] });
      setShowCreate(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => schoolsApi.delete(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schools"] });
      setDeleteTarget(null);
    },
  });

  const inviteMutation = useMutation({
    mutationFn: (values: InviteFormValues & { school_id: string }) =>
      adminUsersApi.invite(token ?? "", {
        email: values.email,
        display_name: values.display_name,
        role: "school_admin",
        school_id: values.school_id,
      }),
    onSuccess: (invite) => {
      setInviteSuccess(invite.email);
      inviteForm.reset();
    },
  });

  const form = useForm<SchoolFormValues>({
    resolver: zodResolver(schoolSchema),
    defaultValues: {
      name: "",
      district_id: user?.district_id ?? "",
    },
  });

  const inviteForm = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", display_name: "" },
  });

  function openCreate() {
    setShowCreate(true);
    form.reset({
      name: "",
      district_id: isPlatformAdmin
        ? filterDistrictId || districts?.[0]?.id || ""
        : user?.district_id ?? "",
    });
  }

  async function handleSubmit(values: SchoolFormValues) {
    await createMutation.mutateAsync(values);
  }

  function openInvite(school: School) {
    setInviteTarget(school);
    setInviteSuccess(null);
    inviteForm.reset({ email: "", display_name: "" });
  }

  async function handleInviteSubmit(values: InviteFormValues) {
    if (!inviteTarget) return;
    await inviteMutation.mutateAsync({ ...values, school_id: inviteTarget.id });
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isPlatformAdmin && !effectiveDistrictId) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("platform_subtitle")}</p>
        </div>
        <div className="max-w-md">
          <Label htmlFor="district-filter">{t("district_filter_label")}</Label>
          <select
            id="district-filter"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={filterDistrictId}
            onChange={(e) => setFilterDistrictId(e.target.value)}
          >
            <option value="">{t("district_filter_placeholder")}</option>
            {(districts ?? []).map((d: District) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        description={t("error")}
        onRetry={() => refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  return (
    <div className="space-y-6">
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

      {isPlatformAdmin && districts && (
        <div className="max-w-md">
          <Label htmlFor="district-filter">{t("district_filter_label")}</Label>
          <select
            id="district-filter"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={filterDistrictId}
            onChange={(e) => setFilterDistrictId(e.target.value)}
          >
            {(districts as District[]).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {!data || data.length === 0 ? (
        <EmptyState
          icon={SchoolIcon}
          title={t("empty.title")}
          description={t("empty.description")}
          action={{ label: t("empty.cta"), onClick: openCreate }}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" role="table" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-start">
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.name")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.created")}
                </th>
                <th className="px-4 py-3 text-end font-medium text-gray-500">
                  {t("col.actions")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((school) => (
                <tr key={school.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{school.name}</td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">
                    {format.dateTime(new Date(school.created_at))}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openInvite(school)}
                        aria-label={t("actions.invite", { name: school.name })}
                      >
                        <UserPlus className="size-4" aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(school)}
                        aria-label={t("actions.delete", { name: school.name })}
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

      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title={t("modal.create_title")}
        size="md"
        closeLabel={t("modal.close")}
      >
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          {!isPlatformAdmin && (
            <input type="hidden" {...form.register("district_id")} />
          )}
          {isPlatformAdmin && (
            <div>
              <Label htmlFor="school-district" required>
                {t("modal.district_label")}
              </Label>
              <select
                id="school-district"
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                {...form.register("district_id")}
              >
                {(districts ?? []).map((d: District) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div>
            <Label htmlFor="school-name" required>
              {t("modal.name_label")}
            </Label>
            <Input
              id="school-name"
              {...form.register("name")}
              placeholder={t("modal.name_placeholder")}
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
              <Label htmlFor="school-invite-email" required>
                {t("invite_modal.email_label")}
              </Label>
              <Input
                id="school-invite-email"
                type="email"
                {...inviteForm.register("email")}
                placeholder={t("invite_modal.email_placeholder")}
              />
            </div>
            <div>
              <Label htmlFor="school-invite-name" required>
                {t("invite_modal.name_label")}
              </Label>
              <Input
                id="school-invite-name"
                {...inviteForm.register("display_name")}
                placeholder={t("invite_modal.name_placeholder")}
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" size="md" onClick={() => setInviteTarget(null)}>
                {t("invite_modal.cancel")}
              </Button>
              <Button type="submit" variant="primary" size="md" loading={inviteMutation.isPending}>
                {t("invite_modal.send")}
              </Button>
            </div>
          </form>
        )}
      </Modal>

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
