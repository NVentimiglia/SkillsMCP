# SkillMCP

Local MCP server that serves project skills to AI coding agents (Cursor, Claude Code, Gemini CLI, Antigravity).

The host spawns `skills-mcp serve` over **stdio** (no HTTP). SkillMCP injects a short session ritual via MCP instructions and exposes tools to list and read `SKILL.md` files on demand.

Pairs well with [LearnSkill](https://github.com/NVentimiglia/LearnSkill) (session friction) and [claude-mem](https://github.com/thedotmack/claude-mem) (long-term memory).

**Requirements:** Python ≥ 3.11. Standalone package — no monorepo or sibling tools required.

---

## Install

```bash
cd SkillMCP

# Option A — uv (recommended)
uv sync
uv run skills-mcp --version

# Option B — pip
pip install -e .
skills-mcp --version
```

---

## Quick start

```bash
cd /path/to/your-project
skills-mcp init .          # skillmcp.toml, .agents/skills/, register MCP with hosts
skills-mcp verify            # layout + registration check
```

Restart your agent host so it picks up the new MCP server entry.

Example project layout (see `examples/my-project/`):

```
your-project/
  skillmcp.toml
  .agents/
    skills/
      my-skill/
        SKILL.md
```

---

## Configuration

### `skillmcp.toml`

Lists **skill folders** in priority order. Later entries win on **name collision**.

```toml
skill_folders = [
    "/path/to/shared/skills",
    ".agents/skills",
]
```

| Case | Result |
|------|--------|
| File missing | Defaults to `[".agents/skills"]` |
| `skill_folders = []` or null | Same default |

Each `skill_folders` entry can be either:

| Path kind | Detection | Example |
|-----------|-----------|---------|
| **Skill library** | No `SKILL.md` at the folder root — scan subfolders and flat `.md` files | `.agents/skills/` → `project-starter/SKILL.md` |
| **Single skill** | `SKILL.md` at the folder root — load exactly that skill | `LearnSkill/learn/` → one `learn` skill |

```toml
skill_folders = [
    "/path/to/LearnSkill/learn",   # single skill folder
    ".agents/skills",              # project skill library
]
```

**Skill library** contents:

- Directory skills: `foo/SKILL.md` plus optional `references/`, `scripts/`, `assets/`
- Flat legacy files: `foo.md` (YAML frontmatter + body)

**Single skill folder:** point at the directory that contains `SKILL.md` (name in frontmatter need not match the folder name).

Frontmatter fields: `name`, `description`, optional `triggers`, `metadata`, `license`, `compatibility`.

### Environment variables

| Variable | Meaning |
|----------|---------|
| `SKILLS_MCP_ROOT` | Project directory containing `skillmcp.toml` (set by host MCP config) |
| `SKILLS_MCP_LIBRARY` | Optional shared **skills folder** (lowest priority; prepended before `skill_folders`) |
| `SKILLS_MCP_RULES_INSTRUCTIONS_MAX_CHARS` | Cap MCP instruction block size (`0` = no cap) |

Config discovery: walk up from cwd for `skillmcp.toml`, or use `SKILLS_MCP_ROOT` when set.

### Skill sources (merge order)

| Priority | Source |
|----------|--------|
| Lowest | `SKILLS_MCP_LIBRARY` (optional env) |
| ↑ | Earlier entries in `skill_folders` |
| Highest | Last entry in `skill_folders` |

Project rules (`AGENT.md`, `AGENTS.md`, Cursor rules/hooks) are **not** injected by SkillMCP — configure those in your agent host.

### MCP host registration

`skills-mcp init` and `skills-mcp mcp register` write a server entry to:

| Host | Config file |
|------|-------------|
| Claude Code | `<project>/.mcp.json` |
| Cursor | `<project>/.cursor/mcp.json` |
| Antigravity | `<project>/.agents/mcp_config.json` |
| Gemini CLI | `~/.gemini/settings.json` (global) |

Example entry (Cursor / Claude):

```json
{
  "mcpServers": {
    "skills-mcp": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "skills_mcp", "serve", "--root", "/path/to/your-project"],
      "env": {
        "SKILLS_MCP_ROOT": "/path/to/your-project",
        "SKILLS_MCP_LIBRARY": "/path/to/shared/skills"
      }
    }
  }
}
```

On Windows, use the full path to `python.exe` in `command` if `skills-mcp` is not on PATH. Add `-u` before `-m` in args if stdio buffering causes handshake timeouts.

Optional shared library: set `SKILLS_MCP_LIBRARY` to a skills folder (e.g. `SkillMCP/examples/my-project/.agents/skills`).

**Manual config (no `init`):** add the same `mcpServers` block yourself using the Python where `skills-mcp` is installed, then restart the host.

---

## MCP tools

| Tool | Description |
|------|-------------|
| `verify_setup` | JSON health snapshot: paths, skill counts, registration status |
| `list_skills` | JSON catalog (`project_path` optional — merge another repo's skills) |
| `read_skill` | Full `SKILL.md` markdown by name |
| `list_skill_files` | Files under a skill's `references` / `scripts` / `assets` |
| `read_skill_file` | Read one UTF-8 file from a skill subdirectory |
| `learn_paths` | JSON: `.learn` output paths from `skillmcp.toml` `[learn]` |
| `learn_run_script` | Run a learn skill script (detectors, collect-cursor) |
| `learn_stamp` | Ensure `.learn/inbox` exists and update `lean.stamp` |

### `list_skills` response

Returns metadata only (not full bodies):

```json
[
  {
    "name": "role-plan",
    "description": "Produce an execution-ready plan before writing code…",
    "path": ".agents/skills/role-plan/SKILL.md",
    "format": "directory",
    "references_dir": "references",
    "scripts_dir": "",
    "assets_dir": ""
  }
]
```

Pass `project_path` when working in a repo other than `SKILLS_MCP_ROOT` to merge that project's skills (local names win on collision).

### Session instructions

Every session gets a fixed ritual: call `list_skills`, then `read_skill(name)` before implementing patterns a skill covers. Large skill bodies stay out of context until explicitly loaded.

---

## CLI

| Command | Description |
|---------|-------------|
| `init [path]` | Create `.agents/skills/`, `skillmcp.toml`, register MCP |
| `serve [--root PATH]` | Run MCP server on stdio (host spawns this) |
| `verify` | Verify layout and MCP registration |
| `mcp register` | Re-register with all supported hosts |

Debug serve manually:

```bash
skills-mcp serve --root /path/to/your-project
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Stale paths after moving project | Run `skills-mcp mcp register` from the new location |
| Missing skills | Run `skills-mcp verify` or MCP `verify_setup` — check `project_root`, `skill_dirs`, `skills_count` |
| Server not starting | Host MCP config must use the same Python where `skills-mcp` is installed |
| Wrong skills from another repo | Workspace MCP config must set `SKILLS_MCP_ROOT` to **this** project |
| Windows handshake timeout | Add `-u` before `-m` in python args |

---

## Design notes

- **Stdio, not HTTP** — local-only; every MCP host supports it
- **Instructions + tools** — small ritual always on; skill bodies loaded on demand
- **Last-wins merge** — shared library + early folders; project skills in later folders override by name
- **No daemon** — host spawns the server per session; skill index rebuilt each spawn

---

## Related projects

| Project | Role |
|---------|------|
| [LearnSkill](https://github.com/NVentimiglia/LearnSkill) | Session friction analysis |
| [claude-mem](https://github.com/thedotmack/claude-mem) | Long-term memory across sessions |
