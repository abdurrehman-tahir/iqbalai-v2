"use client";

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Upload } from "lucide-react";
import { bulkImportApi, type BulkImportJob } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE_MB = 5;

export function BulkImportClient() {
  const t = useTranslations("coordinator.bulk_import");
  const { mounted, token } = useClientAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [result, setResult] = useState<BulkImportJob | null>(null);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile || !token) throw new Error("Missing file or token");
      return bulkImportApi.dryRun(token, selectedFile);
    },
    onSuccess: (job) => {
      setResult(job);
      setFileError("");
    },
    onError: (err: Error) => {
      setFileError(err.message);
    },
  });

  function handleFileChange(file: File | null) {
    setFileError("");
    setResult(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const lower = file.name.toLowerCase();
    if (!lower.endsWith(".csv") && !lower.endsWith(".xlsx")) {
      setFileError(t("errors.invalid_type"));
      setSelectedFile(null);
      return;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setFileError(t("errors.too_large", { max: MAX_FILE_SIZE_MB }));
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (mounted && token && selectedFile) {
      uploadMutation.mutate();
    }
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-1 text-sm text-gray-600">{t("subtitle")}</p>
      </div>

      <form onSubmit={handleSubmit} className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
        <div>
          <Label htmlFor="bulk-import-file">{t("file_label")}</Label>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <input
              ref={fileInputRef}
              id="bulk-import-file"
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="sr-only"
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="size-4 me-2" aria-hidden="true" />
              {t("choose_file")}
            </Button>
            {selectedFile && (
              <span className="text-sm text-gray-600">{selectedFile.name}</span>
            )}
          </div>
          <p className="mt-2 text-xs text-gray-500">{t("file_hint")}</p>
          {fileError && <p className="mt-2 text-sm text-red-600">{fileError}</p>}
        </div>

        <Button
          type="submit"
          disabled={!mounted || !token || !selectedFile || uploadMutation.isPending}
        >
          {uploadMutation.isPending ? t("validating") : t("run_dry_run")}
        </Button>
      </form>

      {result && (
        <section className="space-y-4" aria-live="polite">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-lg font-medium text-gray-900">{t("results_title")}</h3>
            <Badge variant="secondary">{t("summary.total", { count: result.total_rows })}</Badge>
            <Badge variant="success">{t("summary.valid", { count: result.success_rows })}</Badge>
            <Badge variant="destructive">{t("summary.invalid", { count: result.failed_rows })}</Badge>
          </div>

          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-start text-gray-600">
                <tr>
                  <th className="px-4 py-3 font-medium">{t("table.row")}</th>
                  <th className="px-4 py-3 font-medium">{t("table.name")}</th>
                  <th className="px-4 py-3 font-medium">{t("table.email")}</th>
                  <th className="px-4 py-3 font-medium">{t("table.grade")}</th>
                  <th className="px-4 py-3 font-medium">{t("table.status")}</th>
                  <th className="px-4 py-3 font-medium">{t("table.errors")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.rows.map((row) => (
                  <tr key={row.row_number}>
                    <td className="px-4 py-3">{row.row_number}</td>
                    <td className="px-4 py-3">{row.data?.name ?? "—"}</td>
                    <td className="px-4 py-3">{row.data?.email ?? "—"}</td>
                    <td className="px-4 py-3">{row.data?.grade ?? "—"}</td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={row.status === "valid" ? "success" : "destructive"}
                        className={cn(row.status === "valid" && "capitalize")}
                      >
                        {row.status === "valid" ? t("status.valid") : t("status.invalid")}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-red-600">
                      {row.errors.length
                        ? row.errors.map((code) => t(`error_codes.${code}`)).join("; ")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Button type="button" disabled title={t("commit_disabled_hint")}>
            {t("commit_disabled")}
          </Button>
        </section>
      )}
    </div>
  );
}
