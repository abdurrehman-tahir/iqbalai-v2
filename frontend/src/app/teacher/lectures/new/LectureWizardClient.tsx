"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { lectureWizardApi, ApiError } from "@/lib/api";
import type { LectureDraftUpsert, TeacherOfferingRead } from "@/lib/api/types";
import { useClientAuth } from "@/hooks/use-client-auth";
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
              onClick={() => persist(2, data)}
            >
              {t("save_continue")}
            </Button>
          </div>
          <p className="text-xs text-gray-500">{t("steps_3_5_later")}</p>
        </section>
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
