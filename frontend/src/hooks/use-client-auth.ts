"use client";

import { useEffect, useState } from "react";
import { getAuthCredential } from "@/lib/auth";

/**
 * Client auth gate for data fetching. Returns a credential the API client
 * understands: {@link COOKIE_AUTH} for BFF cookie sessions, or a legacy JWT
 * in `oidc_redirect` mode. Use `mounted` so the first client render matches SSR.
 */
export function useClientAuth() {
  const [mounted, setMounted] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setToken(getAuthCredential());
    setMounted(true);
  }, []);

  return { mounted, token };
}
