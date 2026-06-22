"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { studentOnboardingApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

export function StudentOnboardingGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { mounted, token } = useClientAuth();

  const { data: onboarding, isLoading } = useQuery({
    queryKey: ["student", "onboarding"],
    queryFn: () => studentOnboardingApi.getOnboarding(token!),
    enabled: mounted && !!token,
  });

  useEffect(() => {
    if (isLoading || !onboarding) return;
    if (pathname.startsWith("/student/onboarding")) return;
    if (!onboarding.ready_to_study) {
      router.replace("/student/onboarding");
    }
  }, [isLoading, onboarding, pathname, router]);

  if (pathname.startsWith("/student/onboarding")) {
    return children;
  }

  if (isLoading || (onboarding && !onboarding.ready_to_study)) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <p className="text-sm text-gray-500">Loading…</p>
      </div>
    );
  }

  return children;
}
