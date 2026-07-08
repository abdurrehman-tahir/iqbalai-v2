"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api";

type Phase = "form" | "success";

/** Forgot-password form — always shows success to avoid enumeration (M-07b T-243). */
export function ForgotPasswordForm() {
  const t = useTranslations("auth.forgot_password");
  const [email, setEmail] = useState("");
  const [phase, setPhase] = useState<Phase>("form");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setErrorMsg("");
    setSubmitting(true);
    try {
      await authApi.forgotPassword(email.trim());
      setPhase("success");
    } catch {
      setErrorMsg(t("error.generic"));
      setSubmitting(false);
    }
  }

  if (phase === "success") {
    return (
      <div className="space-y-4 text-center" role="status">
        <p className="text-sm text-gray-700">{t("success_message")}</p>
        <Link
          href="/login"
          className="inline-flex text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          {t("back_to_login")}
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="forgot-email">{t("email_label")}</Label>
        <Input
          id="forgot-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
          placeholder={t("email_placeholder")}
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
        <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
          {t("back_to_login")}
        </Link>
      </p>
    </form>
  );
}
