import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");
const requiredProductionAuthEnv = [
  "NEXT_PUBLIC_AUTHENTIK_URL",
  "NEXT_PUBLIC_APP_URL",
  "NEXT_PUBLIC_AUTHENTIK_CLIENT_ID",
] as const;

if (process.env.NODE_ENV === "production") {
  const missing = requiredProductionAuthEnv.filter((name) => !process.env[name]);
  if (missing.length > 0) {
    throw new Error(
      `Missing required production authentication environment variable(s): ${missing.join(", ")}`,
    );
  }
} else if (!process.env.NEXT_PUBLIC_AUTHENTIK_URL) {
  console.warn(
    "NEXT_PUBLIC_AUTHENTIK_URL is unset; using http://localhost:9000 for local development only.",
  );
}

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [],
  },
};

export default withNextIntl(nextConfig);
