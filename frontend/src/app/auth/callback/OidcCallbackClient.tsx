"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { authApi, tosApi, ApiError } from "@/lib/api";
import { clearToken, getPostLoginPath, setUser, toAppRole } from "@/lib/auth";
import { TosModal } from "./TosModal";

type Phase = "loading" | "tos" | "suspended" | "error";

interface TosData {
  id: string;
  version: number;
  content: string;
}

export function OidcCallbackClient() {
  const router = useRouter();
  const t = useTranslations("auth.callback");

  const [phase, setPhase] = useState<Phase>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [tosData, setTosData] = useState<TosData | null>(null);
  useEffect(() => {
    void loadCookieSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadCookieSession() {
    try {
      const user = await authApi.me();
      setUser({
        user_id: user.user_id,
        email: user.email,
        role: user.role,
        district_id: user.district_id,
        school_id: user.school_id,
        tos_acceptance_required: user.tos_acceptance_required,
        current_tos_version_id: user.current_tos_version_id,
      });

      if (user.account_status === "suspended" && !user.tos_acceptance_required) {
        setPhase("suspended");
        return;
      }

      if (user.tos_acceptance_required && user.current_tos_version_id) {
        const tos = await tosApi.getCurrent("");
        setTosData({
          id: tos.id,
          version: tos.version,
          content: tos.content,
        });
        setPhase("tos");
      } else {
        router.replace(getPostLoginPath(toAppRole(user.role)));
      }
    } catch (err) {
      console.error("OIDC callback error:", err);
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
      const user = await authApi.me();
      await tosApi.acceptTos("", tosData.id);
      router.replace(getPostLoginPath(toAppRole(user.role)));
    } catch {
      setErrorMsg(t("error.tos_accept_failed"));
      setPhase("error");
    }
  }

  async function handleTosDecline() {
    try {
      await tosApi.declineTos("");
      clearToken();
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
