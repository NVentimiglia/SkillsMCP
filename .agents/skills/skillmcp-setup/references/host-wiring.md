# Skills MCP — host wiring

**Rule for multi-repo users:** use **workspace-level** MCP config per project.
Do **not** pin one global `--root` to a single repo (e.g. PropTrader) when you
also work in GammaCharts, PropTrader4, etc.

Global configs are for **shared** servers only (e.g. `claude-mem`), not project-scoped
`skills-mcp`.

---

## Config file map

| Host | Workspace (preferred) | Global (shared only) |
|------|----------------------|----------------------|
| **Cursor** | `.cursor/mcp.json` | `~/.cursor/mcp.json` |
| **Claude Code** | `.mcp.json` (project root) | `~/.claude.json` (user/local scope) |
| **Antigravity** | `.agents/mcp_config.json` | `~/.gemini/antigravity/mcp_config.json`, `~/.gemini/config/mcp_config.json` |
| **Gemini CLI** | `.gemini/settings.json` (if used) | `~/.gemini/settings.json` |

**Merge behavior:** Cursor project config **overrides** global for the same server name.

**Claude Code:** `mcpServers` in `~/.claude/settings.json` or `.claude/settings.json`
is **silently ignored**. Use `.mcp.json` or `~/.claude.json` only.

**Antigravity:** Workspace customization root is **`.agents/`** — place
`mcp_config.json` there, not only at repo root.

---

## Workspace setup workflow (recommended)

For each repo that uses Skills MCP:

1. Ensure `skillmcp.toml` and `.agents/AGENT.md` exist (`skills-mcp init .`).
2. Copy the `skills-mcp` block from `references/mcp-templates.md`.
3. Set `--root` and `SKILLS_MCP_ROOT` to **this repo's absolute path**.
4. Set `SKILLS_MCP_LIBRARY` to your bundled library `.agents` (optional).
5. Place the block in the correct workspace file (table above).
6. **Clear** `skills-mcp` from global configs (or leave global `mcpServers` empty).
7. Restart the host; run `verify_setup`.

Repeat for every active repo (GammaCharts, PropTrader4, etc.).

---

## `skills-mcp mcp register` (per project)

```bash
cd /path/to/your-project
skills-mcp mcp register
```

Writes **workspace** configs for the current project:

| Host | File created |
|------|----------------|
| Claude Code | `.mcp.json` |
| Cursor | `.cursor/mcp.json` |
| Antigravity | `.agents/mcp_config.json` |
| Gemini CLI | `~/.gemini/settings.json` (global only) |

Safe to run in each repo. Does **not** overwrite other projects' workspace files.

**Avoid:** pinning one global Cursor/Gemini root for all repos when using multiple checkouts.

---

## Claude Code scopes

| Scope | File | Commit? |
|-------|------|---------|
| **project** | `.mcp.json` at repo root | Yes — team sharing |
| **local** | `~/.claude.json` under project path | No |
| **user** | `~/.claude.json` top-level | No |

CLI:

```bash
claude mcp add --scope project skills-mcp <command> <args>
```

Or hand-edit `.mcp.json` (see templates).

First session may prompt to **approve** project MCP servers.

---

## Antigravity specifics

1. Open MCP Store → Manage MCP Servers → View raw config.
2. **Global** path (GUI): `~/.gemini/config/mcp_config.json` per Google docs.
3. **Workspace** path: `.agents/mcp_config.json` in the opened project.
4. Clear stale global `skills-mcp` entries pointing at wrong repos.

`${workspaceFolder}` in args is **not always expanded** — prefer absolute `--root`
in workspace config files.

---

## Gemini CLI

Project or user `mcpServers` in `~/.gemini/settings.json`. Same JSON shape as Cursor.
Prefer workspace config if your Gemini version supports project-level settings.

---

## After any config change

1. **Restart** the agent host (reload window / new session).
2. `verify_setup` → correct `project_root`.
3. `list_skills` → project + library skills visible.
4. Injected instructions → correct `AGENT.md` (not another project's rules).

---

## `project_path` tool parameter

When one global server must serve multiple checkouts, `list_skills` and `read_skill`
accept optional `project_path` to merge that repo's skills. **AGENT.md injection**
still comes from `SKILLS_MCP_ROOT` only — prefer correct workspace root over relying
on this parameter.
