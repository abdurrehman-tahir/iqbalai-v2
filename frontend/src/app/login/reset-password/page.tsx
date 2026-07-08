import { Suspense } from "react";
import { useTranslations } from "next-intl";
import { AuthPageShell } from "@/components/auth/AuthPageShell";
import { ResetPasswordForm } from "./ResetPasswordForm";

export default function ResetPasswordPage() {
  const t = useTranslations("auth.reset_password");

  return (
    <AuthPageShell title={t("title")} subtitle={t("subtitle")}>
      <Suspense fallback={<p className="text-sm text-gray-500">{t("loading")}</p>}>
        <ResetPasswordForm />
      </Suspense>
    </AuthPageShell>
  );
}
