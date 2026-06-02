from __future__ import annotations

import json

import pytest

from skills_mcp.server import configure_for_tests, list_skill_files, read_skill, read_skill_file
from skills_mcp.skills.loader import SkillIndex


def test_skill_index_rejects_duplicate_names(tmp_path) -> None:
    d = tmp_path / "bad_skills"
    d.mkdir()
    (d / "a.md").write_text(
        "---\nname: dup\ndescription: A\ntriggers: []\n---\nBody A\n", encoding="utf-8"
    )
    (d / "b.md").write_text(
        "---\nname: dup\ndescription: B\ntriggers: []\n---\nBody B\n", encoding="utf-8"
    )
    ix = SkillIndex([d], project_root=tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        ix.scan()


def test_skill_missing_frontmatter_skipped(tmp_path) -> None:
    # Files without YAML frontmatter (e.g. Project.md, README.md) are silently
    # ignored so they can coexist in the skills directory without crashing.
    p = tmp_path / "x.md"
    p.write_text("no frontmatter\n", encoding="utf-8")
    ix = SkillIndex([tmp_path], project_root=tmp_path)
    ix.scan()
    assert list(ix.list_skills_meta()) == []


def test_read_skill_rejects_paths(project_home) -> None:
    configure_for_tests(project_home)
    with pytest.raises(KeyError):
        read_skill("does-not-exist")


def test_read_skill_path_injection(project_home) -> None:
    configure_for_tests(project_home)
    with pytest.raises(ValueError):
        read_skill("../../etc/passwd")


def test_read_skill_roundtrip(project_home) -> None:
    (project_home / ".agents" / "skills" / "ping.md").write_text(
        "---\nname: ping\ndescription: Smoke read_skill\n---\nUse list_skills first.\n",
        encoding="utf-8",
    )
    configure_for_tests(project_home)
    body = read_skill("ping")
    assert "list_skills" in body
    assert body.startswith("---")


def test_directory_skill_spec_and_resources(project_home) -> None:
    d = project_home / ".agents" / "skills" / "pdf-processing"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        (
            "---\n"
            "name: pdf-processing\n"
            "description: Extract text and forms from PDFs.\n"
            "license: Apache-2.0\n"
            "compatibility: Requires python and local files\n"
            "metadata:\n"
            "  author: test-suite\n"
            "allowed-tools: Bash(git:*) Read\n"
            "---\n"
            "Use scripts and references as needed.\n"
        ),
        encoding="utf-8",
    )
    (d / "references").mkdir(exist_ok=True)
    (d / "scripts").mkdir(exist_ok=True)
    (d / "assets").mkdir(exist_ok=True)
    (d / "references" / "REFERENCE.md").write_text("Reference doc", encoding="utf-8")
    (d / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (d / "assets" / "template.txt").write_text("template", encoding="utf-8")

    configure_for_tests(project_home)
    from skills_mcp.server import list_skills, read_skill

    skills = json.loads(list_skills())
    item = next(s for s in skills if s["name"] == "pdf-processing")
    assert item["format"] == "directory"
    assert item["references_dir"].endswith("references")
    assert item["scripts_dir"].endswith("scripts")
    assert item["assets_dir"].endswith("assets")

    body = read_skill("pdf-processing")
    assert "Use scripts and references as needed." in body
    assert (d / "references" / "REFERENCE.md").read_text(encoding="utf-8") == "Reference doc"


def test_directory_skill_name_must_match_parent(project_home) -> None:
    d = project_home / ".agents" / "skills" / "code-review"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: reviewer\ndescription: mismatch name\n---\nBody\n",
        encoding="utf-8",
    )
    ix = SkillIndex([project_home / ".agents" / "skills"], project_root=project_home)
    with pytest.raises(ValueError, match="must match parent directory"):
        ix.scan()


def test_skill_name_constraints_enforced(project_home) -> None:
    """A SKILL.md with an invalid name is silently skipped (warn+skip keeps server alive)."""
    d = project_home / ".agents" / "skills" / "bad-name"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: Bad-Name\ndescription: invalid case\n---\nBody\n",
        encoding="utf-8",
    )
    ix = SkillIndex([project_home / ".agents" / "skills"], project_root=project_home)
    ix.scan()  # must NOT raise — invalid skill is warned and skipped
    names = [s["name"] for s in ix.list_skills_meta()]
    assert "Bad-Name" not in names
    assert "bad-name" not in names


def test_list_skill_files_and_read_skill_file(project_home) -> None:
    d = project_home / ".agents" / "skills" / "toolbox"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: toolbox\ndescription: has refs/scripts/assets\n---\nBody\n",
        encoding="utf-8",
    )
    (d / "references").mkdir(exist_ok=True)
    (d / "scripts").mkdir(exist_ok=True)
    (d / "assets").mkdir(exist_ok=True)
    (d / "references" / "guide.md").write_text("Guide text", encoding="utf-8")
    (d / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (d / "assets" / "template.txt").write_text("TEMPLATE", encoding="utf-8")

    configure_for_tests(project_home)
    refs = json.loads(list_skill_files("toolbox", "references"))
    assert refs[0]["path"] == "guide.md"
    assert isinstance(refs[0]["bytes"], int)

    script = read_skill_file("toolbox", "run.py", kind="scripts")
    assert "print('ok')" in script


def test_read_skill_file_rejects_traversal(project_home) -> None:
    d = project_home / ".agents" / "skills" / "safe-skill"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: safe-skill\ndescription: safe\n---\nBody\n",
        encoding="utf-8",
    )
    (d / "references").mkdir(exist_ok=True)
    (d / "references" / "ok.md").write_text("ok", encoding="utf-8")
    configure_for_tests(project_home)

    with pytest.raises(ValueError, match="inside the skill directory"):
        read_skill_file("safe-skill", "../SKILL.md", kind="references")


def test_list_skill_files_invalid_kind(project_home) -> None:
    d = project_home / ".agents" / "skills" / "kind-check"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: kind-check\ndescription: check kind\n---\nBody\n",
        encoding="utf-8",
    )
    configure_for_tests(project_home)

    with pytest.raises(ValueError, match="invalid kind"):
        list_skill_files("kind-check", "docs")


