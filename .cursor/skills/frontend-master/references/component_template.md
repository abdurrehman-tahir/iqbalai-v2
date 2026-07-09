# Canonical component template

This is the canonical full-feature pattern from `ARCHITECTURE.md` §12.22. Copy it as the starting point for any new feature page.

It demonstrates:
- Server Component (page) + Client Component (interactive list) split
- TanStack Query for data
- All four UI states (loading skeleton, empty state, error state, success)
- next-intl translation keys throughout
- shadcn/ui primitives
- React-hook-form + Zod for the inline form
- Logical Tailwind utilities (RTL-aware)
- Accessibility (labels, ARIA, semantic HTML)
- next/image (in the card component)
- Optimistic mutation with rollback
- Cursor-based pagination support

## File layout

```
frontend/src/
├── app/
│   └── lectures/
│       ├── page.tsx                       — Server Component (entry point)
│       └── new/
│           └── page.tsx                   — Server Component (new lecture form)
├── features/
│   └── lectures/
│       ├── api.ts                         — apiClient calls
│       ├── schemas.ts                     — Zod schemas
│       ├── components/
│       │   ├── lecture-list-client.tsx    — Client Component (the list)
│       │   ├── lecture-list-skeleton.tsx  — loading state
│       │   ├── lecture-card.tsx           — list item
│       │   └── lecture-form.tsx           — create form
│       └── hooks/
│           └── use-lectures.ts            — TanStack Query hooks
└── messages/
    ├── en.json
    ├── ur.json
    ├── sd.json
    └── ps.json
```

## `app/lectures/page.tsx` — Server Component

```tsx
import { getTranslations } from "next-intl/server";

import { LectureListClient } from "@/features/lectures/components/lecture-list-client";

export async function generateMetadata() {
  const t = await getTranslations("lectures.list");
  return { title: t("title"), description: t("meta.description") };
}

export default async function LecturesPage() {
  const t = await getTranslations("lectures.list");
  return (
    <main className="container mx-auto px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">{t("title")}</h1>
      </header>
      <LectureListClient />
    </main>
  );
}
```

Notice:
- `"use client"` is NOT at the top — this is a Server Component
- No data fetching here at the page level (the client component does its own fetch + caching); could also pre-fetch on the server and hydrate
- `getTranslations` (server-side) instead of `useTranslations`
- The page is a thin shell; the interactive part is in `LectureListClient`

## `features/lectures/api.ts` — apiClient calls

```tsx
import { apiClient } from "@/lib/api";
import type { LectureRead, LectureCreate } from "./schemas";

export const lecturesApi = {
  list: async (params?: { cursor?: string; limit?: number }) =>
    apiClient.get<{ items: LectureRead[]; next_cursor: string | null }>("/lectures", { params }),

  get: async (id: string) =>
    apiClient.get<LectureRead>(`/lectures/${id}`),

  create: async (payload: LectureCreate) =>
    apiClient.post<LectureRead>("/lectures", payload),

  delete: async (id: string) =>
    apiClient.delete(`/lectures/${id}`),
};
```

## `features/lectures/schemas.ts` — Zod + TS types

```tsx
import { z } from "zod";

export const lectureCreateSchema = z.object({
  title: z.string().min(1).max(500),
  topicId: z.string().uuid(),
});

export type LectureCreate = z.infer<typeof lectureCreateSchema>;

export interface LectureRead {
  id: string;
  title: string;
  status: "draft" | "published" | "archived";
  created_at: string;
  updated_at: string;
}
```

## `features/lectures/hooks/use-lectures.ts` — TanStack Query

```tsx
"use client";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { lecturesApi } from "@/features/lectures/api";
import type { LectureCreate, LectureRead } from "@/features/lectures/schemas";

const KEYS = {
  all: ["lectures"] as const,
  list: () => [...KEYS.all, "list"] as const,
  byId: (id: string) => [...KEYS.all, "byId", id] as const,
};

export function useLecturesList() {
  return useInfiniteQuery({
    queryKey: KEYS.list(),
    queryFn: ({ pageParam }) => lecturesApi.list({ cursor: pageParam }),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    initialPageParam: undefined as string | undefined,
  });
}

export function useCreateLecture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LectureCreate) => lecturesApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.list() }),
  });
}

export function useDeleteLecture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => lecturesApi.delete(id),
    onMutate: async (id) => {
      // Optimistic update
      await qc.cancelQueries({ queryKey: KEYS.list() });
      const previous = qc.getQueryData(KEYS.list());
      qc.setQueryData(KEYS.list(), (old: any) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page: any) => ({
            ...page,
            items: page.items.filter((l: LectureRead) => l.id !== id),
          })),
        };
      });
      return { previous };
    },
    onError: (_, __, context) => {
      // Rollback
      if (context?.previous) {
        qc.setQueryData(KEYS.list(), context.previous);
      }
    },
    onSettled: () => qc.invalidateQueries({ queryKey: KEYS.list() }),
  });
}
```

## `features/lectures/components/lecture-list-client.tsx`

```tsx
"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

import { useLecturesList } from "../hooks/use-lectures";
import { LectureCard } from "./lecture-card";
import { LectureListSkeleton } from "./lecture-list-skeleton";

export function LectureListClient() {
  const t = useTranslations("lectures.list");

  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useLecturesList();

  if (isLoading) {
    return <LectureListSkeleton />;
  }

  if (isError) {
    return (
      <ErrorState
        title={t("error.title")}
        description={t("error.description")}
        onRetry={refetch}
      />
    );
  }

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  if (items.length === 0) {
    return (
      <EmptyState
        title={t("empty.title")}
        description={t("empty.description")}
        action={{ label: t("empty.cta"), href: "/lectures/new" }}
      />
    );
  }

  return (
    <>
      <ul
        role="list"
        className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
      >
        {items.map((lecture) => (
          <li key={lecture.id}>
            <LectureCard lecture={lecture} />
          </li>
        ))}
      </ul>
      {hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="outline"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? t("loading_more") : t("load_more")}
          </Button>
        </div>
      )}
    </>
  );
}
```

## `features/lectures/components/lecture-list-skeleton.tsx`

```tsx
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslations } from "next-intl";

export function LectureListSkeleton() {
  const t = useTranslations("common.status");
  return (
    <div
      role="status"
      aria-label={t("loading")}
      className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-40 w-full rounded-lg" />
      ))}
    </div>
  );
}
```

## `features/lectures/components/lecture-card.tsx`

```tsx
"use client";
import Image from "next/image";
import Link from "next/link";
import { ChevronEnd } from "lucide-react";   // hypothetical "end" chevron; in practice ChevronRight + rtl:rotate-180
import { useTranslations, useFormatter } from "next-intl";

import { Badge } from "@/components/ui/badge";
import type { LectureRead } from "../schemas";

interface Props { lecture: LectureRead; }

export function LectureCard({ lecture }: Props) {
  const t = useTranslations("lectures.card");
  const format = useFormatter();

  return (
    <Link
      href={`/lectures/${lecture.id}`}
      className="group flex flex-col rounded-lg border bg-card p-4 transition hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between">
        <h3 className="font-medium text-foreground line-clamp-2">{lecture.title}</h3>
        <ChevronRight
          className="size-4 shrink-0 text-muted-foreground rtl:rotate-180"
          aria-hidden="true"
        />
      </div>
      <div className="mt-auto pt-4 flex items-center justify-between text-sm text-muted-foreground">
        <Badge variant={lecture.status === "published" ? "default" : "secondary"}>
          {t(`status.${lecture.status}`)}
        </Badge>
        <time dateTime={lecture.created_at}>
          {format.dateTime(new Date(lecture.created_at), { dateStyle: "medium" })}
        </time>
      </div>
    </Link>
  );
}
```

## `features/lectures/components/lecture-form.tsx`

```tsx
"use client";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

import { lectureCreateSchema, type LectureCreate } from "../schemas";
import { useCreateLecture } from "../hooks/use-lectures";

export function LectureForm() {
  const t = useTranslations("lectures.form");
  const tErr = useTranslations("common.error");
  const router = useRouter();
  const create = useCreateLecture();

  const form = useForm<LectureCreate>({
    resolver: zodResolver(lectureCreateSchema),
    defaultValues: { title: "", topicId: "" },
  });

  const onSubmit = async (values: LectureCreate) => {
    try {
      const lecture = await create.mutateAsync(values);
      toast.success(t("created"));
      router.push(`/lectures/${lecture.id}`);
    } catch (err: any) {
      // Map server-side field errors onto the form
      const details = err?.response?.data?.error?.details;
      if (Array.isArray(details)) {
        details.forEach((d: { field: string; message: string }) => {
          form.setError(d.field as any, { message: d.message });
        });
      } else {
        const code = err?.response?.data?.error?.code ?? "INTERNAL_ERROR";
        toast.error(tErr(code as any));
      }
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("title.label")}</FormLabel>
              <FormControl>
                <Input placeholder={t("title.placeholder")} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="topicId"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("topic.label")}</FormLabel>
              <FormControl>
                {/* TopicCombobox component would go here; uses @/components/ui/combobox */}
                <Input placeholder={t("topic.placeholder")} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.back()}
          >
            {t("cancel")}
          </Button>
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? t("submitting") : t("submit")}
          </Button>
        </div>
      </form>
    </Form>
  );
}
```

## Translation keys used

```json
{
  "common": {
    "actions": {},
    "error": {
      "VALIDATION_ERROR": "...",
      "INTERNAL_ERROR": "..."
    },
    "status": {
      "loading": "Loading…"
    }
  },
  "lectures": {
    "list": {
      "title": "Lectures",
      "meta": { "description": "..." },
      "empty": { "title": "...", "description": "...", "cta": "..." },
      "error": { "title": "...", "description": "..." },
      "load_more": "Load more",
      "loading_more": "Loading more…"
    },
    "card": {
      "status": {
        "draft": "Draft",
        "published": "Published",
        "archived": "Archived"
      }
    },
    "form": {
      "title": {
        "label": "Lecture title",
        "placeholder": "e.g. Newton's Laws of Motion"
      },
      "topic": {
        "label": "Topic",
        "placeholder": "Select a topic"
      },
      "submit": "Create",
      "submitting": "Creating…",
      "cancel": "Cancel",
      "created": "Lecture created"
    }
  }
}
```

## What this template demonstrates (checklist)

When using this template for a new feature, verify these are all present:

- [ ] Server Component for the page, `"use client"` pushed down
- [ ] TanStack Query hooks in `hooks/use-<feature>.ts`
- [ ] Zod schema in `schemas.ts`, types derived via `z.infer`
- [ ] All four UI states (loading skeleton, empty state, error state, success)
- [ ] Every visible string via `useTranslations` / `getTranslations`
- [ ] All 4 message files (en/ur/sd/ps) updated with the same keys
- [ ] shadcn/ui primitives (`Button`, `Input`, `Form`, `Badge`, `Skeleton`)
- [ ] Logical Tailwind utilities (`me-`, `ms-`, `text-start`, etc.) where direction matters
- [ ] Icons via lucide-react; directional icons have `rtl:rotate-180`
- [ ] react-hook-form + zodResolver for the form
- [ ] Server errors mapped to form fields via `form.setError`
- [ ] Optimistic mutation with rollback on the delete path
- [ ] Cursor-based infinite pagination (matching §5.6)
- [ ] `next/image` (where images appear) — not raw `<img>`
- [ ] Semantic HTML (`<ul role="list">`, `<time dateTime>`, `<main>`, `<header>`)
- [ ] Visible focus styles preserved (no `outline-none` without replacement)
