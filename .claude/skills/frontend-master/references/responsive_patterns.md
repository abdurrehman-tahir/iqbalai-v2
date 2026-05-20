# Responsive patterns — viewport idioms

Per `docs/ARCHITECTURE.md` §12 and `frontend-master/SKILL.md` Rule 11.

The IqbalAI frontend runs from 320px-wide Android phones up to 2560px+ desktop monitors. This file is the practical reference for HOW to make components responsive — when to use which pattern, what the breakpoints are, what shadcn primitives to combine.

## The viewport classes

These match Tailwind's default breakpoints. Locked.

| Class | Min width | Tailwind prefix | What we design for |
|---|---|---|---|
| Mobile (small) | 320px | (default, no prefix) | Older Android phones in portrait |
| Mobile (normal) | 480px | `xs:` (custom, see below) | Most current Android phones in portrait |
| Mobile landscape / small tablet | 640px | `sm:` | Phones in landscape, small tablets |
| Tablet portrait | 768px | `md:` | Standard tablets in portrait |
| Tablet landscape / small laptop | 1024px | `lg:` | Tablets in landscape, low-end laptops |
| Desktop | 1280px | `xl:` | Standard desktop monitors |
| Large desktop | 1536px | `2xl:` | Larger displays |

**Note on `xs`:** Tailwind doesn't ship `xs` by default. If you want the 480px breakpoint (helpful for "looks fine on a slightly bigger phone"), add it in `tailwind.config.ts`:

```ts
// tailwind.config.ts
module.exports = {
  theme: {
    screens: {
      xs: "480px",
      ...defaultTheme.screens,
    },
  },
};
```

Locked: don't add MORE custom breakpoints. The seven above (one custom + six default) cover everything realistic.

## The 320px floor

The smallest viewport we support is **320 × 568 px** (old iPhone SE, low-end Android in portrait). Every screen must work at this width.

"Work" means:
- No horizontal scroll on the body
- All text legible (minimum 14px / `text-sm`)
- All buttons reachable and ≥ 44 × 44 px
- All primary actions accessible (no critical button hidden behind a "more" menu unless that menu is also accessible)

If a page doesn't work at 320px, the PR is blocked.

## Touch target sizing (WCAG 2.5.5)

Every interactive element on a touch device must be at least **44 × 44 px**.

shadcn/ui defaults:

| Component | Default size | Touch-friendly? |
|---|---|---|
| `Button` default | `h-10 px-4` (40px) | Borderline — pass `size="lg"` (h-11 = 44px) for mobile-primary surfaces |
| `Button` `size="sm"` | `h-9` (36px) | NO — never on touch surfaces |
| `Button` `size="lg"` | `h-11` (44px) | ✅ |
| `Button` `size="icon"` | `size-10` (40px) | Borderline — for icon buttons in mobile nav, use `size-11` |
| `Input` | `h-10` (40px) | Borderline |
| `Checkbox` | `size-4` (16px) | NO — but the surrounding label clickable area extends the target. Wrap in a label with proper padding. |
| `Switch` | `h-6 w-11` (24 × 44px) | Horizontal axis ok; vertical needs padding |

**Recommended pattern for icon buttons on mobile-primary screens:**

```tsx
<Button
  variant="ghost"
  size="icon"
  className="size-11"   // override default 40px → 44px
  aria-label={t("nav.menu")}
>
  <Menu />
</Button>
```

**For form inputs on mobile:**

```tsx
// Default Input is h-10 (40px). Bump to h-11 on mobile, h-10 on desktop.
<Input className="h-11 md:h-10" {...field} />
```

## Container max-widths

Three canonical containers:

```tsx
// 1. STANDARD — feature pages, list views
// Centered, max ~1280px, generous side padding
<main className="container mx-auto px-4 py-8 sm:px-6 lg:px-8">

// 2. WIDE — dashboards, data-heavy views
// Max ~1536px to use available space on big monitors
<main className="container mx-auto max-w-screen-2xl px-4 py-8 sm:px-6 lg:px-8">

// 3. NARROW — forms, settings, single-task pages
// Max ~640px to keep line lengths readable
<main className="container mx-auto max-w-2xl px-4 py-6 sm:px-6 sm:py-8">
```

Tailwind's `container` class respects screen breakpoints natively. Combined with `mx-auto` it centers; `px-4 sm:px-6 lg:px-8` gives progressive padding.

## Grid patterns

### List / card grid

The standard pattern — single column on mobile, scaling up:

```tsx
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
  {items.map((item) => <Card key={item.id} {...item} />)}
</div>
```

### Two-column layout (form + sidebar)

```tsx
<div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_320px]">
  <section>{/* Main content */}</section>
  <aside>{/* Sidebar — under content on mobile, beside on lg+ */}</aside>
</div>
```

### Three-column dashboard

```tsx
<div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
  <Card>...</Card>
  <Card>...</Card>
  <Card>...</Card>
</div>
```

## Layout transformations

### Sidebar navigation → drawer on mobile

This is the canonical app-shell pattern:

```tsx
"use client";
import { useState } from "react";
import { Menu } from "lucide-react";
import { useTranslations } from "next-intl";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("common.nav");

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar — visible at md+ */}
      <aside
        className="hidden md:flex md:w-64 shrink-0 flex-col border-e bg-card"
        aria-label={t("primary_nav")}
      >
        <SidebarNav />
      </aside>

      {/* Main area */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Top bar with mobile menu trigger */}
        <header className="flex h-14 items-center gap-3 border-b px-4 md:px-6">
          {/* Mobile menu — visible below md */}
          <Sheet>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden size-11"
                aria-label={t("open_menu")}
              >
                <Menu className="size-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="start" className="w-72 p-0">
              <SidebarNav />
            </SheetContent>
          </Sheet>

          <TopBar />
        </header>

        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
```

Note: `side="start"` makes the Sheet slide from the start edge (left in LTR, right in RTL). Don't hardcode `side="left"`.

### Bottom tab bar on mobile + top nav on desktop

For apps with 3-5 primary surfaces, this is common:

```tsx
<div className="flex min-h-screen flex-col pb-16 md:pb-0">
  {/* Desktop top nav */}
  <header className="hidden md:flex h-14 items-center border-b px-6">
    <TopNav />
  </header>

  <main className="flex-1">{children}</main>

  {/* Mobile bottom tab bar */}
  <nav
    className="md:hidden fixed bottom-0 inset-x-0 z-50 h-16 border-t bg-background"
    aria-label={t("primary_nav")}
  >
    <BottomTabs />
  </nav>
</div>
```

Bottom-tab pattern requires:
- `pb-16` on the parent so content isn't hidden behind the bar
- `fixed bottom-0 inset-x-0` for the nav
- Touch targets — each tab should be the full tab width and ≥ 44px tall

### Dialog (desktop) ↔ Sheet (mobile)

Use a Dialog for desktop, a Sheet sliding from the bottom on mobile. There's no single shadcn primitive yet; the pattern is a conditional render:

```tsx
"use client";
import { useMediaQuery } from "@/hooks/use-media-query";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: React.ReactNode;
}

export function ResponsiveDialog({ open, onOpenChange, title, children }: Props) {
  const isDesktop = useMediaQuery("(min-width: 768px)");

  if (isDesktop) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          {children}
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="h-[90vh] rounded-t-xl">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        {children}
      </SheetContent>
    </Sheet>
  );
}
```

Tiny `use-media-query` hook (if not already in the codebase):

```tsx
// hooks/use-media-query.ts
"use client";
import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(query);
    setMatches(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}
```

### Tables that wrap to cards on mobile

Wide data tables don't fit on mobile. Two options:

**Option 1 — horizontal scroll (simpler):**

```tsx
<div className="overflow-x-auto rounded-lg border">
  <Table>...</Table>
</div>
```

This is acceptable for "data tables that occasionally need to be read on mobile." The user can swipe.

**Option 2 — card list on mobile, table on desktop (better UX for primary surfaces):**

```tsx
<>
  {/* Mobile: card list */}
  <div className="md:hidden space-y-3">
    {items.map((item) => <ItemCard key={item.id} {...item} />)}
  </div>

  {/* Desktop: table */}
  <div className="hidden md:block">
    <Table>
      <TableHeader>...</TableHeader>
      <TableBody>
        {items.map((item) => <TableRow key={item.id}>...</TableRow>)}
      </TableBody>
    </Table>
  </div>
</>
```

This duplicates render logic but produces a far better mobile UX. Worth it for surfaces the user lives in.

## Typography scale

Fluid scaling across viewports:

```tsx
// Body text — never below text-sm on mobile
<p className="text-sm sm:text-base">

// Page title
<h1 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight">

// Section heading
<h2 className="text-xl sm:text-2xl font-semibold tracking-tight">

// Subsection heading
<h3 className="text-lg sm:text-xl font-medium">

// Small / muted text
<span className="text-xs sm:text-sm text-muted-foreground">
```

**Locked rule:** never use `text-xs` (12px) for body content. It's too small to read comfortably on mobile. Reserve `text-xs` for captions, badges, labels.

## Spacing scale

Default spacing should also scale:

```tsx
// Page padding — grows with viewport
<div className="p-4 sm:p-6 lg:p-8">

// Stack vertical spacing
<div className="space-y-3 sm:space-y-4 lg:space-y-6">

// Grid gaps
<div className="grid grid-cols-1 gap-3 sm:gap-4 lg:gap-6">
```

## Forms on mobile

Forms feel cramped on mobile if not designed for it:

```tsx
<Form {...form}>
  <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5 sm:space-y-4">
    {/* More vertical space between fields on mobile */}

    <FormField
      name="title"
      render={({ field }) => (
        <FormItem>
          <FormLabel>{t("title.label")}</FormLabel>
          <FormControl>
            {/* Bigger inputs on mobile for easier tap */}
            <Input className="h-11 md:h-10" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />

    {/* Action buttons stack on mobile, inline on desktop */}
    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
      <Button type="button" variant="outline" onClick={onCancel}>
        {t("cancel")}
      </Button>
      <Button type="submit" size="lg" className="sm:size-default">
        {t("submit")}
      </Button>
    </div>
  </form>
</Form>
```

Note: `flex-col-reverse` for the buttons puts the primary action at the bottom on mobile (where the thumb naturally rests).

## Charts on mobile

Charts (Recharts, ECharts) often have minimum sensible widths. Set min-widths and let them scroll horizontally if needed:

```tsx
<div className="overflow-x-auto">
  <div className="min-w-[640px]">
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>...</LineChart>
    </ResponsiveContainer>
  </div>
</div>
```

Or, hide some axes/labels on mobile:

```tsx
const isMobile = useMediaQuery("(max-width: 767px)");

<LineChart data={data}>
  <XAxis hide={isMobile} />
  <YAxis />
  ...
</LineChart>
```

## Modal-vs-page on mobile

Some flows that are "open in modal" on desktop should be "navigate to a full page" on mobile. Examples: complex multi-step forms, detail views with lots of fields.

```tsx
// Hypothetical pattern using Next.js parallel routes
// On desktop: open as an intercepted route (modal overlay)
// On mobile: navigate to full page

<Link href={`/lectures/${id}`}>View lecture</Link>
// app/lectures/[id]/page.tsx — full page
// app/@modal/(.)lectures/[id]/page.tsx — intercepted route with Dialog
```

This is a Next.js App Router pattern. Defer to Phase 2 if it adds too much complexity; "always open as modal, on mobile use Sheet" is simpler.

## Common idioms cheat sheet

```tsx
// Hide on mobile, show on desktop
className="hidden md:block"

// Show on mobile, hide on desktop
className="md:hidden"

// Hide on tablet, show on mobile and desktop (rare)
className="block md:hidden lg:block"

// Stack on mobile, row on tablet+
className="flex flex-col gap-3 sm:flex-row sm:gap-4"

// Full-width on mobile, auto on desktop
className="w-full md:w-auto"

// Container that doesn't exceed viewport
className="container mx-auto px-4 max-w-full overflow-x-auto"

// Responsive grid that adapts to content
className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(280px,1fr))]"
```

## What to verify before opening a PR

For every new page or major component, manually test at:

1. **360 × 640** — a typical small Android phone in portrait
2. **768 × 1024** — a tablet in portrait
3. **1440 × 900** — a typical laptop

Quickest way in a browser:
- Chrome DevTools → Device Toolbar → choose "Responsive" → set width manually
- Or use Chrome's preset devices: "Pixel 5" (393 × 851), "iPad" (768 × 1024), "Laptop" (1440 × 900)

For each viewport, verify:
- [ ] No horizontal scroll on the body
- [ ] All interactive elements ≥ 44 × 44 px on mobile
- [ ] Touch targets have visible focus states
- [ ] Primary actions are reachable without horizontal scrolling
- [ ] Text is legible (no smaller than 14px / `text-sm` for body)
- [ ] Navigation works (mobile drawer or bottom tabs accessible)
- [ ] Forms are usable (inputs not cramped, buttons not too small)

Then test in RTL:
- Switch the app to Urdu (`/ur` if URL-prefixed locales exist, or via the language switcher)
- Verify all the above still works
- Check for asymmetric layouts that don't flip correctly

## Phase 2 — automated responsive testing (deferred)

When Playwright snapshot tests land, every new page/component will be snapshotted at the three breakpoints (360, 768, 1440) in both en (LTR) and ur (RTL). Drift = a failed test. Until then, manual verification per PR.
