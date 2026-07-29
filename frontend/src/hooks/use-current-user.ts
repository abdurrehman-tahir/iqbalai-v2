"use client";

import { useQuery } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";

/**
 * Current session's display state (T-245) — replaces the old sessionStorage
 * `getUser()`. Tokens are HttpOnly cookies now, so "who am I" for shell nav
 * (name/role) or an ownership check has to come from the server, not a local
 * copy the client could read/tamper with.
 */
export function useCurrentUser() {
  const { mounted, token } = useClientAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => authApi.me(),
    enabled: mounted && !!token,
    staleTime: 5 * 60 * 1000,
  });

  return { user: data ?? null, isLoading };
}
