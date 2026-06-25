"""Tests for skill_folders — multiple skill directories merging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills_mcp.app_state import init_app
from skills_mcp.cli import cmd_init
from skills_mcp.config import DEFAULT_SKILL_FOLDERS, load_config
from skills_mcp.server import configure_for_tests, list_skills


def _make_project(tmp_path: Path, config: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SKILLS_MCP_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    cmd_init(tmp_path)
    (tmp_path / "skillmcp.toml").write_text(config, encoding="utf-8")
    return tmp_path


def _write_skill(directory: Path, name: str, description: str = "A skill") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nBody.\n",
        encoding="utf-8",
    )


def test_empty_skill_folders_defaults_to_agents_skills(tmp_path: Path) -> None:
    (tmp_path / "skillmcp.toml").write_text("skill_folders = []\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.skill_folders == list(DEFAULT_SKILL_FOLDERS)


def test_missing_skillmcp_uses_default_skill_folders(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert cfg.skill_folders == list(DEFAULT_SKILL_FOLDERS)


def test_skill_dirs_populated_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_skills = tmp_path / "shared_skills"
    shared_skills.mkdir()

    cfg = f'skill_folders = ["{shared_skills.as_posix()}", ".agents/skills"]\n'
    root = _make_project(tmp_path, cfg, monkeypatch)
    app = init_app(root)

    assert len(app.skill_dirs) == 2
    assert app.skill_dirs[0] == shared_skills.resolve()
    assert app.skill_dirs[1] == (root / ".agents" / "skills").resolve()


def test_missing_skill_dir_excluded_from_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nonexistent = tmp_path / "ghost_skills"
    cfg = f'skill_folders = ["{nonexistent.as_posix()}", ".agents/skills"]\n'
    root = _make_project(tmp_path, cfg, monkeypatch)
    init_app(root)
    configure_for_tests(root)
    skills = json.loads(list_skills())
    assert isinstance(skills, list)


def test_single_folder_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = 'skill_folders = [".agents/skills"]\n'
    root = _make_project(tmp_path, cfg, monkeypatch)
    app = init_app(root)
    assert len(app.skill_dirs) == 1


def test_shared_skills_visible_via_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_skills = tmp_path / "shared_skills"
    _write_skill(shared_skills, "shared-widget", "A shared widget skill")

    cfg = f'skill_folders = ["{shared_skills.as_posix()}", ".agents/skills"]\n'
    root = _make_project(tmp_path, cfg, monkeypatch)
    configure_for_tests(root)

    skills = json.loads(list_skills())
    names = [s["name"] for s in skills]
    assert "shared-widget" in names


def test_last_folder_wins_on_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_skills = tmp_path / "shared_skills"
    _write_skill(shared_skills, "my-skill", "Shared version")

    cfg = f'skill_folders = ["{shared_skills.as_posix()}", ".agents/skills"]\n'
    root = _make_project(tmp_path, cfg, monkeypatch)
    _write_skill(root / ".agents" / "skills", "my-skill", "Project version")
    configure_for_tests(root)

    skills = json.loads(list_skills())
    match = next(s for s in skills if s["name"] == "my-skill")
    assert "Project version" in match["description"]


def test_no_extra_folders_works_normally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = 'skill_folders = [".agents/skills"]\n'
    root = _make_project(tmp_path, cfg, monkeypatch)
    app = init_app(root)
    assert len(app.skill_dirs) == 1
