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
};

export default withNextIntl(nextConfig);
