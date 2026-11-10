"""Find simulation result folders automatically (no Qt).

The engine writes each run to `<sharc dir>/<output_dir>/<prefix>_<date>_<NN>/` (or straight into
`<sharc dir>/<output_dir>` when `overwrite_output` is on) and, in the numbered case, copies the
parameter file into that folder. A result folder is any folder holding at least one `.csv`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional

import yaml

SHARC_DIR = Path(__file__).resolve().parents[2]          # .../sharc (the engine's `__sharc_dir`)
_SKIP = {"_deprecated", "__pycache__", "node_modules", ".git"}


def has_results(folder: Path) -> bool:
    try:
        return any(p.suffix.lower() == ".csv" for p in folder.iterdir() if p.is_file())
    except OSError:
        return False


def _general(yaml_path: str) -> dict:
    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            return (yaml.safe_load(fh) or {}).get("general", {}) or {}
    except (OSError, yaml.YAMLError):
        return {}


def find_job_results(yaml_path: str, sharc_dir: Path = SHARC_DIR) -> Optional[Path]:
    """Result folder written by the run of `yaml_path`, or None when nothing was written (yet)."""
    gen = _general(yaml_path)
    parent = sharc_dir / str(gen.get("output_dir", "output") or "output")     # absolute output_dir wins
    prefix = str(gen.get("output_dir_prefix", "output") or "output")
    if gen.get("overwrite_output", True):
        return parent if has_results(parent) else None
    if not parent.is_dir():
        return None
    name = os.path.basename(yaml_path)
    candidates = [d for d in parent.iterdir()
                  if d.is_dir() and d.name.startswith(prefix + "_") and has_results(d)]
    mine = [d for d in candidates if (d / name).is_file()] or candidates   # the engine copies the YAML in
    return max(mine, key=lambda d: d.stat().st_mtime, default=None)


def discover(roots: Iterable[Path], max_depth: int = 2) -> List[Path]:
    """Every result folder under `roots` (depth-limited), newest first, without duplicates."""
    found = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for cur, dirs, _files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in _SKIP and not d.startswith(".")]
            here = Path(cur)
            if len(here.parts) - base_depth >= max_depth:
                dirs[:] = []
            if has_results(here):
                found[here.resolve()] = here.stat().st_mtime
    return sorted(found, key=found.get, reverse=True)
