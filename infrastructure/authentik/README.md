# Authentik login branding — IQBAL AI

Authentik (our IdP) owns the login/enrollment HTML. We **skin** it to match the
IqbalAI product design — we do not rebuild the form. This folder holds the
branding CSS; logo/title/background are set in the Authentik admin UI.

## Files

| File | Purpose |
|---|---|
| `custom.css` | Restyles the PatternFly flow executor (green accent, styled inputs, pill button; card made transparent to blend onto the background art). Mounted at `/web/dist/custom.css`. |
| `login-bg-raw.png` | Blank two-panel green art (source). |
| `make_login_bg.py` | Composites "Join us for free" + social pills + CREATE ACCOUNT onto the right panel of the raw art → `login-bg.png`. Run: `api/.venv/bin/python infrastructure/authentik/make_login_bg.py`. |
| `login-bg.png` | Generated flow background. Mounted to `/media/public/login-bg.png`; set as the `default-authentication-flow` **background** with **layout = content_left** (form floats over the left panel). |
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
`tenant_type` (from each user's attributes). Idempotent. **Dev only.**

```bash
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
`role`/`tenant_type` claims). Lives in Authentik's DB — reset on `down -v`; re-run
the seed to restore.

## Flow configuration (to approach the two-panel mockup)

These are **admin/DB changes**, not files — they live in Authentik's database, so
they reset if the Authentik DB is wiped. Re-apply after a fresh bootstrap (or
convert to a blueprint later for full reproducibility).

Applied so far:
- **One-screen email + password** — identification stage
  `default-authentication-identification` → **Password stage** =
  `default-authentication-password`. (Applied via `ak shell`.)
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
- **Sources** → social login buttons (Google/LinkedIn/GitHub); each needs a real
  OAuth app (client id + secret) created in Directory → Federation & Social login.
  Callback URL: `http://localhost:9000/source/oauth/callback/<source-slug>/`.

Not renderable by the flow executor (would need the custom-frontend approach):
"Remember this device" checkbox, "Secure Connection" badge, the dark top header,
and the right "Join us for free" marketing panel.

## Retuning colors

All colors live in the `:root { --iqbal-* }` block at the top of `custom.css`.
Change those variables; everything else derives from them.

## Notes / limits

- Authentik controls the **form layout**. We restyle it; we can't reproduce a
  pixel-perfect custom two-panel Next.js design inside the flow executor.
- Version pinned: **authentik 2024.12** (PatternFly 4). Selectors target that
  release; re-verify after an Authentik upgrade (internal classes can change).
- The 2025.4+ shadow-root CSS-adoption model differs slightly; if we upgrade,
  most of this still applies but re-test the card/input selectors.
