"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, Archive, Plus, UserPlus } from "lucide-react";
import Link from "next/link";
import {
  gradesApi,
  sectionsApi,
  subjectsApi,
  offeringsApi,
  usersApi,
  ApiError,
  type Section,
  type OfferingRead,
  type EligibleTeacherRead,
} from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";

const sectionSchema = z.object({ name: z.string().min(1).max(100) });
type SectionFormValues = z.infer<typeof sectionSchema>;

const offeringSchema = z.object({ subject_id: z.string().min(1) });
type OfferingFormValues = z.infer<typeof offeringSchema>;

export function GradeDetailClient() {
  const params = useParams<{ gradeId: string }>();
  const gradeId = params.gradeId;
  const t = useTranslations("coordinator.grade_detail");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [showCreateSection, setShowCreateSection] = useState(false);
  const [archiveSectionTarget, setArchiveSectionTarget] = useState<Section | null>(null);
  const [showCreateOffering, setShowCreateOffering] = useState(false);
  const [archiveOfferingTarget, setArchiveOfferingTarget] = useState<OfferingRead | null>(null);
  const [assignTarget, setAssignTarget] = useState<OfferingRead | null>(null);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string>("");
  const [overrideCapacity, setOverrideCapacity] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [assignError, setAssignError] = useState<string | null>(null);

  const { data: me } = useQuery({
    queryKey: ["users", "me"],
    queryFn: () => usersApi.getMe(token!),
    enabled: mounted && !!token,
  });

  const { data: grade, isLoading: gradeLoading, isError: gradeError, refetch: refetchGrade } = useQuery({
    queryKey: ["grades", gradeId],
    queryFn: () => gradesApi.get(token!, gradeId),
    enabled: mounted && !!token,
  });

  const { data: sections, isLoading: sectionsLoading, isError: sectionsError, refetch: refetchSections } = useQuery({
    queryKey: ["sections", gradeId],
    queryFn: () => sectionsApi.list(token!, gradeId),
    enabled: mounted && !!token,
  });

  const { data: offerings, isLoading: offeringsLoading, isError: offeringsError, refetch: refetchOfferings } = useQuery({
    queryKey: ["offerings", gradeId],
    queryFn: () => offeringsApi.list(token!, gradeId),
    enabled: mounted && !!token,
  });

  const { data: subjects } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => subjectsApi.list(token!),
    enabled: mounted && !!token,
  });

  const {
    data: eligibleTeachers,
    isLoading: eligibleTeachersLoading,
    isError: eligibleTeachersError,
    refetch: refetchEligibleTeachers,
  } = useQuery({
    queryKey: ["eligible-teachers", gradeId],
    queryFn: () => offeringsApi.eligibleTeachers(token!, gradeId),
    enabled: mounted && !!token && !!assignTarget,
  });

  const sectionForm = useForm<SectionFormValues>({ resolver: zodResolver(sectionSchema), defaultValues: { name: "" } });
  const offeringForm = useForm<OfferingFormValues>({ resolver: zodResolver(offeringSchema), defaultValues: { subject_id: "" } });

  const subjectNameById = new Map(subjects?.map((s) => [s.id, s.name]) ?? []);
  const teacherNameById = new Map(eligibleTeachers?.map((t) => [t.id, t.display_name]) ?? []);
  const canOverride = me?.role === "school_admin" || me?.role === "platform_admin" || me?.role === "district_admin";

  const createSectionMutation = useMutation({
    mutationFn: (values: SectionFormValues) => sectionsApi.create(token ?? "", gradeId, values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sections", gradeId] });
      setShowCreateSection(false);
      sectionForm.reset();
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError && err.status === 409 ? t("sections.duplicate_error") : t("sections.generic_error"));
    },
  });

  const archiveSectionMutation = useMutation({
    mutationFn: (sectionId: string) => sectionsApi.archive(token ?? "", gradeId, sectionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sections", gradeId] });
      setArchiveSectionTarget(null);
    },
  });

  const createOfferingMutation = useMutation({
    mutationFn: (values: OfferingFormValues) => offeringsApi.create(token ?? "", gradeId, values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offerings", gradeId] });
      setShowCreateOffering(false);
      offeringForm.reset();
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError && err.status === 409 ? t("offerings.duplicate_error") : t("offerings.generic_error"));
    },
  });

  const archiveOfferingMutation = useMutation({
    mutationFn: (offeringId: string) => offeringsApi.archive(token ?? "", gradeId, offeringId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offerings", gradeId] });
      setArchiveOfferingTarget(null);
    },
  });

  const assignMutation = useMutation({
    mutationFn: ({ offering, teacherId, override }: { offering: OfferingRead; teacherId: string; override: boolean }) =>
      offeringsApi.assign(token ?? "", gradeId, offering.id, { teacher_id: teacherId, override }, offering.updated_at),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offerings", gradeId] });
      qc.invalidateQueries({ queryKey: ["eligible-teachers", gradeId] });
      setAssignTarget(null);
      setSelectedTeacherId("");
      setOverrideCapacity(false);
    },
    onError: (err: unknown) => {
      setAssignError(err instanceof ApiError && err.status === 412 ? t("offerings.assign.capacity_error") : t("offerings.assign.generic_error"));
    },
  });

  const unassignMutation = useMutation({
    mutationFn: (offering: OfferingRead) =>
      offeringsApi.unassign(token ?? "", gradeId, offering.id, offering.updated_at),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offerings", gradeId] });
      qc.invalidateQueries({ queryKey: ["eligible-teachers", gradeId] });
    },
  });

  if (!mounted || gradeLoading) return <Skeleton className="h-64 w-full" />;
  if (gradeError || !grade) {
    return <ErrorState message={t("error")} onRetry={() => refetchGrade()} retryLabel={t("retry")} />;
  }

  const offeredSubjectIds = new Set(offerings?.map((o) => o.subject_id) ?? []);
  const availableSubjects = subjects?.filter((s) => !offeredSubjectIds.has(s.id)) ?? [];

  return (
    <div className="space-y-8">
      <div>
        <Link href="/coordinator/grades" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4">
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t("back")}
        </Link>
        <h2 className="text-2xl font-bold text-gray-900">{grade.name}</h2>
        <p className="text-sm text-gray-500">{t("session_label", { session: grade.academic_session })}</p>
      </div>

      <section aria-labelledby="sections-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 id="sections-heading" className="text-lg font-semibold text-gray-900">{t("sections.title")}</h3>
          <Button size="sm" onClick={() => { setShowCreateSection(true); setFormError(null); sectionForm.reset(); }}>
            <Plus className="size-4 me-2" aria-hidden="true" />
            {t("sections.add_button")}
          </Button>
        </div>

        {sectionsLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : sectionsError ? (
          <ErrorState message={t("sections.error")} onRetry={() => refetchSections()} retryLabel={t("retry")} />
        ) : !sections?.length ? (
          <EmptyState title={t("sections.empty.title")} description={t("sections.empty.description")} />
        ) : (
          <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
            {sections.map((section) => (
              <li key={section.id} className="flex items-center justify-between px-4 py-3">
                <span className="text-sm font-medium text-gray-900">{section.name}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setArchiveSectionTarget(section)}
                  aria-label={t("sections.archive", { name: section.name })}
                >
                  <Archive className="size-4" aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="offerings-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 id="offerings-heading" className="text-lg font-semibold text-gray-900">{t("offerings.title")}</h3>
          <Button size="sm" onClick={() => { setShowCreateOffering(true); setFormError(null); offeringForm.reset(); }}>
            <Plus className="size-4 me-2" aria-hidden="true" />
            {t("offerings.add_button")}
          </Button>
        </div>

        {offeringsLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : offeringsError ? (
          <ErrorState message={t("offerings.error")} onRetry={() => refetchOfferings()} retryLabel={t("retry")} />
        ) : !offerings?.length ? (
          <EmptyState title={t("offerings.empty.title")} description={t("offerings.empty.description")} />
        ) : (
          <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
            {offerings.map((offering) => (
              <li key={offering.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <span className="text-sm font-medium text-gray-900">
                    {subjectNameById.get(offering.subject_id) ?? offering.subject_id}
                  </span>
                  <p className="text-xs text-gray-500">
                    {offering.assigned_teacher_id
                      ? teacherNameById.get(offering.assigned_teacher_id) ?? offering.assigned_teacher_id
                      : t("offerings.unassigned")}
                  </p>
                </div>
                <div className="flex gap-2">
                  {offering.assigned_teacher_id ? (
                    <Button variant="ghost" size="sm" onClick={() => unassignMutation.mutate(offering)} disabled={unassignMutation.isPending}>
                      {t("offerings.assign.unassign")}
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => { setAssignTarget(offering); setAssignError(null); setSelectedTeacherId(""); setOverrideCapacity(false); }}
                    >
                      <UserPlus className="size-4 me-1" aria-hidden="true" />
                      {t("offerings.assign.button")}
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => setArchiveOfferingTarget(offering)} aria-label={t("offerings.archive")}>
                    <Archive className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Modal open={showCreateSection} onClose={() => setShowCreateSection(false)} title={t("sections.modal.title")}>
        <form
          onSubmit={sectionForm.handleSubmit((v) => { setFormError(null); createSectionMutation.mutate(v); })}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="section-name">{t("sections.modal.name_label")}</Label>
            <Input id="section-name" {...sectionForm.register("name")} placeholder={t("sections.modal.name_placeholder")} />
          </div>
          {formError && <p className="text-sm text-red-600">{formError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setShowCreateSection(false)}>{t("sections.modal.cancel")}</Button>
            <Button type="submit" disabled={createSectionMutation.isPending}>{t("sections.modal.create")}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!archiveSectionTarget} onClose={() => setArchiveSectionTarget(null)} title={t("sections.archive_modal.title")}>
        <p className="text-sm text-gray-600 mb-4">{t("sections.archive_modal.description", { name: archiveSectionTarget?.name ?? "" })}</p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setArchiveSectionTarget(null)}>{t("sections.archive_modal.cancel")}</Button>
          <Button variant="danger" onClick={() => archiveSectionTarget && archiveSectionMutation.mutate(archiveSectionTarget.id)} disabled={archiveSectionMutation.isPending}>
            {t("sections.archive_modal.confirm")}
          </Button>
        </div>
      </Modal>

      <Modal open={showCreateOffering} onClose={() => setShowCreateOffering(false)} title={t("offerings.modal.title")}>
        <form
          onSubmit={offeringForm.handleSubmit((v) => { setFormError(null); createOfferingMutation.mutate(v); })}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="offering-subject">{t("offerings.modal.subject_label")}</Label>
            <select
              id="offering-subject"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              {...offeringForm.register("subject_id")}
            >
              <option value="">{t("offerings.modal.subject_placeholder")}</option>
              {availableSubjects.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          {formError && <p className="text-sm text-red-600">{formError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setShowCreateOffering(false)}>{t("offerings.modal.cancel")}</Button>
            <Button type="submit" disabled={createOfferingMutation.isPending}>{t("offerings.modal.create")}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!archiveOfferingTarget} onClose={() => setArchiveOfferingTarget(null)} title={t("offerings.archive_modal.title")}>
        <p className="text-sm text-gray-600 mb-4">{t("offerings.archive_modal.description")}</p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setArchiveOfferingTarget(null)}>{t("offerings.archive_modal.cancel")}</Button>
          <Button variant="danger" onClick={() => archiveOfferingTarget && archiveOfferingMutation.mutate(archiveOfferingTarget.id)} disabled={archiveOfferingMutation.isPending}>
            {t("offerings.archive_modal.confirm")}
          </Button>
        </div>
      </Modal>

      <Modal open={!!assignTarget} onClose={() => setAssignTarget(null)} title={t("offerings.assign.title")}>
        <div className="space-y-4">
          {eligibleTeachersLoading && (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}
          {eligibleTeachersError && (
            <ErrorState message={t("offerings.assign.load_error")} onRetry={() => refetchEligibleTeachers()} />
          )}
          {!eligibleTeachersLoading && !eligibleTeachersError && (eligibleTeachers ?? []).length === 0 && (
            <EmptyState title={t("offerings.assign.empty_title")} description={t("offerings.assign.empty_description")} />
          )}
          {!eligibleTeachersLoading && !eligibleTeachersError && (eligibleTeachers ?? []).length > 0 && (
          <ul className="max-h-48 overflow-y-auto divide-y divide-gray-100 rounded border border-gray-200">
            {(eligibleTeachers ?? []).map((teacher: EligibleTeacherRead) => {
              const disabled = teacher.at_capacity && !(canOverride && overrideCapacity);
              return (
                <li key={teacher.id} className="flex items-center justify-between px-3 py-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="teacher"
                      value={teacher.id}
                      disabled={disabled}
                      checked={selectedTeacherId === teacher.id}
                      onChange={() => setSelectedTeacherId(teacher.id)}
                    />
                    <span>{teacher.display_name}</span>
                    <span className="text-xs text-gray-500">
                      ({teacher.assignment_count}/{teacher.capacity})
                    </span>
                  </label>
                  {teacher.at_capacity && (
                    <span className="text-xs text-amber-600">
                      {t("offerings.assign.at_capacity", { count: teacher.assignment_count, cap: teacher.capacity })}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
          )}
          {canOverride && selectedTeacherId && eligibleTeachers?.find((t) => t.id === selectedTeacherId)?.at_capacity && (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={overrideCapacity} onChange={(e) => setOverrideCapacity(e.target.checked)} />
              {t("offerings.assign.override_label")}
            </label>
          )}
          {assignError && <p className="text-sm text-red-600">{assignError}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setAssignTarget(null)}>{t("offerings.assign.cancel")}</Button>
            <Button
              onClick={() => assignTarget && selectedTeacherId && assignMutation.mutate({
                offering: assignTarget,
                teacherId: selectedTeacherId,
                override: overrideCapacity,
              })}
              disabled={!selectedTeacherId || assignMutation.isPending}
            >
              {t("offerings.assign.confirm")}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
