import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.PORT ?? "3000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  timeout: 120_000,
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "pnpm dev",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    // Forward the mock-suite bypass into Next's process. Edge middleware only
    // sees env vars present when `next dev` starts (static `process.env.X`
    // access in middleware.ts); without this, a shell-prefix env on `pnpm e2e`
    // would not reach the middleware and @smoke would keep redirecting.
    env: {
      ...process.env,
      PLAYWRIGHT_BYPASS_AUTH_MIDDLEWARE:
        process.env.PLAYWRIGHT_BYPASS_AUTH_MIDDLEWARE ?? "",
    },
  },
});
