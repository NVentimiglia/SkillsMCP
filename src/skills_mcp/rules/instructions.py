from __future__ import annotations

import os

INSTRUCTIONS = """**skills-mcp** is active. Follow these rituals every session.

## Session start
1. Call `list_skills` — check for applicable shared and project-local skills.
2. Call `read_skill(name)` for any skill that applies to the current task.

## During the session
- Call `read_skill` before implementing patterns a skill covers.
- For session learning: `learn_paths` → `learn_run_script` → write inbox → `learn_stamp`.
- After 2 consecutive tool failures, change strategy — do not retry the same action.

Project rules live in the workspace (e.g. `AGENT.md`, `AGENTS.md`, harness pointers) — read those separately; this server only serves skills.
"""


def render_mcp_instructions(*, truncate_at: int | None = None) -> str:
    """MCP ``instructions`` string: fixed skill-server ritual."""
    limit = truncate_at if truncate_at is not None else _max_chars_env()
    if limit is None or limit <= 0:
        return INSTRUCTIONS
    if len(INSTRUCTIONS) <= limit:
        return INSTRUCTIONS
    suffix = "\n\n...(truncated; set SKILLS_MCP_RULES_INSTRUCTIONS_MAX_CHARS=0 for no cap).\n"
    budget = limit - len(suffix)
    if budget < 1:
        return INSTRUCTIONS[:limit]
    return INSTRUCTIONS[:budget].rstrip() + suffix


def _max_chars_env() -> int | None:
    raw = os.environ.get("SKILLS_MCP_RULES_INSTRUCTIONS_MAX_CHARS")
    if raw is None:
        raw = os.environ.get("AGENT_MCP_RULES_INSTRUCTIONS_MAX_CHARS")
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or stripped == "0":
        return None
    try:
        return int(stripped, 10)
    except ValueError:
        return None
