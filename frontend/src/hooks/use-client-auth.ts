"use client";

import { useEffect, useState } from "react";

/**
 * The HttpOnly cookie is verified by the API. `token` is a compatibility
 * sentinel for existing feature clients while their token parameters retire.
 */
export function useClientAuth() {
  const [mounted, setMounted] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setToken("cookie-session");
    setMounted(true);
  }, []);

  return { mounted, token };
}
