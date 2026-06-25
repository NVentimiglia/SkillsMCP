"""Learn skill MCP tools — paths, script runner, stamp (skillmcp.toml [learn])."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import tomllib
from pathlib import Path

DEFAULT_OUTPUT = ".learn"
DEFAULT_INBOX = "inbox"
LEARN_SKILL = "learn"
ALLOWED_SCRIPTS = frozenset(
    {
        "collect-cursor.py",
        "detect-corrections.py",
        "detect-error-loops.py",
        "detect-keep-going.py",
        "detect-thrashing.py",
        "detect-tool-efficiency.py",
    }
)


def resolve_project_root(project_path: str, fallback: Path) -> Path:
    if project_path and project_path.strip():
        return Path(project_path.strip()).resolve()
    return fallback.resolve()


def load_learn_paths(root: Path) -> dict[str, str]:
    cfg_path = root / "skillmcp.toml"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"skillmcp.toml not found under {root}")
    raw = tomllib.loads(cfg_path.read_text(encoding="utf-8-sig"))
    learn = raw.get("learn", {})
    output = (root / learn.get("output_dir", DEFAULT_OUTPUT)).resolve()
    inbox = (output / learn.get("inbox_dir", DEFAULT_INBOX)).resolve()
    scripts = (root / ".agents" / "skills" / LEARN_SKILL / "scripts").resolve()
    if not (scripts / "detect-thrashing.py").is_file():
        raise FileNotFoundError(f"Missing bundled learn skill scripts: {scripts}")
    return {
        "project_root": str(root),
        "output_dir": str(output),
        "inbox_dir": str(inbox),
        "stamp_file": str(output / "lean.stamp"),
        "scripts_dir": str(scripts),
    }


def ensure_learn_dirs(paths: dict[str, str]) -> None:
    Path(paths["output_dir"]).mkdir(parents=True, exist_ok=True)
    Path(paths["inbox_dir"]).mkdir(parents=True, exist_ok=True)


def run_learn_script(root: Path, script: str, session_path: str = "", since: str = "") -> str:
    name = script if script.endswith(".py") else f"{script}.py"
    if name not in ALLOWED_SCRIPTS:
        allowed = ", ".join(sorted(ALLOWED_SCRIPTS))
        raise ValueError(f"script must be one of: {allowed}")
    script_path = root / ".agents" / "skills" / LEARN_SKILL / "scripts" / name
    if not script_path.is_file():
        raise FileNotFoundError(f"learn script not found: {script_path}")

    cmd = [sys.executable, str(script_path)]
    if name == "collect-cursor.py":
        if since.strip():
            cmd.extend(["--since", since.strip()])
    else:
        if not session_path.strip():
            raise ValueError(f"session_path required for {name}")
        cmd.append(session_path.strip())

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=root,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout
    if proc.stderr.strip():
        out = f"{out.rstrip()}\n{proc.stderr}".strip() if out else proc.stderr.strip()
    return out


def update_learn_stamp(root: Path) -> dict[str, str]:
    paths = load_learn_paths(root)
    ensure_learn_dirs(paths)
    stamp = str(time.time())
    Path(paths["stamp_file"]).write_text(stamp, encoding="utf-8")
    paths["stamp_written"] = stamp
    return paths


def learn_paths_json(project_path: str, fallback: Path) -> str:
    root = resolve_project_root(project_path, fallback)
    return json.dumps(load_learn_paths(root), indent=2)


def learn_run_script_json(
    script: str,
    project_path: str,
    fallback: Path,
    session_path: str = "",
    since: str = "",
) -> str:
    root = resolve_project_root(project_path, fallback)
    output = run_learn_script(root, script, session_path=session_path, since=since)
    return json.dumps({"script": script, "output": output}, ensure_ascii=False)


def learn_stamp_json(project_path: str, fallback: Path) -> str:
    root = resolve_project_root(project_path, fallback)
    paths = update_learn_stamp(root)
    return json.dumps(paths, indent=2)
