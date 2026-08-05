"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { lectureWizardApi, ApiError } from "@/lib/api";
import type {
  LectureDraftUpsert,
  LectureGenerateRequest,
  LectureParagraphRead,
  TeacherOfferingRead,
} from "@/lib/api/types";
import { useClientAuth } from "@/hooks/use-client-auth";
import { useLectureGenerationStream } from "@/lib/ws/lecture-generation-socket";
import { useLectureVoiceSession } from "@/lib/ws/lecture-voice-socket";
import { Mic, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";

type WizardData = {
  grade_subject_offering_id?: string;
  topic?: string;
  topic_source?: "tree" | "freeform";
  curriculum_id?: string;
  reference_book_ids?: string[];
  include_cross_grade?: boolean;
  teaching_mode?: "auto" | "manual" | "voice_assisted";
  lecture_id?: string;
};

export function LectureWizardClient() {
  const t = useTranslations("teacher.lectures.wizard");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [step, setStep] = useState(1);
  const [data, setData] = useState<WizardData>({});
  const [freeformTopic, setFreeformTopic] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const draftQuery = useQuery({
    queryKey: ["teacher", "lecture-draft"],
    queryFn: () => lectureWizardApi.getDraft(token!),
    enabled: mounted && !!token,
  });

  const offeringsQuery = useQuery({
    queryKey: ["teacher", "offerings"],
    queryFn: () => lectureWizardApi.listOfferings(token!),
    enabled: mounted && !!token,
  });

  const curriculaQuery = useQuery({
    queryKey: ["teacher", "wizard-curricula", data.grade_subject_offering_id],
    queryFn: () => lectureWizardApi.listCurricula(token!, data.grade_subject_offering_id!),
    enabled: mounted && !!token && !!data.grade_subject_offering_id && step >= 2,
  });

  const topicsQuery = useQuery({
    queryKey: ["teacher", "wizard-topics", data.curriculum_id, data.grade_subject_offering_id],
    queryFn: () =>
      lectureWizardApi.listTopics(
        token!,
        data.curriculum_id!,
        data.grade_subject_offering_id!
      ),
    enabled:
      mounted &&
      !!token &&
      !!data.curriculum_id &&
      !!data.grade_subject_offering_id &&
      step === 1,
  });

  useEffect(() => {
    if (!draftQuery.data || hydrated) return;
    const draft = draftQuery.data;
    setStep(draft.step >= 1 && draft.step <= 5 ? draft.step : 1);
    const raw = (draft.data ?? {}) as WizardData;
    setData(raw);
    if (raw.topic_source === "freeform" && raw.topic) {
      setFreeformTopic(raw.topic);
    }
    setHydrated(true);
  }, [draftQuery.data, hydrated]);

  // When curricula load on step 2 and no curriculum chosen, default to primary.
  useEffect(() => {
    if (step !== 2 || !curriculaQuery.data?.length || data.curriculum_id) return;
    const primary = curriculaQuery.data.find((c) => c.is_primary) ?? curriculaQuery.data[0];
    setData((prev) => ({ ...prev, curriculum_id: primary.id }));
  }, [step, curriculaQuery.data, data.curriculum_id]);

  const saveMutation = useMutation({
    mutationFn: (payload: LectureDraftUpsert) =>
      lectureWizardApi.upsertDraft(token ?? "", payload),
    onSuccess: async () => {
      setSaveError(null);
      await qc.invalidateQueries({ queryKey: ["teacher", "lecture-draft"] });
    },
    onError: (err: unknown) => {
      setSaveError(err instanceof ApiError ? err.message : t("save_error"));
    },
  });

  const persist = useCallback(
    (nextStep: number, nextData: WizardData) => {
      setStep(nextStep);
      setData(nextData);
      if (!token) return;
      saveMutation.mutate({ step: nextStep, data: nextData });
    },
    [saveMutation, token]
  );

  const offerings = useMemo(
    () => offeringsQuery.data ?? [],
    [offeringsQuery.data]
  );
  const selectedOffering: TeacherOfferingRead | undefined = useMemo(
    () => offerings.find((o) => o.id === data.grade_subject_offering_id),
    [offerings, data.grade_subject_offering_id]
  );

  const parseDegraded = topicsQuery.data?.parse_degraded === true;
  const topics = topicsQuery.data?.topics ?? [];

  if (!mounted || draftQuery.isLoading || offeringsQuery.isLoading) {
    return (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (draftQuery.isError || offeringsQuery.isError) {
    return (
      <ErrorState
        title={t("load_error")}
        description={t("load_error_hint")}
        onRetry={() => {
          void draftQuery.refetch();
          void offeringsQuery.refetch();
        }}
        retryLabel={t("retry")}
      />
    );
  }

  if (offerings.length === 0) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6" role="status">
        <h2 className="text-lg font-semibold text-gray-900">{t("empty_offerings_title")}</h2>
        <p className="mt-2 text-sm text-gray-700">{t("empty_offerings_body")}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="text-sm text-gray-600">{t("subtitle")}</p>
        <p className="text-xs text-gray-500" aria-live="polite">
          {t("step_indicator", { step, total: 5 })}
          {saveMutation.isPending ? ` · ${t("saving")}` : null}
          {saveMutation.isSuccess && !saveMutation.isPending ? ` · ${t("saved")}` : null}
        </p>
      </header>

      {saveError ? (
        <p className="text-sm text-red-700" role="alert">
          {saveError}
        </p>
      ) : null}

      {step === 1 ? (
        <section className="space-y-4" aria-labelledby="wizard-step1">
          <h3 id="wizard-step1" className="text-lg font-medium text-gray-900">
            {t("step1_title")}
          </h3>

          <div className="space-y-2">
            <Label htmlFor="offering">{t("offering_label")}</Label>
            <select
              id="offering"
              className="flex h-11 w-full rounded-md border border-gray-300 bg-white px-3 text-sm"
              value={data.grade_subject_offering_id ?? ""}
              onChange={(e) => {
                const id = e.target.value;
                persist(1, {
                  grade_subject_offering_id: id,
                  topic: undefined,
                  topic_source: undefined,
                  curriculum_id: undefined,
                });
                setFreeformTopic("");
              }}
            >
              <option value="">{t("offering_placeholder")}</option>
              {offerings.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.grade_name} · {o.subject_name} ({o.academic_session})
                </option>
              ))}
            </select>
          </div>

          {data.grade_subject_offering_id && !data.curriculum_id ? (
            <p className="text-sm text-gray-600">{t("pick_curriculum_hint")}</p>
          ) : null}

          {/* Curriculum is confirmed in step 2; for step 1 topics we need a curriculum.
              Auto-pick primary when offering selected by loading curricula briefly. */}
          {data.grade_subject_offering_id && !data.curriculum_id ? (
            <CurriculumBootstrap
              token={token!}
              offeringId={data.grade_subject_offering_id}
              onReady={(curriculumId) =>
                setData((prev) => ({ ...prev, curriculum_id: curriculumId }))
              }
            />
          ) : null}

          {data.curriculum_id && topicsQuery.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : null}

          {data.curriculum_id && parseDegraded ? (
            <div className="space-y-2">
              <p className="text-sm text-amber-800" role="status">
                {t("freeform_hint")}
              </p>
              <Label htmlFor="freeform-topic">{t("freeform_label")}</Label>
              <Input
                id="freeform-topic"
                value={freeformTopic}
                onChange={(e) => setFreeformTopic(e.target.value)}
                maxLength={500}
              />
            </div>
          ) : null}

          {data.curriculum_id && !parseDegraded && topics.length > 0 ? (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-gray-900">{t("topics_label")}</legend>
              <ul className="max-h-64 space-y-1 overflow-y-auto rounded-md border border-gray-200 p-2">
                {topics.map((topic) => (
                  <li key={topic.path}>
                    <button
                      type="button"
                      className={
                        data.topic === topic.path
                          ? "w-full rounded-md bg-brand-50 px-3 py-2 text-start text-sm text-brand-800"
                          : "w-full rounded-md px-3 py-2 text-start text-sm text-gray-800 hover:bg-gray-50"
                      }
                      onClick={() =>
                        setData((prev) => ({
                          ...prev,
                          topic: topic.path,
                          topic_source: "tree",
                        }))
                      }
                    >
                      {topic.path}
                    </button>
                  </li>
                ))}
              </ul>
            </fieldset>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              disabled={
                !data.grade_subject_offering_id ||
                !(parseDegraded ? freeformTopic.trim() : data.topic)
              }
              onClick={() => {
                const next: WizardData = {
                  ...data,
                  topic: parseDegraded ? freeformTopic.trim() : data.topic,
                  topic_source: parseDegraded ? "freeform" : "tree",
                };
                persist(2, next);
              }}
            >
              {t("next")}
            </Button>
          </div>
        </section>
      ) : null}

      {step === 2 ? (
        <section className="space-y-4" aria-labelledby="wizard-step2">
          <h3 id="wizard-step2" className="text-lg font-medium text-gray-900">
            {t("step2_title")}
          </h3>
          {selectedOffering ? (
            <p className="text-sm text-gray-600">
              {t("offering_summary", {
                grade: selectedOffering.grade_name,
                subject: selectedOffering.subject_name,
              })}
            </p>
          ) : null}
          <p className="text-sm text-gray-700">
            {t("topic_summary", { topic: data.topic ?? "" })}
          </p>

          {curriculaQuery.isLoading ? <Skeleton className="h-24 w-full" /> : null}
          {curriculaQuery.isError ? (
            <ErrorState
              title={t("curricula_error")}
              description={t("load_error_hint")}
              onRetry={() => void curriculaQuery.refetch()}
              retryLabel={t("retry")}
            />
          ) : null}

          {curriculaQuery.data && curriculaQuery.data.length === 0 ? (
            <p className="text-sm text-gray-600" role="status">
              {t("curricula_empty")}
            </p>
          ) : null}

          {curriculaQuery.data && curriculaQuery.data.length > 0 ? (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-gray-900">
                {t("curriculum_label")}
              </legend>
              <ul className="space-y-2">
                {curriculaQuery.data.map((c) => (
                  <li key={c.id}>
                    <label className="flex cursor-pointer items-start gap-3 rounded-md border border-gray-200 p-3 hover:bg-gray-50">
                      <input
                        type="radio"
                        name="curriculum"
                        className="mt-1 size-4"
                        checked={data.curriculum_id === c.id}
                        onChange={() =>
                          setData((prev) => ({ ...prev, curriculum_id: c.id }))
                        }
                      />
                      <span className="text-sm text-gray-900">
                        {c.title}
                        {c.is_primary ? (
                          <span className="ms-2 text-xs font-medium text-brand-700">
                            {t("primary_badge")}
                          </span>
                        ) : null}
                        {c.parse_degraded ? (
                          <span className="ms-2 text-xs text-amber-700">
                            {t("degraded_badge")}
                          </span>
                        ) : null}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
          ) : null}

          <div className="flex justify-between gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => persist(1, data)}
            >
              {t("back")}
            </Button>
            <Button
              type="button"
              disabled={!data.curriculum_id}
              onClick={() => persist(3, data)}
            >
              {t("next")}
            </Button>
          </div>
        </section>
      ) : null}

      {step === 3 ? (
        <section className="space-y-4" aria-labelledby="wizard-step3">
          <h3 id="wizard-step3" className="text-lg font-medium text-gray-900">
            {t("step3_title")}
          </h3>
          <label className="flex items-center gap-3 text-sm text-gray-800">
            <input
              type="checkbox"
              className="size-4"
              checked={Boolean(data.include_cross_grade)}
              onChange={(e) => {
                const next = {
                  ...data,
                  include_cross_grade: e.target.checked,
                  reference_book_ids: [] as string[],
                };
                persist(3, next);
              }}
            />
            {t("cross_grade_toggle")}
          </label>
          <ReferencesStep
            token={token!}
            offeringId={data.grade_subject_offering_id!}
            includeCrossGrade={Boolean(data.include_cross_grade)}
            selected={data.reference_book_ids ?? []}
            onToggle={(id) => {
              const current = new Set(data.reference_book_ids ?? []);
              if (current.has(id)) current.delete(id);
              else current.add(id);
              setData((prev) => ({
                ...prev,
                reference_book_ids: Array.from(current),
              }));
            }}
            labels={{
              loading: t("refs_loading"),
              empty: t("refs_empty"),
              error: t("refs_error"),
              retry: t("retry"),
              crossBadge: t("cross_grade_badge"),
            }}
          />
          <div className="flex justify-between gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => persist(2, data)}>
              {t("back")}
            </Button>
            <Button
              type="button"
              onClick={() =>
                persist(4, {
                  ...data,
                  reference_book_ids: data.reference_book_ids ?? [],
                  include_cross_grade: Boolean(data.include_cross_grade),
                })
              }
            >
              {t("next")}
            </Button>
          </div>
        </section>
      ) : null}

      {step === 4 ? (
        <section className="space-y-4" aria-labelledby="wizard-step4">
          <h3 id="wizard-step4" className="text-lg font-medium text-gray-900">
            {t("step4_title")}
          </h3>
          <fieldset className="space-y-2">
            <legend className="sr-only">{t("step4_title")}</legend>
            {(["auto", "manual", "voice_assisted"] as const).map((mode) => (
              <label
                key={mode}
                className="flex cursor-pointer items-start gap-3 rounded-md border border-gray-200 p-3 hover:bg-gray-50"
              >
                <input
                  type="radio"
                  name="teaching_mode"
                  className="mt-1 size-4"
                  checked={data.teaching_mode === mode}
                  onChange={() => setData((prev) => ({ ...prev, teaching_mode: mode }))}
                />
                <span className="text-sm text-gray-900">{t(`mode_${mode}`)}</span>
              </label>
            ))}
          </fieldset>
          <div className="flex justify-between gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => persist(3, data)}>
              {t("back")}
            </Button>
            <Button
              type="button"
              disabled={!data.teaching_mode}
              onClick={() => persist(5, data)}
            >
              {t("next")}
            </Button>
          </div>
        </section>
      ) : null}

      {step === 5 ? (
        <Step5Confirm
          token={token!}
          data={data}
          selectedOffering={selectedOffering}
          t={t}
          onBack={() => persist(4, data)}
          onGenerated={(lectureId) => {
            setData((prev) => ({ ...prev, lecture_id: lectureId }));
          }}
        />
      ) : null}
    </div>
  );
}

/** Loads curricula once so Step 1 can show topics before Step 2 confirmation. */
function CurriculumBootstrap({
  token,
  offeringId,
  onReady,
}: {
  token: string;
  offeringId: string;
  onReady: (curriculumId: string) => void;
}) {
  const { data } = useQuery({
    queryKey: ["teacher", "wizard-curricula-boot", offeringId],
    queryFn: () => lectureWizardApi.listCurricula(token, offeringId),
  });

  useEffect(() => {
    if (!data?.length) return;
    const primary = data.find((c) => c.is_primary) ?? data[0];
    onReady(primary.id);
  }, [data, onReady]);

  return null;
}

function ReferencesStep({
  token,
  offeringId,
  includeCrossGrade,
  selected,
  onToggle,
  labels,
}: {
  token: string;
  offeringId: string;
  includeCrossGrade: boolean;
  selected: string[];
  onToggle: (id: string) => void;
  labels: {
    loading: string;
    empty: string;
    error: string;
    retry: string;
    crossBadge: string;
  };
}) {
  const query = useQuery({
    queryKey: ["teacher", "wizard-refs", offeringId, includeCrossGrade],
    queryFn: () => lectureWizardApi.listReferences(token, offeringId, includeCrossGrade),
  });

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) {
    return (
      <ErrorState
        title={labels.error}
        description={labels.error}
        onRetry={() => void query.refetch()}
        retryLabel={labels.retry}
      />
    );
  }
  if (!query.data?.length) {
    return (
      <p className="text-sm text-gray-600" role="status">
        {labels.empty}
      </p>
    );
  }

  return (
    <ul className="max-h-64 space-y-2 overflow-y-auto">
      {query.data.map((ref) => (
        <li key={ref.id}>
          <label className="flex cursor-pointer items-start gap-3 rounded-md border border-gray-200 p-3 hover:bg-gray-50">
            <input
              type="checkbox"
              className="mt-1 size-4"
              checked={selected.includes(ref.id)}
              onChange={() => onToggle(ref.id)}
            />
            <span className="text-sm text-gray-900">
              {ref.title}
              {ref.is_cross_grade ? (
                <span className="ms-2 text-xs text-amber-700">{labels.crossBadge}</span>
              ) : null}
            </span>
          </label>
        </li>
      ))}
    </ul>
  );
}

function Step5Confirm({
  token,
  data,
  selectedOffering,
  t,
  onBack,
  onGenerated,
}: {
  token: string;
  data: WizardData;
  selectedOffering: TeacherOfferingRead | undefined;
  t: ReturnType<typeof useTranslations>;
  onBack: () => void;
  onGenerated: (lectureId: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const mode = data.teaching_mode ?? "auto";
  const refs = data.reference_book_ids ?? [];

  const estimateQuery = useQuery({
    queryKey: ["teacher", "wizard-estimate", mode, refs.length],
    queryFn: () => lectureWizardApi.getEstimate(token, mode, refs.length),
  });

  const generateMutation = useMutation({
    mutationFn: (payload: LectureGenerateRequest) =>
      lectureWizardApi.generate(token, payload),
    onSuccess: (result) => {
      onGenerated(result.lecture_id);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : t("generate_error"));
    },
  });

  if (data.lecture_id) {
    return <GenerationStreamPanel lectureId={data.lecture_id} t={t} />;
  }

  return (
    <section className="space-y-4" aria-labelledby="wizard-step5">
      <h3 id="wizard-step5" className="text-lg font-medium text-gray-900">
        {t("step5_title")}
      </h3>
      {selectedOffering ? (
        <p className="text-sm text-gray-600">
          {t("offering_summary", {
            grade: selectedOffering.grade_name,
            subject: selectedOffering.subject_name,
          })}
        </p>
      ) : null}
      <p className="text-sm text-gray-700">{t("topic_summary", { topic: data.topic ?? "" })}</p>
      <p className="text-sm text-gray-700">{t(`mode_${mode}`)}</p>
      <p className="text-sm text-gray-700">
        {t("refs_summary", { count: refs.length })}
      </p>
      {estimateQuery.isLoading ? <Skeleton className="h-8 w-48" /> : null}
      {estimateQuery.data ? (
        <p className="text-sm font-medium text-brand-800" role="status">
          {t("estimate_label", { seconds: estimateQuery.data.estimated_seconds })}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex justify-between gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onBack}>
          {t("back")}
        </Button>
        <Button
          type="button"
          loading={generateMutation.isPending}
          disabled={
            !data.grade_subject_offering_id ||
            !data.topic ||
            !data.curriculum_id ||
            !data.teaching_mode
          }
          onClick={() => {
            setError(null);
            generateMutation.mutate({
              grade_subject_offering_id: data.grade_subject_offering_id!,
              topic: data.topic!,
              curriculum_id: data.curriculum_id!,
              reference_book_ids: refs,
              teaching_mode: mode,
              include_cross_grade: Boolean(data.include_cross_grade),
            });
          }}
        >
          {t("generate")}
        </Button>
      </div>
    </section>
  );
}

/** Live generation transcript over WebSocket (T-117) — reconnects and resumes automatically. */
function GenerationStreamPanel({
  lectureId,
  t,
}: {
  lectureId: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const { mounted, token } = useClientAuth();
  const stream = useLectureGenerationStream(lectureId, mounted);

  if (stream.status === "error") {
    return (
      <ErrorState
        title={t("generating_error_title")}
        description={
          stream.errorReason === "timed_out"
            ? t("generating_error_timeout")
            : t("generating_error_body")
        }
      />
    );
  }

  if (stream.status === "connecting" && !stream.text) {
    return (
      <section className="space-y-3" aria-busy="true">
        <h3 className="text-lg font-medium text-gray-900">{t("generating_title")}</h3>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full" />
      </section>
    );
  }

  if (stream.status === "complete") {
    return (
      <section className="space-y-3">
        <div role="status">
          <h3 className="text-lg font-medium text-gray-900">{t("generating_complete_title")}</h3>
          <p className="text-sm text-gray-700">{t("generating_complete_body")}</p>
        </div>
        <LectureParagraphsView token={token!} lectureId={lectureId} t={t} />
        <LectureLinksPanel token={token!} lectureId={lectureId} t={t} />
        <VoiceConversationPanel lectureId={lectureId} t={t} />
      </section>
    );
  }

  return (
    <section className="space-y-3" aria-labelledby="wizard-step5-generating">
      <h3 id="wizard-step5-generating" className="text-lg font-medium text-gray-900">
        {t("generating_title")}
      </h3>
      {stream.status === "reconnecting" ? (
        <p className="text-sm text-amber-700" role="status" aria-live="polite">
          {t("generating_reconnecting")}
        </p>
      ) : null}
      <div
        dir="auto"
        aria-label={t("generating_streaming_label")}
        className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md border border-gray-200 bg-gray-50 p-3 font-mono text-sm text-gray-800"
      >
        {stream.text}
      </div>
    </section>
  );
}

/** Reads back the persisted paragraphs once generation completes, with source badges (T-118). */
function LectureParagraphsView({
  token,
  lectureId,
  t,
}: {
  token: string;
  lectureId: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const query = useQuery({
    queryKey: ["teacher", "lecture-paragraphs", lectureId],
    queryFn: () => lectureWizardApi.getParagraphs(token, lectureId),
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
          <SourceBadge paragraph={paragraph} t={t} />
          <p dir="auto" className="text-sm text-gray-800">
            {paragraph.text}
          </p>
        </li>
      ))}
    </ul>
  );
}

function SourceBadge({
  paragraph,
  t,
}: {
  paragraph: LectureParagraphRead;
  t: ReturnType<typeof useTranslations>;
}) {
  switch (paragraph.tier) {
    case "curriculum":
      return (
        <span className="inline-block rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-800">
          {t("badge_curriculum")}
        </span>
      );
    case "reference":
      return (
        <span className="inline-block rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-800">
          {t("badge_reference", { book: paragraph.book_name ?? "" })}
        </span>
      );
    case "web":
      return (
        <span className="inline-block rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
          {t("badge_web")}
        </span>
      );
    case "ai_knowledge":
      return (
        <span className="inline-block rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-800">
          {t("badge_ai_knowledge")}
        </span>
      );
    default: {
      const _exhaustive: never = paragraph.tier;
      throw new Error(`unhandled source tier: ${_exhaustive}`);
    }
  }
}

/** Cross-grade / cross-subject lecture linking (T-122, #21) — the lecture detail view. */
function LectureLinksPanel({
  token,
  lectureId,
  t,
}: {
  token: string;
  lectureId: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const qc = useQueryClient();
  const [targetOfferingId, setTargetOfferingId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);

  const offeringsQuery = useQuery({
    queryKey: ["teacher", "offerings"],
    queryFn: () => lectureWizardApi.listOfferings(token),
  });

  const linksQuery = useQuery({
    queryKey: ["teacher", "lecture-links", lectureId],
    queryFn: () => lectureWizardApi.listLinks(token, lectureId),
  });

  const linkMutation = useMutation({
    mutationFn: (offeringId: string) =>
      lectureWizardApi.createLink(token, lectureId, {
        target_grade_subject_offering_id: offeringId,
      }),
    onSuccess: () => {
      setLinkError(null);
      setTargetOfferingId("");
      void qc.invalidateQueries({ queryKey: ["teacher", "lecture-links", lectureId] });
    },
    onError: (err: unknown) => {
      setLinkError(err instanceof ApiError ? err.message : t("links_create_error"));
    },
  });

  if (linksQuery.isLoading || offeringsQuery.isLoading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (linksQuery.isError) {
    return (
      <ErrorState
        title={t("links_error")}
        description={t("links_error")}
        onRetry={() => void linksQuery.refetch()}
        retryLabel={t("retry")}
      />
    );
  }

  const offerings = offeringsQuery.data ?? [];
  const links = linksQuery.data ?? [];

  return (
    <section className="space-y-3" aria-labelledby="lecture-links-heading">
      <h3 id="lecture-links-heading" className="text-lg font-medium text-gray-900">
        {t("links_title")}
      </h3>

      {links.length === 0 ? (
        <p className="text-sm text-gray-600" role="status">
          {t("links_empty")}
        </p>
      ) : (
        <ul className="space-y-2">
          {links.map((link) => (
            <li
              key={link.id}
              className="rounded-md border border-gray-200 p-2 text-sm text-gray-800"
            >
              {t("links_item", {
                grade: link.target_grade_name,
                subject: link.target_subject_name,
              })}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="link-target-offering">{t("links_target_label")}</Label>
          <select
            id="link-target-offering"
            className="flex h-11 w-full min-w-64 rounded-md border border-gray-300 bg-white px-3 text-sm"
            value={targetOfferingId}
            onChange={(e) => setTargetOfferingId(e.target.value)}
          >
            <option value="">{t("links_target_placeholder")}</option>
            {offerings.map((o) => (
              <option key={o.id} value={o.id}>
                {o.grade_name} · {o.subject_name} ({o.academic_session})
              </option>
            ))}
          </select>
        </div>
        <Button
          type="button"
          disabled={!targetOfferingId || linkMutation.isPending}
          onClick={() => linkMutation.mutate(targetOfferingId)}
        >
          {linkMutation.isPending ? t("links_linking") : t("links_link_button")}
        </Button>
      </div>

      {linkError ? (
        <p className="text-sm text-red-700" role="alert">
          {linkError}
        </p>
      ) : null}
    </section>
  );
}

// Lecture generation doesn't expose a per-lecture language selector anywhere
// yet (service.py's generate_from_wizard hardcodes "en" — no UI built for it
// in M-09 so far), so the voice session matches that: English only for now.
const VOICE_LANGUAGE = "en";

/** "Talk to AI" voice conversation during/after lecture creation (T-121, #25). */
function VoiceConversationPanel({
  lectureId,
  t,
}: {
  lectureId: string;
  t: ReturnType<typeof useTranslations>;
}) {
  const voice = useLectureVoiceSession(lectureId, VOICE_LANGUAGE);

  if (voice.status === "idle") {
    return (
      <div className="border-t border-gray-100 pt-4">
        <Button type="button" variant="outline" onClick={voice.startSession} className="gap-2">
          <Mic className="size-4" aria-hidden="true" />
          {t("voice_start_button")}
        </Button>
      </div>
    );
  }

  const isBusy = voice.status === "recording" || voice.status === "processing";

  return (
    <section className="space-y-3 border-t border-gray-100 pt-4" aria-labelledby="voice-panel-heading">
      <h3 id="voice-panel-heading" className="text-lg font-medium text-gray-900">
        {t("voice_panel_title")}
      </h3>

      {voice.status === "connecting" ? (
        <p className="text-sm text-gray-600" role="status" aria-live="polite">
          {t("voice_connecting")}
        </p>
      ) : null}

      {voice.status === "error" ? (
        <ErrorState title={t("voice_error_title")} description={t("voice_error_body")} />
      ) : null}

      {voice.unavailableNotice ? (
        <p className="text-sm text-amber-700" role="status">
          {t("voice_tts_unavailable")}
        </p>
      ) : null}

      {voice.status === "ready" || isBusy ? (
        <div className="flex items-center gap-3">
          {voice.status === "recording" ? (
            <Button
              type="button"
              variant="destructive"
              size="icon"
              className="size-11 rounded-full"
              onClick={voice.stopRecording}
              aria-label={t("voice_stop_recording")}
            >
              <Square className="size-4" aria-hidden="true" />
            </Button>
          ) : (
            <Button
              type="button"
              variant="primary"
              size="icon"
              className="size-11 rounded-full"
              onClick={() => void voice.startRecording()}
              disabled={voice.status === "processing"}
              aria-label={t("voice_start_recording")}
            >
              <Mic className="size-4" aria-hidden="true" />
            </Button>
          )}
          <p className="text-sm text-gray-600" role="status" aria-live="polite">
            {voice.status === "recording"
              ? t("voice_recording")
              : voice.status === "processing"
                ? t("voice_processing")
                : t("voice_ready")}
          </p>
        </div>
      ) : null}

      {voice.turns.length > 0 ? (
        <ul
          className="max-h-64 space-y-2 overflow-y-auto"
          aria-label={t("voice_transcript_label")}
        >
          {voice.turns.map((turn, i) => (
            <li key={i} className="rounded-md border border-gray-200 p-2 text-sm">
              <p dir="auto" className="text-gray-500">
                {turn.transcript}
              </p>
              <p dir="auto" className="text-gray-900">
                {turn.confirmation}
              </p>
              {turn.hadDraftEdit ? (
                <span className="text-xs text-brand-700">{t("voice_draft_updated")}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {voice.status === "ended" ? (
        <p className="text-sm text-gray-600" role="status">
          {t("voice_session_ended")}
        </p>
      ) : (
        <Button type="button" variant="outline" size="sm" onClick={voice.endSession}>
          {t("voice_end_session")}
        </Button>
      )}
    </section>
  );
}
