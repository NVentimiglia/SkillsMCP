# Skills MCP — best practices

---

## What goes where

| Concern | Location | Loaded |
|---------|----------|--------|
| Never-break rules | `.agents/AGENT.md` | Every session (MCP instructions) |
| Task IC guides | `.agents/skills/<name>/SKILL.md` | On demand (`read_skill`) |
| Architecture truth | Project design docs | Linked from L1/L2 |
| IDE-specific globs | `.cursor/rules/*.mdc` | Cursor only |
| Tool entry stubs | `README.md`, `CLAUDE.md`, `AGENTS.md` | Pointers only (≤5 lines) |

**Anti-patterns:**

- 400-line `.cursorrules` duplicating or contradicting `AGENT.md`
- Pasting full hot-path design into every skill (link instead)
- `mcpServers` in Claude `settings.json` (ignored)
- One global `SKILLS_MCP_ROOT` for unrelated repos

---

## skillmcp.toml

```toml
agent_folders = [
    ".agents/",
]
```

Multiple folders (last wins on skill **name** collision; all `AGENT.md` files **merge**):

```toml
agent_folders = [
    "/path/to/shared/agents",
    ".agents/",
]
```

---

## Skill authoring

Each skill directory:

```
.agents/skills/my-skill/
  SKILL.md              # required — YAML frontmatter + body
  references/           # optional — read via list_skill_files / read_skill_file
  scripts/              # optional
  assets/               # optional
```

Frontmatter minimum:

```yaml
---
name: my-skill
description: >-
  One paragraph: what + when to trigger. Include stack and project name.
---
```

GammaCharts IC skills should open with:

1. Assume injected `AGENT.md`
2. Skill-specific `references/<checklist>.md`
3. Link to canonical design doc

SDK skills (`scott-plot`, `skia`) stay generic; pair from IC skills via `pairs_with`.

---

## Library vs project skills

| Source | Path | Priority |
|--------|------|----------|
| Library | `SKILLS_MCP_LIBRARY` → `skills/` | Lowest |
| Project | `<root>/.agents/skills/` | Wins on name collision |

Ship cross-cutting workflow skills (`role-plan`, `handoff`, `skillmcp-setup`) in the library.
Ship domain IC skills (`code-chart`, `data-path`) in each project.

---

## Companion MCP servers

Run **separate processes** — do not fold memory/learn into SkillMCP.

| Server | Purpose | Config tip |
|--------|---------|------------|
| `skills-mcp` | Rules + skills | Workspace-rooted per repo |
| `learn-mcp` | Friction analysis → `.learn/` | `LEARN_MCP_ROOT` per project |
| `claude-mem` | Cross-session memory | Global OK; node/bun path |

Keep global MCP lean. Project-scoped servers belong in workspace config files.

---

## Multi-tool adapter pattern

Same content, thin per-tool stubs:

```
README.md          ← hub
.agents/AGENT.md   ← L1 rules (SkillMCP injects)
CLAUDE.md          ← pointer → README
AGENTS.md          ← pointer → README (Antigravity)
GEMINI.md          ← pointer → README

Cursor:     .cursor/mcp.json + .cursor/rules/*.mdc
Claude:     .mcp.json
Antigravity: .agents/mcp_config.json
```

Document MCP paths in the project's always-on cursor rule (e.g. `gammacharts-agent.mdc`).

---

## Verification checklist (new teammate)

1. `skills-mcp --version` works
2. Open repo in Cursor / Claude / Antigravity
3. MCP tools visible: `verify_setup`, `list_skills`, `read_skill`
4. `verify_setup.project_root` matches opened repo
5. `list_skills` includes expected project skill names
6. Session instructions show **this** project's `AGENT.md`
7. `read_skill('<domain-skill>')` loads before IC work

---

## Telemetry

SkillMCP writes `telemetry.json` in `SKILLS_MCP_ROOT`. Optional; safe to gitignore.
Use `skill_health` for server counters.

---

## Related tools

| Tool | Relationship |
|------|----------------|
| **LearnSkill** (`learn-mcp`) | Audits sessions → `.learn/proposals/` → promote to skills or `AGENT.md` lessons |
| **claude-mem** | Long-term memory; orthogonal to skills |
| **skill-creator** | Authoring/eval skills in library |

SkillMCP answers *what should the agent do?* Learn answers *what friction happened?*
