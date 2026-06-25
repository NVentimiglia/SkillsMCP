from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from mcp.server.fastmcp import FastMCP

from skills_mcp.app_state import AppContext, init_app, reset_app
from skills_mcp.config import load_config, resolve_skill_dirs
from skills_mcp.paths import project_root_from_env_or_discover
from skills_mcp.learn_tools import (
    learn_paths_json,
    learn_run_script_json,
    learn_stamp_json,
)
from skills_mcp.rules.instructions import render_mcp_instructions
from skills_mcp.setup_check import build_setup_report
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
    mcp._mcp_server.instructions = render_mcp_instructions()

    return _APP


def reset_runtime() -> None:
    global _SKILLS, _APP
    _SKILLS = None
    _APP = None
    reset_app()


def _require_runtime() -> tuple[SkillIndex, AppContext]:
    if _SKILLS is None or _APP is None:
        configure()
    return _SKILLS, _APP


def _impl_verify_setup() -> str:
    skills, app = _require_runtime()
    meta = skills.list_skills_meta()
    report = build_setup_report(
        root=app.root,
        skill_dirs=app.skill_dirs,
        skills_count=len(meta),
    )
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False)


@mcp.tool()
def verify_setup(session_note: str = "") -> str:
    """One-call health snapshot: paths, skill counts, and registration status."""
    return _impl_verify_setup()


def _local_skill_index(project_path: str, app: AppContext) -> "SkillIndex | None":
    """Build a SkillIndex for a local project path if it differs from the global root."""
    if not project_path or not project_path.strip():
        return None
    local_root = Path(project_path.strip()).resolve()
    if local_root == app.root:
        return None
    # Load skill_folders from local skillmcp.toml if present, else default
    local_cfg_path = local_root / "skillmcp.toml"
    if local_cfg_path.is_file():
        local_cfg = load_config(local_root)
        dirs = resolve_skill_dirs(local_root, local_cfg)
    else:
        default = resolve_skill_dirs(local_root, load_config(local_root))
        dirs = default
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
    return _impl_list_skills(project_path)


def _impl_read_skill(name: str, project_path: str, usage_reason: str) -> str:
    skills, app = _require_runtime()
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
    return _impl_read_skill(name, project_path, usage_reason)


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
    return _impl_list_skill_files(name, kind, project_path)


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
    return _impl_read_skill_file(name, kind, rel_path, project_path)


@mcp.tool()
def learn_paths(project_path: str = "", session_note: str = "") -> str:
    """Resolve LearnSkill output paths from skillmcp.toml [learn] section.

    Returns JSON: project_root, output_dir, inbox_dir, stamp_file, scripts_dir.
    """
    _, app = _require_runtime()
    return learn_paths_json(project_path, app.root)


@mcp.tool()
def learn_run_script(
    script: str,
    project_path: str = "",
    session_path: str = "",
    since: str = "",
    session_note: str = "",
) -> str:
    """Run a bundled learn skill script (detectors or collect-cursor).

    script: e.g. detect-thrashing.py or collect-cursor.py
    session_path: required for detect-* scripts (path to JSONL session file)
    since: optional Unix timestamp for collect-cursor.py
    Returns JSON with stdout (stderr appended if present).
    """
    _, app = _require_runtime()
    return learn_run_script_json(script, project_path, app.root, session_path, since)


@mcp.tool()
def learn_stamp(project_path: str = "", session_note: str = "") -> str:
    """Ensure .learn output dirs exist and update lean.stamp after a learn run."""
    _, app = _require_runtime()
    return learn_stamp_json(project_path, app.root)


def run_stdio_server(root: Path | None = None) -> None:
    configure(root=root)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio_server()
