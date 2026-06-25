from __future__ import annotations

import json

from skills_mcp.server import configure_for_tests, list_skills, verify_setup


def test_verify_setup_reports_paths_and_counts(project_home) -> None:
    configure_for_tests(project_home)
    raw = verify_setup()
    rep = json.loads(raw)
    assert rep["skills_count"] >= 0
    assert isinstance(rep["issues"], list)
    assert "skill_dirs" in rep
    assert isinstance(rep["skill_dirs"], list)
    assert "skills_count" in rep
    assert "registration" in rep
    assert "warnings" in rep


def test_list_skills_returns_json_array(project_home) -> None:
    configure_for_tests(project_home)
    skills = json.loads(list_skills())
    assert isinstance(skills, list)
