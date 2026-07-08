"use client";

import { useSearchParams } from "next/navigation";
import { useState, Suspense } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authApi } from "@/lib/api";
import { AuthNavLinks } from "@/components/auth/AuthNavLinks";
import { clearSession, buildAppLoginUrl } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const acceptSchema = z
  .object({
    display_name: z.string().min(1).max(255).optional(),
    password: z.string().min(8).max(128),
    confirm_password: z.string().min(8).max(128),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "passwords_must_match",
    path: ["confirm_password"],
  });

type AcceptFormValues = z.infer<typeof acceptSchema>;

function AcceptInviteForm() {
  const t = useTranslations("auth.accept_invite");
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [done, setDone] = useState(false);
  const [acceptedEmail, setAcceptedEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<AcceptFormValues>({
    resolver: zodResolver(acceptSchema),
    defaultValues: { display_name: "", password: "", confirm_password: "" },
  });

  if (!token) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-sm text-red-700">{t("missing_token")}</p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center space-y-4">
        <p className="text-sm text-green-800">{t("success")}</p>
        <p className="text-xs text-green-700">{t("success_sign_in_hint")}</p>
        <button
          type="button"
          className="inline-flex h-10 items-center justify-center rounded-md bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
          onClick={() => {
            clearSession();
            window.location.href = buildAppLoginUrl(acceptedEmail ?? undefined);
          }}
        >
          {t("go_login")}
        </button>
      </div>
    );
  }

  async function onAccept(values: AcceptFormValues) {
    setError(null);
    setSubmitting(true);
    try {
      const result = await authApi.acceptInvite({
        token,
        action: "accept",
        password: values.password,
        display_name: values.display_name || undefined,
      });
      clearSession();
      setAcceptedEmail(result.email ?? null);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error_generic"));
    } finally {
      setSubmitting(false);
    }
  }

  async function onReject() {
    setError(null);
    setSubmitting(true);
    try {
      await authApi.acceptInvite({ token, action: "reject" });
      setError(t("declined"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error_generic"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <AuthNavLinks showSignupOptions />
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {error && (
        <p className="text-sm text-red-600 rounded-md bg-red-50 border border-red-200 p-3" role="alert">
          {error}
        </p>
      )}

      <form onSubmit={form.handleSubmit(onAccept)} className="space-y-4">
        <div>
          <Label htmlFor="display-name">{t("name_label")}</Label>
          <Input id="display-name" {...form.register("display_name")} />
        </div>
        <div>
          <Label htmlFor="password" required>
            {t("password_label")}
          </Label>
          <Input id="password" type="password" {...form.register("password")} />
        </div>
        <div>
          <Label htmlFor="confirm-password" required>
            {t("confirm_password_label")}
          </Label>
          <Input
            id="confirm-password"
            type="password"
            {...form.register("confirm_password")}
          />
        </div>
        <div className="flex flex-wrap gap-3 pt-2">
          <Button type="submit" variant="primary" size="md" loading={submitting}>
            {t("accept")}
          </Button>
          <Button type="button" variant="outline" size="md" loading={submitting} onClick={onReject}>
            {t("decline")}
          </Button>
        </div>
      </form>
    </div>
  );
}

export function AcceptInviteClient() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <Suspense fallback={<p className="text-sm text-gray-500">Loading…</p>}>
          <AcceptInviteForm />
        </Suspense>
      </div>
    </div>
  );
}
