"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

interface TosModalProps {
  tos: { id: string; version: number; content: string };
  onAccept: () => Promise<void>;
  onDecline: () => void;
}

export function TosModal({ tos, onAccept, onDecline }: TosModalProps) {
  const t = useTranslations("auth.tos_modal");
  const [scrolledToEnd, setScrolledToEnd] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const checkScrollEnd = useCallback(() => {
    const el = contentRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    if (nearBottom) setScrolledToEnd(true);
  }, []);

  useLayoutEffect(() => {
    checkScrollEnd();
  }, [tos.content, checkScrollEnd]);

  function handleScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    if (nearBottom) setScrolledToEnd(true);
  }

  async function handleAccept() {
    setAccepting(true);
    try {
      await onAccept();
    } catch {
      setAccepting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tos-modal-title"
    >
      <div className="w-full max-w-2xl bg-white rounded-xl shadow-2xl flex flex-col max-h-[90vh] min-h-0">
        {/* Header */}
        <div className="p-6 border-b border-gray-100">
          <h2 id="tos-modal-title" className="text-xl font-semibold text-gray-900">
            {t("title")}
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            {t("version", { version: tos.version })}
          </p>
        </div>

        {/* Scrollable content */}
        <div
          ref={contentRef}
          onScroll={handleScroll}
          className="flex-1 min-h-48 max-h-[50vh] overflow-y-auto overscroll-contain p-6 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap"
          tabIndex={0}
          aria-label={t("content_label")}
        >
          {tos.content.trim() ? (
            tos.content
          ) : (
            <p className="text-gray-400 italic">{t("empty_content")}</p>
          )}
        </div>

        {!scrolledToEnd && (
          <p className="px-6 py-2 text-xs text-gray-400 text-center border-t border-gray-100">
            {t("scroll_hint")}
          </p>
        )}

        {/* Actions */}
        <div className="p-6 border-t border-gray-100 flex flex-col-reverse sm:flex-row gap-3 justify-end">
          <Button
            variant="outline"
            size="md"
            onClick={onDecline}
            disabled={accepting}
          >
            {t("decline")}
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={handleAccept}
            disabled={!scrolledToEnd}
            loading={accepting}
            aria-disabled={!scrolledToEnd}
          >
            {t("accept")}
          </Button>
        </div>
      </div>
    </div>
  );
}
