"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { authApi, tosApi, ApiError } from "@/lib/api";
import { getPostLoginPath } from "@/lib/auth";
import { useClientAuth } from "@/hooks/use-client-auth";
import { TosModal } from "./TosModal";

type Phase = "loading" | "tos" | "suspended" | "error";

interface TosData {
  id: string;
  version: number;
  content: string;
}

/**
 * T-245: the OIDC code+PKCE exchange happens entirely server-side now
 * (T-244's GET /api/v1/auth/callback) — the browser is redirected straight
 * to the role dashboard, or here with `?tos_required=1` if the just-logged-in
 * user still needs to accept the current ToS. This page's only job is
 * resolving that one case; it never sees a `code` or exchanges anything.
 */
export function OidcCallbackClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations("auth.callback");
  const { token } = useClientAuth();

  const [phase, setPhase] = useState<Phase>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [tosData, setTosData] = useState<TosData | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const loadAttempted = useRef(false);

  useEffect(() => {
    if (loadAttempted.current) return;
    loadAttempted.current = true;

    if (searchParams.get("tos_required") !== "1") {
      router.replace("/login");
      return;
    }

    void loadTos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadTos() {
    try {
      const me = await authApi.me();
      setRole(me.role);
      const tos = await tosApi.getCurrent(token ?? "");
      setTosData({ id: tos.id, version: tos.version, content: tos.content });
      setPhase("tos");
    } catch (err) {
      console.error("OIDC callback ToS load error:", err);
      if (err instanceof ApiError && err.code === "ACCOUNT_SUSPENDED") {
        setErrorMsg(t("error.account_suspended"));
        setPhase("suspended");
        return;
      }
      setErrorMsg(t("error.generic"));
      setPhase("error");
    }
  }

  async function handleTosAccept() {
    if (!tosData) return;
    try {
      await tosApi.acceptTos(token ?? "", tosData.id);
      router.replace(getPostLoginPath(role ?? "platform_admin"));
    } catch {
      setErrorMsg(t("error.tos_accept_failed"));
      setPhase("error");
    }
  }

  async function handleTosDecline() {
    try {
      await tosApi.declineTos(token ?? "");
      setPhase("suspended");
    } catch {
      setErrorMsg(t("error.tos_decline_failed"));
      setPhase("error");
    }
  }

  if (phase === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span
            className="size-10 animate-spin rounded-full border-4 border-brand-200 border-t-brand-600"
            aria-hidden="true"
          />
          <p className="text-sm text-gray-500">{t("loading")}</p>
        </div>
      </main>
    );
  }

  if (phase === "error" || phase === "suspended") {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <div className="max-w-sm text-center space-y-4">
          <h1 className={phase === "suspended" ? "text-lg font-semibold text-gray-900" : undefined}>
            {phase === "suspended" ? t("suspended.title") : undefined}
          </h1>
          <p
            className={phase === "suspended" ? "text-sm text-gray-600" : "text-red-600 font-medium"}
          >
            {errorMsg || (phase === "suspended" ? t("suspended.message") : "")}
          </p>
          <a href="/login" className="text-sm text-brand-600 underline">
            {t("error.back_to_login")}
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      {tosData && (
        <TosModal tos={tosData} onAccept={handleTosAccept} onDecline={handleTosDecline} />
      )}
    </main>
  );
}
