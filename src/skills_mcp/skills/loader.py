from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from skills_mcp.skills.schema import ParsedSkill, SkillFrontmatter

log = logging.getLogger(__name__)


def _rel_display(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix().replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _subdir_display_maybe(subdir: Path, project_root: Path) -> str | None:
    if not subdir.is_dir():
        return None
    return _rel_display(subdir, project_root)


@dataclass
class LoadedSkill:
    skill_root: Path
    main_file: Path
    rel_path: str
    format: str  # "directory" or "legacy_file"
    references_dir: str | None
    scripts_dir: str | None
    assets_dir: str | None
    parsed: ParsedSkill
    catalog_origin: str = "project"


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n(.*)$", text, re.DOTALL)
    if not m:
        return None
    return m.group(1), m.group(2)


def parse_skill_file(
    path: Path,
    *,
    project_root: Path,
    skill_disk_root: Path | None = None,
    fmt: str = "legacy_file",
) -> LoadedSkill | None:
    path = path.resolve()
    root = project_root.resolve()
    raw = path.read_text(encoding="utf-8")
    split = _split_frontmatter(raw)
    if split is None:
        if fmt == "directory":
            raise ValueError(f"missing YAML frontmatter in {path} (expected --- ... ---)")
        return None  # Legacy file without frontmatter is not a skill

    fm_raw, body = split
    try:
        data = yaml.safe_load(fm_raw) or {}
        if not isinstance(data, dict):
            raise ValueError("frontmatter must be a YAML mapping")
        fm = SkillFrontmatter.model_validate(data)
    except Exception as e:
        raise ValueError(f"invalid skill frontmatter in {path}: {e}") from e

    sr = (skill_disk_root or path.parent).resolve()
    rel = _rel_display(path, root)
    parsed = ParsedSkill(fm=fm, body=body)

    refs = sr / "references"
    scripts = sr / "scripts"
    assets = sr / "assets"
    return LoadedSkill(
        skill_root=sr,
        main_file=path,
        rel_path=rel,
        format=fmt,
        references_dir=_subdir_display_maybe(refs, root),
        scripts_dir=_subdir_display_maybe(scripts, root),
        assets_dir=_subdir_display_maybe(assets, root),
        parsed=parsed,
        catalog_origin="project",
    )


def _is_single_skill_folder(scan_root: Path) -> bool:
    """True when the path itself is one skill (SKILL.md at folder root)."""
    return (scan_root / "SKILL.md").is_file()


def _load_single_skill_folder(scan_root: Path, project_root: Path) -> dict[str, LoadedSkill]:
    sk_path = scan_root / "SKILL.md"
    try:
        ls = parse_skill_file(
            sk_path,
            project_root=project_root,
            skill_disk_root=scan_root.resolve(),
            fmt="directory",
        )
    except ValueError as exc:
        log.warning("Skipping invalid single-skill folder %s: %s", scan_root, exc)
        return {}
    if ls is None:
        return {}
    return {ls.parsed.fm.name: ls}


def _gather_tree_into_dict(scan_root: Path, project_root: Path) -> dict[str, LoadedSkill]:
    if not scan_root.is_dir():
        raise FileNotFoundError(f"skills directory missing: {scan_root}")

    if _is_single_skill_folder(scan_root):
        return _load_single_skill_folder(scan_root, project_root)

    dir_skill_files = sorted(scan_root.rglob("SKILL.md"))
    loaded: list[LoadedSkill] = []
    dir_roots: list[Path] = []

    for sk in dir_skill_files:
        rd = sk.parent.resolve()
        try:
            ls = parse_skill_file(
                sk,
                project_root=project_root,
                skill_disk_root=rd,
                fmt="directory",
            )
        except ValueError as exc:
            log.warning("Skipping invalid skill file %s: %s", sk, exc)
            continue
        if ls.parsed.fm.name != rd.name:
            raise ValueError(
                f"skill name `{ls.parsed.fm.name}` must match parent directory `{rd.name}` "
                f"for {sk}"
            )
        loaded.append(ls)
        dir_roots.append(rd)

    md_files = sorted(scan_root.rglob("*.md"))
    legacy_files: list[Path] = []
    for p in md_files:
        if p.name == "SKILL.md":
            continue
        rp = p.resolve()
        if any(root in rp.parents for root in dir_roots):
            continue
        legacy_files.append(p)

    paths_by_name: dict[str, list[LoadedSkill]] = {}
    for ls in loaded:
        paths_by_name.setdefault(ls.parsed.fm.name, []).append(ls)
    for p in legacy_files:
        try:
            ls = parse_skill_file(
                p,
                project_root=project_root,
                skill_disk_root=p.parent,
                fmt="legacy_file",
            )
        except ValueError as exc:
            log.warning("Skipping invalid skill file %s: %s", p, exc)
            continue
        if ls is not None:
            paths_by_name.setdefault(ls.parsed.fm.name, []).append(ls)

    dups = {n: [x.rel_path for x in lst] for n, lst in paths_by_name.items() if len(lst) > 1}
    if dups:
        parts = [f"`{n}` -> {sorted(v)}" for n, v in sorted(dups.items())]
        raise ValueError("duplicate skill names: " + "; ".join(parts))

    return {n: lst[0] for n, lst in paths_by_name.items()}


class SkillIndex:
    def __init__(
        self,
        skill_dirs: list[Path],
        *,
        project_root: Path,
    ) -> None:
        self.project_root = project_root.resolve()
        self._skill_dirs: list[Path] = []
        seen: set[Path] = set()
        for p in skill_dirs:
            rp = Path(p).expanduser().resolve()
            if rp not in seen and rp.is_dir():
                self._skill_dirs.append(rp)
                seen.add(rp)
        self._by_name: dict[str, LoadedSkill] = {}

    def scan(self) -> None:
        merged: dict[str, LoadedSkill] = {}
        last = len(self._skill_dirs) - 1
        for i, skill_dir in enumerate(self._skill_dirs):
            blob = _gather_tree_into_dict(skill_dir, self.project_root)
            origin = "project" if i == last else "library"
            for name, sk in blob.items():
                merged[name] = replace(sk, catalog_origin=origin)
        self._by_name = merged

    def list_skills_meta(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for s in sorted(self._by_name.values(), key=lambda x: x.parsed.fm.name):
            row: dict[str, Any] = {
                "name": s.parsed.fm.name,
                "description": s.parsed.fm.description,
                "path": s.rel_path,
                "format": s.format,
                "references_dir": s.references_dir or "",
                "scripts_dir": s.scripts_dir or "",
                "assets_dir": s.assets_dir or "",
            }
            if s.catalog_origin != "project":
                row["skill_origin"] = s.catalog_origin
            if s.parsed.fm.triggers:
                row["triggers"] = list(s.parsed.fm.triggers)
            if s.parsed.fm.metadata:
                row["metadata"] = dict(s.parsed.fm.metadata)
            if s.parsed.fm.license:
                row["license"] = s.parsed.fm.license
            if s.parsed.fm.compatibility:
                row["compatibility"] = s.parsed.fm.compatibility
            rows.append(row)
        return rows

    def get_by_name(self, name: str) -> LoadedSkill:
        if "/" in name or "\\" in name or ".." in name:
            raise ValueError("skill name cannot contain paths")
        if name not in self._by_name:
            raise KeyError(f"unknown skill: {name}")
        return self._by_name[name]

