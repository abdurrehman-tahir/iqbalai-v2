"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { schoolLibraryApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function TeacherLibraryUploadClient() {
  const t = useTranslations("teacher.library_upload");
  const { mounted, token } = useClientAuth();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: () =>
      schoolLibraryApi.upload(token ?? "", {
        file: file!,
        title,
        content_type: "reference",
        language: "en",
      }),
    onSuccess: (result) => {
      setError(null);
      setMessage(
        result.storage_deduplicated
          ? t("success_deduped", { title: result.item.title })
          : t("success_new", { title: result.item.title }),
      );
      setTitle("");
      setFile(null);
    },
    onError: (err: unknown) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : t("error_generic"));
    },
  });

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("subtitle")}</p>
      </div>

      <form
        className="space-y-4 rounded-lg border border-gray-200 bg-white p-6"
        onSubmit={(event) => {
          event.preventDefault();
          if (!file || !title.trim()) return;
          uploadMutation.mutate();
        }}
      >
        <div>
          <Label htmlFor="library-title" required>
            {t("title_label")}
          </Label>
          <Input
            id="library-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>

        <div>
          <Label htmlFor="library-file" required>
            {t("file_label")}
          </Label>
          <Input
            id="library-file"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <p className="mt-1 text-xs text-gray-500">{t("file_help")}</p>
        </div>

        {message && (
          <p className="text-sm text-green-700" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <Button
          type="submit"
          disabled={!mounted || !token || !file || !title.trim() || uploadMutation.isPending}
        >
          {uploadMutation.isPending ? t("uploading") : t("submit")}
        </Button>
      </form>
    </div>
  );
}
