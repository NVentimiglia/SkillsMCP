from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from skills_mcp import __version__

BUNDLED = Path(__file__).resolve().parent / "bundled"


def cmd_init(target: Path) -> None:
    from skills_mcp.mcp_registration import register_all

    target = target.resolve()
    (target / ".agents" / "skills").mkdir(parents=True, exist_ok=True)

    cfg_dst = target / "skillmcp.toml"
    if not cfg_dst.is_file():
        bundled_cfg = BUNDLED / "skillmcp.toml"
        cfg_dst.write_text(bundled_cfg.read_text(encoding="utf-8"), encoding="utf-8")

    _ok, msg = register_all(target)
    for line in msg.splitlines():
        print(f"  mcp: {line}")



def cmd_serve(root: Path | None = None) -> None:
    from skills_mcp.server import run_stdio_server

    run_stdio_server(root=root)


def cmd_verify() -> int:
    from skills_mcp.setup_check import run_verify_cli

    return run_verify_cli()


def cmd_mcp_register() -> int:
    from skills_mcp.mcp_registration import register_all
    from skills_mcp.paths import project_root_from_env_or_discover

    root = project_root_from_env_or_discover()
    _ok, msg = register_all(root)
    for line in msg.splitlines():
        print(f"mcp: {line}")
    print("mcp: restart your agent host to pick up the new server entry.")
    return 0


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="skills-mcp", description="SkillsMCP MCP server CLI")
    parser.add_argument("--version", action="store_true", help="Print version")
    sub = parser.add_subparsers(dest="cmd")

    p_init = sub.add_parser("init", help="Create .agents/skills + skillmcp.toml + register MCP")
    p_init.add_argument("path", nargs="?", default=".", type=Path)

    p_serve = sub.add_parser("serve", help="Run MCP server (stdio)")
    p_serve.add_argument("--root", type=Path, help="Project root directory")

    sub.add_parser("verify", help="Verify project layout and MCP registration")

    p_mcp = sub.add_parser("mcp", help="Manage MCP server registration with host agents")
    p_mcp_sub = p_mcp.add_subparsers(dest="mcp_cmd")
    p_mcp_sub.add_parser(
        "register",
        help="Register skills-mcp in Claude Code, Gemini, Cursor, and Antigravity configs",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=os.environ.get("SKILLS_MCP_LOG_LEVEL")
        or os.environ.get("AGENT_MCP_LOG_LEVEL")
        or "INFO"
    )

    if args.version:
        print(__version__)
        return

    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    if args.cmd == "init":
        cmd_init(Path(args.path))
        return

    if args.cmd == "serve":
        cmd_serve(root=args.root)
        return

    if args.cmd == "verify":
        sys.exit(cmd_verify())

    if args.cmd == "mcp":
        if args.mcp_cmd == "register":
            sys.exit(cmd_mcp_register())
        p_mcp.print_help()
        sys.exit(1)

    parser.error(f"unknown command {args.cmd}")


if __name__ == "__main__":
    main()
