"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

type Provider = "google" | "linkedin" | "github";

const PROVIDERS: Provider[] = ["google", "linkedin", "github"];

/**
 * Row of SSO provider buttons. Rendered for the branded auth surface but
 * disabled for now — federated Google/LinkedIn/GitHub sign-in is not wired up
 * yet, so the buttons are presentational and announce a "coming soon" hint
 * rather than starting a flow that would fail.
 */
export function SocialButtons({ className }: { className?: string }) {
  const t = useTranslations("auth.social");

  return (
    <div className={cn("grid grid-cols-3 gap-3", className)}>
      {PROVIDERS.map((provider) => (
        <button
          key={provider}
          type="button"
          disabled
          title={t("coming_soon")}
          aria-label={`${t(provider)} — ${t("coming_soon")}`}
          className={cn(
            "inline-flex cursor-not-allowed items-center justify-center gap-2 rounded-xl border border-brand-200/80 bg-white/70",
            "px-3 py-2.5 text-sm font-medium text-gray-600 shadow-sm opacity-80"
          )}
        >
          <ProviderIcon provider={provider} />
          <span className="hidden sm:inline">{t(provider)}</span>
        </button>
      ))}
    </div>
  );
}

function ProviderIcon({ provider }: { provider: Provider }) {
  if (provider === "google") {
    return (
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
        />
        <path
          fill="#34A853"
          d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
        />
        <path
          fill="#FBBC05"
          d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
        />
        <path
          fill="#EA4335"
          d="M9 3.58c1.32 0 2.5.46 3.44 1.35l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
        />
      </svg>
    );
  }
  if (provider === "linkedin") {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="#0A66C2" aria-hidden="true">
        <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13ZM7.12 20.45H3.56V9h3.56v11.45ZM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0Z" />
      </svg>
    );
  }
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="#181717"
      aria-hidden="true"
      className="dark:fill-white"
    >
      <path d="M12 .5a12 12 0 0 0-3.79 23.4c.6.1.82-.26.82-.58v-2c-3.34.73-4.04-1.6-4.04-1.6-.55-1.4-1.34-1.77-1.34-1.77-1.1-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5 1 .1-.78.42-1.3.76-1.6-2.67-.3-5.47-1.34-5.47-5.96 0-1.32.47-2.4 1.24-3.24-.12-.3-.54-1.52.12-3.18 0 0 1-.32 3.3 1.24a11.5 11.5 0 0 1 6 0c2.3-1.56 3.3-1.24 3.3-1.24.66 1.66.24 2.88.12 3.18.77.84 1.24 1.92 1.24 3.24 0 4.63-2.8 5.65-5.48 5.95.43.37.81 1.1.81 2.22v3.29c0 .32.22.69.83.57A12 12 0 0 0 12 .5Z" />
    </svg>
  );
}
