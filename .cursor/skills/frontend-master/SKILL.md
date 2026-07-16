---
name: frontend-master
description: |
  Enforce the IqbalAI v2 frontend patterns from ARCHITECTURE.md §12 and §13 — four UI states
  on every component, accessibility (WCAG 2.1 AA), Tailwind design tokens (no inline styles,
  no raw hex), next-intl translation keys (no hardcoded English in JSX), Server Components
  by default with "use client" pushed down, TanStack Query for server state, react-hook-form
  with Zod for forms, Zustand only when justified, shadcn/ui primitives only, RTL-aware
  logical Tailwind utilities (me-/ms-/text-start), performance budgets, next/image, and
  responsiveness across all viewport sizes from 320px (small Android phone) to 2560px+. Also: co-located tests (Vitest + RTL on every data component, Playwright @smoke on every page) and every page reachable from the app-shell nav (no orphan routes).
  Load this skill ONLY when working on .tsx files under frontend/src/ AND the change is
  one of: a form, a data-fetching component, an accessibility-sensitive interaction, a new
  visible page or screen, or adding a frontend dependency. Do NOT load it for trivial
  label/copy/text edits, prop renames, simple style-token swaps, or test-only changes —
  those go straight through pre-commit + CI.
  (large desktop) with WCAG 2.5.5 touch targets (≥44×44px). Use this skill before writing
  ANY .tsx file under frontend/src/, before adding a frontend dependency, before writing
  a form, before writing a component that fetches data, before adding a new page/route.
  Trigger whenever Hamza or a contributor asks Cursor to "build a UI", "make a screen",
  "add a page", "create a component", "build a form", "show this data", "implement the
  dashboard", "add a chart", "build the modal", or any frontend task — even when the
  request doesn't explicitly mention React, Next.js, Tailwind, or responsiveness. Triggers
  also when the user mentions translation, i18n, RTL, accessibility, mobile, tablet,
  responsive, or styling.
---

# frontend-master

**You are writing the IqbalAI v2 frontend.** This skill enforces the patterns locked in `docs/ARCHITECTURE.md` §12 (frontend architecture) and §13 (internationalization). The frontend is the part of the system real users see — generic-looking AI-generated UIs erode trust fast. Following these patterns produces something polished, accessible, multilingual, and consistent.

## Why this skill exists

A frontend without these patterns enforced will accumulate problems faster than any other layer:

- **Inconsistent UI states** — three different "loading" spinners, two different "no data" messages, four different error displays. Users feel like they're using four different apps.
- **Hardcoded strings** — when the app needs to ship in Urdu, every JSX file becomes a rewrite. We've locked four languages from day one (en, ur, sd, ps); hardcoded English breaks all three non-English locales.
- **Inline styles and raw hex codes** — design changes mean searching the codebase. Tokens via Tailwind theme = one place to change.
- **Missing accessibility** — government schools may be procurement-evaluated on WCAG compliance. Adding it after the fact is 10x the cost of building it in.
- **Generic shadcn-defaults look** — every AI-built site looks the same. We can't afford that look for an education product Punjab schools will evaluate.

The frontend lead (Hamza) is weak on frontend by his own description. This skill is the safety net.

## When to apply this skill

Apply whenever you're about to write or modify anything under `frontend/src/`:

1. **New page / route** (`frontend/src/app/.../page.tsx`)
2. **New component** (`frontend/src/components/`, `frontend/src/features/<feature>/components/`)
3. **New form** (anywhere using `react-hook-form`)
4. **New data-fetching component** (anywhere using `useQuery`, `useMutation`, or `fetch`)
5. **New layout** (`layout.tsx`)
6. **Adding a translation string**
7. **Adding a chart, table, or list with state**
8. **Modifying styling on any existing component**
9. **Adding a frontend dependency to `frontend/package.json`**

## How to apply

For each file you're about to write or modify, walk through Rules 1–15 in order. Stop at the first violation; explain it to the user; propose the fix. After passing all 15 rules, generate the code.

The rules are not optional. They're the difference between a frontend that ages well and one that needs a rewrite in 18 months.

## Rule 1 — Allowed frontend stack only

Verify every `import` against the locked stack (`docs/STACK_LOCK.md` Frontend section):

| Allowed | Use for |
|---|---|
| `react`, `next/*` (App Router) | base framework |
| `@/components/ui/*` (shadcn/ui) | UI primitives |
| `tailwindcss` (via class names) | styling |
| `lucide-react` | icons (the only icon set) |
| `@tanstack/react-query` | server state |
| `zustand` | client state (ONLY when TanStack Query isn't a fit) |
| `react-hook-form`, `@hookform/resolvers/zod`, `zod` | forms + validation |
| `next-intl` | i18n |
| `recharts` | standard charts |
| `echarts-for-react` | advanced visualizations only |
| `@fullcalendar/*` | calendar |
| `dompurify` | sanitizing untrusted HTML |
| `react-markdown` + `remark-gfm` | rendering markdown |
| `clsx`, `tailwind-merge` | conditional class names |
| `date-fns` (NOT moment) | date utilities |

**Forbidden imports:**

| Forbidden | Why | Use instead |
|---|---|---|
| `material-ui`, `@mui/*`, `chakra-ui`, `mantine`, `antd` | Other UI libraries fight shadcn/ui patterns | `@/components/ui/*` |
| `styled-components`, `@emotion/*` | Locked on Tailwind | Tailwind utilities |
| `framer-motion`, `react-spring` | Heavy; not justified at launch | Tailwind `transition-*` utilities, CSS keyframes |
| `react-icons`, `@fortawesome/*`, `heroicons` | Locked on lucide-react | `lucide-react` |
| `moment`, `dayjs` | Locked on date-fns | `date-fns` |
| `redux`, `mobx`, `recoil`, `jotai`, `valtio` | Locked on TanStack Query + Zustand | TanStack Query for server, Zustand for client when needed |
| `axios`, `swr` | TanStack Query + the locked `apiClient` | `apiClient` from `src/lib/api/` |
| `react-router-dom` | Next.js App Router only | Next.js `Link`, `useRouter`, `redirect` |
| `react-bootstrap`, `bootstrap` | Never | shadcn/ui |
| `react-modal`, `react-dialog` | shadcn ships these | `@/components/ui/dialog` |
| `react-select`, `downshift` | shadcn ships these | `@/components/ui/select`, `@/components/ui/combobox` |
| `react-table` | shadcn + TanStack Table directly if needed | `@/components/ui/table`, `@tanstack/react-table` if interactive |
| `react-toastify`, `react-hot-toast` | shadcn ships sonner | `@/components/ui/sonner` |

If a needed library isn't in the allowed list, **stop**. Propose the locked alternative or request a deviation.

## Rule 2 — Server Components by default

Next.js App Router defaults to Server Components. **Do not add `"use client"` unless you actually need client-side interactivity.**

You need `"use client"` for:
- `useState`, `useEffect`, `useReducer`, `useRef`, custom hooks that use them
- Event handlers (`onClick`, `onChange`, `onSubmit`)
- Browser APIs (`window`, `document`, `localStorage`)
- Third-party client libraries (TanStack Query providers, charts, calendars)

You do NOT need `"use client"` for:
- Reading data on the server
- Rendering layouts or static content
- Passing data to child Client Components

**Pattern:** push the `"use client"` boundary as deep as possible. The page (Server Component) renders a small Client Component island.

```tsx
// app/lectures/page.tsx — Server Component (no "use client")
import { LectureListClient } from "./LectureListClient";
import { fetchLectures } from "@/features/lectures/api";

export default async function LecturesPage() {
  const lectures = await fetchLectures();  // server-side fetch
  return (
    <main className="container mx-auto py-8">
      <h1 className="text-2xl font-semibold">Lectures</h1>
      <LectureListClient initial={lectures} />
    </main>
  );
}
```

```tsx
// app/lectures/LectureListClient.tsx
"use client";
import { useQuery } from "@tanstack/react-query";
// ... interactive list
```

**Detection:** if the top of every page file starts with `"use client"`, you're not following App Router patterns. Push the boundary down.

## Rule 3 — The four UI states (the most enforced rule)

**Every component that displays data MUST handle all four states explicitly:**

1. **Loading** — show a `Skeleton` matching the eventual content shape (not a generic spinner)
2. **Empty** — show an `EmptyState` with a description and an action (CTA to do the thing)
3. **Error** — show an `ErrorState` with a retry mechanism
4. **Success** — the actual content

The bar for "needs all four": any component fetching from the API or showing a list/table/grid that could be empty.

```tsx
// CORRECT — all four states
"use client";
import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LectureCard } from "./LectureCard";
import { useTranslations } from "next-intl";

export function LectureList() {
  const t = useTranslations("lectures.list");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["lectures", "list"],
    queryFn: fetchLectures,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-40 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <ErrorState description={t("error.description")} onRetry={refetch} />;
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        title={t("empty.title")}
        description={t("empty.description")}
        action={{ label: t("empty.cta"), href: "/lectures/new" }}
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {data.map((lecture) => (
        <LectureCard key={lecture.id} lecture={lecture} />
      ))}
    </div>
  );
}
```

**Common violations:**

```tsx
// WRONG — no loading state
const { data } = useQuery(...);
return <div>{data?.map(...)}</div>;

// WRONG — generic spinner instead of skeleton
if (isLoading) return <Spinner />;

// WRONG — bare "No data" text instead of EmptyState
if (!data?.length) return <p>No lectures.</p>;

// WRONG — toast on error but no inline ErrorState
if (isError) { toast.error("Failed"); return null; }
```

## Rule 4 — Translation keys, never hardcoded strings

**Every visible string in JSX goes through `next-intl`.** Per ARCHITECTURE.md §13.4.

```tsx
// WRONG
<button>Publish</button>
<h1>Welcome back</h1>
<p>You have no lectures yet.</p>

// CORRECT
const t = useTranslations("lectures");
<button>{t("publish.cta")}</button>

const tAuth = useTranslations("auth.login");
<h1>{tAuth("title")}</h1>

const tEmpty = useTranslations("lectures.list.empty");
<p>{tEmpty("description")}</p>
```

**When you add a new string, you add it to ALL four message files in the same PR:**

```
frontend/messages/
├── en.json    — full English string
├── ur.json    — Urdu translation (or "__TODO__ <English>" placeholder)
├── sd.json    — Sindhi translation (or "__TODO__ <English>")
└── ps.json    — Pashto translation (or "__TODO__ <English>")
```

The CI `i18n:verify` check fails if key sets diverge. The CI `i18n:check-todos` check counts `__TODO__` entries — production deploy is blocked if any exist.

**Key naming convention** (§13.11):
- `common.<area>.<key>` — app-wide strings (`common.actions.save`, `common.error.RATE_LIMITED`)
- `<feature>.<surface>.<key>` — feature-specific (`lectures.list.title`, `auth.login.submit`)
- `<feature>.<surface>.<element>.<attr>` — element attributes (`lectures.form.title.label`, `lectures.form.title.placeholder`, `lectures.form.title.error.required`)

**Error message keys must match the §5.5 error codes:** `common.error.VALIDATION_ERROR`, `common.error.RATE_LIMITED`, `common.error.PERMISSION_DENIED`.

**Plurals use ICU MessageFormat** (§13.7):

```json
{
  "lectures": {
    "count": "{count, plural, =0 {No lectures} one {1 lecture} other {{count} lectures}}"
  }
}
```

```tsx
const t = useTranslations("lectures");
<p>{t("count", { count: lectures.length })}</p>
```

**Numbers, dates, currency, relative time go through next-intl formatters:**

```tsx
import { useFormatter } from "next-intl";

const format = useFormatter();
<span>{format.dateTime(date, { dateStyle: "long" })}</span>
<span>{format.number(amount, { style: "currency", currency: "PKR" })}</span>
<span>{format.relativeTime(date)}</span>
```

Never `Date.toLocaleString()`, never `Intl.NumberFormat()` directly.

## Rule 5 — Design tokens, not inline styles

**No inline `style={{...}}` for visual styling.** All visuals come from Tailwind utility classes mapped to design tokens defined in `tailwind.config.ts`.

```tsx
// WRONG
<div style={{ padding: "16px", backgroundColor: "#3b82f6", color: "white" }}>

// CORRECT
<div className="bg-primary text-primary-foreground p-4">
```

**No raw hex codes in `className`.** Use the semantic token names: `bg-background`, `bg-card`, `bg-primary`, `bg-secondary`, `bg-muted`, `bg-accent`, `bg-destructive`, `text-foreground`, `text-muted-foreground`, `border`, `border-input`, `ring`.

**No arbitrary values for design decisions.** `className="bg-[#3b82f6]"` defeats the entire token system. The only acceptable arbitrary values are for one-off layout adjustments where no token applies (e.g., `top-[37px]` for pixel-perfect alignment with a third-party widget) — and even those need a comment explaining why.

**Inline `style` is ONLY acceptable for:**
- Dynamic values from data (`style={{ width: `${percentage}%` }}` for a progress bar)
- CSS variables set at the component root (`style={{ "--accent-h": hue }}`)
- Never for static visual decisions

## Rule 6 — RTL-aware spacing

The frontend must work in both LTR (en) and RTL (ur, sd, ps). **Use logical Tailwind utilities, not physical ones.**

| ✅ Use | ❌ Avoid |
|---|---|
| `ms-4` (margin-start) | `ml-4` (margin-left) |
| `me-4` (margin-end) | `mr-4` (margin-right) |
| `ps-4` (padding-start) | `pl-4` (padding-left) |
| `pe-4` (padding-end) | `pr-4` (padding-right) |
| `start-0` (positioning) | `left-0` |
| `end-0` | `right-0` |
| `text-start` | `text-left` |
| `text-end` | `text-right` |
| `rounded-s-md` | `rounded-l-md` |
| `rounded-e-md` | `rounded-r-md` |
| `border-s` | `border-l` |
| `border-e` | `border-r` |

**Physical utilities are OK only for genuinely directional things** — arrows that always point a fixed direction (download icon), or content that's intrinsically directional (a chart x-axis labeling time, which always reads left-to-right).

**Icons that imply direction (next/back chevrons) must flip in RTL:**

```tsx
<ChevronRight className="rtl:rotate-180" />
```

**For wrapping LTR content inside RTL prose** (e.g., a URL or code snippet inside an Urdu paragraph): use `<bdi>` for isolation or wrap in `<span dir="ltr">`.

## Rule 7 — Accessibility (WCAG 2.1 AA)

The bar:

1. **Every interactive element has a name** — visible label or `aria-label`.
2. **Every form input has an associated label** — `<Label htmlFor="..." />` paired with `<Input id="..." />`. shadcn/ui's `FormLabel` does this automatically.
3. **Every image has `alt`** — descriptive for content images, `alt=""` for purely decorative ones (intentionally empty, not missing).
4. **Color is never the only signal** — error states have an icon + text, not just a red border.
5. **Focus is visible** — never `outline: none` without a replacement. shadcn's default focus rings stay.
6. **Heading hierarchy** — `<h1>` → `<h2>` → `<h3>`, no skipping levels. One `<h1>` per page.
7. **Keyboard navigable** — every action reachable by Tab + Enter/Space. Modals trap focus. `Esc` closes dialogs.
8. **ARIA live regions for async updates** — toast notifications use `role="status"` (sonner does this).
9. **Buttons vs links** — `<button>` for actions, `<a>` (or `<Link>`) for navigation. Don't use `<div onClick>`.
10. **Color contrast ≥ 4.5:1 for body text, ≥ 3:1 for large text.** Tailwind's semantic tokens are tuned for this.

**Common violations:**

```tsx
// WRONG — icon-only button with no name
<button><X /></button>

// CORRECT
<button aria-label={t("common.actions.close")}><X /></button>

// WRONG — div as button
<div onClick={handleClick}>Click me</div>

// CORRECT
<Button onClick={handleClick}>{t("...")}</Button>

// WRONG — placeholder as label
<Input placeholder="Email" />

// CORRECT (using shadcn Form)
<FormField name="email" render={({ field }) => (
  <FormItem>
    <FormLabel>{t("email.label")}</FormLabel>
    <FormControl><Input {...field} /></FormControl>
    <FormMessage />
  </FormItem>
)} />
```

## Rule 8 — Forms: react-hook-form + Zod, always

**Every form uses `react-hook-form` with a Zod resolver.** No exceptions.

```tsx
"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const schema = z.object({
  title: z.string().min(1).max(500),
});

type FormValues = z.infer<typeof schema>;

export function LectureForm({ onSubmit }: { onSubmit: (v: FormValues) => Promise<void> }) {
  const t = useTranslations("lectures.form");
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "" },
  });

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
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? t("submitting") : t("submit")}
        </Button>
      </form>
    </Form>
  );
}
```

**Server validation errors come back via the API error envelope** (§5.4–§5.6). Map them onto the form using `form.setError(field, { message })` keyed by the field name from `error.details`.

**Forbidden:**
- Plain `<form>` with `onSubmit` and manual state via `useState`
- `Formik`, `final-form` (not in stack)
- Inline validation without a schema

## Rule 9 — Data fetching via TanStack Query (or the locked apiClient)

**Server state goes through `@tanstack/react-query`. Period.** Use `useQuery` for reads, `useMutation` for writes.

```tsx
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

// Read
const { data, isLoading, isError, refetch } = useQuery({
  queryKey: ["lectures", "byId", lectureId],
  queryFn: () => apiClient.lectures.get(lectureId),
});

// Write
const qc = useQueryClient();
const mutation = useMutation({
  mutationFn: (payload) => apiClient.lectures.create(payload),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["lectures"] }),
});
```

**API request/response types are generated, never hand-written (AMENDMENTS A-002).** The `apiClient` methods and your feature `types.ts` consume types from `frontend/src/lib/api/schema.d.ts`, generated from the backend OpenAPI via `pnpm gen:api` (openapi-typescript). After any backend contract change, **regenerate** — never edit `schema.d.ts`, never re-declare a request/response shape by hand.

```tsx
// CORRECT — type comes from the generated schema
import type { components } from "@/lib/api/schema";
type LectureRead = components["schemas"]["LectureRead"];

// WRONG — hand-mirrored interface drifts from the backend
interface LectureRead { id: string; title: string; /* ... */ }
```

**Type request bodies from the generated `*Create`/`*Update` schema — never an inline object literal.** This is the most common real bug: the *read* type gets generated but the *create* payload is hand-typed, so it silently drifts from the contract (M-01a: `syllabiApi.create` shipped `{ name, description }` while the API required `exam_board` and had no `description` → 422 on every create).

```tsx
type ExamSyllabusCreate = components["schemas"]["ExamSyllabusCreate"];
// CORRECT — request body typed from the generated Create schema
create: (token, data: ExamSyllabusCreate) => request<ExamSyllabusRead>("/admin/exam-syllabi", { method: "POST", body: JSON.stringify(data) }, token)

// WRONG — inline literal drifts from the contract (missing exam_board, extra description)
create: (token, data: { name: string; description?: string }) => request<ExamSyllabusRead>(...)
```

**Parse the error envelope correctly.** Read errors from `body.error.code` / `body.error.message` (not top level), and parse FastAPI 422 `detail[]` into a readable message; every mutation has an `onError` that surfaces it — a silently-freezing modal is a bug, not a non-event.

**Query key convention** (hierarchical, lockable):
- `[<feature>]` — all data in feature
- `[<feature>, <surface>]` — a specific listing
- `[<feature>, <surface>, <id>]` — a specific item

**Forbidden:**
- Raw `fetch()` in components — use `apiClient`
- `axios` directly
- `swr`
- Calling the API from inside `useEffect` (use `useQuery` instead)
- Hand-writing or `interface`-mirroring API request/response types — they're **generated** from the backend OpenAPI (`pnpm gen:api`); import from `@/lib/api/schema` (AMENDMENTS A-002)
- Typing a request body with an inline object literal instead of the generated `*Create`/`*Update` schema (silently drifts from the contract — M-01a create-flow bug)
- Reading errors from `body.code`/`body.message` (use `body.error.*`) or leaving a mutation without an `onError` that surfaces the message

**Mutations include `Idempotency-Key` header automatically via `apiClient`. Don't roll your own.**

**Client state via `zustand` ONLY when:**
- The state isn't derivable from server data
- It's shared across components that don't have a common parent
- It outlives any single component's lifetime

Otherwise: prop-drilling, React Context, or `useState` is fine.

## Rule 10 — Performance budgets

Per §12.21:

- **LCP < 2.5s** on a mid-range Android over 4G
- **FID/INP < 100ms**
- **CLS < 0.1**
- **Initial JS bundle < 200 KB gzipped**

Practical rules to keep us inside the budget:

1. **`next/image` for every image** — not `<img>`. It handles lazy loading, srcset, and AVIF/WebP.
2. **Dynamic import for heavy components** — charts (recharts/echarts), calendars (FullCalendar), markdown editors:
   ```tsx
   const Chart = dynamic(() => import("./Chart"), { ssr: false, loading: () => <Skeleton className="h-64" /> });
   ```
3. **`next/font` for self-hosted fonts** — Inter for en, Noto Nastaliq Urdu for ur/sd/ps. No external font CDNs.
4. **Code-split by route automatically** (App Router handles this). Don't import 50 features into a single shared barrel.
5. **No `import *`** from large libs. Tree-shake by importing only what you use.
6. **Memoize judiciously** — `useMemo`/`useCallback` only when profiling shows a real win. Premature memoization adds noise.

## Rule 11 — Responsive across all viewport sizes

The IqbalAI frontend runs on a wide range of devices. Pakistani teachers and students access it on mid-range Android phones, low-cost tablets, laptops, and desktop browsers. The frontend must work on all of them — from a 320px-wide phone in portrait up to a 2560px+ desktop monitor.

This is NOT "mobile-first" as a philosophy. It's "responsive at every breakpoint." Tailwind's responsive utilities express conditions as "at this width and above," which happens to be mobile-first syntax, but the lock is on the OUTCOME: every screen works at every viewport.

### Locked viewports

| Class | Width range | Devices |
|---|---|---|
| Mobile portrait (small) | 320-479px | Older Android phones in portrait |
| Mobile portrait (normal) | 480-639px | Most current Android phones in portrait |
| Mobile landscape / small tablet | 640-767px (`sm`) | Phones in landscape, small tablets in portrait |
| Tablet portrait | 768-1023px (`md`) | Most tablets in portrait |
| Tablet landscape / small laptop | 1024-1279px (`lg`) | Tablets in landscape, small laptops, ChromeBooks |
| Desktop | 1280-1535px (`xl`) | Standard desktop monitors |
| Large desktop | 1536px+ (`2xl`) | Larger displays |

**Locked rule:** every page MUST work at the smallest end (320px). "Works" means: nothing is cut off, all text is legible, all interactive elements remain reachable, no horizontal scrolling on the body.

### Touch targets (WCAG 2.5.5)

Every interactive element MUST be at least **44 × 44 pixels** on touch devices. shadcn/ui primitives meet this by default for `Button`, `Input`, `Select`. When you make your own interactive elements, verify:

```tsx
// Tailwind's default button height is h-10 (40px) — below the touch target minimum
// shadcn's Button uses h-10 with px-4 — fine for desktop, borderline on touch
// For touch-heavy surfaces (mobile nav, action sheets), explicitly size:

<Button size="lg">  {/* h-11 = 44px, meets the minimum */}
<button className="size-11">  {/* explicit 44 × 44 for icon-only buttons */}
```

For icon buttons in toolbars, headers, navigation: always use `size-10` or larger (40px) — and prefer `size-11` (44px) for mobile-primary surfaces.

### Responsive layout patterns (locked)

These are the patterns we use; deviation is allowed but should be justified.

**Container max-widths:**

```tsx
// Standard page container — content centered, max ~1280px
<main className="container mx-auto px-4 py-8">

// Wider container for dashboards — max ~1536px
<main className="container mx-auto max-w-screen-2xl px-4 py-8">

// Narrow container for forms / settings — max ~640px
<main className="container mx-auto max-w-2xl px-4 py-8">
```

**Grid → stack on mobile:**

```tsx
// 3 columns desktop, 2 columns tablet, 1 column mobile (the default)
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
```

**Sidebar layout (desktop) → drawer (mobile):**

```tsx
// Desktop: sidebar + content side by side
// Mobile: hamburger button opens a Sheet drawer
<div className="flex">
  {/* Sidebar visible at md+ */}
  <aside className="hidden md:block md:w-64 shrink-0 border-e">
    <SidebarNav />
  </aside>

  {/* Mobile: drawer trigger */}
  <Sheet>
    <SheetTrigger asChild className="md:hidden">
      <Button variant="ghost" size="icon" aria-label={t("nav.open")}>
        <Menu />
      </Button>
    </SheetTrigger>
    <SheetContent side="start" className="w-64">
      <SidebarNav />
    </SheetContent>
  </Sheet>

  <div className="flex-1 min-w-0">
    {/* Page content */}
  </div>
</div>
```

**Tab bar (mobile) → top nav (desktop):**

For primary navigation in apps with 3-5 main sections, a bottom tab bar on mobile + top nav on desktop is the canonical pattern.

```tsx
// Top nav visible at md+
<header className="hidden md:flex h-14 items-center border-b px-4">
  <TopNav />
</header>

// Bottom tab bar visible below md
<nav className="md:hidden fixed bottom-0 inset-x-0 h-16 border-t bg-background">
  <BottomTabs />
</nav>
```

**Dialog (desktop) → Sheet (mobile):**

For modal forms, the standard pattern: a `Dialog` on desktop becomes a `Sheet` sliding up from the bottom on mobile. There's no single shadcn primitive that does both yet; the canonical wrapper is a conditional render based on viewport (use `useMediaQuery` from a small hook or read CSS).

### Fluid type and spacing scale

Don't lock pixel sizes for text. Use Tailwind's responsive scale:

```tsx
// Body text — fluid scale
<p className="text-sm sm:text-base lg:text-lg">

// Page title — bigger on bigger screens
<h1 className="text-2xl sm:text-3xl lg:text-4xl font-semibold">

// Section heading
<h2 className="text-lg sm:text-xl lg:text-2xl font-semibold">
```

### Forbidden patterns

- **Fixed-pixel widths for content containers.** `className="w-[1200px]"` breaks below 1200px. Always use `max-w-*` + `w-full`.
- **`<table>` without horizontal scroll on mobile.** Wide tables MUST be wrapped in `<div className="overflow-x-auto">` or replaced with a card list on mobile.
- **Modals taking 90% of viewport on mobile and feeling cramped.** Use `Sheet` (full-height bottom drawer) instead of `Dialog` for forms on mobile.
- **Hidden content with no mobile alternative.** Don't `hidden md:block` something critical without providing a mobile path to the same action.
- **Pixel-perfect designs imported from Figma.** Designs adapt; pixel-perfect at one viewport is acceptable, pixel-perfect at all viewports is impossible.
- **`min-width:` set higher than 320px.** The body should be horizontally scrollable only as a last resort — never by design.

### Verification per PR

For every new page or major component, manually verify (or, once Playwright snapshot tests exist, automatically) at these widths:

- **360 × 640** (a typical small phone in portrait)
- **768 × 1024** (a tablet in portrait)
- **1440 × 900** (a typical desktop laptop)

These three widths catch ~95% of layout issues. Edge cases (320px tiny screens, 2560px+ huge monitors) are nice-to-have but not blocking at launch.

**Locked rule:** if a screen breaks at 360px width, the PR is blocked. 360px is the floor.

### Test in RTL too

When testing responsiveness, also test in RTL (Urdu or Sindhi locale). RTL flips logical Tailwind utilities; bugs that only appear in RTL are common (e.g., a fixed `right-0` element that should have been `end-0`).

See `references/responsive_patterns.md` for the full responsive component library + common idioms.

## Rule 12 — Tests ship with the component (not "later")

Every component, hook, and page you author or change ships with tests in the **same PR** — this is the rule that gives the four-states / nav / i18n rules teeth. "I'll add tests later" is how M-01 shipped blank pages that passed review.

**Vitest + React Testing Library — component & hook tests.** For any component that displays data, assert **all four UI states render** (loading, empty, error, success) and that the primary action behaves. Co-locate as `*.test.tsx`.

```tsx
import { render, screen } from "@testing-library/react";
import { LectureList } from "./LectureList";

it("renders the empty state when there are no lectures", () => {
  render(<LectureList />, { wrapper: withQuery({ lectures: [] }) });
  expect(screen.getByText(/no lectures yet/i)).toBeInTheDocument();
});

it("renders an error state with retry on failure", () => {
  render(<LectureList />, { wrapper: withQuery({ error: true }) });
  expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
});
```

**Playwright `@smoke` — the page acceptance path.** For any new/changed page, write one `@smoke` E2E driving the ticket's **UX-acceptance checklist**: reachable from the nav, renders real content (not a blank shell), primary flow works.

**Create/update smoke runs against the REAL backend — never mock the contract.** A mocked create test certifies your own assumption, not the API (M-01a: every create 422'd while mocked tests stayed green and `e2e-smoke` passed). At least the create/update `@smoke` paths run against the real seeded compose backend and assert the real success response (201 + persisted row); and a **contract test** asserts your mock payloads + client request types match the generated `*Create`/`*Update` schemas, failing on any divergence.

```ts
test("@smoke teacher reaches the lecture list and sees content", async ({ page }) => {
  await loginAs(page, "teacher");
  await page.getByRole("link", { name: "Lectures" }).click();          // reachable from nav
  await expect(page.getByRole("heading", { name: "Lectures" })).toBeVisible(); // real content
});
```

**Coverage:** 60% on `frontend/src/features/`. `pnpm test` (Vitest) + `pnpm e2e` (Playwright) green before the PR. A data component with no four-states test, or a page with no `@smoke`, is an **incomplete ticket** — not a follow-up.

**Forbidden:** merging a data component without a four-states test; merging a page without a `@smoke` E2E; `test.skip` without a justification comment.

## Rule 13 — Every page is reachable and renders real content

A route that exists but isn't linked from the app navigation is an **orphan** — users can't reach it. This is the M-01 failure (admin pages built, no working nav; ToS page rendered blank/no-scroll). Every page you add:

1. **Renders inside the app shell** (`app/(auth)/.../layout.tsx`) — the persistent role-aware sidebar + header — not as a bare standalone route.
2. **Registers a nav entry** in the shell's nav config, filtered by the viewer's role (a page a role can't open must not show its nav item).
3. **Is reachable by clicking** from the shell — verified by the Rule 12 `@smoke` test (click nav item → page renders).
4. **Renders real content immediately** — non-empty first paint (respecting the four states), never a blank shell or a dead `return null`; content that overflows **scrolls** (no clipped, unreachable content).

**Forbidden:** a new route with no nav entry; a page that renders an empty shell with no loading/empty/error/success content; a non-scrolling container that clips its content.

## Rule 14 — Switches over role/enum unions are exhaustive; tests derive from the union

When a backend enum/role union grows, every dependent switch and hand-enumerated test silently rots (M-06 added `student`/`parent`; `getPostLoginPath` defaulted both to `/admin` and its 5-role hand-listed test stayed green — AUDIT_LOG `[enum-switch-drift]`).

```tsx
// CORRECT — the never-guard turns a missing case into a compile error
switch (role) {
  case "student": return "/student";
  /* …every union member, no silent default… */
  default: { const _exhaustive: never = role; throw new Error(`unhandled role: ${role}`); }
}
// Tests enumerate the union programmatically (single source of truth), never a hand-list:
for (const role of ALL_ROLES) expect(getPostLoginPath(role)).toBe(EXPECTED[role]);
```

**Forbidden:** a `default:` that silently routes unknown members to a real page; a test that hand-enumerates union members.

## Rule 15 — Deploy-critical env vars: documented, required in prod, never silently defaulted

`NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000"` shipped to staging and sent real users' browsers to a dead port (AUDIT_LOG `[env-fallback]`; same class as the `EMBEDDING_PROVIDER` incident).

1. Every `process.env.NEXT_PUBLIC_*` you read has a documented key in `.env.example` (the `env-example-parity` CI guard enforces this).
2. Deploy-critical URLs/IDs **fail the production build when unset** (prebuild assert); localhost defaults are dev-only and log a console warning even there.

**Forbidden:** `?? "http://localhost:…"` on any URL a deployed user's browser will follow; reading an env var `.env.example` doesn't document.

## Workflow

When writing a frontend file:

1. **Identify the file type.** Page? Component? Form? Layout? List view?
2. **Walk through Rules 1–15** in order. For each, ask: does the code I'm about to write comply?
3. **If a rule would be violated:** state the rule, state the fix, then write the corrected code.
4. **For NEW visible strings:** add the translation key + add it to all four `messages/*.json` files (en with real text, ur/sd/ps with `__TODO__` placeholder).
5. **For NEW dependencies:** stop and ask. Don't add a package without explicit approval.
6. **For NEW pages or major components:** verify the layout at 360px, 768px, 1440px. Verify in RTL too (set locale to `ur`).

## Where things live (§12 folder structure)

```
frontend/src/
├── app/                      — App Router routes
│   ├── (auth)/               — auth-gated layouts
│   ├── (public)/             — public pages
│   └── api/                  — Next.js API routes (rare; most calls go to FastAPI)
├── features/<feature>/
│   ├── components/           — feature-specific components
│   ├── hooks/                — feature-specific hooks
│   ├── api.ts                — apiClient calls for this feature
│   └── schemas.ts            — Zod schemas for this feature's forms
├── components/
│   ├── ui/                   — shadcn primitives (DO NOT MODIFY directly; re-export with extensions if needed)
│   ├── empty-state.tsx       — the canonical EmptyState component
│   ├── error-state.tsx       — the canonical ErrorState component
│   └── ...                   — shared composite components
├── lib/
│   ├── api/                  — apiClient + interceptors
│   ├── i18n.ts               — next-intl config
│   ├── utils.ts              — `cn()` helper + small utilities
│   └── ...
└── messages/                 — translation JSON files (en/ur/sd/ps)
```

## What this skill does NOT cover

This skill is frontend-focused. Backend patterns (layer purity, LLM abstraction, NATS) are covered by `stack-enforcer`. End-of-feature comprehensive review is covered by `phase-complete-review`.

## Reference files

- `references/four_ui_states.md` — full anatomy of the four required states with copy-paste templates
- `references/i18n_keys.md` — translation key conventions + ICU MessageFormat patterns
- `references/component_template.md` — the canonical full-feature component shape (the §12.22 example)
- `references/responsive_patterns.md` — responsive layout idioms, viewport-specific patterns, touch-target sizing, RTL-aware breakpoint behavior
- `references/hybrid_input_widget.md` — **the canonical hybrid text/voice/image input widget (#57)**. Mandatory for every student-facing AI chat surface. Lecture Q&A, wizard chat, group study, self-study, study plan, VA — all use this one widget. NO duplicate implementations.