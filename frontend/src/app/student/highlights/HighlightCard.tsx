"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { ExternalLink, RotateCcw, Trash2 } from "lucide-react";
import {
  ApiError,
  studentHighlightsApi,
  type FlashcardBackUpdate,
  type MyHighlightRead,
} from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const backSchema = z.object({
  back_text: z.string().trim().min(1).max(8000),
});

type Props = { item: MyHighlightRead };

export function lecturePositionHref(item: MyHighlightRead): string {
  return `/student/lectures/${item.lecture.id}?highlight=${encodeURIComponent(item.id)}`;
}

export function HighlightCard({ item }: Props) {
  const t = useTranslations("student.highlights");
  const format = useFormatter();
  const { token } = useClientAuth();
  const queryClient = useQueryClient();
  const [showBack, setShowBack] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const card = item.flashcard;

  const form = useForm<FlashcardBackUpdate>({
    resolver: zodResolver(backSchema),
    defaultValues: { back_text: card?.back_text ?? "" },
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["student", "my-highlights"] });

  const errorMessage = (err: unknown) =>
    err instanceof ApiError ? err.message : t("action_error");

  const saveMutation = useMutation({
    mutationFn: (body: FlashcardBackUpdate) =>
      studentHighlightsApi.updateFlashcardBack(token!, card!.id, body),
    onSuccess: () => {
      setEditing(false);
      setMutationError(null);
      void invalidate();
    },
    onError: (err) => setMutationError(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: () => studentHighlightsApi.deleteHighlight(token!, item.id),
    onSuccess: () => {
      setMutationError(null);
      void invalidate();
    },
    onError: (err) => setMutationError(errorMessage(err)),
  });

  const backId = `flashcard-back-${item.id}`;

  return (
    <article
      className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
      data-testid="my-highlight"
      data-highlight-id={item.id}
      dir="auto"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-base text-gray-900">
          <mark className="rounded-sm bg-yellow-200 px-0.5 text-gray-900">
            {item.highlighted_text}
          </mark>
        </p>
        <time className="text-xs text-gray-500" dateTime={item.created_at}>
          {format.dateTime(new Date(item.created_at), { dateStyle: "medium" })}
        </time>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-gray-700" data-testid="my-highlight-lecture">
          {t("lecture_label", { title: item.lecture.title })}
        </span>
        {item.concept_tag ? (
          <Badge variant="secondary" data-testid="my-highlight-concept">
            {t("concept_label", { concept: item.concept_tag })}
          </Badge>
        ) : null}
        <a
          href={lecturePositionHref(item)}
          className="inline-flex min-h-11 items-center gap-1 text-blue-700 hover:underline"
          data-testid="my-highlight-open"
        >
          <ExternalLink className="size-4" aria-hidden="true" />
          {t("open_in_lecture")}
        </a>
      </div>

      {card ? (
        <section
          className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3"
          aria-label={t("flashcard_label")}
          data-testid="my-highlight-flashcard"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-amber-900">
              {showBack ? t("flashcard_back") : t("flashcard_front")}
            </p>
            <Button
              variant="ghost"
              size="sm"
              aria-pressed={showBack}
              aria-controls={backId}
              onClick={() => setShowBack((v) => !v)}
              data-testid="flashcard-flip"
            >
              <RotateCcw className="size-4 me-1" aria-hidden="true" />
              {showBack ? t("show_front") : t("show_back")}
            </Button>
          </div>
          <div id={backId} aria-live="polite" className="text-sm text-gray-900">
            {!showBack ? (
              <p data-testid="flashcard-front">{card.front_text}</p>
            ) : card.back_is_placeholder && !editing ? (
              <p className="text-gray-600" data-testid="flashcard-placeholder">
                {t("placeholder_back")}
              </p>
            ) : !editing ? (
              <p className="whitespace-pre-wrap" data-testid="flashcard-back">
                {card.back_text}
              </p>
            ) : null}
          </div>

          {showBack && editing ? (
            <form
              className="space-y-2"
              onSubmit={form.handleSubmit((values) =>
                saveMutation.mutate(values),
              )}
              data-testid="flashcard-edit-form"
            >
              <Label htmlFor={`back-${item.id}`} required>
                {t("edit_back_label")}
              </Label>
              <Textarea
                id={`back-${item.id}`}
                rows={3}
                {...form.register("back_text")}
              />
              {form.formState.errors.back_text ? (
                <p className="text-sm text-red-600" role="alert">
                  {t("edit_back_required")}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="submit"
                  size="md"
                  disabled={saveMutation.isPending}
                >
                  {saveMutation.isPending ? t("saving") : t("save")}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="md"
                  onClick={() => setEditing(false)}
                >
                  {t("cancel")}
                </Button>
              </div>
            </form>
          ) : showBack ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                form.reset({ back_text: card.back_text });
                setEditing(true);
              }}
              data-testid="flashcard-edit"
            >
              {card.back_is_placeholder ? t("add_back") : t("edit_back")}
            </Button>
          ) : null}
        </section>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-2">
        {confirmDelete ? (
          <>
            <span className="text-sm text-gray-700">{t("delete_confirm")}</span>
            <Button
              variant="destructive"
              size="md"
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
              data-testid="my-highlight-delete-confirm"
            >
              {t("delete_yes")}
            </Button>
            <Button
              variant="ghost"
              size="md"
              onClick={() => setConfirmDelete(false)}
            >
              {t("cancel")}
            </Button>
          </>
        ) : (
          <Button
            variant="ghost"
            size="md"
            onClick={() => setConfirmDelete(true)}
            data-testid="my-highlight-delete"
          >
            <Trash2 className="size-4 me-1" aria-hidden="true" />
            {t("delete")}
          </Button>
        )}
      </div>
      {mutationError ? (
        <p className="text-sm text-red-600" role="alert">
          {mutationError}
        </p>
      ) : null}
    </article>
  );
}
