# Design tokens (T-226) — one-screen reference

The token contract: components consume **semantic Tailwind classes** that resolve to
HSL CSS variables. Never write raw hex, never write inline `style={...}`. A theme change
is then a one-place edit in `globals.css`. Enforced by ESLint
(`react/forbid-dom-props` / `react/forbid-component-props` ban the `style` prop) and the
`tailwind.config.ts` semantic-token map.

## Where each piece lives

| Concern | File |
|---|---|
| HSL variable values (light + `.dark`) | `frontend/src/app/globals.css` |
| Semantic name → `hsl(var(--…))` map, radius, fonts | `frontend/tailwind.config.ts` |
| shadcn generator config | `frontend/components.json` |
| Inline-style ban | `frontend/.eslintrc.json` |

## Semantic color tokens

Each token has a surface value and (where it applies) a `-foreground` for text/icons on
that surface. Use them as Tailwind utilities: `bg-card`, `text-card-foreground`,
`border-border`, `bg-primary text-primary-foreground`, etc. Opacity modifiers compose
(`bg-card/50`) because values are stored as HSL channel triples.

| Token | Utility examples | Use for |
|---|---|---|
| `background` / `foreground` | `bg-background` `text-foreground` | App canvas + default text |
| `card` / `card-foreground` | `bg-card` `text-card-foreground` | Cards, panels, raised surfaces |
| `popover` / `popover-foreground` | `bg-popover` | Menus, dropdowns, tooltips |
| `primary` / `primary-foreground` | `bg-primary text-primary-foreground` | Primary actions, active state |
| `secondary` / `secondary-foreground` | `bg-secondary` | Secondary buttons, chips |
| `muted` / `muted-foreground` | `text-muted-foreground` | De-emphasised text, captions |
| `accent` / `accent-foreground` | `bg-accent` | Hover/active highlight |
| `destructive` / `destructive-foreground` | `bg-destructive text-destructive-foreground` | Delete / error actions |
| `border` | `border-border` | Lines, dividers, card edges |
| `input` | `border-input` | Form-control borders |
| `ring` | `ring-ring` | Focus rings |

> Legacy `brand` hex scale (`brand-500` …) is retained only for not-yet-migrated
> components. New code uses `primary`. Do not introduce new `brand-*` usage.

## Radius, type, spacing

- **Radius:** `rounded-lg` → `var(--radius)` (0.5rem); `rounded-md`/`rounded-sm` derive from it.
- **Fonts:** `font-sans` (Inter), `font-urdu` (Noto Nastaliq Urdu), `font-arabic` (Noto Naskh Arabic).
- **Spacing + base type scale:** Tailwind's canonical scale — no custom overrides.

## Do / don't

```tsx
// ✅ token classes
<div className="rounded-lg border border-border bg-card text-card-foreground p-6" />

// ❌ raw hex / palette literals / inline style — all rejected
<div className="border-gray-200 bg-white" />
<div style={{ background: "#fff" }} />
```

## Dark mode

`darkMode: ["class"]`. Toggle by adding `class="dark"` on a root element; every semantic
token swaps to its `.dark` value automatically — components need no changes.
