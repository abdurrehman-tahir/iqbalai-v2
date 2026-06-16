"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { teacherOnboardingApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function TeacherOnboardingGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { mounted, token } = useClientAuth();

  const { data: onboarding, isLoading } = useQuery({
    queryKey: ["teacher", "onboarding"],
    queryFn: () => teacherOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  useEffect(() => {
    if (isLoading || !onboarding) return;
    if (pathname.startsWith("/teacher/onboarding")) return;
    if (!onboarding.profile_complete) {
      router.replace("/teacher/onboarding");
    }
  }, [isLoading, onboarding, pathname, router]);

  if (pathname.startsWith("/teacher/onboarding")) {
    return children;
  }

  if (isLoading || (onboarding && !onboarding.profile_complete)) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <p className="text-sm text-gray-500">Loading…</p>
      </div>
    );
  }

  return children;
}
