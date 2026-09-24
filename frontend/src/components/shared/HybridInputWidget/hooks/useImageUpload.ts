"use client";

/**
 * Client-side image upload hook (M-13 extension point).
 * M-12: stubbed — validates locally then rejects with a clear error until
 * the student_question_image upload profile lands in M-13.
 */

import { useCallback, useState } from "react";

import type { ImageRef } from "../types";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export type ImageUploadErrorCode =
  | "too_large"
  | "format_unsupported"
  | "max_reached"
  | "not_implemented";

export type UseImageUploadOptions = {
  maxImages?: number;
  enabled?: boolean;
  onAttached?: (count: number) => void;
};

export function useImageUpload(options: UseImageUploadOptions = {}) {
  const { maxImages = 3, enabled = false, onAttached } = options;
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
      if (!enabled) {
        setError("not_implemented");
        return null;
      }
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

      // M-13: POST /api/v1/uploads with student_question_image profile.
      setUploading(true);
      try {
        setError("not_implemented");
        return null;
      } finally {
        setUploading(false);
        onAttached?.(images.length);
      }
    },
    [enabled, images.length, maxImages, onAttached]
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
