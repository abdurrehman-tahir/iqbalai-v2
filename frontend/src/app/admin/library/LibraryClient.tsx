"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useFormatter } from "next-intl";
import { Library, Upload, Trash2, FileText } from "lucide-react";
import { libraryApi, type LibraryBook } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE_MB = 100;

const STATUS_VARIANT: Record<LibraryBook["status"], "secondary" | "warning" | "success" | "destructive" | "outline"> = {
  ingesting: "warning",
  available: "success",
  ingestion_failed: "destructive",
  soft_deleted: "secondary",
};

export function LibraryClient() {
  const t = useTranslations("admin.library");
  const format = useFormatter();
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadModal, setUploadModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<LibraryBook | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [tags, setTags] = useState({
    language: "en",
    content_type: "curriculum",
    grade_range: "",
    subject_id: "",
  });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["library", "list"],
    queryFn: () => libraryApi.list(token!),
    enabled: mounted && !!token,
    refetchInterval: 10_000, // Poll while items are ingesting
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => libraryApi.softDelete(token ?? "", id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      setDeleteTarget(null);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile || !token) throw new Error("No file or token");

      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("profile", "platform_reference_book");
      formData.append(
        "tags",
        JSON.stringify({
          language: tags.language || undefined,
          content_type: tags.content_type || undefined,
          grade_range: tags.grade_range
            ? tags.grade_range.split(",").map((s) => s.trim())
            : undefined,
          subject_id: tags.subject_id || undefined,
        }),
      );

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/files/upload`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        },
      );

      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { message?: string };
        throw new Error(body.message ?? "Upload failed");
      }

      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      setUploadModal(false);
      setUploadFile(null);
      setUploadError("");
    },
    onError: (err: Error) => {
      setUploadError(err.message);
    },
  });

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setUploadError("");
    if (!file) return;
    if (file.type !== "application/pdf") {
      setUploadError(t("upload.error.not_pdf"));
      return;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setUploadError(t("upload.error.too_large", { size: MAX_FILE_SIZE_MB }));
      return;
    }
    setUploadFile(file);
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
      <ErrorState
        description={t("error")}
        onRetry={() => refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  const visible = (data ?? []).filter((b) => b.status !== "soft_deleted");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <Button
          variant="primary"
          size="md"
          className="gap-2"
          onClick={() => setUploadModal(true)}
        >
          <Upload className="size-4" aria-hidden="true" />
          {t("upload_button")}
        </Button>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon={Library}
          title={t("empty.title")}
          description={t("empty.description")}
          action={{ label: t("upload_button"), onClick: () => setUploadModal(true) }}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm" aria-label={t("table_label")}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.filename")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden sm:table-cell">
                  {t("col.tags")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500">
                  {t("col.status")}
                </th>
                <th className="px-4 py-3 text-start font-medium text-gray-500 hidden md:table-cell">
                  {t("col.uploaded")}
                </th>
                <th className="px-4 py-3 text-end font-medium text-gray-500">
                  {t("col.actions")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {visible.map((book) => (
                <tr key={book.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="size-4 text-gray-400 shrink-0" aria-hidden="true" />
                      <span className="font-medium text-gray-900 break-all">
                        {book.filename}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {book.tags.language && (
                        <Badge variant="secondary">{book.tags.language}</Badge>
                      )}
                      {book.tags.content_type && (
                        <Badge variant="outline">{book.tags.content_type}</Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANT[book.status]}>
                      {t(`status.${book.status}`)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs hidden md:table-cell">
                    {format.dateTime(new Date(book.created_at), {
                      dateStyle: "medium",
                    })}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteTarget(book)}
                        aria-label={t("actions.delete", {
                          name: book.filename,
                        })}
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

      {/* Upload modal */}
      <Modal
        open={uploadModal}
        onClose={() => {
          setUploadModal(false);
          setUploadFile(null);
          setUploadError("");
        }}
        title={t("upload.title")}
        description={t("upload.description")}
        size="md"
        closeLabel={t("upload.close")}
      >
        <div className="space-y-4">
          {/* File picker */}
          <div>
            <Label required>{t("upload.file_label")}</Label>
            <div
              className={cn(
                "mt-1 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors",
                uploadFile
                  ? "border-brand-300 bg-brand-50"
                  : "border-gray-300 hover:border-brand-400",
              )}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ")
                  fileInputRef.current?.click();
              }}
              role="button"
              tabIndex={0}
              aria-label={t("upload.file_picker_label")}
            >
              <Upload
                className={cn(
                  "size-8 mb-2",
                  uploadFile ? "text-brand-500" : "text-gray-400",
                )}
                aria-hidden="true"
              />
              {uploadFile ? (
                <p className="text-sm font-medium text-brand-700">
                  {uploadFile.name}
                </p>
              ) : (
                <p className="text-sm text-gray-500">{t("upload.file_hint")}</p>
              )}
              <p className="text-xs text-gray-400 mt-1">
                {t("upload.file_constraints", { size: MAX_FILE_SIZE_MB })}
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="sr-only"
              onChange={handleFileSelect}
              aria-label={t("upload.file_label")}
            />
            {uploadError && (
              <p className="text-xs text-red-600 mt-1" role="alert">
                {uploadError}
              </p>
            )}
          </div>

          {/* Tags */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="tag-lang">{t("upload.language_label")}</Label>
              <Input
                id="tag-lang"
                value={tags.language}
                onChange={(e) =>
                  setTags((t) => ({ ...t, language: e.target.value }))
                }
                placeholder="en"
              />
            </div>
            <div>
              <Label htmlFor="tag-type">{t("upload.content_type_label")}</Label>
              <Input
                id="tag-type"
                value={tags.content_type}
                onChange={(e) =>
                  setTags((t) => ({ ...t, content_type: e.target.value }))
                }
                placeholder="curriculum"
              />
            </div>
            <div>
              <Label htmlFor="tag-grade">{t("upload.grade_label")}</Label>
              <Input
                id="tag-grade"
                value={tags.grade_range}
                onChange={(e) =>
                  setTags((t) => ({ ...t, grade_range: e.target.value }))
                }
                placeholder="Grade 9, Grade 10"
              />
            </div>
            <div>
              <Label htmlFor="tag-subject">{t("upload.subject_label")}</Label>
              <Input
                id="tag-subject"
                value={tags.subject_id}
                onChange={(e) =>
                  setTags((t) => ({ ...t, subject_id: e.target.value }))
                }
                placeholder={t("upload.subject_placeholder")}
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="outline"
              size="md"
              onClick={() => {
                setUploadModal(false);
                setUploadFile(null);
                setUploadError("");
              }}
            >
              {t("upload.cancel")}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={!uploadFile}
              loading={uploadMutation.isPending}
              onClick={() => uploadMutation.mutate()}
            >
              {t("upload.submit")}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Soft-delete confirmation */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t("delete_modal.title")}
        description={t("delete_modal.description", {
          name: deleteTarget?.filename ?? "",
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
