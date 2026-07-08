import { useTranslations } from "next-intl";
import { AuthPageShell } from "@/components/auth/AuthPageShell";
import { ForgotPasswordForm } from "./ForgotPasswordForm";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth.forgot_password");

  return (
    <AuthPageShell title={t("title")} subtitle={t("subtitle")}>
      <ForgotPasswordForm />
    </AuthPageShell>
  );
}
