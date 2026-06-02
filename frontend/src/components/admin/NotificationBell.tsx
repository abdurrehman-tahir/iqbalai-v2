"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Bell, X } from "lucide-react";
import { notificationsApi, type Notification } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";

export function NotificationBell() {
  const [panelOpen, setPanelOpen] = useState(false);
  const t = useTranslations("admin.notifications");
  const qc = useQueryClient();

  const token = getToken();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => notificationsApi.list(token ?? ""),
    enabled: !!token,
    refetchInterval: 60_000, // poll every 60s
  });

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(token ?? "", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const unread = data?.filter((n) => !n.is_read) ?? [];
  const unreadCount = unread.length;
  const badgeLabel = unreadCount > 99 ? "99+" : String(unreadCount);

  // Group by namespace
  const grouped = (data ?? []).reduce<Record<string, Notification[]>>(
    (acc, n) => {
      const ns = n.feature_namespace;
      if (!acc[ns]) acc[ns] = [];
      acc[ns].push(n);
      return acc;
    },
    {},
  );

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("aria_label", { count: unreadCount })}
        aria-expanded={panelOpen}
        aria-haspopup="true"
        onClick={() => setPanelOpen((p) => !p)}
        className="relative"
      >
        <Bell className="size-5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span
            className="absolute top-1 end-1 flex size-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white"
            aria-hidden="true"
          >
            {badgeLabel}
          </span>
        )}
      </Button>

      {/* Panel */}
      {panelOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30"
            onClick={() => setPanelOpen(false)}
            aria-hidden="true"
          />

          <div
            role="dialog"
            aria-label={t("panel_label")}
            className={cn(
              "absolute end-0 top-full mt-2 z-40",
              "w-80 max-h-[480px] flex flex-col",
              "rounded-xl border border-gray-200 bg-white shadow-xl overflow-hidden",
            )}
          >
            {/* Panel header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-900">
                {t("title")}
              </h3>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPanelOpen(false)}
                aria-label={t("close")}
                className="size-7"
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {isLoading && (
                <div className="space-y-3 p-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              )}

              {isError && (
                <ErrorState
                  description={t("error")}
                  onRetry={() => refetch()}
                  retryLabel={t("retry")}
                  className="py-8"
                />
              )}

              {!isLoading && !isError && data?.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                  <Bell className="size-8 text-gray-300 mb-3" aria-hidden="true" />
                  <p className="text-sm text-gray-500">{t("empty")}</p>
                </div>
              )}

              {!isLoading && !isError && data && data.length > 0 && (
                <div className="divide-y divide-gray-50">
                  {Object.entries(grouped).map(([ns, items]) => (
                    <div key={ns}>
                      <div className="px-4 py-2 bg-gray-50 flex items-center gap-2">
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                          {ns.replace(/_/g, " ")}
                        </span>
                        <Badge variant="secondary" className="text-xs">
                          {items.filter((i) => !i.is_read).length}
                        </Badge>
                      </div>
                      {items.map((n) => (
                        <button
                          key={n.id}
                          className={cn(
                            "w-full text-start px-4 py-3 hover:bg-gray-50 transition-colors",
                            !n.is_read && "bg-brand-50/40",
                          )}
                          onClick={() => markRead.mutate(n.id)}
                        >
                          <p
                            className={cn(
                              "text-sm font-medium text-gray-900",
                              n.is_read && "text-gray-500 font-normal",
                            )}
                          >
                            {n.title}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">
                            {n.body}
                          </p>
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
