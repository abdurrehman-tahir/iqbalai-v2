"use client";

import { useEffect, useState } from "react";
import { getToken } from "@/lib/auth";

/**
 * Session token lives in sessionStorage (browser-only).
 * Use `mounted` so the first client render matches SSR (avoids hydration errors).
 */
export function useClientAuth() {
  const [mounted, setMounted] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setToken(getToken());
    setMounted(true);
  }, []);

  return { mounted, token };
}
