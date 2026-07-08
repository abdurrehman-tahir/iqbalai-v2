"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import Link from "next/link";
import { dataRightsApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export function StudentDataRightsClient() {
  const t = useTranslations("student.data_rights");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: status } = useQuery({
    queryKey: ["student", "data-rights"],
    queryFn: () => dataRightsApi.getStudentStatus(token!),
    enabled: mounted && !!token,
  });

  const exportMutation = useMutation({
    mutationFn: () => dataRightsApi.requestStudentExport(token ?? ""),
    onSuccess: () => {
      setError(null);
      setSuccess(t("export_requested"));
      void qc.invalidateQueries({ queryKey: ["student", "data-rights"] });
    },
    onError: (err) => {
      setSuccess(null);
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  const deletionMutation = useMutation({
    mutationFn: () => dataRightsApi.requestStudentDeletion(token ?? "", true),
    onSuccess: () => {
      setError(null);
      setSuccess(t("deletion_requested"));
      setConfirmDelete(false);
      void qc.invalidateQueries({ queryKey: ["student", "data-rights"] });
    },
    onError: (err) => {
      setSuccess(null);
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  const cancelDeletionMutation = useMutation({
    mutationFn: (requestId: string) => dataRightsApi.cancelStudentDeletion(token ?? "", requestId),
    onSuccess: () => {
      setError(null);
      setSuccess(t("deletion_cancelled"));
      void qc.invalidateQueries({ queryKey: ["student", "data-rights"] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  async function handleDownload(requestId: string) {
    try {
      const blob = await dataRightsApi.downloadStudentExport(token ?? "", requestId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `iqbalai-export-${requestId.slice(0, 8)}.zip`;
      anchor.click();
      URL.revokeObjectURL(url);
      setSuccess(t("download_started"));
      setError(null);
    } catch (err) {
      setSuccess(null);
      setError(err instanceof Error ? err.message : t("error_generic"));
    }
  }

  const exportRequest = status?.export_request;
  const deletionRequest = status?.deletion_request;

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <Link href="/student" className="text-sm text-brand-600 hover:underline">
          {t("back_to_dashboard")}
        </Link>
        <h2 className="mt-2 text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("subtitle")}</p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {success && <p className="text-sm text-green-800">{success}</p>}

      <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h3 className="text-lg font-medium text-gray-900">{t("export_title")}</h3>
        <p className="text-sm text-gray-600">
          {status?.export_policy_message ?? t("export_policy")}
        </p>
        {exportRequest && (
          <p className="text-sm text-gray-700">
            {t("export_status", { status: exportRequest.status })}
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          <Button
            variant="primary"
            size="sm"
            loading={exportMutation.isPending}
            disabled={!!exportRequest && exportRequest.status !== "expired"}
            onClick={() => exportMutation.mutate()}
          >
            {t("export_request")}
          </Button>
          {exportRequest?.download_available && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void handleDownload(exportRequest.id)}
            >
              {t("export_download")}
            </Button>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h3 className="text-lg font-medium text-gray-900">{t("deletion_title")}</h3>
        <p className="text-sm text-gray-600">
          {status?.deletion_policy_message ?? t("deletion_policy")}
        </p>
        {deletionRequest?.status === "grace_period" && (
          <p className="text-sm text-amber-800">
            {t("deletion_grace_active", {
              date: deletionRequest.deletion_scheduled_at?.slice(0, 10) ?? "",
            })}
          </p>
        )}
        {deletionRequest?.status === "grace_period" ? (
          <Button
            variant="ghost"
            size="sm"
            loading={cancelDeletionMutation.isPending}
            onClick={() => cancelDeletionMutation.mutate(deletionRequest.id)}
          >
            {t("deletion_cancel")}
          </Button>
        ) : (
          <div className="space-y-3">
            <div className="flex items-start gap-2">
              <input
                id="confirm-delete"
                type="checkbox"
                checked={confirmDelete}
                onChange={(event) => setConfirmDelete(event.target.checked)}
                className="mt-1"
              />
              <Label htmlFor="confirm-delete" className="text-sm text-gray-700">
                {t("deletion_confirm_label")}
              </Label>
            </div>
            <Button
              variant="destructive"
              size="sm"
              loading={deletionMutation.isPending}
              disabled={!confirmDelete}
              onClick={() => deletionMutation.mutate()}
            >
              {t("deletion_request")}
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
