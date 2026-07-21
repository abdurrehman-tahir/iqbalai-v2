"use client";

import { useEffect, useState } from "react";

/**
 * T-245: the session is an HttpOnly cookie the browser attaches automatically
 * — there is no JS-readable token anymore. `token` is kept as a non-secret
 * truthy sentinel (present only once mounted) so the many existing
 * `!!token`/`token!` call sites across the app — which exist to avoid firing
 * a fetch before the client has hydrated, not to hold a real credential —
 * keep working unchanged. The API call itself succeeds or 401s based on the
 * cookie, regardless of this value.
 *
 * Use `mounted` so the first client render matches SSR (avoids hydration errors).
 */
export function useClientAuth() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return { mounted, token: mounted ? "cookie-session" : null };
}
