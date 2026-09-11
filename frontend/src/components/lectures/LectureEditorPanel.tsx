"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { useTranslations } from "next-intl";
import { useEditor, EditorContent, type JSONContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Image from "@tiptap/extension-image";
import {
  Bold,
  Italic,
  Heading2,
  List,
  ListOrdered,
  Mic,
  Square,
  ImagePlus,
  Check,
  X,
} from "lucide-react";
import { ApiError } from "@/lib/api";
import type {
  DiagramSuggestionAccept,
  DiagramSuggestionsRead,
  LectureImageUploadRead,
  LectureVersionRead,
  LectureVersionSaveRequest,
  VoiceTranscribeRead,
} from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";

const AUTOSAVE_DEBOUNCE_MS = 3000;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/gif"]);

const VOICE_LANGUAGES = ["auto", "en", "ur", "sd", "ps"] as const;
type VoiceLanguage = (typeof VOICE_LANGUAGES)[number];

/** Splits a plain-text body (M-09 v1's "\n\n"-joined paragraphs) into a TipTap
 * doc — used only to seed the editor the first time a lecture is opened for
 * editing (versions saved via T-130 already carry content_jsonb).
 */
function bodyToInitialDoc(body: string): JSONContent {
  const paragraphs = body
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);
  if (paragraphs.length === 0) {
    return { type: "doc", content: [{ type: "paragraph" }] };
  }
  return {
    type: "doc",
    content: paragraphs.map((text) => ({
      type: "paragraph",
      content: [{ type: "text", text }],
    })),
  };
}

interface ToolbarButtonProps {
  label: string;
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function ToolbarButton({ label, active, onClick, children }: ToolbarButtonProps) {
  return (
    <Button
      type="button"
      variant={active ? "secondary" : "ghost"}
      size="icon"
      className="size-10"
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

export interface LectureEditorApi {
  getCurrentVersion: (token: string, lectureId: string) => Promise<LectureVersionRead>;
  saveVersion: (
    token: string,
    lectureId: string,
    data: LectureVersionSaveRequest
  ) => Promise<LectureVersionRead>;
  transcribeVoice: (
    token: string,
    lectureId: string,
    audio: Blob,
    language?: string
  ) => Promise<VoiceTranscribeRead>;
  uploadImage: (
    token: string,
    lectureId: string,
    image: File | Blob
  ) => Promise<LectureImageUploadRead>;
  /** Undefined for the independent tenant — no AI diagram suggestion there
   * (T-132: independent teachers' personal reference content has no
   * page-chunked structure to draw suggestions from). */
  getDiagramSuggestions?: (token: string, lectureId: string) => Promise<DiagramSuggestionsRead>;
  acceptDiagramSuggestion?: (
    token: string,
    lectureId: string,
    data: DiagramSuggestionAccept
  ) => Promise<LectureImageUploadRead>;
}

/** TipTap editor + immutable-version save/autosave (T-130). Shared between the
 * school and independent lecture wizards — only the `api` client and query-key
 * prefix differ per tenant (§3.16: no cross-tenant coupling in the component
 * itself, just which endpoint it calls).
 */
export function LectureEditorPanel({
  token,
  lectureId,
  api,
  t,
  queryKeyPrefix,
}: {
  token: string;
  lectureId: string;
  api: LectureEditorApi;
  t: ReturnType<typeof useTranslations>;
  queryKeyPrefix: "teacher" | "independent-teacher";
}) {
  const qc = useQueryClient();
  const [saveError, setSaveError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);
  const [voiceLanguage, setVoiceLanguage] = useState<VoiceLanguage>("auto");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [dismissedSuggestionKeys, setDismissedSuggestionKeys] = useState<Set<string>>(new Set());
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initializedRef = useRef(false);
  const usedVoiceEditRef = useRef(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const queryKey = [queryKeyPrefix, "lecture-version-current", lectureId];

  const versionQuery = useQuery({
    queryKey,
    queryFn: () => api.getCurrentVersion(token, lectureId),
  });

  const diagramSuggestionsQuery = useQuery({
    queryKey: [queryKeyPrefix, "diagram-suggestions", lectureId],
    queryFn: () => api.getDiagramSuggestions!(token, lectureId),
    enabled: !!api.getDiagramSuggestions,
  });

  const saveMutation = useMutation({
    mutationFn: (vars: { contentJsonb: JSONContent; isAutosave: boolean }) =>
      api.saveVersion(token, lectureId, {
        content_jsonb: vars.contentJsonb,
        is_autosave: vars.isAutosave,
        used_voice_edit: usedVoiceEditRef.current,
      }),
    onSuccess: (result) => {
      setSaveError(null);
      setJustSaved(true);
      usedVoiceEditRef.current = false;
      qc.setQueryData(queryKey, result);
    },
    onError: (err: unknown) => {
      setSaveError(err instanceof ApiError ? err.message : t("editor_save_error"));
    },
  });

  const editor = useEditor(
    {
      extensions: [
        StarterKit,
        Placeholder.configure({ placeholder: t("editor_placeholder") }),
        Image,
      ],
      immediatelyRender: false,
      editorProps: {
        attributes: {
          class: "prose prose-sm max-w-none focus:outline-none min-h-48",
        },
      },
      onUpdate: ({ editor: current }) => {
        setJustSaved(false);
        if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
        // Debounced auto-save — never fires per keystroke (T-130 acceptance #3).
        autosaveTimer.current = setTimeout(() => {
          saveMutation.mutate({ contentJsonb: current.getJSON(), isAutosave: true });
        }, AUTOSAVE_DEBOUNCE_MS);
      },
    },
    []
  );

  // Seed the editor exactly once, the first time the current version loads —
  // never again, so an autosave-triggered refetch can't stomp on in-progress
  // typing.
  useEffect(() => {
    if (!editor || initializedRef.current || !versionQuery.data) return;
    const doc = versionQuery.data.content_jsonb ?? bodyToInitialDoc(versionQuery.data.body);
    editor.commands.setContent(doc as JSONContent);
    initializedRef.current = true;
  }, [editor, versionQuery.data]);

  useEffect(() => {
    return () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    };
  }, []);

  const handleManualSave = useCallback(() => {
    if (!editor) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    saveMutation.mutate({ contentJsonb: editor.getJSON(), isAutosave: false });
  }, [editor, saveMutation]);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const handleStartRecording = useCallback(async () => {
    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      recorder.onstop = () => {
        stopStream();
        const blob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        audioChunksRef.current = [];
        setIsTranscribing(true);
        api
          .transcribeVoice(
            token,
            lectureId,
            blob,
            voiceLanguage === "auto" ? undefined : voiceLanguage
          )
          .then((result) => {
            if (editor && result.transcript) {
              // TipTap's insertContent replaces the current selection when one
              // exists, or inserts at the cursor otherwise — acceptance #1/#2
              // need no separate insert-vs-replace branching.
              editor.chain().focus().insertContent(result.transcript).run();
              usedVoiceEditRef.current = true;
              setJustSaved(false);
            }
          })
          .catch((err: unknown) => {
            setVoiceError(err instanceof ApiError ? err.message : t("editor_voice_error"));
          })
          .finally(() => setIsTranscribing(false));
      };

      recorder.start();
      setIsRecording(true);
    } catch {
      setVoiceError(t("editor_voice_mic_error"));
    }
  }, [api, editor, lectureId, stopStream, t, token, voiceLanguage]);

  const handleStopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }, []);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop();
      stopStream();
    };
  }, [stopStream]);

  const insertImage = useCallback(
    (src: string) => {
      editor?.chain().focus().setImage({ src }).run();
      setJustSaved(false);
    },
    [editor]
  );

  const handleImageFile = useCallback(
    async (file: File) => {
      setImageError(null);
      if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
        setImageError(t("editor_image_type_error"));
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        setImageError(t("editor_image_size_error"));
        return;
      }
      setIsUploadingImage(true);
      try {
        const result = await api.uploadImage(token, lectureId, file);
        insertImage(result.image_url);
      } catch (err) {
        setImageError(err instanceof ApiError ? err.message : t("editor_image_upload_error"));
      } finally {
        setIsUploadingImage(false);
      }
    },
    [api, insertImage, lectureId, t, token]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDraggingOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleImageFile(file);
    },
    [handleImageFile]
  );

  const acceptSuggestionMutation = useMutation({
    mutationFn: (payload: DiagramSuggestionAccept) =>
      api.acceptDiagramSuggestion!(token, lectureId, payload),
    onSuccess: (result) => {
      insertImage(result.image_url);
    },
    onError: (err: unknown) => {
      setImageError(err instanceof ApiError ? err.message : t("editor_image_upload_error"));
    },
  });

  const suggestionKey = (s: { library_item_id: string; page_number: number }) =>
    `${s.library_item_id}:${s.page_number}`;
  const activeSuggestion = diagramSuggestionsQuery.data?.suggestions.find(
    (s) => !dismissedSuggestionKeys.has(suggestionKey(s))
  );

  if (versionQuery.isLoading) {
    return (
      <section className="space-y-2" aria-busy="true">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-64 w-full" />
      </section>
    );
  }

  if (versionQuery.isError) {
    return (
      <ErrorState
        title={t("editor_error")}
        description={t("editor_error")}
        onRetry={() => void versionQuery.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  return (
    <section className="space-y-3" aria-labelledby="lecture-editor-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="lecture-editor-heading" className="text-lg font-medium text-gray-900">
          {t("editor_title")}
        </h3>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500" role="status" aria-live="polite">
            {saveMutation.isPending ? t("editor_saving") : justSaved ? t("editor_saved") : null}
          </span>
          <Button
            type="button"
            onClick={handleManualSave}
            disabled={!editor || saveMutation.isPending}
          >
            {t("editor_save_button")}
          </Button>
        </div>
      </div>

      {saveError ? (
        <p className="text-sm text-red-600" role="alert">
          {saveError}
        </p>
      ) : null}

      <div className="rounded-md border border-gray-200">
        <div
          className="flex items-center gap-1 border-b border-gray-200 p-1"
          role="toolbar"
          aria-label={t("editor_toolbar_label")}
        >
          <ToolbarButton
            label={t("editor_toolbar_bold")}
            active={!!editor?.isActive("bold")}
            onClick={() => editor?.chain().focus().toggleBold().run()}
          >
            <Bold className="size-4" aria-hidden="true" />
          </ToolbarButton>
          <ToolbarButton
            label={t("editor_toolbar_italic")}
            active={!!editor?.isActive("italic")}
            onClick={() => editor?.chain().focus().toggleItalic().run()}
          >
            <Italic className="size-4" aria-hidden="true" />
          </ToolbarButton>
          <ToolbarButton
            label={t("editor_toolbar_heading")}
            active={!!editor?.isActive("heading", { level: 2 })}
            onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
          >
            <Heading2 className="size-4" aria-hidden="true" />
          </ToolbarButton>
          <ToolbarButton
            label={t("editor_toolbar_bullet_list")}
            active={!!editor?.isActive("bulletList")}
            onClick={() => editor?.chain().focus().toggleBulletList().run()}
          >
            <List className="size-4" aria-hidden="true" />
          </ToolbarButton>
          <ToolbarButton
            label={t("editor_toolbar_ordered_list")}
            active={!!editor?.isActive("orderedList")}
            onClick={() => editor?.chain().focus().toggleOrderedList().run()}
          >
            <ListOrdered className="size-4" aria-hidden="true" />
          </ToolbarButton>
          <ToolbarButton
            label={t("editor_image_insert")}
            active={false}
            onClick={() => imageInputRef.current?.click()}
          >
            <ImagePlus className="size-4" aria-hidden="true" />
          </ToolbarButton>
          <input
            ref={imageInputRef}
            type="file"
            accept="image/jpeg,image/png,image/gif"
            className="sr-only"
            aria-label={t("editor_image_insert")}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleImageFile(file);
              e.target.value = "";
            }}
          />

          <div className="ms-auto flex items-center gap-2">
            <label className="sr-only" htmlFor="voice-edit-language">
              {t("editor_voice_language_label")}
            </label>
            <select
              id="voice-edit-language"
              className="h-10 rounded-md border border-gray-300 bg-white px-2 text-sm"
              value={voiceLanguage}
              disabled={isRecording || isTranscribing}
              onChange={(e) => setVoiceLanguage(e.target.value as VoiceLanguage)}
            >
              {VOICE_LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {t(`editor_voice_language_${lang}`)}
                </option>
              ))}
            </select>
            <Button
              type="button"
              variant={isRecording ? "destructive" : "outline"}
              size="icon"
              className="size-10"
              aria-label={isRecording ? t("editor_voice_stop") : t("editor_voice_dictate")}
              disabled={isTranscribing}
              onClick={isRecording ? handleStopRecording : handleStartRecording}
            >
              {isRecording ? (
                <Square className="size-4" aria-hidden="true" />
              ) : (
                <Mic className="size-4" aria-hidden="true" />
              )}
            </Button>
          </div>
        </div>
        <div
          dir="auto"
          className={`p-3 ${isDraggingOver ? "bg-blue-50 outline-2 outline-dashed outline-blue-300" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDraggingOver(true);
          }}
          onDragLeave={() => setIsDraggingOver(false)}
          onDrop={handleDrop}
        >
          <EditorContent editor={editor} />
        </div>
      </div>

      <div className="text-sm text-gray-500" role="status" aria-live="polite">
        {isRecording
          ? t("editor_voice_recording")
          : isTranscribing
            ? t("editor_voice_transcribing")
            : isUploadingImage
              ? t("editor_image_uploading")
              : null}
      </div>
      {voiceError ? (
        <p className="text-sm text-red-600" role="alert">
          {voiceError}
        </p>
      ) : null}
      {imageError ? (
        <p className="text-sm text-red-600" role="alert">
          {imageError}
        </p>
      ) : null}

      {activeSuggestion ? (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 p-3"
          role="status"
        >
          <p className="text-sm text-amber-900">
            {t("editor_diagram_suggestion", {
              page: activeSuggestion.page_number,
              book: activeSuggestion.book_name,
            })}
          </p>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              disabled={acceptSuggestionMutation.isPending}
              onClick={() =>
                acceptSuggestionMutation.mutate({
                  library_item_id: activeSuggestion.library_item_id,
                  page_number: activeSuggestion.page_number,
                })
              }
            >
              <Check className="me-1 size-4" aria-hidden="true" />
              {t("editor_diagram_accept")}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                setDismissedSuggestionKeys((prev) =>
                  new Set(prev).add(suggestionKey(activeSuggestion))
                )
              }
            >
              <X className="me-1 size-4" aria-hidden="true" />
              {t("editor_diagram_decline")}
            </Button>
          </div>
        </div>
      ) : null}

      {versionQuery.data ? (
        <p className="text-xs text-gray-500">
          {t("editor_version_label", { version: versionQuery.data.version })}
        </p>
      ) : null}
    </section>
  );
}
