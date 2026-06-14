"""Register skills-mcp as an MCP server in host agent configs.

Once registered, the host spawns ``skills-mcp serve`` automatically at session
start — the user never runs it manually.

Supported hosts (workspace-first where possible)
------------------------------------------------
claude      — <project>/.mcp.json
cursor      — <project>/.cursor/mcp.json
gemini      — ~/.gemini/settings.json  (global)
antigravity — <project>/.agents/mcp_config.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SERVER_KEY = "skills-mcp"


def _load_json(path: Path) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _server_entry(project_root: Path) -> dict:
    """Build the mcpServers entry for this installation."""
    root_path = str(project_root.resolve())
    env: dict[str, str] = {"SKILLS_MCP_ROOT": root_path}

    pkg_agent = Path(__file__).resolve().parent.parent.parent / ".agents"
    if pkg_agent.is_dir():
        env["SKILLS_MCP_LIBRARY"] = str(pkg_agent)

    args = ["-m", "skills_mcp", "serve", "--root", root_path]
    if sys.platform == "win32":
        args = ["-u", *args]

    return {
        "command": sys.executable,
        "args": args,
        "env": env,
    }


def _register_host(settings_path: Path, project_root: Path) -> tuple[bool, str]:
    """Generic registration logic for any host."""
    data = _load_json(settings_path)
    servers = data.setdefault("mcpServers", {})
    entry = _server_entry(project_root)

    if _SERVER_KEY in servers:
        existing = servers[_SERVER_KEY]
        if (
            existing.get("command") == entry["command"]
            and existing.get("args") == entry["args"]
            and existing.get("env", {}).get("SKILLS_MCP_ROOT") == entry["env"]["SKILLS_MCP_ROOT"]
        ):
            return False, f"already registered ({settings_path})"

    servers[_SERVER_KEY] = entry
    try:
        _save_json(settings_path, data)
    except OSError as exc:
        return False, f"could not write {settings_path}: {exc}"
    return True, str(settings_path)


def _resolve_project_root(project_root: Path | None) -> Path | None:
    if project_root is not None:
        return project_root.resolve()
    try:
        from skills_mcp.paths import project_root_from_env_or_discover

        return project_root_from_env_or_discover()
    except FileNotFoundError:
        return None


def _host_registered(settings_path: Path) -> bool:
    data = _load_json(settings_path)
    return _SERVER_KEY in (data.get("mcpServers") or {})


# ---------------------------------------------------------------------------
# Claude Code  (<project>/.mcp.json)
# ---------------------------------------------------------------------------


def _claude_settings(project_root: Path) -> Path:
    return project_root / ".mcp.json"


def claude_registered(project_root: Path | None = None) -> bool:
    root = _resolve_project_root(project_root)
    if root is None:
        return False
    return _host_registered(_claude_settings(root))


def register_claude(project_root: Path) -> tuple[bool, str]:
    return _register_host(_claude_settings(project_root), project_root)


# ---------------------------------------------------------------------------
# Cursor  (<project>/.cursor/mcp.json)
# ---------------------------------------------------------------------------


def _cursor_settings(project_root: Path) -> Path:
    return project_root / ".cursor" / "mcp.json"


def cursor_registered(project_root: Path | None = None) -> bool:
    root = _resolve_project_root(project_root)
    if root is None:
        return False
    return _host_registered(_cursor_settings(root))


def register_cursor(project_root: Path) -> tuple[bool, str]:
    return _register_host(_cursor_settings(project_root), project_root)


# ---------------------------------------------------------------------------
# Gemini CLI  (~/.gemini/settings.json)
# ---------------------------------------------------------------------------

_GEMINI_SETTINGS = Path.home() / ".gemini" / "settings.json"


def gemini_registered(project_root: Path | None = None) -> bool:
    del project_root
    return _host_registered(_GEMINI_SETTINGS)


def register_gemini(project_root: Path) -> tuple[bool, str]:
    return _register_host(_GEMINI_SETTINGS, project_root)


# ---------------------------------------------------------------------------
# Antigravity  (<project>/.agents/mcp_config.json)
# ---------------------------------------------------------------------------


def _antigravity_settings(project_root: Path) -> Path:
    return project_root / ".agents" / "mcp_config.json"


def antigravity_registered(project_root: Path | None = None) -> bool:
    root = _resolve_project_root(project_root)
    if root is None:
        return False
    return _host_registered(_antigravity_settings(root))


def register_antigravity(project_root: Path) -> tuple[bool, str]:
    return _register_host(_antigravity_settings(project_root), project_root)


# ---------------------------------------------------------------------------
# Unified API
# ---------------------------------------------------------------------------


def registration_status(project_root: Path | None = None) -> dict[str, bool]:
    """Return per-host registration status for the given or discovered project."""
    root = _resolve_project_root(project_root)
    return {
        "claude": claude_registered(root),
        "cursor": cursor_registered(root),
        "gemini": gemini_registered(root),
        "antigravity": antigravity_registered(root),
    }


def register_all(project_root: Path) -> tuple[bool, str]:
    """Register with all supported hosts. Returns (ok, message)."""
    results: list[str] = []
    ok = True
    for host, fn in (
        ("claude", register_claude),
        ("cursor", register_cursor),
        ("gemini", register_gemini),
        ("antigravity", register_antigravity),
    ):
        installed, msg = fn(project_root)
        results.append(f"{host}: {'registered' if installed else msg}")
        if not installed and "already" not in msg:
            ok = False
    return ok, "\n".join(results)
