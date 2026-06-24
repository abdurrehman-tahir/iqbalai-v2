# The four UI states — full anatomy

Per `docs/ARCHITECTURE.md` §12.8.

**The rule:** every component that displays data (or could display data) must explicitly handle all four states. Skeleton on load, EmptyState when there's nothing, ErrorState when fetching fails, and the actual content on success. This is the most-enforced frontend rule because it's the most-violated one in AI-generated UI code.

The reason it matters: when one screen has the four states and the next screen just shows blank-then-pop-in, users feel like they're using two different apps. Consistency across the surface is a feature.

## When the rule applies

The component fetches from the API, OR shows a list that could be empty, OR shows a single item that could be missing → all four states required.

The component shows static content (a static page, a help text block) → no fetching, no states required.

The component is a leaf primitive like a `Button` → it doesn't fetch; it just renders → no states required.

## The shape

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { apiClient } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";

export function LectureList({ classId }: { classId: string }) {
  const t = useTranslations("lectures.list");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["lectures", "byClass", classId],
    queryFn: () => apiClient.lectures.listByClass(classId),
  });

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

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon="BookOpen"
        title={t("empty.title")}
        description={t("empty.description")}
        action={{ label: t("empty.cta"), href: "/lectures/new" }}
      />
    );
  }

  return (
    <ul role="list" className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {data.map((lecture) => (
        <LectureCard key={lecture.id} lecture={lecture} />
      ))}
    </ul>
  );
}

// Skeleton matches the eventual content shape — same grid, same card height
function LectureListSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading lectures"
      className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-40 w-full rounded-lg" />
      ))}
    </div>
  );
}
```

## The four states explained

### 1. Loading — skeleton, not spinner

A `Skeleton` is a placeholder shaped like the eventual content. It tells the user *"the page works; the data is coming."* A spinner tells them *"something is happening but I don't know what."*

Rules:
- Use `Skeleton` from `@/components/ui/skeleton` (shadcn primitive)
- The skeleton's shape **matches the eventual content** — same grid layout, same card height
- Wrap the whole skeleton in `role="status"` + `aria-label` for screen readers
- For very short loads (<200ms) that would cause a "flash of skeleton," consider not rendering a skeleton at all — TanStack Query's `isFetching` distinction can help; usually not worth optimizing for at launch

When a spinner IS appropriate:
- Inside a button that's submitting a form (`<Loader2 className="animate-spin" />` inside the button)
- For genuinely indeterminate background work where the user is waiting on a specific action they just took

### 2. Empty — title + description + CTA

An `EmptyState` is not the absence of UI. It's a UI state that says *"there's nothing here yet, and here's what to do about it."*

Required props:
- `title` — short, in the user's language ("No lectures yet")
- `description` — what this list shows when populated, plus the next action ("Create your first lecture to get started")
- `action` — a CTA button or link to do the thing

Optional:
- `icon` — a lucide-react icon name (`BookOpen`, `Inbox`, `Users`)
- `secondary action` — a secondary link (e.g., "Or import from a template")

The canonical component (lives at `@/components/empty-state.tsx`):

```tsx
import { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface EmptyStateProps {
  icon?: string;
  title: string;
  description: string;
  action?: { label: string; href?: string; onClick?: () => void };
  secondary?: { label: string; href?: string; onClick?: () => void };
}

export function EmptyState({ icon, title, description, action, secondary }: EmptyStateProps) {
  return (
    <div
      role="status"
      className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card p-12 text-center"
    >
      {/* icon would resolve via a small icon-name registry */}
      <h3 className="mt-4 text-lg font-semibold text-foreground">{title}</h3>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">{description}</p>
      <div className="mt-6 flex gap-3">
        {action && (
          action.href ? (
            <Button asChild><Link href={action.href}>{action.label}</Link></Button>
          ) : (
            <Button onClick={action.onClick}>{action.label}</Button>
          )
        )}
        {secondary && (
          secondary.href ? (
            <Button variant="outline" asChild><Link href={secondary.href}>{secondary.label}</Link></Button>
          ) : (
            <Button variant="outline" onClick={secondary.onClick}>{secondary.label}</Button>
          )
        )}
      </div>
    </div>
  );
}
```

**Anti-patterns:**

```tsx
// WRONG — bare "No data" text
if (!data?.length) return <p>No lectures.</p>;

// WRONG — hiding the UI entirely
if (!data?.length) return null;

// WRONG — confusing the user with a permission denial
if (!data?.length) return <p>You don't have access to lectures.</p>;
// (use the API's 403 with PERMISSION_DENIED for that, not the empty state)
```

### 3. Error — inline, with retry

When fetching fails, the user needs:
- To know something failed (not a silent blank screen)
- To know what to do (retry, or contact someone)
- To not lose the rest of the page (don't kill the whole layout)

The canonical component (lives at `@/components/error-state.tsx`):

```tsx
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslations } from "next-intl";

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({ title, description, onRetry }: ErrorStateProps) {
  const t = useTranslations("common.error");
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center"
    >
      <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
      <h3 className="mt-3 text-base font-semibold text-foreground">
        {title ?? t("generic")}
      </h3>
      {description && (
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {onRetry && (
        <Button variant="outline" onClick={onRetry} className="mt-4">
          {t("retry")}
        </Button>
      )}
    </div>
  );
}
```

Rules:
- `role="alert"` so screen readers announce it
- An icon + text — color is never the only signal
- A retry callback when the operation is genuinely retryable (most reads are)
- For mutation errors, show a toast (sonner) + leave the form populated so the user can retry their submission

**Anti-patterns:**

```tsx
// WRONG — error displayed only as toast, leaving blank UI
if (isError) { toast.error("Failed"); return null; }

// WRONG — full-page error obliterating navigation
if (isError) return <FullPageError />;

// WRONG — leaking technical error messages
if (isError) return <p>{error.message}</p>;
// (display a friendly message; log the technical details to telemetry)
```

### 4. Success — the actual content

The success state is just the rendered content. Important sub-rules:

- The component renders without "ghosting" — no Skeleton AND real content showing at once
- If the list is large (>50 items), virtualize with `@tanstack/react-virtual` or paginate via cursors per §5.6
- For optimistic updates on mutations, render the optimistic state immediately and reconcile on success/rollback on failure

## Variants

### Inline state (small component, not full page)

If the component sits within a larger page (e.g., a side panel showing recent activity), the states are smaller too:

- Loading: a small Skeleton matching the panel size
- Empty: a single-line `<p>` with muted styling — full EmptyState is too heavy
- Error: a `<button>` saying "Retry" with an icon — full ErrorState is too heavy

The principle is the same; the visual weight scales.

### Pagination state

When loading subsequent pages of a paginated list:

- Show existing items (don't blank the list)
- Show a small loading indicator below the list while fetching the next page
- If the next page errors, show a retry button at the bottom — don't disrupt items already shown

```tsx
{data?.pages.map((page) => page.items.map((item) => <Item key={item.id} item={item} />))}
{isFetchingNextPage && <div className="py-4 text-center"><Spinner /></div>}
{nextPageError && <Button onClick={fetchNextPage}>{t("load_more")}</Button>}
{hasNextPage && !isFetchingNextPage && (
  <Button onClick={fetchNextPage} variant="ghost">{t("load_more")}</Button>
)}
```

### Streaming state (SSE / WebSocket)

Per §12.17, streaming responses (e.g., lecture Q&A) show:

1. Loading skeleton while waiting for first chunk
2. Render chunks as they arrive (no spinner during streaming)
3. A subtle "streaming" indicator (cursor blink, "thinking" badge) on the active message
4. Error inline on the message if the stream fails mid-flight
5. Final state when stream completes — citations, action buttons appear

## How to check this rule yourself

Before generating a fetch-using component, write the four states first as comments:

```tsx
function MyComponent() {
  // LOADING: skeleton matching final grid shape
  // EMPTY: title + description + CTA "Create your first X"
  // ERROR: inline alert with retry
  // SUCCESS: render the list
}
```

Then fill them in. If you can't articulate one of them clearly, that's a sign the component is doing too much — split it.
