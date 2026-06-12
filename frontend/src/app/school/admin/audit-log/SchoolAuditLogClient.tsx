"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations, useFormatter } from "next-intl";
import { ClipboardList } from "lucide-react";
import { schoolAdminApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export function SchoolAuditLogClient() {
  const t = useTranslations("school_admin.audit_log");
  const format = useFormatter();
  const { mounted, token } = useClientAuth();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["school-admin", "audit-log"],
    queryFn: () => schoolAdminApi.listAuditLog(token!),
    enabled: mounted && !!token,
  });

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
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
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-1 text-sm text-gray-600">{t("subtitle")}</p>
      </div>

      {!data || data.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title={t("empty.title")}
          description={t("empty.description")}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.when")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.action")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden sm:table-cell">
                  {t("col.actor")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.target")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {format.dateTime(new Date(entry.created_at), {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900">{entry.action}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs hidden sm:table-cell break-all">
                    {entry.actor_id ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs hidden md:table-cell">
                    {entry.target_type ?? "—"}
                    {entry.target_id ? (
                      <span className="text-gray-300"> / {entry.target_id}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-4 py-3 text-xs text-gray-400 border-t border-gray-100">
            {t("showing_last", { count: data.length })}
          </p>
        </div>
      )}
    </div>
  );
}
