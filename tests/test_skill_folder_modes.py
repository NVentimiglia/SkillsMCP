"""Tests for multi-skill libraries vs single-skill folder paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills_mcp.server import configure_for_tests, list_skills, read_skill
from skills_mcp.skills.loader import SkillIndex, _is_single_skill_folder


def _write_dir_skill(folder: Path, name: str, description: str = "desc") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nBody for {name}.\n",
        encoding="utf-8",
    )


def test_is_single_skill_folder_detects_root_skill_md(tmp_path: Path) -> None:
    lib = tmp_path / "skills-lib"
    lib.mkdir()
    assert _is_single_skill_folder(lib) is False

    single = tmp_path / "learn"
    _write_dir_skill(single, "learn")
    assert _is_single_skill_folder(single) is True


def test_single_skill_folder_loads_one_skill(tmp_path: Path) -> None:
    single = tmp_path / "learn"
    _write_dir_skill(single, "learn", "Session learning skill")

    ix = SkillIndex([single], project_root=tmp_path)
    ix.scan()

    meta = ix.list_skills_meta()
    assert len(meta) == 1
    assert meta[0]["name"] == "learn"
    assert "Session learning" in meta[0]["description"]


def test_single_skill_folder_allows_name_dir_mismatch(tmp_path: Path) -> None:
    folder = tmp_path / "learn-skill"
    _write_dir_skill(folder, "learn", "Name differs from folder")

    ix = SkillIndex([folder], project_root=tmp_path)
    ix.scan()

    assert ix.get_by_name("learn").parsed.fm.description == "Name differs from folder"


def test_multi_skill_library_loads_children(tmp_path: Path) -> None:
    lib = tmp_path / ".agents" / "skills"
    _write_dir_skill(lib / "alpha", "alpha")
    _write_dir_skill(lib / "beta", "beta")

    ix = SkillIndex([lib], project_root=tmp_path)
    ix.scan()

    names = {s["name"] for s in ix.list_skills_meta()}
    assert names == {"alpha", "beta"}


def test_mixed_single_skill_and_library_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    single = tmp_path / "external" / "learn"
    _write_dir_skill(single, "learn", "From single folder")

    lib = tmp_path / ".agents" / "skills"
    _write_dir_skill(lib / "project-starter", "project-starter", "From library")

    (tmp_path / "skillmcp.toml").write_text(
        f'skill_folders = [\n  "{single.as_posix()}",\n  ".agents/skills",\n]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILLS_MCP_ROOT", str(tmp_path))

    configure_for_tests(tmp_path)
    names = {s["name"] for s in json.loads(list_skills())}
    assert names == {"learn", "project-starter"}


def test_library_with_root_skill_md_is_single_not_container(tmp_path: Path) -> None:
    lib = tmp_path / "skills"
    lib.mkdir()
    _write_dir_skill(lib, "root-skill", "Only this skill")
    _write_dir_skill(lib / "nested", "nested", "Must not load when root SKILL.md exists")

    ix = SkillIndex([lib], project_root=tmp_path)
    ix.scan()

    names = {s["name"] for s in ix.list_skills_meta()}
    assert names == {"root-skill"}


def test_read_skill_from_single_skill_folder_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    single = tmp_path / "learn"
    _write_dir_skill(single, "learn", "Readable")
    (tmp_path / "skillmcp.toml").write_text(
        f'skill_folders = ["{single.as_posix()}"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILLS_MCP_ROOT", str(tmp_path))

    configure_for_tests(tmp_path)
    body = read_skill("learn")
    assert "Body for learn." in body
