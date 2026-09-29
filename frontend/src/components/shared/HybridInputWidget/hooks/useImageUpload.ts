"use client";

/**
 * Client-side image upload hook (T-167).
 *
 * POSTs to `studentQuestionImagesApi.upload` (student_question_image upload
 * profile, T-166) and keeps a local thumbnail (FileReader data URL) alongside
 * the returned MinIO storage key so `ImageAttachmentChip` can render without
 * a round-trip, and `HybridInputWidget.onSubmit` can thread the storage keys
 * up to the parent as `attached_images`.
 */

import { useCallback, useState } from "react";

import { useClientAuth } from "@/hooks/use-client-auth";
import { studentQuestionImagesApi } from "@/lib/api";

import type { ImageRef } from "../types";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export type ImageUploadErrorCode =
  | "too_large"
  | "format_unsupported"
  | "max_reached"
  | "upload_failed";

export type UseImageUploadOptions = {
  maxImages?: number;
  enabled?: boolean;
  onAttached?: (count: number) => void;
};

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(reader.error ?? new Error("file_read_failed"));
    reader.readAsDataURL(file);
  });
}

export function useImageUpload(options: UseImageUploadOptions = {}) {
  const { maxImages = 3, enabled = false, onAttached } = options;
  const { token } = useClientAuth();

  const [images, setImages] = useState<ImageRef[]>([]);
  const [error, setError] = useState<ImageUploadErrorCode | null>(null);
  const [uploading, setUploading] = useState(false);

  const clearError = useCallback(() => setError(null), []);

  const removeImage = useCallback((storageKey: string) => {
    setImages((prev) => prev.filter((img) => img.storage_key !== storageKey));
  }, []);

  const clearImages = useCallback(() => setImages([]), []);

  const uploadImage = useCallback(
    async (file: File): Promise<ImageRef | null> => {
      setError(null);
      if (!enabled) return null;
      if (images.length >= maxImages) {
        setError("max_reached");
        return null;
      }
      if (!ALLOWED_TYPES.has(file.type)) {
        setError("format_unsupported");
        return null;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        setError("too_large");
        return null;
      }

      setUploading(true);
      try {
        const result = await studentQuestionImagesApi.upload(
          token ?? "cookie-session",
          file,
          images.length
        );
        const thumbnailDataUrl = await readAsDataUrl(file).catch(() => "");
        const ref: ImageRef = {
          storage_key: result.storage_key,
          mime_type: result.mime_type,
          size_bytes: result.size_bytes,
          thumbnail_data_url: thumbnailDataUrl,
        };
        setImages((prev) => [...prev, ref]);
        onAttached?.(images.length + 1);
        return ref;
      } catch {
        setError("upload_failed");
        return null;
      } finally {
        setUploading(false);
      }
    },
    [enabled, images.length, maxImages, onAttached, token]
  );

  return {
    images,
    error,
    uploading,
    uploadImage,
    removeImage,
    clearImages,
    clearError,
    maxImages,
  };
}
