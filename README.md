# SkillMCP

Serves project-specific skills and behavioral rules to AI agents via MCP.

Works with Claude Code, Gemini CLI, Cursor, and Antigravity.

Pairs well with [LearnSkill](https://github.com/NVentimiglia/LearnSkill) (behavioral auditing) and [claude-mem](https://github.com/thedotmack/claude-mem) (long-term memory).

**How it works (MCP, registration, code examples):** see [ABOUT.md](ABOUT.md).

---

## Install (standalone)

SkillMCP installs and runs on its own. You do not need the parent Agents monorepo or any sibling tool (LearnSkill, claude-mem, etc.).

```bash
cd SkillMCP    # this directory only

# Option A — uv (recommended)
uv sync
uv run skills-mcp --version

# Option B — pip
pip install -e .
skills-mcp --version
```

Then wire it into a project:

```bash
cd /path/to/your-project
skills-mcp init .          # skillmcp.toml, .agents/, register MCP with hosts
skills-mcp doctor            # verify layout and host registration
```

Restart your agent host (Cursor, Claude Code, etc.) so it spawns the new MCP server.

**Requirements:** Python ≥ 3.11.

---

## Quick Start

```bash
cd /path/to/your-project
skills-mcp init .
```

Restart your agent host to pick up the new skills.

---

## How it works

Injects knowledge into every agent session automatically via the MCP instruction block.

### AGENT.md — behavioral rules

Markdown files injected into the system prompt at session start. All sources are combined; none are dropped.

| Source | Location |
|---|---|
| Bundled (SkillMCP install) | `<skillmcp>/.agents/AGENT.md` |
| Configured agent folders | `AGENT.md` in each `agent_folders` entry |

### Skills — on-demand knowledge

Markdown skill files the agent fetches with `list_skills` / `read_skill` as needed. Later entries in `agent_folders` win on name collision.

| Source | Location |
|---|---|
| Bundled (SkillMCP install) | `<skillmcp>/.agents/skills/` |
| Configured agent folders | `skills/` subdir of each `agent_folders` entry |

---

## Setup

1. **Install** (see [Install (standalone)](#install-standalone) above).

2. **Initialize**
   ```bash
   skills-mcp init .
   ```

3. **Configure**
   Edit `skillmcp.toml` to add agent folders. Last entry wins on collision.

   ```toml
   agent_folders = [
       "/path/to/shared/agents",
       ".agents/",
   ]
   ```

   Each agent folder can contain:
   - `AGENT.md` — behavioral rules injected into every session (all folders combined)
   - `skills/` — skill library scanned for `list_skills` / `read_skill`

4. **Re-register after moving the project**
   ```bash
   skills-mcp mcp register
   ```

---

## MCP tools

When the host has registered `skills-mcp`, the agent can call:

| Tool | Description |
|------|-------------|
| `verify_setup` | Health snapshot: paths, skill counts |
| `list_skills` | JSON catalog of skills (`project_path` optional for local merge) |
| `read_skill` | Full `SKILL.md` markdown by name |
| `list_skill_files` | List files in a skill's `references` / `scripts` / `assets` directory |
| `read_skill_file` | Read one file from a skill's `references` / `scripts` / `assets` directory |
| `skill_health` | Server status and telemetry counters |

See [ABOUT.md](ABOUT.md) for protocol details and Python client examples.

---

## Telemetry & Metrics

SkillMCP automatically tracks usage metrics to build a scalable dataset of agent behavior and skill utilization. Telemetry data is persisted to `telemetry.json` in your project root.

### Telemetry Dataset (`telemetry.json`)

Tracks sessions, tool counts, and skill access leaderboards:

```json
{
  "TotalSessions": 100,
  "TotalSkillCalls": 5,
  "ToolCalls": {
    "verify_setup": 10,
    "list_skills": 12,
    "read_skill": 5,
    "skill_health": 1
  },
  "Skills": [
    { "role-plan": 3 },
    { "role-research": 2 }
  ]
}
```

### Health Diagnostics (`skill_health`)

The server exposes a health-check tool `skill_health` that returns details about the server health and the sequence number of the current tool execution:

```json
{
  "status": "healthy",
  "call_number": 5,
  "total_sessions": 100,
  "total_skill_calls": 5,
  "checked_at": "2026-05-17T16:00:00Z"
}
```

---

## CLI Reference

| Command | Description |
|---|---|
| `init [path]` | Scaffold `.agents/`, `skillmcp.toml`, `AGENT.md`, register MCP |
| `serve [--root PATH]` | Run MCP server on stdio (normally spawned by the host) |
| `doctor` | Verify directory layout and MCP registration |
| `mcp register` | Re-register with all agent hosts (Claude, Gemini, etc.) |

---

## Troubleshooting

- **Stale paths**: If you move your project, run `skills-mcp mcp register` from the new location to update absolute paths in the MCP configs.
- **Missing skills**: Run `skills-mcp doctor` to see which `skillmcp.toml` is discovered and how many skills were found.
- **Server not starting**: Confirm the host’s `mcp.json` / `settings.json` entry points at the same Python where you installed `skills-mcp`. See [ABOUT.md — Manual host config](ABOUT.md#4-manual-host-config-no-init).
