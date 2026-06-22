"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { parentSignupApi } from "@/lib/api";
import { clearToken, getLoginUrl } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const signupSchema = z
  .object({
    email: z.string().email(),
    display_name: z.string().min(1).max(255),
    password: z.string().min(8).max(128),
    confirm_password: z.string().min(8).max(128),
    language_preference: z.enum(["en", "ur", "sd", "ps"]),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "passwords_must_match",
    path: ["confirm_password"],
  });

type SignupFormValues = z.infer<typeof signupSchema>;

export function ParentSignupClient() {
  const t = useTranslations("parent.signup");
  const [done, setDone] = useState(false);
  const [signedUpEmail, setSignedUpEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [languages, setLanguages] = useState<string[]>(["en", "ur", "sd", "ps"]);

  const form = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      email: "",
      display_name: "",
      password: "",
      confirm_password: "",
      language_preference: "en",
    },
  });

  useEffect(() => {
    void parentSignupApi.getInfo().then((info) => {
      if (info.languages.length > 0) setLanguages(info.languages);
    });
  }, []);

  async function onSubmit(values: SignupFormValues) {
    setError(null);
    setSubmitting(true);
    try {
      const result = await parentSignupApi.signup({
        email: values.email,
        password: values.password,
        display_name: values.display_name,
        language_preference: values.language_preference,
      });
      clearToken();
      setSignedUpEmail(result.email);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error_generic"));
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center space-y-4">
        <p className="text-sm text-green-800">{t("success")}</p>
        <button
          type="button"
          className="inline-flex h-10 items-center justify-center rounded-md bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
          onClick={() => {
            window.location.href = getLoginUrl({
              promptLogin: true,
              loginHint: signedUpEmail ?? undefined,
            });
          }}
        >
          {t("go_login")}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{t("title")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {error && (
        <p className="text-sm text-red-600 rounded-md bg-red-50 border border-red-200 p-3" role="alert">
          {error}
        </p>
      )}

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <Label htmlFor="display-name" required>{t("name_label")}</Label>
          <Input id="display-name" {...form.register("display_name")} />
        </div>

        <div>
          <Label htmlFor="email" required>{t("email_label")}</Label>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
        </div>

        <div>
          <Label htmlFor="language" required>{t("language_label")}</Label>
          <select
            id="language"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            {...form.register("language_preference")}
          >
            {languages.map((lang) => (
              <option key={lang} value={lang}>
                {t(`language_${lang}` as "language_en")}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label htmlFor="password" required>{t("password_label")}</Label>
          <Input id="password" type="password" autoComplete="new-password" {...form.register("password")} />
        </div>

        <div>
          <Label htmlFor="confirm-password" required>{t("confirm_password_label")}</Label>
          <Input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            {...form.register("confirm_password")}
          />
          {form.formState.errors.confirm_password?.message === "passwords_must_match" && (
            <p className="mt-1 text-xs text-red-600">{t("passwords_must_match")}</p>
          )}
        </div>

        <div className="flex flex-wrap gap-3 pt-2">
          <Button type="submit" variant="primary" size="md" loading={submitting}>
            {t("submit")}
          </Button>
          <Link
            href="/login"
            className="inline-flex h-10 items-center justify-center rounded-md border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            {t("have_account")}
          </Link>
        </div>
      </form>
    </div>
  );
}
