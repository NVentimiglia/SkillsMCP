from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from skills_mcp.learn_tools import load_learn_paths, update_learn_stamp
from skills_mcp.server import configure_for_tests, learn_paths, learn_run_script, learn_stamp


def _learn_scripts_src() -> Path:
    learn_skill = Path(__file__).resolve().parents[2].parent / "LearnSkill" / "learn" / "scripts"
    if learn_skill.is_dir():
        return learn_skill
    scaffold = (
        Path(__file__).resolve().parents[2].parent.parent
        / "AgentScaffold"
        / "NewProject"
        / ".agents"
        / "skills"
        / "learn"
        / "scripts"
    )
    if scaffold.is_dir():
        return scaffold
    raise FileNotFoundError("learn scripts directory not found")


@pytest.fixture
def learn_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    learn_dir = root / ".agents" / "skills" / "learn"
    shutil.copytree(_learn_scripts_src(), learn_dir / "scripts")
    (learn_dir / "SKILL.md").write_text("---\nname: learn\ndescription: test\n---\n", encoding="utf-8")
    (root / "skillmcp.toml").write_text(
        'skill_folders = [".agents/skills"]\n\n[learn]\noutput_dir = ".learn"\ninbox_dir = "inbox"\n',
        encoding="utf-8",
    )
    fixture = Path(__file__).resolve().parents[2].parent / "LearnSkill" / "tests" / "fixtures" / "claude_thrashing.jsonl"
    if fixture.is_file():
        shutil.copy(fixture, root / "session.jsonl")
    return root


def test_load_learn_paths(learn_project: Path) -> None:
    paths = load_learn_paths(learn_project)
    assert Path(paths["inbox_dir"]).name == "inbox"
    assert Path(paths["scripts_dir"]).is_dir()


def test_learn_stamp_creates_inbox(learn_project: Path) -> None:
    configure_for_tests(learn_project)
    data = json.loads(learn_stamp(str(learn_project)))
    assert Path(data["inbox_dir"]).is_dir()
    assert Path(data["stamp_file"]).is_file()


def test_learn_paths_tool(learn_project: Path) -> None:
    configure_for_tests(learn_project)
    data = json.loads(learn_paths(str(learn_project)))
    assert "scripts_dir" in data


def test_learn_run_detector(learn_project: Path) -> None:
    configure_for_tests(learn_project)
    session = learn_project / "session.jsonl"
    if not session.is_file():
        pytest.skip("claude_thrashing.jsonl fixture not available")
    raw = learn_run_script("detect-thrashing.py", str(learn_project), str(session))
    data = json.loads(raw)
    assert "THRASH" in data["output"] or data["output"] == ""
