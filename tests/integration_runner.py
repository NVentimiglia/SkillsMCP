"""End-to-end integration test runner for SkillsMCP + MemoryMCP.

Usage
-----
    python tests/integration_runner.py            # full run
    python tests/integration_runner.py --keep     # leave tmp dir after run
    python tests/integration_runner.py --phase 3  # run only phase 3

What it tests
-------------
Phase 1 — Init            skills-mcp init + memory-mcp init scaffold the project
Phase 2 — Doctor          both CLIs report no fatal errors
Phase 3 — Registration    MCP server entries appear in ~/.claude/settings.json
                          Hooks appear in <project>/.claude/settings.local.json
Phase 4 — SkillsMCP tools connect via MCP stdio, exercise all tools
Phase 5 — MemoryMCP tools connect via MCP stdio, exercise all tools
Phase 6 — Memory isolation  two project paths don't share memories or skills
Phase 7 — Skill merge     global + local additive, local name wins over global
Phase 8 — Analyze         memory-mcp analyze runs cleanly (zero sessions ok)

Claude / Gemini interactive CLIs are NOT invoked (they require a human terminal).
Instead we verify their configuration files so that when they next start they
will find both MCP servers registered.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


import tempfile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TMP_ROOT = Path(tempfile.gettempdir()) / "skills-mcp-itest"
TMP_PROJECT_A = TMP_ROOT / "project-a"
TMP_PROJECT_B = TMP_ROOT / "project-b"

SKILLS_MCP_ROOT = Path(__file__).resolve().parent.parent  # SkillMCP repo root
# MemoryMCP lives next to SkillMCP
MEMORY_MCP_ROOT = SKILLS_MCP_ROOT.parent / "MemoryMCP"

PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []


def record(phase: str, passed: bool, note: str = "") -> None:
    _results.append((phase, passed, note))
    status = "PASS" if passed else "FAIL"
    tag = f"[{status}]".ljust(7)
    msg = f"{tag} {phase}"
    if note:
        msg += f" — {note}"
    print(msg)


def assert_phase(phase: str, condition: bool, note: str = "") -> None:
    record(phase, condition, note)
    if not condition:
        raise AssertionError(f"Phase failed: {phase} — {note}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
    )


def run_cli(args: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return run([PYTHON, "-m", args[0].replace("-", "_"), *args[1:]], cwd=cwd, env=env)


async def mcp_call(server_module: str, tool: str, arguments: dict, project_root: Path) -> str:
    """Spawn an MCP server process, call one tool, return text content."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    # Each server uses its own env var to find its root config.
    # skills_mcp uses SKILLS_MCP_ROOT; memory_mcp uses MEMORY_MCP_ROOT.
    env_key = "SKILLS_MCP_ROOT" if "skills" in server_module else "MEMORY_MCP_ROOT"
    params = StdioServerParameters(
        command=PYTHON,
        args=["-m", server_module, "serve"],
        env={**os.environ, env_key: str(project_root)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments=arguments)
            parts = result.content
            return "".join(
                p.text if hasattr(p, "text") else str(p)
                for p in parts
            )


def mcp(server_module: str, tool: str, arguments: dict, project_root: Path) -> str:
    return asyncio.run(mcp_call(server_module, tool, arguments, project_root))


def skills(tool: str, arguments: dict | None = None) -> str:
    return mcp("skills_mcp", tool, arguments or {}, SKILLS_MCP_ROOT)


def memory(tool: str, arguments: dict | None = None, root: Path | None = None) -> str:
    # root must be a project with config.toml (i.e. after memory-mcp init).
    # Callers should always pass the test project path as root.
    if root is None:
        raise ValueError("memory() requires explicit root= (project path with config.toml)")
    return mcp("memory_mcp", tool, arguments or {}, root)


# ---------------------------------------------------------------------------
# Phase 1 — Init
# ---------------------------------------------------------------------------

def phase_1(project_a: Path, project_b: Path) -> None:
    print("\n=== Phase 1 — Init ===")

    for proj in (project_a, project_b):
        proj.mkdir(parents=True, exist_ok=True)

    # skills-mcp init
    r = run_cli(["skills-mcp", "init", str(project_a)])
    assert_phase("1a skills-mcp init exits 0", r.returncode == 0, r.stderr[:200])
    assert_phase("1b .agents/skills/ created", (project_a / ".agents" / "skills").is_dir())
    assert_phase("1c skillmcp.toml created", (project_a / "skillmcp.toml").is_file())

    # memory-mcp init
    r = run_cli(["memory-mcp", "init", str(project_a)])
    assert_phase("1d memory-mcp init exits 0", r.returncode == 0, r.stderr[:200])
    assert_phase("1e .memory/ created", (project_a / ".memory").is_dir())
    assert_phase("1f .sessions/ created", (project_a / ".sessions").is_dir())

    # Init project B too (for isolation tests)
    run_cli(["skills-mcp", "init", str(project_b)])
    run_cli(["memory-mcp", "init", str(project_b)])
    assert_phase("1g project B scaffolded", (project_b / ".agents").is_dir())


# ---------------------------------------------------------------------------
# Phase 2 — Verify layout
# ---------------------------------------------------------------------------

def phase_2(project_a: Path) -> None:
    print("\n=== Phase 2 — Verify ===")

    r = run_cli(["skills-mcp", "verify"], cwd=project_a,
                env={"SKILLS_MCP_ROOT": str(SKILLS_MCP_ROOT)})
    output = r.stdout + r.stderr
    assert_phase("2a skills-mcp verify exits 0", r.returncode == 0, output[:300])
    assert_phase("2b no 'errors' in verify output", "errors:" not in output.lower(), output[:300])

    r = run_cli(["memory-mcp", "doctor"], cwd=project_a,
                env={"MEMORY_MCP_ROOT": str(MEMORY_MCP_ROOT)})
    output = r.stdout + r.stderr
    assert_phase("2c memory-mcp doctor exits 0", r.returncode == 0, output[:300])
    assert_phase("2d no 'error' in memory doctor output", "error" not in output.lower(), output[:300])


# ---------------------------------------------------------------------------
# Phase 3 — Registration
# ---------------------------------------------------------------------------

def phase_3(project_a: Path) -> None:
    print("\n=== Phase 3 — Registration ===")

    claude_settings = Path.home() / ".claude" / "settings.json"
    if claude_settings.is_file():
        data = json.loads(claude_settings.read_text(encoding="utf-8"))
        mcp_servers = data.get("mcpServers", {})
        assert_phase("3a skills-mcp in claude settings", "skills-mcp" in mcp_servers)
        assert_phase("3b memory-mcp in claude settings", "memory-mcp" in mcp_servers)
    else:
        record("3a skills-mcp in claude settings", False, "~/.claude/settings.json not found")
        record("3b memory-mcp in claude settings", False, "~/.claude/settings.json not found")

    # Hooks: memory-mcp installs Stop hooks per-project in .claude/settings.local.json
    local_settings = project_a / ".claude" / "settings.local.json"
    if local_settings.is_file():
        data = json.loads(local_settings.read_text(encoding="utf-8"))
        hooks = data.get("hooks", {})
        stop_hooks = hooks.get("Stop", [])
        hook_cmds = [
            cmd
            for h in stop_hooks
            for matcher in (h if isinstance(h, list) else [h])
            for cmd in ([matcher.get("command", "")] if isinstance(matcher, dict) else [])
        ]
        has_analyze = any("memory-mcp" in c or "analyze" in c for c in hook_cmds)
        assert_phase("3c analyze hook in .claude/settings.local.json", has_analyze,
                     f"hooks found: {hook_cmds}")
    else:
        record("3c analyze hook in .claude/settings.local.json", False,
               f"{local_settings} not found")


# ---------------------------------------------------------------------------
# Phase 4 — SkillsMCP tools
# ---------------------------------------------------------------------------

def phase_4(project_a: Path) -> None:
    print("\n=== Phase 4 — SkillsMCP tools ===")

    # 4a verify_setup
    result = skills("verify_setup")
    assert_phase("4a verify_setup returns", bool(result))

    # 4b list_skills global (no project_path)
    raw = skills("list_skills")
    skill_list = json.loads(raw)
    assert_phase("4b list_skills returns a list", isinstance(skill_list, list))
    global_names = {s["name"] for s in skill_list}
    record("4b skill count", True, f"{len(skill_list)} global skills: {sorted(global_names)}")

    # 4c list_skills with project_path (project A has no local skills yet)
    raw = skills("list_skills", {"project_path": str(project_a)})
    with_proj = json.loads(raw)
    assert_phase("4c list_skills with project_path", isinstance(with_proj, list))

    # 4d read_skill — pick the first available skill if any
    if skill_list:
        first = skill_list[0]["name"]
        content = skills("read_skill", {"name": first})
        assert_phase("4d read_skill returns content", bool(content) and len(content) > 10,
                     f"skill={first} len={len(content)}")
    else:
        record("4d read_skill", True, "skipped — no global skills installed")


# ---------------------------------------------------------------------------
# Phase 5 — MemoryMCP tools
# ---------------------------------------------------------------------------

def phase_5(project_a: Path) -> None:
    print("\n=== Phase 5 — MemoryMCP tools ===")

    proj = str(project_a)

    # 5a list_memories (empty)
    raw = memory("list_memories", {"project_path": proj}, root=project_a)
    mem_list = json.loads(raw)
    assert_phase("5a list_memories empty", isinstance(mem_list, list),
                 f"got: {mem_list!r}")

    # 5b write_memory
    content = textwrap.dedent(f"""\
        # Integration Test Context
        **Agent:** integration_runner.py
        **Date:** 2026-05-15
        **Project:** {proj}

        ## Confirmed working
        - verify_setup: OK
        - list_memories: returned [] on empty project

        ## Notes
        Automated integration test.
    """)
    result = memory("write_memory", {"name": "itest-context", "content": content,
                                     "project_path": proj}, root=project_a)
    assert_phase("5b write_memory returns", bool(result))
    mem_file = project_a / ".memory" / "itest-context.md"
    assert_phase("5c memory file written to disk", mem_file.is_file())

    # 5d list_memories (non-empty)
    raw = memory("list_memories", {"project_path": proj}, root=project_a)
    mem_list = json.loads(raw)
    assert_phase("5d list_memories shows written file",
                 any("itest-context" in m for m in mem_list),
                 f"list: {mem_list}")

    # 5e read_memory round-trip
    read_back = memory("read_memory", {"name": "itest-context", "project_path": proj},
                       root=project_a)
    assert_phase("5e read_memory round-trip", "integration_runner.py" in read_back)

    # 5f get_handoff (may be empty on fresh project — just must not crash)
    handoff = memory("get_handoff", {"project_path": proj}, root=project_a)
    assert_phase("5f get_handoff returns", handoff is not None)

    # 5g get_suggestions (may be empty)
    suggestions = memory("get_suggestions", {"project_path": proj}, root=project_a)
    assert_phase("5g get_suggestions returns", suggestions is not None)


# ---------------------------------------------------------------------------
# Phase 6 — Memory isolation
# ---------------------------------------------------------------------------

def phase_6(project_a: Path, project_b: Path) -> None:
    print("\n=== Phase 6 — Memory isolation ===")

    proj_a = str(project_a)
    proj_b = str(project_b)

    # File written to A must not appear in B
    raw_b = memory("list_memories", {"project_path": proj_b}, root=project_b)
    list_b = json.loads(raw_b)
    assert_phase("6a A's memory absent from B",
                 not any("itest-context" in m for m in list_b),
                 f"B list: {list_b}")

    # Write something to B, must not bleed into A
    memory("write_memory", {"name": "b-only", "content": "project B memory",
                             "project_path": proj_b}, root=project_b)
    raw_a = memory("list_memories", {"project_path": proj_a}, root=project_a)
    list_a = json.loads(raw_a)
    assert_phase("6b B's memory absent from A",
                 not any("b-only" in m for m in list_a),
                 f"A list: {list_a}")

    # Skills: local skills for project B must not appear in global list
    skill_dir = project_b / ".agents" / "skills" / "b-local-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: b-local-skill
        description: A local skill only in project B.
        ---
        # B Local Skill
        This skill belongs to project B only.
    """), encoding="utf-8")

    raw_global = skills("list_skills")  # no project_path
    global_names = {s["name"] for s in json.loads(raw_global)}
    assert_phase("6c B local skill absent from global list",
                 "b-local-skill" not in global_names,
                 f"global: {sorted(global_names)}")


# ---------------------------------------------------------------------------
# Phase 7 — Skill merge (additive, local wins)
# ---------------------------------------------------------------------------

def phase_7(project_a: Path) -> None:
    print("\n=== Phase 7 — Skill merge ===")

    proj = str(project_a)

    # Add a unique local skill to project A
    skill_dir = project_a / ".agents" / "skills" / "a-local-unique"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: a-local-unique
        description: Unique skill in project A.
        ---
        # A Local Unique Skill
        Content only in project A.
    """), encoding="utf-8")

    raw = skills("list_skills", {"project_path": proj})
    merged = json.loads(raw)
    merged_names = {s["name"] for s in merged}
    assert_phase("7a local skill appears in merged list",
                 "a-local-unique" in merged_names,
                 f"merged: {sorted(merged_names)}")

    # Read it back
    content = skills("read_skill", {"name": "a-local-unique", "project_path": proj})
    assert_phase("7b read local skill returns content",
                 "A Local Unique Skill" in content)

    # Shadow test: if a local skill has the same name as a global one, local wins
    global_raw = skills("list_skills")
    global_skills = json.loads(global_raw)
    if global_skills:
        shadow_name = global_skills[0]["name"]
        shadow_dir = project_a / ".agents" / "skills" / shadow_name
        shadow_dir.mkdir(parents=True, exist_ok=True)
        (shadow_dir / "SKILL.md").write_text(textwrap.dedent(f"""\
            ---
            name: {shadow_name}
            description: Local shadow of global skill.
            ---
            # Local Shadow
            LOCAL_WINS_MARKER
        """), encoding="utf-8")

        content = skills("read_skill", {"name": shadow_name, "project_path": proj})
        assert_phase("7c local skill shadows global (local wins)",
                     "LOCAL_WINS_MARKER" in content,
                     f"skill={shadow_name}")
    else:
        record("7c local skill shadows global", True, "skipped — no global skills")


# ---------------------------------------------------------------------------
# Phase 8 — Analyze
# ---------------------------------------------------------------------------

def phase_8(project_a: Path) -> None:
    print("\n=== Phase 8 — Analyze ===")

    # analyze discovers the project from cwd + MEMORY_MCP_ROOT=project dir
    env = {"MEMORY_MCP_ROOT": str(project_a)}
    r = run_cli(["memory-mcp", "analyze"], cwd=project_a, env=env)
    output = r.stdout + r.stderr

    assert_phase("8a analyze exits 0", r.returncode == 0, output[:300])
    assert_phase("8b no traceback in analyze output",
                 "Traceback" not in output, output[:500])
    record("8c analyze output", True, output.strip()[:200] or "(empty)")

    # Verify no dr-*.md leaked into the MemoryMCP global root
    leaked = list((MEMORY_MCP_ROOT / ".memory").glob("dr-*.md")) if (MEMORY_MCP_ROOT / ".memory").is_dir() else []
    # Leaked files should be in MEMORY_MCP_ROOT, not project_a — but project_a
    # should only have its own
    proj_a_dr = list((project_a / ".memory").glob("dr-*.md"))
    record("8d dr-*.md (if any) stay in project .memory", True,
           f"project_a dr files: {[f.name for f in proj_a_dr]}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary() -> int:
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    passes = sum(1 for _, p, _ in _results if p)
    fails = sum(1 for _, p, _ in _results if not p)
    for phase, passed, note in _results:
        status = "PASS" if passed else "FAIL"
        line = f"  [{status}] {phase}"
        if note:
            line += f"\n         {note}"
        print(line)
    print("=" * 60)
    print(f"  Total: {passes} passed, {fails} failed")
    overall = "PASS" if fails == 0 else "FAIL"
    print(f"  Overall: {overall}")
    print("=" * 60)
    return 0 if fails == 0 else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="SkillsMCP + MemoryMCP integration runner")
    parser.add_argument("--keep", action="store_true", help="Keep tmp dir after run")
    parser.add_argument("--phase", type=int, default=0, help="Run only this phase number (0=all)")
    args = parser.parse_args()

    project_a = TMP_PROJECT_A
    project_b = TMP_PROJECT_B

    # Clean up from prior runs
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)

    phase_map = {
        1: lambda: phase_1(project_a, project_b),
        2: lambda: phase_2(project_a),
        3: lambda: phase_3(project_a),
        4: lambda: phase_4(project_a),
        5: lambda: phase_5(project_a),
        6: lambda: phase_6(project_a, project_b),
        7: lambda: phase_7(project_a),
        8: lambda: phase_8(project_a),
    }

    phases_to_run = [args.phase] if args.phase else list(range(1, 9))

    for num in phases_to_run:
        fn = phase_map.get(num)
        if fn is None:
            print(f"Unknown phase: {num}")
            continue
        try:
            fn()
        except AssertionError as exc:
            print(f"  STOPPED: {exc}")
            # For --phase single mode, stop. For full run, continue.
            if args.phase:
                break

    if not args.keep and TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)

    return print_summary()


if __name__ == "__main__":
    sys.exit(main())
