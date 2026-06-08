"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations, useFormatter } from "next-intl";
import { ClipboardList } from "lucide-react";
import { auditApi, type AuditEntry } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

export function AuditLogClient() {
  const t = useTranslations("admin.audit_log");
  const format = useFormatter();
  const { mounted, token } = useClientAuth();

  const [actorFilter, setActorFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [submitted, setSubmitted] = useState({ actor: "", action: "" });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["audit-log", "list", submitted.actor, submitted.action],
    queryFn: () =>
      auditApi.list(token!, {
        actor: submitted.actor || undefined,
        action: submitted.action || undefined,
      }),
    enabled: mounted && !!token,
  });

  function handleFilter(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted({ actor: actorFilter, action: actionFilter });
  }

  if (!mounted || isLoading) {
    return (
      <div className="space-y-6">
        <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />
        <Skeleton className="h-8 w-48 hidden" aria-hidden="true" />
        <Skeleton className="h-16 w-full" />
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
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
      <AdminPageHeader title={t("title")} subtitle={t("subtitle")} />

      {/* Filters */}
      <form
        onSubmit={handleFilter}
        className="flex flex-wrap gap-4 items-end p-4 rounded-lg border border-gray-200 bg-white shadow-sm"
      >
        <div className="flex-1 min-w-[180px]">
          <Label htmlFor="audit-actor">{t("filter.actor_label")}</Label>
          <Input
            id="audit-actor"
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            placeholder={t("filter.actor_placeholder")}
          />
        </div>
        <div className="flex-1 min-w-[180px]">
          <Label htmlFor="audit-action">{t("filter.action_label")}</Label>
          <Input
            id="audit-action"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder={t("filter.action_placeholder")}
          />
        </div>
        <Button type="submit" variant="primary" size="md">
          {t("filter.apply")}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="md"
          onClick={() => {
            setActorFilter("");
            setActionFilter("");
            setSubmitted({ actor: "", action: "" });
          }}
        >
          {t("filter.clear")}
        </Button>
      </form>

      {/* Table */}
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
              {(data as AuditEntry[]).slice(0, 50).map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {format.dateTime(new Date(entry.created_at), {
                      dateStyle: "short",
                      timeStyle: "short",
                    })}
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {entry.action}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs hidden sm:table-cell break-all">
                    {entry.actor_id}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs hidden md:table-cell">
                    {entry.target_type}
                    {entry.target_id ? (
                      <span className="text-gray-300"> / {entry.target_id}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-4 py-3 text-xs text-gray-400 border-t border-gray-100">
            {t("showing_last", { count: Math.min(data.length, 50) })}
          </p>
        </div>
      )}
    </div>
  );
}
