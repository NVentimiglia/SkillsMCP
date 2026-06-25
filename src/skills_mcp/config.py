from __future__ import annotations

import os
from pathlib import Path

import tomli
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_SKILL_FOLDERS: tuple[str, ...] = (".agents/skills",)


class LearnConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    output_dir: str = ".learn"
    inbox_dir: str = "inbox"


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    #: Skill library (many skills) or single-skill folder (SKILL.md at root). Last wins.
    skill_folders: list[str] = Field(default_factory=lambda: list(DEFAULT_SKILL_FOLDERS))
    learn: LearnConfig = Field(default_factory=LearnConfig)

    @model_validator(mode="after")
    def _default_empty_skill_folders(self) -> AgentConfig:
        if not self.skill_folders:
            return self.model_copy(update={"skill_folders": list(DEFAULT_SKILL_FOLDERS)})
        return self


def load_config(root: Path) -> AgentConfig:
    path = root / "skillmcp.toml"
    if not path.is_file():
        return AgentConfig()
    data = tomli.loads(path.read_text(encoding="utf-8"))
    return AgentConfig.model_validate(data)


def resolve_path(root: Path, rel: str) -> Path:
    p = Path(rel).expanduser()
    return p.resolve() if p.is_absolute() else (root / rel).resolve()


def resolve_skill_dirs(root: Path, cfg: AgentConfig) -> list[Path]:
    return [resolve_path(root, folder) for folder in cfg.skill_folders]


def resolve_skill_dirs_with_library(root: Path, cfg: AgentConfig | None = None) -> list[Path]:
    if cfg is None:
        cfg = load_config(root)
    skill_dirs = resolve_skill_dirs(root, cfg)

    library_env = os.environ.get("SKILLS_MCP_LIBRARY")
    if not library_env:
        return skill_dirs

    library_path = Path(library_env).resolve()
    if not library_path.is_dir():
        return skill_dirs

    resolved = {d.resolve() for d in skill_dirs}
    if library_path in resolved:
        return skill_dirs
    return [library_path, *skill_dirs]
