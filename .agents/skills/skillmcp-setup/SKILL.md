---
name: skillmcp-setup
description: >-
  Install, wire, and troubleshoot Skills MCP (skills-mcp) across Cursor, Claude
  Code, Gemini CLI, and Antigravity. Use when setting up a new project, fixing
  wrong project_root, registering MCP hosts, adding workspace MCP configs,
  wiring companion servers (learn-mcp, claude-mem), or explaining AGENT.md vs
  skills layering. Covers Windows, macOS, and Linux.
metadata:
  skill_class: workflow
  taxonomy: skillmcp-ops
  discovers_with: skills-mcp,skillmcp,MCP setup,read_skill,AGENT.md,skillmcp.toml,mcp register,verify_setup
  pairs_with: handoff, role-plan
triggers:
  - install skills mcp
  - setup skillmcp
  - wire mcp
  - skills-mcp doctor
  - mcp register
  - wrong project_root
  - list_skills missing skills
  - workspace mcp.json
  - how does skills mcp work
---

# Skills MCP — setup and operations

**Last updated:** 2026-06-14

SkillMCP is a **local stdio MCP server** that injects `.agents/AGENT.md` every session
and exposes `list_skills` / `read_skill` for on-demand IC guides.

**Deep references (read as needed):**

| Topic | File |
|-------|------|
| Install all platforms | `references/install.md` |
| Per-host MCP wiring | `references/host-wiring.md` |
| Layering, multi-repo, companions | `references/best-practices.md` |
| Config JSON templates | `references/mcp-templates.md` |

Official package docs: SkillMCP `README.md` and `ABOUT.md` in the install directory.

---

## When to use this skill

- New machine or new repo needs Skills MCP
- `verify_setup` shows the **wrong** `project_root`
- `list_skills` omits project skills (e.g. missing `code-chart`)
- User asks how to wire Cursor / Claude / Antigravity / Gemini
- Adding **companion** MCP servers (memory, learn, custom tools)
- Designing **AGENT.md vs skills** split for a project

---

## Quick diagnostic (run first)

1. Call MCP tool **`verify_setup`** (no args).
2. Check JSON fields:

| Field | Expected |
|-------|----------|
| `ok` | `true` |
| `project_root` | Absolute path to **this** repo (contains `skillmcp.toml`) |
| `skill_dirs` | Library path + `<project>/.agents/skills` |
| `skills_count` | > 0 |

3. Call **`list_skills`** — project IC skills must appear (names from `.agents/skills/*/SKILL.md`).

**Wrong root?** Host MCP config still points at another repo. Fix per `references/host-wiring.md`
(workspace config preferred over global single-root).

---

## New project bootstrap

```bash
# 1. Install package (once per machine) — see references/install.md
cd /path/to/SkillMCP
uv sync   # or: pip install -e .

# 2. Initialize repo
cd /path/to/your-project
skills-mcp init .

# 3. Prefer workspace MCP configs (multi-repo) — see references/host-wiring.md
#    Do NOT rely on global register pinning one --root for all projects.

# 4. Restart agent host; verify_setup + list_skills
skills-mcp doctor
```

`init` creates: `skillmcp.toml`, `.agents/AGENT.md`, `.agents/skills/`, and may write
**global** host entries. For multi-repo workflows, **replace global single-root** with
per-repo workspace files from `references/mcp-templates.md`.

---

## Session ritual (for every agent)

Skills MCP injects a preamble requiring:

1. **`list_skills`** at session start
2. **`read_skill(name)`** before implementing any pattern a skill covers

Teach users this ritual in project `README.md` under **Implement**.

---

## Four-layer guidance model (projects using SkillMCP)

| Layer | What | Where |
|-------|------|-------|
| L0 Entry | Pointers only | `README.md`, `CLAUDE.md`, `AGENTS.md` |
| L1 Always-on | Hard rules | `.agents/AGENT.md` (injected via MCP instructions) |
| L2 Skills | IC how-to + project checklists | `.agents/skills/*/SKILL.md` via `read_skill` |
| L3 Truth | Durable architecture | Project docs (e.g. `.docs/designs/`) — link, don't duplicate |

**Do not** put implementation checklists in `AGENT.md`. Keep L1 under ~120 lines.

---

## Wiring additional MCP servers

Companion pattern (separate MCP processes):

| Server | Role | Typical root env |
|--------|------|------------------|
| `skills-mcp` | Rules + skills | `SKILLS_MCP_ROOT` → project with `skillmcp.toml` |
| `learn-mcp` | Session friction / proposals | `LEARN_MCP_ROOT` → project |
| `claude-mem` | Long-term memory | Plugin path / `CLAUDE_CONFIG_DIR` |

Each server gets its own `mcpServers` entry. Use **full Python path** on Windows.
See `references/best-practices.md` and `references/mcp-templates.md`.

---

## Troubleshooting map

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| PropTrader rules in GammaCharts session | Global `--root` wrong | Workspace MCP config for each repo |
| `list_skills` missing project skills | Same as above | Set `SKILLS_MCP_ROOT` to current repo |
| MCP tools unavailable | Host not restarted | Reload window / new Claude session |
| Claude MCP in `settings.json` ignored | Wrong file | Use `.mcp.json` at project root |
| Antigravity stale global server | Old `~/.gemini/.../mcp_config.json` | Clear global; use `.agents/mcp_config.json` |
| Windows handshake timeout | Buffered stdio | Add `-u` before `-m` in python args (Claude) |
| `doctor` warns "not registered" | Workspace-only setup | OK if `.cursor/mcp.json` or `.mcp.json` exists |

---

## Agent checklist when helping a user

- [ ] Confirm Python ≥ 3.11 and `skills-mcp --version` works
- [ ] Confirm `skillmcp.toml` + `.agents/AGENT.md` exist in target repo
- [ ] Write **workspace** MCP config (not one global root for all repos)
- [ ] Set `SKILLS_MCP_LIBRARY` to bundled `.agents` if using shared library skills
- [ ] Restart host; `verify_setup` shows correct `project_root`
- [ ] `list_skills` includes project skills
- [ ] Update project cursor rule / README with MCP file locations
- [ ] Remove stale `.cursorrules` or legacy agent files that contradict `AGENT.md`
