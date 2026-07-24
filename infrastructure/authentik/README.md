# Authentik login branding — IQBAL AI

Authentik (our IdP) owns the login/enrollment HTML. We **skin** it to match the
IqbalAI product design — we do not rebuild the form. This folder holds the
branding CSS; logo/title/background are set in the Authentik admin UI.

## Files

| File | Purpose |
|---|---|
| `custom.css` | Premium 50/50 SaaS login skin: kills Authentik's full-height `.ak-login-container` white sidebar, floats a 440px glass card in the left half, subtle overlay over `login-bg.png`. Mounted at `/web/dist/custom.css`. |
| `login-bg-raw.png` | Blank two-panel green art (source). |
| `make_login_bg.py` | Composites marketing copy onto the right panel (kicker, headline, body, feature bullets). Left panel stays ambient for the CSS form card. Removes instructional "enter password on the left" copy. Run: `python infrastructure/authentik/make_login_bg.py`. |
| `login-bg.png` | Generated flow background. Right = marketing; left = empty zone for the floating form. Bind-mounted over **both** `/media/branding/login-bg.png` (CSS fallback) and `/media/public/flow-backgrounds/iqbalai-login-bg.png` (the path stored on `default-authentication-flow.background` in the Authentik DB). |
| `logo.png` | IqbalAI logo (copied from `frontend/logo.png`). Mounted to `/web/dist/assets/icons/iqbal-logo.png`; served at `/static/dist/assets/icons/iqbal-logo.png`. Set this path in Brands → Branding logo. |

## Apply the CSS

**Option A — mounted file (version-controlled, already wired):**
```bash
docker compose up -d authentik-server   # picks up the mount
```
Then hard-refresh the login page (`Cmd/Ctrl+Shift+R`).

**Option B — Brand field (no restart, handy for quick tweaks):**
Admin → **System → Brands** → your brand → **Branding** tab → paste the contents
of `custom.css` into **Custom CSS** → Update. Keep this in sync with the file, or
pick one method to avoid drift.

## Set logo, title, favicon, background (Brand settings)

These are **not** CSS — set them in Admin → **System → Brands** → your brand:

| Field | Value |
|---|---|
| **Title** | `IqbalAI` (replaces "authentik" in the page/tab title) |
| **Branding logo** | `/static/dist/assets/icons/iqbal-logo.png` (already mounted from `logo.png`) |
| **Favicon** | IqbalAI mark (mount + reference the same way if desired) |
| **Background** (Branding tab) | Optional login background image; leave empty to use the CSS green wash |

The logo is already shipped in-repo (`logo.png`) and mounted in `docker-compose.yml`.
To add a favicon the same way, drop the file here and add a mount, e.g.:
```yaml
- ./infrastructure/authentik/favicon.png:/web/dist/assets/icons/iqbal-favicon.png:ro
```
then set the Brand **Favicon** to `/static/dist/assets/icons/iqbal-favicon.png`.

## Dev seed accounts (login-able, one per role)

`seed_dev_accounts.py` creates one Authentik user per role, all with password
`devpassword`, and installs a scope mapping so the JWT carries `role` +
`tenant_type` + `district_id`/`school_id` (from each user's attributes).
District/school-scoped accounts are wired to the alembic sample district/school
IDs so `/admin/schools` does not 403 with "District scope required". Idempotent.
**Dev only.**

```bash
# Windows (PowerShell) — copy + exec (do not pipe; REPL breaks indented blocks)
docker cp infrastructure/authentik/seed_dev_accounts.py iqbalai_v2-authentik-server-1:/tmp/seed_dev_accounts.py
docker compose exec -T authentik-server ak shell -c "exec(open('/tmp/seed_dev_accounts.py').read())"

# Linux/macOS
docker compose exec -T authentik-server ak shell < \
    infrastructure/authentik/seed_dev_accounts.py
```

| email | password | role |
|---|---|---|
| platform.admin@iqbalai.dev | devpassword | platform_admin |
| district.admin@iqbalai.dev | devpassword | district_admin |
| school.admin@iqbalai.dev | devpassword | school_admin |
| coordinator@iqbalai.dev | devpassword | coordinator |
| teacher@iqbalai.dev | devpassword | teacher |
| student@iqbalai.dev | devpassword | student |
| parent@iqbalai.dev | devpassword | parent |
| ind.teacher@iqbalai.dev | devpassword | independent_teacher |
| ind.student@iqbalai.dev | devpassword | independent_student |

App DB rows are created automatically on first login (post-login upsert reads the
`role`/`tenant_type`/`district_id`/`school_id` claims and reconciles them on
every login). Lives in Authentik's DB — reset on `down -v`; re-run the seed to
restore. After reseeding scoped claims, sign out and sign in once so the app DB
picks up `district_id`/`school_id`.

School-scoped pages (`/grades`, subjects, …) also need an **active academic
session** on Sample School. Run `uv run python scripts/seed_dev.py` (or insert
session `2025-2026` for school `00000000-0000-0000-0000-00000005c001`) so
`GET /api/v1/grades/` does not 422 with "No active academic session".

The seeded coordinator is assigned grades **Grade 1–12** via `scoped_ids`
(flow-2). Without that, creating a grade returns "outside your assigned scope".

## Flow configuration (to approach the two-panel mockup)

These are **admin/DB changes**, not files — they live in Authentik's database, so
they reset if the Authentik DB is wiped. Re-apply after a fresh bootstrap (or
convert to a blueprint later for full reproducibility).

Applied so far:
- **One-screen email + password** — identification stage
  `default-authentication-identification` → **Password stage** =
  `default-authentication-password` (so both fields show on the first login
  screen). Flow **layout = sidebar_left** so `custom.css` can place a floating
  glass form card in the left 50% while the right half of `login-bg.png` shows
  marketing copy. Do **not** use `stacked` — that centers the card over the
  whole viewport and covers the branding. Background =
  `/media/branding/login-bg.png` (cover / center handled in `custom.css`).
  After CSS changes: `docker compose up -d authentik-server` + hard refresh.
- **Forgot password** — applied the bundled blueprint
  `example/flows-recovery-email-verification.yaml` (creates
  `default-recovery-flow`), then linked it to the identification stage's
  **Recovery flow**. SMTP is configured via `AUTHENTIK_EMAIL__*` env vars in
  `docker-compose.yml` (values from `.env`; the **worker** sends the mail).
  Verified: `settings.EMAIL_*` loaded and `get_connection().open()` authenticates
  against `mail.privateemail.com:465` (implicit SSL).

- **Register / Sign up** — intentionally **NOT** enabled on the Authentik card.
  Authentik's identification card can only link to *internal* flows, not the app's
  `/independent/signup` page, and its own enrollment would bypass `tenant_type` /
  ToS / the app's `independent_signup` provisioning. Decision: signup stays in the
  app. The `enrollment-2-stage` blueprint instance exists but is **disabled**, and
  the identification stage's **Enrollment flow** is blank. The "Create account"
  entry point belongs on the app frontend, pointing at `/independent/signup`.
- **Sources** → social login buttons (Google/LinkedIn/GitHub): **not** shown on
  the Authentik card or the flow background. Real social IdP wiring (if ever
  needed) lives under Directory → Federation & Social login; the login
  background is marketing copy only.

Not renderable by the flow executor (would need the custom-frontend approach):
"Remember this device" checkbox, "Secure Connection" badge, the dark top header,
and the right "Join us for free" marketing panel.

## Retuning colors

All colors live in the `:root { --iqbal-* }` block at the top of `custom.css`.
Change those variables; everything else derives from them.

## Notes / limits

- Authentik controls the **form layout**. We restyle it; we can't reproduce a
  pixel-perfect custom two-panel Next.js design inside the flow executor.
- The full-height white bar you may see without our CSS is Authentik's
  `.ak-login-container` (sidebar layouts). `custom.css` forces that shell
  transparent and styles only `.pf-c-login__main` as the floating card.
- **Never** set `background: …` (shorthand) on `.pf-c-background-image` —
  it clears Authentik's `background-image` URL. Soft overlay goes on `::after`
  (PatternFly paints the image on `::before`).
- Mobile (`≤768px`): branding art is suppressed; login card on a clean mint
  wash only.
- Version pinned: **authentik 2024.12** (PatternFly 4). Selectors target that
  release; re-verify after an Authentik upgrade (internal classes can change).
- The 2025.4+ shadow-root CSS-adoption model differs slightly; if we upgrade,
  most of this still applies but re-test the card/input selectors.
