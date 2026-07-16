#!/usr/bin/env python3
"""sync_cursor.py — generate .cursor/ from .claude/ (single source of truth).

Principle: COPY, NEVER TRANSLATE. Bodies are embedded byte-verbatim; the only
mutation is one asserted, anchored substitution in the core rule header (the
words "in Claude Code" -> "in Cursor"), because a verbatim copy would tell
Cursor it is Claude Code. Everything else is mechanical wrapping (frontmatter,
provenance manifest). Zero paraphrasing = zero translation-fidelity risk.

Mapping (managed targets):
  .claude/CLAUDE.md                  -> .cursor/rules/000-core.mdc      (alwaysApply: true)
  .claude/agents/ticket-loader.md    -> .cursor/rules/ticket-loader.mdc (description-triggered)
  .claude/skills/<name>/SKILL.md     -> .cursor/skills/<name>/SKILL.md  (verbatim except the
                                        self-reference substitution "Claude Code" -> "Cursor" in the
                                        BODY only — frontmatter and .claude/ paths untouched; Agent
                                        Skills is a cross-agent standard — Cursor reads these natively)
  (provenance)                       -> .cursor/.sync-manifest.json

NOT managed (hand-maintained, Cursor-only): .cursor/permissions.json, .cursor/cli.json.
FORBIDDEN: .cursor/AGENTS.md (the old hand-clone drift surface) — its presence fails the run.

Usage:
  python scripts/sync_cursor.py          # generate/update .cursor (idempotent)
  python scripts/sync_cursor.py --check  # CI mode: exit 1 if committed .cursor differs
                                          # from what the current .claude sources generate

Determinism: no timestamps anywhere; output depends only on source bytes, so
re-running with unchanged sources is a byte-level no-op (proven in CI by --check).
Rules for humans: edit .claude/*, run this script, commit both. Hand-edits to
managed .cursor files are overwritten here and fail --check in CI.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
CURSOR = ROOT / ".cursor"

PORTABLE_SKILL_KEYS = {"name", "description"}  # Agent Skills cross-agent subset we rely on
GEN_NOTE = "GENERATED from {src} by scripts/sync_cursor.py — DO NOT EDIT. Edit the source and re-run the sync."


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(p: Path) -> str:
    assert p.exists(), f"missing source: {p}"
    return p.read_text(encoding="utf-8")


def frontmatter_keys(text: str) -> tuple[dict, str]:
    """Parse a leading '---' YAML frontmatter block naively (top-level 'key:' lines only)."""
    lines = text.split("\n")
    assert lines[0].strip() == "---", "no frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    keys = {}
    for ln in lines[1:end]:
        if ln and not ln.startswith((" ", "\t")) and ":" in ln:
            k, _, v = ln.partition(":")
            keys[k.strip()] = v.strip()
    body = "\n".join(lines[end + 1:])
    return keys, body


def gen_core(claude_md: str) -> str:
    anchor = "**You are working on IqbalAI v2 in Claude Code.**"
    assert claude_md.count(anchor) == 1, "core header anchor changed — update sync_cursor.py deliberately"
    body = claude_md.replace(anchor, "**You are working on IqbalAI v2 in Cursor.**", 1)
    fm = (
        "---\n"
        "description: IqbalAI v2 core operating rules — stack locks, decision gates, workflow, CI invariants (generated from .claude/CLAUDE.md)\n"
        "alwaysApply: true\n"
        "---\n"
    )
    note = f"<!-- {GEN_NOTE.format(src='.claude/CLAUDE.md')} -->\n\n"
    return fm + note + body


def gen_ticket_loader(agent_md: str) -> str:
    # Claude agent files carry their own frontmatter (name/description[/tools]).
    # Reuse the description for Cursor's trigger; body verbatim; drop Claude-only keys.
    keys, body = frontmatter_keys(agent_md)
    desc = keys.get("description") or 'Load when the user says "Implement T-NNN" or references a ticket ID — assembles the ticket dossier before implementation.'
    desc = desc.strip().strip("|").strip() or 'Load when the user says "Implement T-NNN" — assembles the ticket dossier before implementation.'
    fm = f"---\ndescription: {desc}\nalwaysApply: false\n---\n"
    note = f"<!-- {GEN_NOTE.format(src='.claude/agents/ticket-loader.md')} -->\n\n"
    return fm + note + body.lstrip("\n")


def cursorize_skill(text: str, name: str) -> str:
    """Replace self-references 'Claude Code' -> 'Cursor' in the skill BODY only.
    Frontmatter (name:/description:? both may mention the agent — description is body-facing
    trigger text, so it IS substituted; the name: line never contains it) and literal
    `.claude/` paths are preserved. Deterministic; safe when zero occurrences exist."""
    lines = text.split("\n")
    assert lines[0].strip() == "---"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    head, body = lines[:end + 1], "\n".join(lines[end + 1:])
    # frontmatter: substitute only in description block lines (never the name: line)
    for i, ln in enumerate(head):
        if ln.startswith("name:"):
            assert "Claude Code" not in ln, f"unexpected agent name reference in {name} frontmatter name:"
        elif "Claude Code" in ln:
            head[i] = ln.replace("Claude Code", "Cursor")
    body = body.replace("Claude Code", "Cursor")
    out = "\n".join(head) + "\n" + body
    assert ".claude/" not in text or ".claude/" in out, f"substitution corrupted a .claude/ path in {name}"
    assert "Claude Code" not in out, f"residual Claude Code reference in {name}"
    return out


def build(into: Path) -> dict:
    """Generate the full managed tree under `into`; return the manifest dict."""
    manifest: dict[str, dict] = {}

    # rules/
    (into / "rules").mkdir(parents=True, exist_ok=True)
    core_src = CLAUDE / "CLAUDE.md"
    core_out = gen_core(read(core_src))
    (into / "rules" / "000-core.mdc").write_text(core_out, encoding="utf-8")
    manifest["rules/000-core.mdc"] = {"source": ".claude/CLAUDE.md",
                                      "sha256_source": sha256(core_src.read_bytes()),
                                      "sha256_target": sha256(core_out.encode())}

    tl_src = CLAUDE / "agents" / "ticket-loader.md"
    tl_out = gen_ticket_loader(read(tl_src))
    (into / "rules" / "ticket-loader.mdc").write_text(tl_out, encoding="utf-8")
    manifest["rules/ticket-loader.mdc"] = {"source": ".claude/agents/ticket-loader.md",
                                           "sha256_source": sha256(tl_src.read_bytes()),
                                           "sha256_target": sha256(tl_out.encode())}

    # skills/ — byte-identical (Agent Skills standard; Cursor reads natively)
    for skill_dir in sorted((CLAUDE / "skills").iterdir()):
        if not (skill_dir / "SKILL.md").exists():
            continue
        text = read(skill_dir / "SKILL.md")
        keys, _ = frontmatter_keys(text)
        assert keys.get("name") == skill_dir.name, f"skill frontmatter name != folder: {skill_dir.name}"
        extra = set(keys) - PORTABLE_SKILL_KEYS
        assert not extra, f"non-portable frontmatter keys in {skill_dir.name}: {extra} — verify Cursor supports them before syncing"
        dst = into / "skills" / skill_dir.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(skill_dir, dst)  # copies references/ etc. too
        (dst / "SKILL.md").write_text(cursorize_skill(text, skill_dir.name), encoding="utf-8")
        manifest[f"skills/{skill_dir.name}/SKILL.md"] = {"source": f".claude/skills/{skill_dir.name}/SKILL.md",
                                                         "sha256_source": sha256((skill_dir / 'SKILL.md').read_bytes()),
                                                         "sha256_target": sha256((dst / 'SKILL.md').read_bytes())}

    (into / ".sync-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def managed_paths(manifest: dict) -> list[str]:
    return sorted(list(manifest.keys()) + [".sync-manifest.json"])


def main() -> int:
    check = "--check" in sys.argv
    assert not (CURSOR / "AGENTS.md").exists(), \
        ".cursor/AGENTS.md exists — the hand-clone drift surface is forbidden; delete it (root AGENTS.md + generated rules replace it)."

    if check:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manifest = build(tmp)
            drift = []
            for rel in managed_paths(manifest):
                a, b = tmp / rel, CURSOR / rel
                if not b.exists() or a.read_bytes() != b.read_bytes():
                    drift.append(rel)
            if drift:
                print("CURSOR PARITY DRIFT — regenerate with `python scripts/sync_cursor.py` and commit:")
                for d in drift:
                    print(f"  .cursor/{d}")
                return 1
            print(f"cursor parity OK ({len(managed_paths(manifest))} managed files)")
            return 0

    manifest = build(CURSOR)
    print(f"synced {len(managed_paths(manifest))} managed files into .cursor/ "
          f"(rules: 000-core.mdc, ticket-loader.mdc; skills: {', '.join(sorted(k.split('/')[1] for k in manifest if k.startswith('skills/')))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())