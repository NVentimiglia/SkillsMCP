"""Project layout and MCP registration checks (CLI verify + verify_setup tool)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skills_mcp.config import load_config, resolve_path, resolve_skill_dirs
from skills_mcp.mcp_registration import registration_status
from skills_mcp.paths import CONFIG_NAME


def build_setup_report(
    *,
    root: Path,
    skill_dirs: list[Path],
    skills_count: int,
) -> dict:
    issues: list[str] = []
    warnings: list[str] = []

    cfg_path = root / CONFIG_NAME
    if not cfg_path.is_file():
        issues.append(f"missing {cfg_path}")
    else:
        try:
            cfg = load_config(root)
            for folder in cfg.skill_folders:
                d = resolve_path(root, folder)
                if not d.is_dir():
                    warnings.append(
                        f"skill_folder '{folder}' does not exist yet "
                        "(create it or remove from skill_folders)"
                    )
        except Exception as e:
            issues.append(f"{CONFIG_NAME} invalid: {e}")

    for d in skill_dirs:
        if not d.is_dir():
            issues.append(f"skill_dir_missing: {d}")
    if not skill_dirs:
        issues.append("no skill_folders configured")

    registration = registration_status(root)
    for host, registered in registration.items():
        if not registered:
            warnings.append(
                f"{host}: skills-mcp not registered — run `skills-mcp mcp register` "
                "(host will not spawn the server automatically without this)"
            )

    return {
        "ok": len(issues) == 0,
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_root": str(root.resolve()),
        "skill_dirs": [str(d) for d in skill_dirs],
        "issues": issues,
        "warnings": warnings,
        "skills_count": skills_count,
        "registration": registration,
    }


def run_verify_cli() -> int:
    """Print setup report to stdout; exit 1 on fatal layout issues."""
    import json

    from skills_mcp.app_state import init_app
    from skills_mcp.paths import project_root_from_env_or_discover
    from skills_mcp.skills.loader import SkillIndex

    try:
        root = project_root_from_env_or_discover()
    except Exception as e:
        print(f"verify: error: {e}")
        return 1

    app = init_app(root)
    skills = SkillIndex(app.skill_dirs, project_root=app.root)
    skills.scan()
    report = build_setup_report(
        root=app.root,
        skill_dirs=app.skill_dirs,
        skills_count=len(skills.list_skills_meta()),
    )

    if report["issues"]:
        print("verify: errors:\n- " + "\n- ".join(report["issues"]))
    if report["warnings"]:
        print("verify: warnings:\n- " + "\n- ".join(report["warnings"]))
    if not report["issues"] and not report["warnings"]:
        print(f"verify: OK ({report['skills_count']} skills)")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["issues"] else 0
