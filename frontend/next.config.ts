import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

if (!process.env.NEXT_PUBLIC_AUTHENTIK_URL) {
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
