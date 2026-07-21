# M-07a staging authentication checklist

Complete this checklist on the staging host after the M-07a PR is deployed. Paste
command output, screenshots, and the real-auth Playwright result into the PR.

## Host nginx

- [ ] `sudo nginx -T` confirms the ARCH §15.11 shape, including TLS and
  `location /idp/` proxying to Authentik.
- [ ] The public application and `/idp/` URLs work without exposing a raw port.

## Authentik provider and environment

- [ ] Redirect URI is `https://<domain>/api/v1/auth/callback`.
- [ ] Issuer and JWKS URLs use the public `/idp` URL.
- [ ] Frontend values are `NEXT_PUBLIC_AUTHENTIK_URL=https://<domain>/idp`,
  `NEXT_PUBLIC_APP_URL=https://<domain>`, and the registered client id.
- [ ] API `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, and
  `OIDC_JWKS_URL` are configured without localhost defaults.
- [ ] Authentik branding uses the approved IqbalAI logo and green theme.

## Evidence

- [ ] A clean external browser completes login through `/idp` and reaches its
  role dashboard.
- [ ] Browser storage contains no access token; only `iqbalai_access` and
  `iqbalai_refresh` HttpOnly cookies are present.
- [ ] The `@auth @real` Playwright lane succeeds against staging.
- [ ] Logout revokes the session; replaying its prior access cookie returns 401.
