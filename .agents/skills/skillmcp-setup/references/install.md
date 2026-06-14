# Skills MCP — install by platform

Python **≥ 3.11** required.

---

## Windows

### Option A — uv (recommended)

```powershell
cd D:\Projects\Agents\SkillMCP
uv sync
uv run skills-mcp --version
```

### Option B — pip (editable)

```powershell
cd D:\Projects\Agents\SkillMCP
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
skills-mcp --version
```

### Windows notes

- Use **full path** to `python.exe` in MCP host configs (hosts often spawn without PATH).
- Claude Code on Windows: add **`-u`** (unbuffered) before `-m skills_mcp` in args.
- Chain shell commands with **`;`** not `&&` in PowerShell.

Example python path after venv install:

```
D:\Projects\Agents\.venv\Scripts\python.exe
```

---

## macOS / Linux

### Option A — uv

```bash
cd /path/to/SkillMCP
uv sync
uv run skills-mcp --version
```

### Option B — pip

```bash
cd /path/to/SkillMCP
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
skills-mcp --version
```

MCP config `command`:

```
/path/to/SkillMCP/.venv/bin/python
```

---

## Initialize a project

From the **project root** (where you want `skillmcp.toml`):

```bash
skills-mcp init .
```

Creates:

```
your-project/
  skillmcp.toml
  .agents/
    AGENT.md
    skills/
```

### Verify

```bash
skills-mcp doctor
```

`doctor` checks layout and **global** host registration. Workspace-only setups may
warn "not registered" while still working — see `host-wiring.md`.

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| `SKILLS_MCP_ROOT` | Project dir containing `skillmcp.toml` (set by host MCP config) |
| `SKILLS_MCP_LIBRARY` | Optional shared `.agents` folder (lowest skill priority) |
| `SKILLS_MCP_RULES_INSTRUCTIONS_MAX_CHARS` | Cap injected AGENT.md size (`0` = no cap) |

---

## Standalone install

SkillMCP does **not** require the parent Agents monorepo. Clone/copy only the
`SkillMCP` package directory, install, then `init` in each project.

---

## Upgrade

```bash
cd /path/to/SkillMCP
git pull   # if from git
uv sync    # or pip install -e .
```

Re-open agent hosts. No migration needed unless `skillmcp.toml` schema changes
(check package CHANGELOG).
