"use client";

/**
 * Self-study material upload — 4 tabs (PDF / camera / gallery / typed) + post-upload
 * Instant Answer vs Add to Study Library (T-212 / Flow 8 §3.3).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { HybridInputWidget, type SubmitPayload } from "@/components/shared/HybridInputWidget";
import { Button } from "@/components/ui/button";
import { selfStudyApi, type SelfStudyMaterialUploadResult } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

type Tab = "pdf" | "camera" | "gallery" | "typed";
type Disposition = "instant_answer" | "add_to_library";

const TABS: Tab[] = ["pdf", "camera", "gallery", "typed"];

export function MaterialUploadPanel() {
  const t = useTranslations("self_study.materials");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [tab, setTab] = useState<Tab>("pdf");
  const [disposition, setDisposition] = useState<Disposition>("add_to_library");
  const [result, setResult] = useState<SelfStudyMaterialUploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const {
    data: library,
    isLoading: libraryLoading,
    isError: libraryError,
  } = useQuery({
    queryKey: ["self-study", "materials"],
    queryFn: () => selfStudyApi.listMaterials(token!),
    enabled: mounted && !!token,
  });

  const uploadMutation = useMutation({
    mutationFn: (args: {
      file: Blob;
      filename: string;
      source_type: "pdf" | "camera" | "gallery";
    }) =>
      selfStudyApi.uploadMaterial(token!, {
        ...args,
        disposition,
        title: args.filename,
      }),
    onSuccess: (data) => {
      setResult(data);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["self-study", "materials"] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error"));
    },
  });

  const typedMutation = useMutation({
    mutationFn: (text: string) =>
      selfStudyApi.typedMaterial(token!, {
        text,
        title: t("typed_title"),
        disposition,
      }),
    onSuccess: (data) => {
      setResult(data);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["self-study", "materials"] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error"));
    },
  });

  const categoriseMutation = useMutation({
    mutationFn: (args: {
      materialId: string;
      book_type: "prep_questions" | "reference_content";
    }) => selfStudyApi.categoriseMaterial(token!, args.materialId, args.book_type),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["self-study", "materials"] });
      void qc.invalidateQueries({ queryKey: ["self-study", "prep-gate"] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error"));
    },
  });

  const onFileChange = (source: "pdf" | "camera" | "gallery") => {
    const input = fileRef.current;
    if (!input?.files?.length) return;
    const file = input.files[0];
    uploadMutation.mutate({
      file,
      filename: file.name,
      source_type: source,
    });
    input.value = "";
  };

  const onTypedSubmit = async (payload: SubmitPayload): Promise<void> => {
    const text = payload.text.trim();
    if (!text) return;
    typedMutation.mutate(text);
  };

  const accept =
    tab === "pdf" ? "application/pdf" : "image/jpeg,image/png,image/webp";
  const capture = tab === "camera" ? "environment" : undefined;
  const busy = uploadMutation.isPending || typedMutation.isPending;

  return (
    <section
      className="rounded-lg border border-gray-200 bg-white p-4 space-y-4"
      data-testid="self-study-materials"
      aria-label={t("title")}
    >
      <div>
        <h3 className="text-lg font-medium text-gray-900">{t("title")}</h3>
        <p className="text-xs text-gray-500">{t("help")}</p>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label={t("tabs_label")}>
        {TABS.map((id) => (
          <Button
            key={id}
            type="button"
            size="sm"
            variant={tab === id ? "primary" : "outline"}
            onClick={() => setTab(id)}
            data-testid={`material-tab-${id}`}
          >
            {t(`tab_${id}`)}
          </Button>
        ))}
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-gray-800">{t("disposition_label")}</legend>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="radio"
            name="disposition"
            checked={disposition === "instant_answer"}
            onChange={() => setDisposition("instant_answer")}
            data-testid="disposition-instant"
          />
          {t("disposition_instant")}
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="radio"
            name="disposition"
            checked={disposition === "add_to_library"}
            onChange={() => setDisposition("add_to_library")}
            data-testid="disposition-library"
          />
          {t("disposition_library")}
        </label>
      </fieldset>

      {tab === "typed" ? (
        <HybridInputWidget
          onSubmit={onTypedSubmit}
          disabled={busy}
          placeholder={t("typed_placeholder")}
        />
      ) : (
        <div className="space-y-2">
          <input
            ref={fileRef}
            type="file"
            accept={accept}
            capture={capture}
            className="block w-full text-sm text-gray-700"
            data-testid={`material-file-${tab}`}
            onChange={() => onFileChange(tab)}
            disabled={busy}
          />
          <p className="text-xs text-gray-500">{t(`hint_${tab}`)}</p>
        </div>
      )}

      {busy && <p className="text-sm text-gray-500">{t("uploading")}</p>}
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div
          className="rounded border border-gray-100 bg-gray-50 p-3 space-y-2"
          data-testid="material-upload-result"
        >
          {result.disposition === "instant_answer" && result.instant_answer_text && (
            <p className="text-sm text-gray-800 whitespace-pre-wrap">
              {result.instant_answer_text}
            </p>
          )}
          {result.disposition === "add_to_library" && result.material && (
            <p className="text-sm text-gray-800" data-testid="material-library-saved">
              {t("saved", { title: result.material.title })}
            </p>
          )}
        </div>
      )}

      <div className="space-y-2" data-testid="material-library-list">
        <h4 className="text-sm font-medium text-gray-900">{t("library_title")}</h4>
        {libraryLoading && <p className="text-sm text-gray-500">{t("library_loading")}</p>}
        {libraryError && (
          <p className="text-sm text-red-600" role="alert">
            {t("library_error")}
          </p>
        )}
        {library && library.items.length === 0 && (
          <p className="text-sm text-gray-600" data-testid="material-library-empty">
            {t("library_empty")}
          </p>
        )}
        {library && library.items.length > 0 && (
          <ul className="space-y-2">
            {library.items.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center gap-2 text-sm text-gray-800"
                data-testid="material-library-item"
              >
                <span>
                  {item.title}{" "}
                  <span className="text-xs text-gray-500">({item.source_type})</span>
                </span>
                <select
                  className="rounded border border-gray-300 bg-white px-2 py-1 text-xs"
                  aria-label={t("categorise_label")}
                  data-testid={`material-categorise-${item.id}`}
                  value={item.book_type ?? ""}
                  disabled={categoriseMutation.isPending}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value !== "prep_questions" && value !== "reference_content") return;
                    categoriseMutation.mutate({ materialId: item.id, book_type: value });
                  }}
                >
                  <option value="">{t("categorise_unset")}</option>
                  <option value="prep_questions">{t("categorise_prep")}</option>
                  <option value="reference_content">{t("categorise_reference")}</option>
                </select>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
