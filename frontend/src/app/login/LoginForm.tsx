"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Eye, EyeOff, Lock, LogIn, Mail, ShieldCheck, User } from "lucide-react";
import { Input } from "@/components/ui/input";
import { SocialButtons } from "@/components/auth/SocialButtons";
import { authApi, tosApi, ApiError } from "@/lib/api";
import { COOKIE_AUTH, setUser, clearSession, getPostLoginPath } from "@/lib/auth";
import { TosModal } from "@/app/auth/callback/TosModal";

type Phase = "form" | "tos" | "suspended";

interface TosData {
  id: string;
  version: number;
  content: string;
}

/**
 * Branded email + password login (M-07b T-241). Credentials go to our API
 * (`POST /auth/login`, BFF pattern) — never to the Authentik UI. On success the
 * server sets HttpOnly cookies; post-login/ToS redirect uses the cookie session.
 */
export function LoginForm() {
  return (
    <Suspense fallback={null}>
      <LoginFormInner />
    </Suspense>
  );
}

function LoginFormInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations("auth.login_form");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const [phase, setPhase] = useState<Phase>("form");
  const [role, setRole] = useState("platform_admin");
  const [tosData, setTosData] = useState<TosData | null>(null);

  useEffect(() => {
    const hint = searchParams.get("email");
    if (hint) setEmail(hint);
  }, [searchParams]);

  function messageForError(err: unknown): string {
    if (err instanceof ApiError) {
      switch (err.code) {
        case "INVALID_CREDENTIALS":
          return t("error.invalid_credentials");
        case "ACCOUNT_SUSPENDED":
          return t("error.account_suspended");
        case "EMAIL_NOT_VERIFIED":
          return t("error.email_not_verified");
        case "RATE_LIMITED":
          return t("error.rate_limited");
      }
    }
    return t("error.generic");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setErrorMsg("");
    setSubmitting(true);
    try {
      const user = await authApi.login({ email: email.trim(), password });
      setUser({
        user_id: user.user_id,
        email: user.email,
        role: user.role,
        district_id: user.district_id,
        school_id: user.school_id,
        tos_acceptance_required: user.tos_acceptance_required,
        current_tos_version_id: user.current_tos_version_id,
      });
      setRole(user.role);

      if (user.account_status === "suspended" && !user.tos_acceptance_required) {
        setPhase("suspended");
        return;
      }

      if (user.tos_acceptance_required && user.current_tos_version_id) {
        const tos = await tosApi.getCurrent(COOKIE_AUTH);
        setTosData({ id: tos.id, version: tos.version, content: tos.content });
        setPhase("tos");
        return;
      }

      router.replace(getPostLoginPath(user.role));
    } catch (err) {
      setErrorMsg(messageForError(err));
      setSubmitting(false);
    }
  }

  async function handleTosAccept() {
    if (!tosData) return;
    await tosApi.acceptTos(COOKIE_AUTH, tosData.id);
    router.replace(getPostLoginPath(role));
  }

  async function handleTosDecline() {
    try {
      await tosApi.declineTos(COOKIE_AUTH);
      await authApi.logout();
    } finally {
      clearSession();
      setPhase("suspended");
    }
  }

  if (phase === "tos" && tosData) {
    return <TosModal tos={tosData} onAccept={handleTosAccept} onDecline={handleTosDecline} />;
  }

  if (phase === "suspended") {
    return (
      <div className="space-y-4 text-center" role="alert">
        <h2 className="text-lg font-semibold text-gray-900">{t("suspended_title")}</h2>
        <p className="text-sm text-gray-600">{t("suspended_message")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SocialButtons />

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-brand-200" />
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          {t("or_email")}
        </span>
        <span className="h-px flex-1 bg-brand-200" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <div className="space-y-1.5">
          <label
            htmlFor="login-email"
            className="flex items-center gap-2 text-sm font-semibold text-gray-800"
          >
            <Mail className="size-4 text-brand-600" aria-hidden="true" />
            {t("email_label")}
          </label>
          <div className="relative">
            <Input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              placeholder={t("email_placeholder")}
              className="h-12 rounded-xl border-brand-200 pe-11 focus:border-brand-500 focus:ring-brand-500"
            />
            <User
              className="pointer-events-none absolute inset-y-0 end-3 my-auto size-5 text-gray-400"
              aria-hidden="true"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="login-password"
              className="flex items-center gap-2 text-sm font-semibold text-gray-800"
            >
              <Lock className="size-4 text-brand-600" aria-hidden="true" />
              {t("password_label")}
            </label>
            <Link
              href="/login/forgot-password"
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              {t("forgot_password")}
            </Link>
          </div>
          <div className="relative">
            <Input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              placeholder={t("password_placeholder")}
              className="h-12 rounded-xl border-brand-200 pe-11 focus:border-brand-500 focus:ring-brand-500"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute inset-y-0 end-2 flex items-center rounded-md px-1.5 text-gray-400 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              aria-pressed={showPassword}
              aria-label={showPassword ? t("hide_password") : t("show_password")}
            >
              {showPassword ? (
                <EyeOff className="size-5" aria-hidden="true" />
              ) : (
                <Eye className="size-5" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <label className="inline-flex items-center gap-2 text-gray-700">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="size-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
            />
            {t("remember_device")}
          </label>
          <span className="inline-flex items-center gap-1.5 font-medium text-brand-700">
            <ShieldCheck className="size-4" aria-hidden="true" />
            {t("secure_connection")}
          </span>
        </div>

        {errorMsg && (
          <p className="text-sm font-medium text-red-600" role="alert">
            {errorMsg}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-brand-600 text-lg font-semibold text-white shadow-md shadow-brand-600/20 transition-colors hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-60"
        >
          {submitting ? (
            <>
              <span
                className="size-5 animate-spin rounded-full border-2 border-current border-t-transparent"
                aria-hidden="true"
              />
              {t("submitting")}
            </>
          ) : (
            <>
              <LogIn className="size-5" aria-hidden="true" />
              {t("submit")}
            </>
          )}
        </button>
      </form>

      <p className="text-center text-sm text-gray-600">
        {t("no_account")}{" "}
        <Link href="/signup" className="font-medium text-brand-600 hover:text-brand-700">
          {t("create_account")}
        </Link>
      </p>
    </div>
  );
}
