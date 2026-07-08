"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { parentChildLinksApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";

const linkSchema = z.object({
  student_email: z.string().email(),
});

type LinkFormValues = z.infer<typeof linkSchema>;

export function ParentHomeClient() {
  const t = useTranslations("parent.home");
  const qc = useQueryClient();
  const { mounted, token } = useClientAuth();
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: connections } = useQuery({
    queryKey: ["parent", "connections"],
    queryFn: () => parentChildLinksApi.getConnections(token!),
    enabled: mounted && !!token,
  });

  const form = useForm<LinkFormValues>({
    resolver: zodResolver(linkSchema),
    defaultValues: { student_email: "" },
  });

  const linkMutation = useMutation({
    mutationFn: (values: LinkFormValues) =>
      parentChildLinksApi.createLinkRequest(token ?? "", values.student_email),
    onSuccess: () => {
      setError(null);
      setSuccess(t("success_request"));
      form.reset();
      void qc.invalidateQueries({ queryKey: ["parent"] });
    },
    onError: (err) => {
      setSuccess(null);
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (linkId: string) => parentChildLinksApi.revokeLink(token ?? "", linkId),
    onSuccess: () => {
      setSuccess(null);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["parent"] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  function stateLabel(state: string | undefined) {
    if (state === "LINK_PENDING") return t("state_LINK_PENDING");
    if (state === "LINKED") return t("state_LINKED");
    return t("state_PARENT_ACTIVE_UNLINKED");
  }

  function linkStatusLabel(status: string) {
    if (status === "approved") return t("link_status_approved");
    if (status === "revoked") return t("link_status_revoked");
    return t("link_status_pending");
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <DashboardHeader title={t("title")} subtitle={t("subtitle")}>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <a
            href="/parent/data-rights"
            className="text-sm font-medium text-brand-700 hover:underline"
          >
            {t("data_rights_link")}
          </a>
          {connections && (
            <span className="inline-flex items-center rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-medium text-brand-700">
              {t("state_label")}: {stateLabel(connections.parent_state)}
            </span>
          )}
        </div>
      </DashboardHeader>

      {success && (
        <p className="text-sm text-green-800 rounded-md bg-green-50 border border-green-200 p-3">
          {success}
        </p>
      )}
      {error && (
        <p
          className="text-sm text-red-600 rounded-md bg-red-50 border border-red-200 p-3"
          role="alert"
        >
          {error}
        </p>
      )}

      <form
        onSubmit={form.handleSubmit((values) => {
          setSuccess(null);
          setError(null);
          linkMutation.mutate(values);
        })}
        className="space-y-4 rounded-2xl border border-brand-100 bg-white p-6 shadow-sm"
      >
        <div>
          <Label htmlFor="student-email" required>
            {t("student_email_label")}
          </Label>
          <Input id="student-email" type="email" {...form.register("student_email")} />
        </div>
        <Button type="submit" variant="primary" loading={linkMutation.isPending}>
          {t("submit_link")}
        </Button>
      </form>

      <section className="space-y-3">
        <h3 className="text-lg font-medium text-gray-900">{t("links_title")}</h3>
        {!connections?.links.length ? (
          <p className="text-sm text-gray-500">{t("links_empty")}</p>
        ) : (
          <ul className="divide-y divide-gray-200 rounded-2xl border border-brand-100 bg-white shadow-sm">
            {connections.links.map((link) => (
              <li
                key={link.id}
                className="px-4 py-3 text-sm flex justify-between gap-4 items-center"
              >
                <div>
                  <span>{link.student_name ?? link.student_email ?? link.student_user_id}</span>
                  {link.read_only_access && (
                    <span className="ms-2 text-xs text-brand-700">{t("read_only_badge")}</span>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-gray-500">{linkStatusLabel(link.status)}</span>
                  {link.status === "approved" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={revokeMutation.isPending}
                      onClick={() => revokeMutation.mutate(link.id)}
                    >
                      {t("revoke_link")}
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
