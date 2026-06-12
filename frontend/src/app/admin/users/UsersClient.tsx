"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations, useFormatter } from "next-intl";
import { Users as UsersIcon } from "lucide-react";
import { adminUsersApi, type AdminUser } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { cn } from "@/lib/utils";

type LifecycleAction = "suspend" | "reactivate" | "deactivate";

function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("admin.users.status");
  const styles: Record<string, string> = {
    active: "bg-green-50 text-green-700 ring-green-600/20",
    suspended: "bg-amber-50 text-amber-700 ring-amber-600/20",
    deactivated: "bg-gray-100 text-gray-600 ring-gray-500/20",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        styles[status] ?? styles.deactivated,
      )}
    >
      {t(status as "active" | "suspended" | "deactivated")}
    </span>
  );
}

export function UsersClient() {
  const t = useTranslations("admin.users");
  const format = useFormatter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();

  const [confirmAction, setConfirmAction] = useState<{
    user: AdminUser;
    action: LifecycleAction;
  } | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["admin-users", "list"],
    queryFn: () => adminUsersApi.list(token!),
    enabled: mounted && !!token,
  });

  const lifecycleMutation = useMutation({
    mutationFn: ({ userId, action }: { userId: string; action: LifecycleAction }) => {
      if (action === "suspend") return adminUsersApi.suspend(token ?? "", userId);
      if (action === "reactivate") return adminUsersApi.reactivate(token ?? "", userId);
      return adminUsersApi.deactivate(token ?? "", userId);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      setConfirmAction(null);
    },
  });

  async function handleConfirm() {
    if (!confirmAction) return;
    await lifecycleMutation.mutateAsync({
      userId: confirmAction.user.id,
      action: confirmAction.action,
    });
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
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
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {!data || data.length === 0 ? (
        <EmptyState icon={UsersIcon} title={t("empty.title")} description={t("empty.description")} />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" role="table" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-start">
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.name")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.email")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.role")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">{t("col.status")}</th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.created")}
                </th>
                <th className="px-4 py-3 text-end font-medium text-gray-500">{t("col.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{user.display_name}</td>
                  <td className="px-4 py-3 text-gray-600">{user.email}</td>
                  <td className="px-4 py-3 text-gray-600">{t(`roles.${user.role}` as "roles.teacher")}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={user.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">
                    {format.dateTime(new Date(user.created_at))}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2 flex-wrap">
                      {user.status === "active" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setConfirmAction({ user, action: "suspend" })}
                        >
                          {t("actions.suspend")}
                        </Button>
                      )}
                      {user.status === "suspended" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setConfirmAction({ user, action: "reactivate" })}
                        >
                          {t("actions.reactivate")}
                        </Button>
                      )}
                      {user.status !== "deactivated" && (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => setConfirmAction({ user, action: "deactivate" })}
                        >
                          {t("actions.deactivate")}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        title={t(`confirm.${confirmAction?.action ?? "suspend"}.title`)}
        description={t(`confirm.${confirmAction?.action ?? "suspend"}.description`, {
          name: confirmAction?.user.display_name ?? "",
        })}
        size="sm"
        closeLabel={t("confirm.cancel")}
      >
        <div className="flex justify-end gap-3">
          <Button variant="outline" size="md" onClick={() => setConfirmAction(null)}>
            {t("confirm.cancel")}
          </Button>
          <Button
            variant={confirmAction?.action === "deactivate" ? "destructive" : "primary"}
            size="md"
            loading={lifecycleMutation.isPending}
            onClick={() => void handleConfirm()}
          >
            {t(`confirm.${confirmAction?.action ?? "suspend"}.confirm`)}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
