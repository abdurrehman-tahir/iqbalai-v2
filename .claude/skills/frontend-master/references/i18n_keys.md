# i18n keys + ICU MessageFormat — frontend playbook

Per `docs/ARCHITECTURE.md` §13.

The rule: **every visible string in the frontend goes through `next-intl`.** No hardcoded English in JSX, ever. We ship in four languages at launch (en, ur, sd, ps) and the only mechanism that lets us do that without rewriting every component is translation keys.

## Where translations live

```
frontend/messages/
├── en.json     ← canonical text
├── ur.json     ← Urdu
├── sd.json     ← Sindhi
└── ps.json     ← Pashto
```

**All four files have the exact same key set.** CI's `i18n:verify` script fails the PR if they diverge.

When you add a string, you add it to all four. Use real Urdu/Sindhi/Pashto if you have it; otherwise use `__TODO__ <English text>` as the placeholder. CI's `i18n:check-todos` script counts placeholders and blocks production deploys when any exist.

## Key naming convention (locked)

| Pattern | Use for | Example |
|---|---|---|
| `common.<area>.<key>` | App-wide strings | `common.actions.save`, `common.error.RATE_LIMITED` |
| `<feature>.<surface>.<key>` | Feature-scoped | `lectures.list.title`, `auth.login.submit` |
| `<feature>.<surface>.<element>.<attr>` | Element attributes | `lectures.form.title.label`, `lectures.form.title.placeholder`, `lectures.form.title.error.required` |

**Rules:**
- Lowercase `snake_case` for all key segments
- Match the second segment to the feature folder name: `app/features/lectures/` → keys under `"lectures"`
- Don't embed the text in the key (`save` not `save_button_text`)
- Keep nesting depth ≤ 4

**Error message keys use the §5.5 error codes verbatim:**
- `common.error.VALIDATION_ERROR`
- `common.error.PERMISSION_DENIED`
- `common.error.RATE_LIMITED`
- `common.error.RESOURCE_NOT_FOUND`
- `common.error.IDEMPOTENCY_CONFLICT`
- `common.error.PRECONDITION_FAILED`
- `common.error.INTERNAL_ERROR`

The frontend maps API `error.code` to `common.error.<CODE>` to render the localized message.

## The file shape

Each `messages/*.json` is one big nested object. The `common` block is shared; each feature gets a top-level key.

```json
{
  "common": {
    "actions": {
      "save": "Save",
      "cancel": "Cancel",
      "delete": "Delete",
      "edit": "Edit",
      "confirm": "Confirm",
      "retry": "Try again",
      "close": "Close",
      "back": "Back"
    },
    "error": {
      "generic": "Something went wrong. Please try again.",
      "network": "Connection problem. Check your internet.",
      "retry": "Try again",
      "VALIDATION_ERROR": "Some fields need attention.",
      "PERMISSION_DENIED": "You don't have permission for this.",
      "RATE_LIMITED": "Too many requests. Please slow down.",
      "RESOURCE_NOT_FOUND": "We couldn't find what you're looking for.",
      "IDEMPOTENCY_CONFLICT": "This action was already submitted.",
      "PRECONDITION_FAILED": "The item was changed by someone else. Please refresh.",
      "INTERNAL_ERROR": "An unexpected error occurred."
    },
    "status": {
      "loading": "Loading…",
      "saving": "Saving…",
      "submitting": "Submitting…"
    }
  },

  "auth": {
    "login": {
      "title": "Welcome back",
      "submit": "Sign in",
      "forgot_password": "Forgot password?",
      "email": {
        "label": "Email",
        "placeholder": "you@example.com",
        "error": {
          "required": "Email is required",
          "invalid": "Please enter a valid email"
        }
      }
    }
  },

  "lectures": {
    "list": {
      "title": "Lectures",
      "empty": {
        "title": "No lectures yet",
        "description": "Create your first lecture to get started.",
        "cta": "Create lecture"
      },
      "error": {
        "title": "Couldn't load lectures",
        "description": "Please try again."
      },
      "count": "{count, plural, =0 {No lectures} one {1 lecture} other {{count} lectures}}"
    },
    "form": {
      "title": {
        "label": "Lecture title",
        "placeholder": "e.g. Newton's Laws of Motion",
        "error": {
          "required": "Title is required",
          "max_length": "Title must be at most {max} characters"
        }
      },
      "submit": "Create"
    }
  }
}
```

## Using keys in components

### Basic — single string

```tsx
"use client";
import { useTranslations } from "next-intl";

export function PublishButton() {
  const t = useTranslations("lectures.publish");
  return <Button>{t("cta")}</Button>;
}
```

### Multiple keys from the same namespace

```tsx
const t = useTranslations("lectures.form");
return (
  <form>
    <label>{t("title.label")}</label>
    <input placeholder={t("title.placeholder")} />
    <button>{t("submit")}</button>
  </form>
);
```

### Keys from different namespaces

```tsx
const tForm = useTranslations("lectures.form");
const tCommon = useTranslations("common.actions");

<Button>{tCommon("save")}</Button>
<Button variant="outline">{tCommon("cancel")}</Button>
<Input placeholder={tForm("title.placeholder")} />
```

### Server Components

Server Components use `getTranslations` (not `useTranslations`):

```tsx
// app/lectures/page.tsx — Server Component
import { getTranslations } from "next-intl/server";

export default async function LecturesPage() {
  const t = await getTranslations("lectures.list");
  return <h1 className="text-2xl font-semibold">{t("title")}</h1>;
}
```

### Page-level metadata (titles, descriptions)

```tsx
import { getTranslations } from "next-intl/server";

export async function generateMetadata() {
  const t = await getTranslations("lectures.list");
  return {
    title: t("title"),
    description: t("meta.description"),
  };
}
```

## ICU MessageFormat — pluralization

Different languages have different plural rules. English has 2 (singular, plural); Arabic has 6; Urdu has 2 but different from English. ICU MessageFormat handles all of them through the same syntax — next-intl + CLDR plural rules pick the right form per locale.

```json
{
  "lectures": {
    "count": "{count, plural, =0 {No lectures} one {1 lecture} other {{count} lectures}}"
  }
}
```

Usage:

```tsx
const t = useTranslations("lectures");
<p>{t("count", { count: lectures.length })}</p>
```

**Always use ICU for counts, even when the English rule looks simple.** Other locales need it.

**Anti-pattern:**

```tsx
// WRONG — string interpolation breaks other languages
<p>You have {count} lectures</p>

// WRONG — branching in JSX
<p>{count === 0 ? "No lectures" : count === 1 ? "1 lecture" : `${count} lectures`}</p>

// CORRECT
<p>{t("count", { count })}</p>
```

## ICU MessageFormat — gender / select

For dynamic message variants based on a category:

```json
{
  "profile": {
    "greeting": "{gender, select, male {Welcome, sir} female {Welcome, ma'am} other {Welcome}}"
  }
}
```

We avoid this at launch — it's culturally inconsistent across our four languages, and "other" is what we'd default to almost always. Keep messages gender-neutral by default.

## ICU MessageFormat — rich text (with bold, link)

When part of a translated sentence needs to be a link or bold span:

```json
{
  "auth": {
    "agree_to_terms": "By signing up, you agree to our <link>Terms of Service</link>."
  }
}
```

```tsx
const t = useTranslations("auth");
<p>
  {t.rich("agree_to_terms", {
    link: (chunks) => <Link href="/terms" className="underline">{chunks}</Link>,
  })}
</p>
```

This is preferred over splitting the sentence with concatenation — it keeps the translator in control of where the link goes.

## Numbers, dates, currency, relative time

Always use next-intl's formatters. Never raw `Intl.*` or `Date.toLocaleString()`.

```tsx
import { useFormatter } from "next-intl";

const format = useFormatter();

// Dates
<span>{format.dateTime(date, { dateStyle: "long" })}</span>
<span>{format.dateTime(date, { dateStyle: "medium", timeStyle: "short" })}</span>

// Numbers
<span>{format.number(value)}</span>
<span>{format.number(0.42, { style: "percent" })}</span>

// Currency
<span>{format.number(amount, { style: "currency", currency: "PKR" })}</span>

// Relative time
<span>{format.relativeTime(date)}</span>
// → "3 days ago" / "2 minutes from now" — auto-localized
```

## Adding new keys (the workflow)

When you're writing a component and need a new visible string:

1. **Decide the key path** — `<feature>.<surface>.<key>` per the convention
2. **Open `frontend/messages/en.json`** and add the key with the canonical English text
3. **Open `frontend/messages/ur.json`, `sd.json`, `ps.json`** and add the same key with `__TODO__ <English text>` as the value
4. **Reference the key in your component** via `useTranslations`
5. **Commit all four files in the same PR**

If you forget step 3, CI's `i18n:verify` will reject the PR.

If the production deploy attempts to ship with `__TODO__` entries still in any file, CI's `i18n:check-todos` will block it. A separate translation PR replaces the placeholders with real translations.

## Common mistakes

```tsx
// WRONG — hardcoded English
<button>Save</button>
<h1>Welcome back</h1>

// WRONG — partial translation (mixed)
<p>You have {t("count_label")} {count}</p>
// (use ICU plural in the key)

// WRONG — translating in the component
const message = locale === "ur" ? "خوش آمدید" : "Welcome";
// (always use t())

// WRONG — reusing keys across features
// "common.lectures_title" used for both lecture list and quiz list
// (each feature has its own keys; common is for genuinely cross-cutting strings)

// WRONG — using template literals in the key
const t = useTranslations("lectures");
const key = `status_${lecture.status}`;
<span>{t(key)}</span>
// (this defeats type safety; create explicit keys: status.draft, status.published)

// WRONG — passing user-generated strings through translation
const t = useTranslations("lectures");
<span>{t(lecture.title)}</span>
// (user-generated content is rendered directly; translations are only for app-owned strings)
```

## RTL considerations beyond text direction

When writing strings:

- **Avoid baking in directional metaphors** that don't translate: "swipe left to dismiss" doesn't work in RTL where "left" is logically "after." Use neutral language: "swipe to dismiss."
- **Numbers stay LTR in mixed-script paragraphs** — the browser's bidi algorithm handles this automatically.
- **Code/URLs/emails embedded in Urdu prose** should be wrapped: `<span dir="ltr">{email}</span>` or `<bdi>{email}</bdi>` to prevent bidi mangling.

## Things deferred to TODO

- URL-prefixed locales (`/en/...`, `/ur/...`) — Phase 2; at launch we use cookie + user preference only
- Eastern Arabic digits (۱، ۲، ۳) — per-user setting, Phase 2
- Hijri calendar — Phase 2
- TMS integration (Crowdin/Lokalise/Weblate) — Phase 2; manual JSON editing at launch
- On-the-fly content translation (translating an existing lecture into another language) — Phase 2+
