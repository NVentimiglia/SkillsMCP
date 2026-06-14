"""Tests for MCP server registration (claude, cursor, gemini, antigravity)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skills_mcp.mcp_registration import (
    _SERVER_KEY,
    _server_entry,
    cursor_registered,
    claude_registered,
    gemini_registered,
    antigravity_registered,
    register_claude,
    register_cursor,
    register_gemini,
    register_antigravity,
    register_all,
    registration_status,
)


def _fake_claude_settings(project_root: Path) -> Path:
    return project_root / ".mcp.json"


def _fake_cursor_settings(project_root: Path) -> Path:
    return project_root / ".cursor" / "mcp.json"


def _fake_gemini_settings(tmp_path: Path) -> Path:
    return tmp_path / ".gemini" / "settings.json"


def _fake_antigravity_settings(project_root: Path) -> Path:
    return project_root / ".agents" / "mcp_config.json"


def _patch_gemini(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("skills_mcp.mcp_registration._GEMINI_SETTINGS", _fake_gemini_settings(tmp_path))
    (tmp_path / "skillmcp.toml").write_text('agent_folders = [".agents/"]\n', encoding="utf-8")


# ---------------------------------------------------------------------------
# server entry
# ---------------------------------------------------------------------------


def test_server_entry_contains_project_root(tmp_path: Path) -> None:
    entry = _server_entry(tmp_path)
    assert entry["env"]["SKILLS_MCP_ROOT"] == str(tmp_path.resolve())
    assert "-m" in entry["args"]
    assert "skills_mcp" in entry["args"]


# ---------------------------------------------------------------------------
# register_claude
# ---------------------------------------------------------------------------


def test_register_claude_creates_entry(tmp_path: Path) -> None:
    settings = _fake_claude_settings(tmp_path)

    ok, msg = register_claude(tmp_path)

    assert ok
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert _SERVER_KEY in data["mcpServers"]
    assert data["mcpServers"][_SERVER_KEY]["env"]["SKILLS_MCP_ROOT"] == str(tmp_path.resolve())


def test_register_claude_idempotent(tmp_path: Path) -> None:
    register_claude(tmp_path)
    ok, msg = register_claude(tmp_path)

    assert not ok
    assert "already" in msg


def test_register_claude_merges_existing_config(tmp_path: Path) -> None:
    settings = _fake_claude_settings(tmp_path)
    settings.write_text(json.dumps({"mcpServers": {"other-server": {"command": "x"}}}), encoding="utf-8")

    register_claude(tmp_path)

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "other-server" in data["mcpServers"]
    assert _SERVER_KEY in data["mcpServers"]


# ---------------------------------------------------------------------------
# register_cursor
# ---------------------------------------------------------------------------


def test_register_cursor_creates_entry(tmp_path: Path) -> None:
    settings = _fake_cursor_settings(tmp_path)

    ok, msg = register_cursor(tmp_path)

    assert ok
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert _SERVER_KEY in data["mcpServers"]


def test_register_cursor_idempotent(tmp_path: Path) -> None:
    register_cursor(tmp_path)
    ok, msg = register_cursor(tmp_path)

    assert not ok
    assert "already" in msg


# ---------------------------------------------------------------------------
# register_gemini
# ---------------------------------------------------------------------------


def test_register_gemini_creates_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _fake_gemini_settings(tmp_path)
    monkeypatch.setattr("skills_mcp.mcp_registration._GEMINI_SETTINGS", settings)

    ok, msg = register_gemini(tmp_path)

    assert ok
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert _SERVER_KEY in data["mcpServers"]


def test_register_gemini_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _fake_gemini_settings(tmp_path)
    monkeypatch.setattr("skills_mcp.mcp_registration._GEMINI_SETTINGS", settings)

    register_gemini(tmp_path)
    ok, msg = register_gemini(tmp_path)

    assert not ok
    assert "already" in msg


# ---------------------------------------------------------------------------
# register_antigravity
# ---------------------------------------------------------------------------


def test_register_antigravity_creates_entry(tmp_path: Path) -> None:
    settings = _fake_antigravity_settings(tmp_path)

    ok, msg = register_antigravity(tmp_path)

    assert ok
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert _SERVER_KEY in data["mcpServers"]


def test_register_antigravity_idempotent(tmp_path: Path) -> None:
    register_antigravity(tmp_path)
    ok, msg = register_antigravity(tmp_path)

    assert not ok
    assert "already" in msg


# ---------------------------------------------------------------------------
# register_all
# ---------------------------------------------------------------------------


def test_register_all_installs_all_hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gemini(monkeypatch, tmp_path)

    ok, msg = register_all(tmp_path)

    assert ok
    assert "claude" in msg
    assert "cursor" in msg
    assert "gemini" in msg
    assert "antigravity" in msg


# ---------------------------------------------------------------------------
# registration_status
# ---------------------------------------------------------------------------


def test_registration_status_unregistered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gemini(monkeypatch, tmp_path)

    status = registration_status(tmp_path)
    assert status["claude"] is False
    assert status["cursor"] is False
    assert status["gemini"] is False
    assert status["antigravity"] is False


def test_registration_status_registered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gemini(monkeypatch, tmp_path)

    register_all(tmp_path)
    status = registration_status(tmp_path)

    assert status["claude"] is True
    assert status["cursor"] is True
    assert status["gemini"] is True
    assert status["antigravity"] is True
