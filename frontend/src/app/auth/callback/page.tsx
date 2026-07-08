/**
 * OIDC callback handler (T-016) — `oidc_redirect` fallback only (M-07b T-245).
 * BFF mode uses POST /auth/login on /login instead; this route redirects away.
 */
import { redirect } from "next/navigation";
import { OidcCallbackClient } from "./OidcCallbackClient";

export default function CallbackPage() {
  if ((process.env.NEXT_PUBLIC_AUTH_LOGIN_MODE ?? "bff") !== "oidc_redirect") {
    redirect("/login");
  }
  return <OidcCallbackClient />;
}
