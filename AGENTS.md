# IqbalAI v2 — Cursor agent instructions

Full project rules for **Cursor** live in [`.cursor/AGENTS.md`](.cursor/AGENTS.md).

Claude Code users follow the parallel rules in [`.claude/CLAUDE.md`](.claude/CLAUDE.md). Both toolchains coexist — do not remove either folder.

## Cursor setup (enable once per machine)

1. **Run Mode:** Cursor Settings → enable **Allowlist** or **Auto-review** so `.cursor/permissions.json` applies.
2. **Rules:** `.cursor/rules/*.mdc` auto-load (core, ticket-loader, skills).
3. **Skills:** `.cursor/skills/*/SKILL.md` — loaded when matching rules fire or triggers match.
4. **CLI:** `.cursor/cli.json` permissions apply when using the Cursor CLI in this repo.
