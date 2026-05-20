# Runbook: first-time VM provisioning

**Status: DEFERRED — fills in when we first ship to a VM (post-M-23).**

---

## Why this is empty for now

At launch (and during M-00 through M-23), there is no staging or production VM to provision. All development happens locally on Hamza's laptop via `docker compose up` (see `local-dev-setup.md`).

The first time IqbalAI ships to a real Ubuntu VM, this runbook gets written from the actual experience — capturing exact commands, gotchas, hostname patterns, firewall rules, TLS cert provisioning, env file location on disk, log rotation config, and the deploy user setup.

Writing it now without that experience would just be theoretical commands that may not survive contact with the real VM.

---

## When this runbook becomes active

A backlog ticket (likely in a post-M-23 "Pre-launch readiness" milestone) will own writing this runbook **immediately after** the first successful staging VM provision. The PR that ships the first VM deployment also fills this file in.

---

## What goes in here when it's written

Sketch of expected sections (don't implement these speculatively — capture them when actually doing it):

1. VM specs verified (16 vCPU / 64 GB RAM / 500 GB disk minimum)
2. SSH hardening (disable root login, key-only, fail2ban)
3. Firewall rules (only 22, 80, 443 inbound)
4. Docker + Compose plugin install
5. Create `iqbalai-deploy` user, non-root, in docker group
6. Clone repo to `/opt/iqbalai/app`
7. Place `.env.production` at `/opt/iqbalai/secrets/.env.production` (chmod 600)
8. Bind mount `/opt/iqbalai/data` to compose-managed volumes
9. Let's Encrypt cert via certbot for the domain
10. nginx reverse proxy install + config
11. systemd unit for `docker compose up -d` on boot
12. First `docker compose up -d` + Alembic migrations
13. Smoke test against the public domain
14. Backup cron setup (per ARCH §15.10)

---

## See also

- `docs/runbooks/local-dev-setup.md` — what you DO need today (laptop setup)
- `docs/ARCHITECTURE.md` §15 — deployment topology spec
- `docs/runbooks/deploy.md` — once a VM exists, this is how PRs deploy
- `docs/runbooks/secret-rotation.md` — when secrets need to change

---

**Last updated:** 2026-05-20 (deferred from speculative content to "fill in on first real deploy")
