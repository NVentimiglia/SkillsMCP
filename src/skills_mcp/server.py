from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from mcp.server.fastmcp import FastMCP

from skills_mcp.app_state import AppContext, init_app, reset_app
from skills_mcp.config import load_config, resolve_path
from skills_mcp.paths import project_root_from_env_or_discover
from skills_mcp.rules.instructions import render_mcp_seed_text
from skills_mcp.skills.loader import SkillIndex

mcp = FastMCP("skills-mcp")

_SKILLS: SkillIndex | None = None
_APP: AppContext | None = None


def configure_for_tests(root: Path) -> AppContext:
    """Initialize server globals (used by tests)."""
    return configure(root=root)


def configure(root: Path | None = None) -> AppContext:
    global _SKILLS, _APP
    if root is None:
        try:
            root = project_root_from_env_or_discover()
        except FileNotFoundError as e:
            raise RuntimeError(f"Cannot initialize SkillsMCP: {e}") from e
    _APP = init_app(root)
    _SKILLS = SkillIndex(_APP.skill_dirs, project_root=_APP.root)
    _SKILLS.scan()
    agent_md = _load_agent_md(_APP.agent_dirs)
    mcp._mcp_server.instructions = render_mcp_seed_text(agent_md_content=agent_md)

    from skills_mcp.telemetry import record_session
    record_session(_APP.root)

    return _APP


def _load_agent_md(agent_dirs: list[Path]) -> str | None:
    """Read AGENT.md from each agent folder; return combined content, else None."""
    parts = []
    for d in agent_dirs:
        path = d / "AGENT.md"
        if path.is_file():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                parts.append(content)
    return "\n\n".join(parts) if parts else None


def reset_runtime() -> None:
    global _SKILLS, _APP
    _SKILLS = None
    _APP = None
    reset_app()


def _require_runtime() -> tuple[SkillIndex, AppContext]:
    if _SKILLS is None or _APP is None:
        configure()
    return _SKILLS, _APP


def _run_traced(
    tool_name: str,
    fn: Callable[[], str],
) -> str:
    """Execute tool function."""
    _skills, app = _require_runtime()
    from skills_mcp.telemetry import record_tool_call
    record_tool_call(app.root, tool_name)
    return fn()


def _impl_verify_setup() -> str:
    skills, app = _require_runtime()

    issues: list[str] = []
    for d in app.skill_dirs:
        if not d.is_dir():
            issues.append(f"skill_dir_missing: {d}")
    if not app.skill_dirs:
        issues.append("no agent_folders configured")

    meta = skills.list_skills_meta()

    report = {
        "ok": len(issues) == 0,
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_root": str(app.root.resolve()),
        "skill_dirs": [str(d) for d in app.skill_dirs],
        "issues": issues,
        "skills_count": len(meta),
    }
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False)


@mcp.tool()
def verify_setup(session_note: str = "") -> str:
    """One-call health snapshot: paths and skill counts."""
    return _run_traced("verify_setup", _impl_verify_setup)


def _local_skill_index(project_path: str, app: AppContext) -> "SkillIndex | None":
    """Build a SkillIndex for a local project path if it differs from the global root."""
    if not project_path or not project_path.strip():
        return None
    local_root = Path(project_path.strip()).resolve()
    if local_root == app.root:
        return None
    # Load agent_folders from local skillmcp.toml if present, else default
    local_cfg_path = local_root / "skillmcp.toml"
    if local_cfg_path.is_file():
        local_cfg = load_config(local_root)
        agent_dirs = [resolve_path(local_root, f) for f in local_cfg.agent_folders]
        dirs = [d / "skills" for d in agent_dirs]
    else:
        default = local_root / ".agents" / "skills"
        if not default.is_dir():
            return None
        dirs = [default]
    dirs = [d for d in dirs if d.is_dir()]
    if not dirs:
        return None
    idx = SkillIndex(dirs, project_root=local_root)
    idx.scan()
    return idx


def _impl_list_skills(project_path: str) -> str:
    skills, app = _require_runtime()
    global_meta = list(skills.list_skills_meta())
    local_idx = _local_skill_index(project_path, app)
    if local_idx is None:
        return json.dumps(global_meta, ensure_ascii=False)
    local_meta = list(local_idx.list_skills_meta())
    local_names = {m["name"] for m in local_meta}
    merged = local_meta + [m for m in global_meta if m["name"] not in local_names]
    return json.dumps(merged, ensure_ascii=False)


@mcp.tool()
def list_skills(project_path: str = "", session_note: str = "") -> str:
    """Return JSON list of skill metadata — global skills merged with local project skills.

    Pass ``project_path`` (absolute path of the project you are working in) to
    include skills from that project's skill folders.  Local skills take
    precedence over global on name collision.
    """
    return _run_traced("list_skills", lambda: _impl_list_skills(project_path))


def _impl_read_skill(name: str, project_path: str, usage_reason: str) -> str:
    skills, app = _require_runtime()
    from skills_mcp.telemetry import record_skill_access
    record_skill_access(app.root, name)
    local_idx = _local_skill_index(project_path, app)
    if local_idx is not None:
        try:
            sk = local_idx.get_by_name(name)
            return sk.parsed.full_markdown()
        except (KeyError, ValueError):
            pass
    sk = skills.get_by_name(name)
    return sk.parsed.full_markdown()


@mcp.tool()
def read_skill(name: str, project_path: str = "", usage_reason: str = "", session_note: str = "") -> str:
    """Return the full Markdown for a skill by name.

    Checks the local project's skill folders first (if ``project_path`` given),
    then falls back to global skills.
    """
    return _run_traced("read_skill", lambda: _impl_read_skill(name, project_path, usage_reason))


_SKILL_FILE_KINDS = {"references", "scripts", "assets"}


def _resolve_skill_with_optional_local(name: str, project_path: str):
    skills, app = _require_runtime()
    local_idx = _local_skill_index(project_path, app)
    if local_idx is not None:
        try:
            return local_idx.get_by_name(name)
        except (KeyError, ValueError):
            pass
    return skills.get_by_name(name)


def _skill_files_dir(skill, kind: str) -> Path:
    if kind not in _SKILL_FILE_KINDS:
        allowed = ", ".join(sorted(_SKILL_FILE_KINDS))
        raise ValueError(f"invalid kind `{kind}`; expected one of: {allowed}")
    rel = cast(str | None, getattr(skill, f"{kind}_dir"))
    if not rel:
        raise FileNotFoundError(f"skill `{skill.parsed.fm.name}` has no `{kind}` directory")
    return (skill.skill_root / kind).resolve()


def _impl_list_skill_files(name: str, kind: str, project_path: str) -> str:
    sk = _resolve_skill_with_optional_local(name, project_path)
    base = _skill_files_dir(sk, kind)
    if not base.is_dir():
        raise FileNotFoundError(f"`{kind}` directory missing for skill `{name}`")

    rows: list[dict[str, str | int]] = []
    for file_path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = file_path.relative_to(base).as_posix()
        stat = file_path.stat()
        rows.append(
            {
                "path": rel,
                "bytes": stat.st_size,
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return json.dumps(rows, ensure_ascii=False)


@mcp.tool()
def list_skill_files(
    name: str,
    kind: str = "references",
    project_path: str = "",
    session_note: str = "",
) -> str:
    """List files under a skill's references/scripts/assets directory.

    Returns JSON rows with relative path, byte size, and modified timestamp.
    """
    return _run_traced("list_skill_files", lambda: _impl_list_skill_files(name, kind, project_path))


def _impl_read_skill_file(name: str, kind: str, rel_path: str, project_path: str) -> str:
    sk = _resolve_skill_with_optional_local(name, project_path)
    base = _skill_files_dir(sk, kind)
    if not base.is_dir():
        raise FileNotFoundError(f"`{kind}` directory missing for skill `{name}`")

    candidate = (base / rel_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("rel_path must stay inside the skill directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"file not found: {rel_path}")
    return candidate.read_text(encoding="utf-8")


@mcp.tool()
def read_skill_file(
    name: str,
    rel_path: str,
    kind: str = "references",
    project_path: str = "",
    session_note: str = "",
) -> str:
    """Read one UTF-8 text file from a skill's references/scripts/assets directory."""
    return _run_traced(
        "read_skill_file",
        lambda: _impl_read_skill_file(name, kind, rel_path, project_path),
    )


def _impl_skill_health() -> str:
    skills, app = _require_runtime()
    from skills_mcp.telemetry import _load_telemetry
    
    file_path = app.root / "telemetry.json"
    data = _load_telemetry(file_path)
    
    call_number = data.get("ToolCalls", {}).get("skill_health", 0)
    
    report = {
        "status": "healthy",
        "call_number": call_number,
        "total_sessions": data.get("TotalSessions", 0),
        "total_skill_calls": data.get("TotalSkillCalls", 0),
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return json.dumps(report, indent=2, ensure_ascii=False)


@mcp.tool()
def skill_health(session_note: str = "") -> str:
    """Check health of the SkillsMCP server and return invocation sequence info."""
    return _run_traced("skill_health", _impl_skill_health)


def run_stdio_server(root: Path | None = None) -> None:
    configure(root=root)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio_server()
