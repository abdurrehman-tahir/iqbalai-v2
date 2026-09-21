"use client";

import { ImageIcon, XIcon } from "lucide-react";

import type { ImageRef } from "./types";

type Props = {
  image: ImageRef;
  onRemove: (storageKey: string) => void;
  removeLabel: string;
  disabled?: boolean;
};

/** Thumbnail chip with X-to-remove (M-13 image attach). */
export function ImageAttachmentChip({ image, onRemove, removeLabel, disabled }: Props) {
  return (
    <div
      className="relative inline-flex size-16 overflow-hidden rounded-md border border-gray-200 bg-gray-50"
      data-testid="hybrid-image-chip"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- data-URL thumbnails */}
      <img
        src={image.thumbnail_data_url}
        alt=""
        className="size-full object-cover"
      />
      <button
        type="button"
        className="absolute end-0.5 top-0.5 rounded-full bg-black/60 p-0.5 text-white hover:bg-black/80 disabled:opacity-50"
        aria-label={removeLabel}
        disabled={disabled}
        onClick={() => onRemove(image.storage_key)}
      >
        <XIcon className="size-3" aria-hidden="true" />
      </button>
      <ImageIcon className="sr-only" aria-hidden="true" />
    </div>
  );
}
