import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      reportsDirectory: "./coverage",
      // Scope coverage to the application/feature code M-01 actually ships under
      // (src/app + src/components + src/lib + src/hooks). The canonical
      // src/features/ layout (ARCH §12) is not adopted by M-00/M-01 — the
      // audit-fix tickets (T-231/T-235) harden the existing admin surfaces in
      // place rather than migrating them — so the 60% bar lands on those dirs.
      include: [
        "src/app/**/*.{ts,tsx}",
        "src/components/**/*.{ts,tsx}",
        "src/hooks/**/*.{ts,tsx}",
        "src/lib/**/*.{ts,tsx}",
      ],
      exclude: [
        "**/*.test.{ts,tsx}",
        "**/__tests__/**",
        "src/test/**",
        "src/lib/api/schema.d.ts",
        "src/lib/api/types.ts",
        "**/*.d.ts",
        "**/layout.tsx",
        "**/loading.tsx",
        "**/not-found.tsx",
      ],
      thresholds: {
        lines: 60,
        functions: 60,
        branches: 60,
        statements: 60,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
