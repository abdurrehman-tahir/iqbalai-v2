/**
 * OIDC callback handler (T-016).
 * Authentik redirects here after successful login with ?code=...
 * We exchange the code for a token, call /auth/post-login, and either
 * show the ToS modal or redirect to /admin.
 */
import { OidcCallbackClient } from "./OidcCallbackClient";

export default function CallbackPage() {
  return <OidcCallbackClient />;
}
