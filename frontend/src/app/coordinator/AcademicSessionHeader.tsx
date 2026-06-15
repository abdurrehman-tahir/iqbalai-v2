"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Calendar, ChevronDown } from "lucide-react";
import { academicSessionsApi, ApiError } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const sessionSchema = z.object({
  label: z.string().min(1).max(50),
});

type SessionFormValues = z.infer<typeof sessionSchema>;

export function AcademicSessionHeader() {
  const t = useTranslations("coordinator.sessions");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [showManage, setShowManage] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: active } = useQuery({
    queryKey: ["academic-sessions", "active"],
    queryFn: () => academicSessionsApi.getActive(token!),
    enabled: mounted && !!token,
  });

  const { data: sessions } = useQuery({
    queryKey: ["academic-sessions", "list"],
    queryFn: () => academicSessionsApi.list(token!),
    enabled: mounted && !!token && showManage,
  });

  const form = useForm<SessionFormValues>({
    resolver: zodResolver(sessionSchema),
    defaultValues: { label: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: SessionFormValues) =>
      academicSessionsApi.create(token ?? "", { ...values, set_active: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["academic-sessions"] });
      setShowManage(false);
      form.reset();
    },
    onError: (err: unknown) => {
      setFormError(err instanceof ApiError && err.status === 409 ? t("duplicate_error") : t("generic_error"));
    },
  });

  const activateMutation = useMutation({
    mutationFn: (id: string) => academicSessionsApi.activate(token ?? "", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["academic-sessions"] }),
  });

  const activeLabel = active?.label ?? null;

  return (
    <>
      <div className="flex items-center gap-2 text-sm">
        <Calendar className="size-4 text-gray-500" aria-hidden="true" />
        <span className="text-gray-600">
          {activeLabel ? t("active_label", { label: activeLabel }) : t("no_active")}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="gap-1 h-8 px-2"
          onClick={() => setShowManage(true)}
          aria-label={t("manage_button")}
        >
          {t("manage_button")}
          <ChevronDown className="size-3" aria-hidden="true" />
        </Button>
      </div>

      <Modal
        open={showManage}
        onClose={() => {
          setShowManage(false);
          setFormError(null);
          form.reset();
        }}
        title={t("manage_title")}
      >
        <div className="space-y-6">
          {sessions && sessions.length > 0 && (
            <ul className="space-y-2" aria-label={t("list_label")}>
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2"
                >
                  <span className={s.is_active ? "font-medium text-brand-700" : "text-gray-700"}>
                    {s.label}
                    {s.is_active && (
                      <span className="ms-2 text-xs text-brand-600">({t("active_badge")})</span>
                    )}
                  </span>
                  {!s.is_active && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => activateMutation.mutate(s.id)}
                      disabled={activateMutation.isPending}
                    >
                      {t("set_active")}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}

          <form
            onSubmit={form.handleSubmit((values) => {
              setFormError(null);
              createMutation.mutate(values);
            })}
            className="space-y-4 border-t border-gray-100 pt-4"
          >
            <div>
              <Label htmlFor="session-label">{t("label_field")}</Label>
              <Input
                id="session-label"
                placeholder={t("label_placeholder")}
                {...form.register("label")}
              />
              {form.formState.errors.label && (
                <p className="mt-1 text-sm text-red-600">{t("label_required")}</p>
              )}
            </div>
            {formError && <p className="text-sm text-red-600">{formError}</p>}
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setShowManage(false);
                  setFormError(null);
                }}
              >
                {t("cancel")}
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {t("create_and_activate")}
              </Button>
            </div>
          </form>
        </div>
      </Modal>
    </>
  );
}
