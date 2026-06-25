"""Tests that SKILLS_MCP_LIBRARY merges shared skills (skills folder path)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills_mcp.app_state import init_app
from skills_mcp.server import configure_for_tests, list_skills, mcp


def _write_skill(skills_dir: Path, name: str, description: str) -> None:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nBody.\n",
        encoding="utf-8",
    )


@pytest.fixture()
def dual_skill_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    lib_skills = tmp_path / "lib_skills"
    _write_skill(lib_skills, "lib-skill", "From library")

    project = tmp_path / "my_project"
    project.mkdir()
    _write_skill(project / ".agents" / "skills", "proj-skill", "From project")
    (project / "skillmcp.toml").write_text(
        'skill_folders = [".agents/skills"]\n', encoding="utf-8"
    )

    monkeypatch.setenv("SKILLS_MCP_ROOT", str(project))
    monkeypatch.setenv("SKILLS_MCP_LIBRARY", str(lib_skills))

    return lib_skills, project


def test_skill_dirs_include_library_and_project(dual_skill_setup: tuple[Path, Path]) -> None:
    lib_skills, project = dual_skill_setup
    app = init_app(project)

    assert lib_skills.resolve() in app.skill_dirs
    assert (project / ".agents" / "skills").resolve() in app.skill_dirs


def test_instructions_use_default_prompt_only(dual_skill_setup: tuple[Path, Path]) -> None:
    _, project = dual_skill_setup
    configure_for_tests(project)

    instructions = mcp._mcp_server.instructions or ""
    assert "list_skills" in instructions


def test_list_skills_includes_library_skill(dual_skill_setup: tuple[Path, Path]) -> None:
    _, project = dual_skill_setup
    configure_for_tests(project)

    names = [s["name"] for s in json.loads(list_skills())]
    assert "lib-skill" in names


def test_list_skills_includes_project_skill(dual_skill_setup: tuple[Path, Path]) -> None:
    _, project = dual_skill_setup
    configure_for_tests(project)

    names = [s["name"] for s in json.loads(list_skills())]
    assert "proj-skill" in names


def test_project_skill_overrides_library_on_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib_skills = tmp_path / "lib_skills"
    _write_skill(lib_skills, "shared-skill", "Library version")

    project = tmp_path / "project"
    project.mkdir()
    _write_skill(project / ".agents" / "skills", "shared-skill", "Project version")
    (project / "skillmcp.toml").write_text(
        'skill_folders = [".agents/skills"]\n', encoding="utf-8"
    )

    monkeypatch.setenv("SKILLS_MCP_ROOT", str(project))
    monkeypatch.setenv("SKILLS_MCP_LIBRARY", str(lib_skills))

    configure_for_tests(project)

    skills = json.loads(list_skills())
    match = next(s for s in skills if s["name"] == "shared-skill")
    assert "Project version" in match["description"]
