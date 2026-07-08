"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi, ApiError } from "@/lib/api";

type Phase = "form" | "success" | "missing_token";

/** Reset password with token from recovery email (M-07b T-243). */
export function ResetPasswordForm() {
  const t = useTranslations("auth.reset_password");
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [phase, setPhase] = useState<Phase>(token ? "form" : "missing_token");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setErrorMsg("");

    if (password.length < 8) {
      setErrorMsg(t("error.password_too_short"));
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg(t("error.passwords_must_match"));
      return;
    }

    setSubmitting(true);
    try {
      await authApi.resetPassword(token, password);
      setPhase("success");
    } catch (err) {
      if (err instanceof ApiError && err.code === "INVALID_RESET_TOKEN") {
        setErrorMsg(t("error.invalid_token"));
      } else {
        setErrorMsg(t("error.generic"));
      }
      setSubmitting(false);
    }
  }

  if (phase === "missing_token") {
    return (
      <div className="space-y-4 text-center" role="alert">
        <p className="text-sm text-red-600">{t("missing_token")}</p>
        <Link
          href="/login/forgot-password"
          className="inline-flex text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          {t("request_new_link")}
        </Link>
      </div>
    );
  }

  if (phase === "success") {
    return (
      <div className="space-y-4 text-center" role="status">
        <p className="text-sm text-green-800">{t("success_message")}</p>
        <Link
          href="/login"
          className="inline-flex h-10 items-center justify-center rounded-md bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
        >
          {t("go_login")}
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="reset-password">{t("password_label")}</Label>
        <div className="relative">
          <Input
            id="reset-password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            placeholder={t("password_placeholder")}
            className="pe-16"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute inset-y-0 end-0 flex items-center pe-3 text-xs font-medium text-brand-600"
            aria-pressed={showPassword}
          >
            {showPassword ? t("hide_password") : t("show_password")}
          </button>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="reset-confirm-password">{t("confirm_password_label")}</Label>
        <Input
          id="reset-confirm-password"
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          required
          minLength={8}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          disabled={submitting}
          placeholder={t("confirm_password_placeholder")}
        />
      </div>

      {errorMsg ? (
        <p className="text-sm font-medium text-red-600" role="alert">
          {errorMsg}
        </p>
      ) : null}

      <Button type="submit" variant="primary" size="lg" className="w-full" disabled={submitting}>
        {submitting ? t("submitting") : t("submit")}
      </Button>

      <p className="text-center text-sm">
        <Link
          href="/login/forgot-password"
          className="font-medium text-brand-600 hover:text-brand-700"
        >
          {t("request_new_link")}
        </Link>
      </p>
    </form>
  );
}
