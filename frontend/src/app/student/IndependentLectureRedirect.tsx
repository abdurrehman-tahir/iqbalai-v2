"use client";

/**
 * Independent students have no Lecture Mode (Flow 8 §3.1). Any accidental
 * navigation into `/student/*` (lecture-mode shell) redirects to self-study home.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCurrentUser } from "@/hooks/use-current-user";

const SELF_STUDY_HOME = "/independent/student";

export function IndependentLectureRedirect({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const t = useTranslations("independent.student.home");
  const { user, isLoading } = useCurrentUser();

  useEffect(() => {
    if (isLoading || !user) return;
    if (user.role === "independent_student") {
      router.replace(SELF_STUDY_HOME);
    }
  }, [isLoading, user, router]);

  if (!isLoading && user?.role === "independent_student") {
    return (
      <div
        className="flex min-h-[40vh] items-center justify-center p-6 text-sm text-gray-600"
        data-testid="independent-lecture-redirect"
        role="status"
      >
        {t("redirecting_to_self_study")}
      </div>
    );
  }

  return <>{children}</>;
}
