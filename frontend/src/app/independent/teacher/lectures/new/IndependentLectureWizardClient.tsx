"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Mic, Square } from "lucide-react";
import { independentLectureWizardApi, ApiError } from "@/lib/api";
import type { TeachingMode } from "@/lib/api/types";
import { useClientAuth } from "@/hooks/use-client-auth";
import { useIndependentLectureVoiceSession } from "@/lib/ws/independent-lecture-voice-socket";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Independent teacher lecture wizard (T-125) — the stripped variant of the
 * school wizard: no Grade-Subject offering, no curriculum step, no auto-quiz.
 * A single form (topic + own private references + teaching mode) replaces
 * the school wizard's 5 steps, since 2 of those steps (offering selection,
 * curriculum selection) have no equivalent here at all.
 */
export function IndependentLectureWizardClient() {
  const t = useTranslations("independent.teacher.lectures.wizard");
  const { mounted, token } = useClientAuth();
  const qc = useQueryClient();

  const [topic, setTopic] = useState("");
  const [selectedReferenceIds, setSelectedReferenceIds] = useState<Set<string>>(new Set());
  const [teachingMode, setTeachingMode] = useState<TeachingMode>("auto");
  const [lectureId, setLectureId] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const draftQuery = useQuery({
    queryKey: ["independent-teacher", "lecture-draft"],
    queryFn: () => independentLectureWizardApi.getDraft(token!),
    enabled: mounted && !!token,
  });

  const referencesQuery = useQuery({
    queryKey: ["independent-teacher", "lecture-references"],
    queryFn: () => independentLectureWizardApi.listReferences(token!),
    enabled: mounted && !!token,
  });

  const saveMutation = useMutation({
    mutationFn: (data: { topic: string; reference_content_ids: string[]; teaching_mode: string }) =>
      independentLectureWizardApi.upsertDraft(token!, { step: 1, data }),
  });

  // Resume from the saved draft once, on first load.
  useEffect(() => {
    if (hydrated || !draftQuery.data) return;
    const data = draftQuery.data.data as {
      topic?: string;
      reference_content_ids?: string[];
      teaching_mode?: TeachingMode;
      lecture_id?: string;
    };
    if (data.topic) setTopic(data.topic);
    if (data.reference_content_ids) setSelectedReferenceIds(new Set(data.reference_content_ids));
    if (data.teaching_mode) setTeachingMode(data.teaching_mode);
    if (data.lecture_id) setLectureId(data.lecture_id);
    setHydrated(true);
  }, [hydrated, draftQuery.data]);

  function persist(overrides: Partial<{ topic: string; referenceIds: Set<string>; mode: TeachingMode }>) {
    const nextTopic = overrides.topic ?? topic;
    const nextRefs = overrides.referenceIds ?? selectedReferenceIds;
    const nextMode = overrides.mode ?? teachingMode;
    saveMutation.mutate({
      topic: nextTopic,
      reference_content_ids: Array.from(nextRefs),
      teaching_mode: nextMode,
    });
  }

  const generateMutation = useMutation({
    mutationFn: () =>
      independentLectureWizardApi.generate(token!, {
        topic,
        reference_content_ids: Array.from(selectedReferenceIds),
        teaching_mode: teachingMode,
      }),
    onSuccess: (result) => {
      setGenerateError(null);
      setLectureId(result.lecture_id);
      persist({});
      void qc.invalidateQueries({ queryKey: ["independent-teacher", "lecture-status"] });
    },
    onError: (err: unknown) => {
      setGenerateError(err instanceof ApiError ? err.message : t("generate_error"));
    },
  });

  if (!mounted || draftQuery.isLoading || referencesQuery.isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (referencesQuery.isError) {
    return (
      <ErrorState
        title={t("references_error")}
        description={t("references_error")}
        onRetry={() => void referencesQuery.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  if (lectureId) {
    return <GeneratingOrCompletePanel token={token!} lectureId={lectureId} t={t} />;
  }

  const references = referencesQuery.data ?? [];

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="text-sm text-gray-600">{t("subtitle")}</p>
      </header>

      <div className="space-y-2">
        <Label htmlFor="topic">{t("topic_label")}</Label>
        <Input
          id="topic"
          value={topic}
          placeholder={t("topic_placeholder")}
          onChange={(e) => {
            setTopic(e.target.value);
            persist({ topic: e.target.value });
          }}
        />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-gray-700">{t("references_label")}</legend>
        {references.length === 0 ? (
          <p className="text-sm text-gray-600" role="status">
            {t("references_empty")}
          </p>
        ) : (
          <ul className="space-y-2">
            {references.map((ref) => (
              <li key={ref.id}>
                <label className="flex items-center gap-2 text-sm text-gray-800">
                  <input
                    type="checkbox"
                    className="size-4 rounded border-gray-300"
                    checked={selectedReferenceIds.has(ref.id)}
                    onChange={(e) => {
                      const next = new Set(selectedReferenceIds);
                      if (e.target.checked) next.add(ref.id);
                      else next.delete(ref.id);
                      setSelectedReferenceIds(next);
                      persist({ referenceIds: next });
                    }}
                  />
                  {ref.title}
                </label>
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      <div className="space-y-2">
        <Label htmlFor="teaching-mode">{t("teaching_mode_label")}</Label>
        <select
          id="teaching-mode"
          className="flex h-11 w-full rounded-md border border-gray-300 bg-white px-3 text-sm"
          value={teachingMode}
          onChange={(e) => {
            const mode = e.target.value as TeachingMode;
            setTeachingMode(mode);
            persist({ mode });
          }}
        >
          <option value="auto">{t("teaching_mode_auto")}</option>
          <option value="manual">{t("teaching_mode_manual")}</option>
          <option value="voice_assisted">{t("teaching_mode_voice_assisted")}</option>
        </select>
      </div>

      {generateError ? (
        <p className="text-sm text-red-700" role="alert">
          {generateError}
        </p>
      ) : null}

      <Button
        type="button"
        disabled={!topic.trim() || generateMutation.isPending}
        onClick={() => generateMutation.mutate()}
      >
        {t("generate")}
      </Button>
    </div>
  );
}

/** Polls lecture status until generation completes — no live WS stream in this variant. */
function GeneratingOrCompletePanel({
  token,
  lectureId,
  t,
}: {
  token: string;
  lectureId: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const statusQuery = useQuery({
    queryKey: ["independent-teacher", "lecture-status", lectureId],
    queryFn: () => independentLectureWizardApi.getLecture(token, lectureId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "ready_for_edit" || status === "failed" || status === "timed_out"
        ? false
        : 3000;
    },
  });

  if (statusQuery.isLoading) {
    return (
      <section className="mx-auto max-w-2xl space-y-3" aria-busy="true">
        <h3 className="text-lg font-medium text-gray-900">{t("generating_title")}</h3>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full" />
      </section>
    );
  }

  if (statusQuery.isError) {
    return (
      <ErrorState
        title={t("generating_error_title")}
        description={t("generating_error_body")}
        onRetry={() => void statusQuery.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  const status = statusQuery.data!.status;

  if (status === "failed") {
    return (
      <ErrorState
        title={t("generating_error_title")}
        description={t("generating_error_body")}
        onRetry={() => void statusQuery.refetch()}
        retryLabel={t("retry")}
      />
    );
  }
  if (status === "timed_out") {
    return (
      <ErrorState
        title={t("generating_error_title")}
        description={t("generating_error_timeout")}
        onRetry={() => void statusQuery.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  if (status !== "ready_for_edit") {
    return (
      <section className="mx-auto max-w-2xl space-y-3" aria-busy="true">
        <h3 className="text-lg font-medium text-gray-900">{t("generating_title")}</h3>
        <p className="text-sm text-gray-600" role="status" aria-live="polite">
          {t("generating_body")}
        </p>
        <Skeleton className="h-40 w-full" />
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-2xl space-y-3">
      <div role="status">
        <h3 className="text-lg font-medium text-gray-900">{t("complete_title")}</h3>
        <p className="text-sm text-gray-700">{t("complete_body")}</p>
      </div>
      <ParagraphsView token={token} lectureId={lectureId} t={t} />
      <VoicePanel lectureId={lectureId} t={t} />
    </section>
  );
}

function ParagraphsView({
  token,
  lectureId,
  t,
}: {
  token: string;
  lectureId: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const query = useQuery({
    queryKey: ["independent-teacher", "lecture-paragraphs", lectureId],
    queryFn: () => independentLectureWizardApi.getParagraphs(token, lectureId),
  });

  if (query.isLoading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        title={t("paragraphs_error")}
        description={t("paragraphs_error")}
        onRetry={() => void query.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  if (!query.data?.length) {
    return (
      <p className="text-sm text-gray-600" role="status">
        {t("paragraphs_empty")}
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {query.data.map((paragraph) => (
        <li key={paragraph.ordinal} className="space-y-1 rounded-md border border-gray-200 p-3">
          <SourceBadge tier={paragraph.tier} bookName={paragraph.book_name} t={t} />
          <p dir="auto" className="text-sm text-gray-800">
            {paragraph.text}
          </p>
        </li>
      ))}
    </ul>
  );
}

function SourceBadge({
  tier,
  bookName,
  t,
}: {
  tier: string;
  bookName: string | null | undefined;
  t: ReturnType<typeof useTranslations>;
}) {
  switch (tier) {
    case "reference":
      return (
        <span className="inline-block rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-800">
          {t("badge_reference", { book: bookName ?? "" })}
        </span>
      );
    case "web":
      return (
        <span className="inline-block rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
          {t("badge_web")}
        </span>
      );
    default:
      return (
        <span className="inline-block rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-800">
          {t("badge_ai_knowledge")}
        </span>
      );
  }
}

const VOICE_LANGUAGE = "en";

function VoicePanel({
  lectureId,
  t,
}: {
  lectureId: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const voice = useIndependentLectureVoiceSession(lectureId, VOICE_LANGUAGE);

  if (voice.status === "idle") {
    return (
      <div className="border-t border-gray-100 pt-4">
        <Button type="button" variant="outline" className="gap-2" onClick={voice.startSession}>
          <Mic className="size-4" aria-hidden="true" />
          {t("voice_start_button")}
        </Button>
      </div>
    );
  }

  if (voice.status === "error") {
    return (
      <ErrorState title={t("voice_error_title")} description={t("voice_error_body")} />
    );
  }

  const isBusy = voice.status === "recording" || voice.status === "processing";

  return (
    <section
      className="space-y-3 border-t border-gray-100 pt-4"
      aria-labelledby="independent-voice-panel-heading"
    >
      <h3 id="independent-voice-panel-heading" className="text-lg font-medium text-gray-900">
        {t("voice_panel_title")}
      </h3>

      <p className="text-sm text-gray-600" role="status" aria-live="polite">
        {voice.status === "connecting" && t("voice_connecting")}
        {voice.status === "ready" && t("voice_ready")}
        {voice.status === "recording" && t("voice_recording")}
        {voice.status === "processing" && t("voice_processing")}
        {voice.status === "ended" && t("voice_session_ended")}
      </p>

      {voice.unavailableNotice ? (
        <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-800">
          {t("voice_tts_unavailable")}
        </p>
      ) : null}

      {voice.turns.length > 0 ? (
        <ul aria-label={t("voice_transcript_label")} className="space-y-2">
          {voice.turns.map((turn, i) => (
            <li key={i} dir="auto" className="rounded-md bg-gray-50 p-2 text-sm">
              <p className="font-medium text-gray-800">{turn.transcript}</p>
              <p className="text-gray-700">{turn.confirmation}</p>
              {turn.hadDraftEdit ? (
                <p className="text-xs text-brand-700">{t("voice_draft_updated")}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {voice.status !== "ended" ? (
        <div className="flex gap-2">
          {voice.status === "ready" ? (
            <Button type="button" onClick={() => void voice.startRecording()} disabled={isBusy}>
              <Mic className="size-4" aria-hidden="true" />
              {t("voice_start_recording")}
            </Button>
          ) : null}
          {voice.status === "recording" ? (
            <Button type="button" variant="destructive" onClick={voice.stopRecording}>
              <Square className="size-4" aria-hidden="true" />
              {t("voice_stop_recording")}
            </Button>
          ) : null}
          <Button type="button" variant="outline" onClick={voice.endSession}>
            {t("voice_end_session")}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
