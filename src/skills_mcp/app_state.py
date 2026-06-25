from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from skills_mcp.config import AgentConfig, load_config, resolve_skill_dirs_with_library
from skills_mcp.paths import CONFIG_NAME


@dataclass
class AppContext:
    """Resolved filesystem layout for one project."""

    root: Path
    config: AgentConfig
    #: Resolved skill directories in priority order (last = highest priority).
    skill_dirs: list[Path]


_APP: AppContext | None = None


def init_app(root: Path) -> AppContext:
    cfg = load_config(root)
    resolved_root = root.resolve()
    skill_dirs = resolve_skill_dirs_with_library(resolved_root, cfg)

    global _APP
    _APP = AppContext(
        root=resolved_root,
        config=cfg,
        skill_dirs=skill_dirs,
    )
    return _APP


def get_app() -> AppContext:
    if _APP is None:
        raise RuntimeError(f"SkillsMCP not initialized. Missing {CONFIG_NAME} load?")
    return _APP


def reset_app() -> None:
    global _APP
    _APP = None
