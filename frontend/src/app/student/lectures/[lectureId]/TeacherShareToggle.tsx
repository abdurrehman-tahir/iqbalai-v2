"use client";

import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { studentPrivacyApi, type TeacherActivityShare } from "@/lib/api";

type Props = { token: string };

/**
 * #72 share-with-teacher toggle on the lecture viewer (T-162).
 * Independent students never see this (API 404); school students default to share.
 */
export function TeacherShareToggle({ token }: Props) {
  const t = useTranslations("student.lecture_viewer");
  const queryClient = useQueryClient();

  const privacyQuery = useQuery({
    queryKey: ["student", "privacy", "teacher-share"],
    queryFn: () => studentPrivacyApi.getTeacherShare(token),
    staleTime: 60_000,
  });

  const mutation = useMutation({
    mutationFn: (next: TeacherActivityShare) =>
      studentPrivacyApi.setTeacherShare(token, next),
    onSuccess: (data) => {
      queryClient.setQueryData(["student", "privacy", "teacher-share"], data);
    },
  });

  if (privacyQuery.isError) {
    // Independent / unavailable — hide the control.
    return null;
  }

  const share = privacyQuery.data?.teacher_activity_share ?? "share";
  const checked = share === "share";
  const busy = privacyQuery.isLoading || mutation.isPending;

  return (
    <label
      className="flex max-w-md cursor-pointer items-start gap-2 text-sm text-gray-700"
      data-testid="teacher-share-toggle"
    >
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-gray-300"
        checked={checked}
        disabled={busy}
        aria-checked={checked}
        onChange={() => {
          const next: TeacherActivityShare = checked ? "private" : "share";
          mutation.mutate(next);
        }}
      />
      <span>
        <span className="font-medium">{t("privacy_share_label")}</span>
        <span className="mt-0.5 block text-xs text-gray-500">{t("privacy_share_help")}</span>
      </span>
    </label>
  );
}
