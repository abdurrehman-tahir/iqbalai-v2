"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserCog, Plus } from "lucide-react";
import { adminUsersApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const GRADE_OPTIONS = [
  "Grade 6",
  "Grade 7",
  "Grade 8",
  "Grade 9",
  "Grade 10",
  "Grade 11",
  "Grade 12",
] as const;

const inviteSchema = z.object({
  email: z.string().email(),
  display_name: z.string().min(1).max(200),
  grade_scope: z.array(z.string()).min(1, "Select at least one grade"),
});

type InviteFormValues = z.infer<typeof inviteSchema>;

export function CoordinatorsClient() {
  const t = useTranslations("school_admin.coordinators");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const [showInvite, setShowInvite] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["admin-users", "coordinators"],
    queryFn: async () => {
      const users = await adminUsersApi.list(token!);
      return users.filter((u) => u.role === "coordinator");
    },
    enabled: mounted && !!token,
  });

  const inviteMutation = useMutation({
    mutationFn: (values: InviteFormValues) =>
      adminUsersApi.invite(token ?? "", {
        email: values.email,
        display_name: values.display_name,
        role: "coordinator",
        grade_scope: values.grade_scope,
      }),
    onSuccess: (invite) => {
      setInviteSuccess(invite.email);
      inviteForm.reset({ email: "", display_name: "", grade_scope: [] });
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const inviteForm = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", display_name: "", grade_scope: [] },
  });

  const selectedGrades = inviteForm.watch("grade_scope");

  function toggleGrade(grade: string) {
    const current = inviteForm.getValues("grade_scope");
    if (current.includes(grade)) {
      inviteForm.setValue(
        "grade_scope",
        current.filter((g) => g !== grade),
        { shouldValidate: true },
      );
    } else {
      inviteForm.setValue("grade_scope", [...current, grade], { shouldValidate: true });
    }
  }

  async function handleInviteSubmit(values: InviteFormValues) {
    await inviteMutation.mutateAsync(values);
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 w-full" />
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
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <Button
          variant="primary"
          size="md"
          className="gap-2"
          onClick={() => {
            setShowInvite(true);
            setInviteSuccess(null);
            inviteForm.reset({ email: "", display_name: "", grade_scope: [] });
          }}
        >
          <Plus className="size-4" aria-hidden="true" />
          {t("invite_button")}
        </Button>
      </div>

      {!data || data.length === 0 ? (
        <EmptyState
          icon={UserCog}
          title={t("empty.title")}
          description={t("empty.description")}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" role="table" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-start">
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.name")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.email")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.scope")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.status")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((coord) => (
                <tr key={coord.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{coord.display_name}</td>
                  <td className="px-4 py-3 text-gray-600">{coord.email}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {coord.scoped_ids?.split(",").join(", ") ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{coord.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={showInvite}
        onClose={() => {
          setShowInvite(false);
          setInviteSuccess(null);
        }}
        title={t("invite_modal.title")}
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
                  setShowInvite(false);
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
              <Label htmlFor="coord-email" required>
                {t("invite_modal.email_label")}
              </Label>
              <Input id="coord-email" type="email" {...inviteForm.register("email")} />
            </div>
            <div>
              <Label htmlFor="coord-name" required>
                {t("invite_modal.name_label")}
              </Label>
              <Input id="coord-name" {...inviteForm.register("display_name")} />
            </div>
            <fieldset>
              <legend className="text-sm font-medium text-gray-700 mb-2">
                {t("invite_modal.scope_label")}
              </legend>
              <div className="flex flex-wrap gap-2">
                {GRADE_OPTIONS.map((grade) => (
                  <label
                    key={grade}
                    className="inline-flex items-center gap-2 rounded-md border border-gray-200 px-3 py-1.5 text-sm cursor-pointer hover:bg-gray-50"
                  >
                    <input
                      type="checkbox"
                      checked={selectedGrades.includes(grade)}
                      onChange={() => toggleGrade(grade)}
                    />
                    {grade}
                  </label>
                ))}
              </div>
              {inviteForm.formState.errors.grade_scope && (
                <p className="text-xs text-red-600 mt-1" role="alert">
                  {inviteForm.formState.errors.grade_scope.message}
                </p>
              )}
            </fieldset>
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" size="md" onClick={() => setShowInvite(false)}>
                {t("invite_modal.cancel")}
              </Button>
              <Button type="submit" variant="primary" size="md" loading={inviteMutation.isPending}>
                {t("invite_modal.send")}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
