import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

import { assertAuthEnv } from "./src/lib/env-guard";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// T-240: fail the build instead of silently shipping a localhost Authentik
// URL to production (audit B1 — see src/lib/env-guard.ts for the incident).
assertAuthEnv(process.env.NODE_ENV);

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [],
  },
  // Edge middleware only sees statically named env vars that Next inlines at
  // compile/start. Wire the Playwright mock-suite bypass through so
  // `process.env.PLAYWRIGHT_BYPASS_AUTH_MIDDLEWARE` in middleware.ts is
  // defined when the e2e webServer sets it (see playwright.config.ts).
  env: {
    PLAYWRIGHT_BYPASS_AUTH_MIDDLEWARE: process.env.PLAYWRIGHT_BYPASS_AUTH_MIDDLEWARE ?? "",
  },
};

export default withNextIntl(nextConfig);
