# Skills MCP — MCP config templates

Replace `PROJECT_ROOT`, `PYTHON`, and `LIBRARY_AGENTS` with absolute paths.

```
PROJECT_ROOT   = e.g. D:\Projects\StockDev\GammaCharts
PYTHON         = e.g. D:\Projects\Agents\.venv\Scripts\python.exe
LIBRARY_AGENTS = e.g. D:\Projects\Agents\SkillMCP\.agents
```

---

## skills-mcp server block (shared shape)

```json
"skills-mcp": {
  "command": "PYTHON",
  "args": [
    "-u",
    "-m",
    "skills_mcp",
    "serve",
    "--root",
    "PROJECT_ROOT"
  ],
  "env": {
    "SKILLS_MCP_ROOT": "PROJECT_ROOT",
    "SKILLS_MCP_LIBRARY": "LIBRARY_AGENTS"
  }
}
```

- **`-u`**: recommended on Windows for Claude Code (unbuffered stdio).
- Omit `SKILLS_MCP_LIBRARY` if not using bundled library skills.

---

## Cursor — `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "skills-mcp": {
      "command": "PYTHON",
      "args": ["-m", "skills_mcp", "serve", "--root", "PROJECT_ROOT"],
      "env": {
        "SKILLS_MCP_ROOT": "PROJECT_ROOT",
        "SKILLS_MCP_LIBRARY": "LIBRARY_AGENTS"
      }
    }
  }
}
```

Global `~/.cursor/mcp.json`: keep only **shared** servers (e.g. `claude-mem`), not
project `skills-mcp`.

---

## Claude Code — `.mcp.json` (project root)

```json
{
  "mcpServers": {
    "skills-mcp": {
      "command": "PYTHON",
      "args": [
        "-u",
        "-m",
        "skills_mcp",
        "serve",
        "--root",
        "PROJECT_ROOT"
      ],
      "env": {
        "SKILLS_MCP_ROOT": "PROJECT_ROOT",
        "SKILLS_MCP_LIBRARY": "LIBRARY_AGENTS"
      }
    }
  }
}
```

Commit this file. Approve project servers on first Claude session.

---

## Antigravity — `.agents/mcp_config.json`

```json
{
  "mcpServers": {
    "skills-mcp": {
      "command": "PYTHON",
      "args": ["-m", "skills_mcp", "serve", "--root", "PROJECT_ROOT"],
      "env": {
        "SKILLS_MCP_ROOT": "PROJECT_ROOT",
        "SKILLS_MCP_LIBRARY": "LIBRARY_AGENTS"
      }
    }
  }
}
```

Clear global `skills-mcp` from `~/.gemini/antigravity/mcp_config.json` and
`~/.gemini/config/mcp_config.json` when using workspace configs.

---

## Global shared servers only — `~/.cursor/mcp.json` example

```json
{
  "mcpServers": {
    "claude-mem": {
      "command": "node",
      "args": ["PATH/TO/claude-mem/plugin/scripts/mcp-server.cjs"]
    }
  }
}
```

---

## learn-mcp companion (workspace or global)

```json
"learn-mcp": {
  "command": "PYTHON",
  "args": ["-m", "learn_mcp", "serve"],
  "env": {
    "LEARN_MCP_ROOT": "PROJECT_ROOT"
  }
}
```

Point `LEARN_MCP_ROOT` at the repo whose `.learn/` folder should be analyzed.

---

## skillmcp.toml (project)

```toml
# SkillMCP — injects agent context every session
#
# AGENT.md = rules (always injected).
# skills/*/SKILL.md = IC guides (load via read_skill).

agent_folders = [
    ".agents/",
]
```

---

## README snippet (for project docs)

```markdown
## Agents / Skills MCP

| Layer | Location |
|-------|----------|
| Hard rules | [`.agents/AGENT.md`](.agents/AGENT.md) (injected every session) |
| IC skills | `read_skill(name)` — [`.agents/skills/`](.agents/skills/) |

**MCP config (this repo):**

| Host | File |
|------|------|
| Cursor | `.cursor/mcp.json` |
| Claude Code | `.mcp.json` |
| Antigravity | `.agents/mcp_config.json` |

Setup help: `read_skill('skillmcp-setup')`.
```
