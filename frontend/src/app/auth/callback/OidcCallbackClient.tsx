"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { authApi, tosApi, ApiError } from "@/lib/api";
import { setToken, setUser, getPostLoginPath } from "@/lib/auth";
import { TosModal } from "./TosModal";
import { SuspendedPage } from "./SuspendedPage";

type Phase = "loading" | "tos" | "suspended" | "error";

interface TosData {
  id: string;
  version: number;
  content: string;
}

export function OidcCallbackClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations("auth.callback");

  const [phase, setPhase] = useState<Phase>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [tosData, setTosData] = useState<TosData | null>(null);
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  // Guard against React 18 StrictMode double-invocation: authorization codes are single-use.
  const exchangeAttempted = useRef(false);

  useEffect(() => {
    if (exchangeAttempted.current) return;
    exchangeAttempted.current = true;

    const code = searchParams.get("code");
    const error = searchParams.get("error");

    if (error) {
      setErrorMsg(t("error.auth_denied"));
      setPhase("error");
      return;
    }

    if (!code) {
      setErrorMsg(t("error.no_code"));
      setPhase("error");
      return;
    }

    // Exchange code for token via Authentik token endpoint, then call post-login
    void exchangeCode(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function exchangeCode(code: string) {
    try {
      const authentikBase =
        process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";
      const clientId =
        process.env.NEXT_PUBLIC_AUTHENTIK_CLIENT_ID ?? "iqbalai-frontend";
      const redirectUri =
        (process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000") +
        "/auth/callback";

      const res = await fetch(
        `${authentikBase}/application/o/token/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "authorization_code",
            code,
            client_id: clientId,
            redirect_uri: redirectUri,
          }),
        },
      );

      if (!res.ok) throw new Error("Token exchange failed");
      const tokenData = await res.json() as { access_token: string };
      const token = tokenData.access_token;

      setToken(token);
      setPendingToken(token);

      // Post-login to create/update user record
      const user = await authApi.postLogin(token);
      setUser({
        user_id: user.user_id,
        email: user.email,
        role: user.role,
        district_id: user.district_id,
        school_id: user.school_id,
        tos_acceptance_required: user.tos_acceptance_required,
        current_tos_version_id: user.current_tos_version_id,
      });

      if (
        user.account_status === "suspended" &&
        !user.tos_acceptance_required
      ) {
        setPhase("suspended");
        return;
      }

      if (user.tos_acceptance_required && user.current_tos_version_id) {
        // Fetch ToS content to display in modal
        const tos = await tosApi.getCurrent(token);
        setTosData({
          id: tos.id,
          version: tos.version,
          content: tos.content,
        });
        setPhase("tos");
      } else {
        router.replace(getPostLoginPath(user.role));
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
    if (!pendingToken || !tosData) return;
    try {
      await tosApi.acceptTos(pendingToken, tosData.id);
      const stored = JSON.parse(sessionStorage.getItem("iqbalai_user") ?? "{}") as {
        role?: string;
      };
      router.replace(getPostLoginPath(stored.role ?? "platform_admin"));
    } catch {
      setErrorMsg(t("error.tos_accept_failed"));
      setPhase("error");
    }
  }

  async function handleTosDecline() {
    if (!pendingToken) return;
    try {
      await tosApi.declineTos(pendingToken);
      import("@/lib/auth").then(({ clearToken }) => clearToken());
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
          <p className={phase === "suspended" ? "text-sm text-gray-600" : "text-red-600 font-medium"}>
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
        <TosModal
          tos={tosData}
          onAccept={handleTosAccept}
          onDecline={handleTosDecline}
        />
      )}
    </main>
  );
}
