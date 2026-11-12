# -*- coding: utf-8 -*-
"""Checkpoint / resume of an interrupted simulation.

Every time the engine flushes the samples to the CSV files (every 10 snapshots) it records a
checkpoint: the last snapshot whose samples are safely on disk, the size of each CSV at that
moment and the state of the shared random generator used by the propagation models.

The checkpoint is written twice (atomically):

* ``<output dir>/sharc_checkpoint.json``  -- travels with the results;
* ``<parameter file>.resume.json``        -- lets the GUI/CLI find the run from the YAML alone.

Resuming (``main_cli.py -p file.yaml --resume``) reopens the same output folder, cuts every CSV
back to the size recorded in the checkpoint (dropping rows written after it, e.g. a flush cut in
half by a crash) and continues from the next snapshot. Each snapshot draws from its own seed
(derived from ``general.seed``), so the resumed run produces the same snapshots as an
uninterrupted one.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np

VERSION = 1
CHECKPOINT_NAME = "sharc_checkpoint.json"
POINTER_SUFFIX = ".resume.json"


@dataclass
class Checkpoint:
    param_file: str
    param_hash: str
    output_dir: str
    snapshot: int = 0
    num_snapshots: int = 0
    completed: bool = False
    files: Dict[str, int] = field(default_factory=dict)      # csv name -> size in bytes
    rng_state: Optional[dict] = None
    updated: float = 0.0
    pid: int = 0
    version: int = VERSION

    @property
    def pct(self) -> float:
        return 100.0 * self.snapshot / self.num_snapshots if self.num_snapshots else 0.0

    @property
    def resumable(self) -> bool:
        return not self.completed and self.snapshot < self.num_snapshots


# ------------------------------------------------------------------ helpers
def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def pointer_path(param_file: str) -> Path:
    return Path(str(param_file) + POINTER_SUFFIX)


def rng_state_to_json(rng: np.random.RandomState) -> dict:
    name, keys, pos, has_gauss, cached = rng.get_state()
    return {"name": name, "keys": keys.tolist(), "pos": int(pos),
            "has_gauss": int(has_gauss), "cached": float(cached)}


def rng_state_from_json(data: dict) -> tuple:
    return (data["name"], np.asarray(data["keys"], dtype=np.uint32), int(data["pos"]),
            int(data["has_gauss"]), float(data["cached"]))


def _atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read(path: Path) -> Optional[Checkpoint]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("version") != VERSION:
            return None
        return Checkpoint(**data)
    except (OSError, ValueError, TypeError):
        return None


# ---------------------------------------------------------------- write/read
def save(ckpt: Checkpoint) -> None:
    """Write the checkpoint next to the results and next to the parameter file."""
    ckpt.updated = time.time()
    ckpt.pid = os.getpid()
    payload = asdict(ckpt)
    for target in (Path(ckpt.output_dir) / CHECKPOINT_NAME, pointer_path(ckpt.param_file)):
        try:
            _atomic_write(target, payload)
        except OSError:
            pass            # a read-only YAML folder must not break the simulation


def csv_sizes(output_dir: str, names: Iterable[str]) -> Dict[str, int]:
    sizes = {}
    for name in names:
        p = Path(output_dir) / f"{name}.csv"
        if p.is_file():
            sizes[name] = p.stat().st_size
    return sizes


def find(param_file: str) -> Optional[Checkpoint]:
    """Checkpoint of the last run of `param_file` (None when there is none)."""
    return _read(pointer_path(param_file))


def find_valid(param_file: str) -> tuple[Optional[Checkpoint], str]:
    """Checkpoint that can really be resumed, or (None, reason)."""
    ckpt = find(param_file)
    if ckpt is None:
        return None, "no checkpoint found"
    if not ckpt.resumable:
        return None, "the previous run already finished"
    if not Path(ckpt.output_dir).is_dir():
        return None, f"output folder {ckpt.output_dir} no longer exists"
    try:
        if file_hash(param_file) != ckpt.param_hash:
            return None, "the parameter file changed since the interrupted run"
    except OSError as exc:
        return None, str(exc)
    return ckpt, ""


def restore_files(ckpt: Checkpoint, sample_names: Iterable[str]) -> None:
    """Cut the CSVs back to the checkpoint: rows written after it are dropped."""
    for name in sample_names:
        p = Path(ckpt.output_dir) / f"{name}.csv"
        if not p.is_file():
            continue
        size = ckpt.files.get(name)
        if size is None:
            p.unlink()                         # created after the checkpoint
        elif p.stat().st_size > size:
            with open(p, "r+b") as fh:
                fh.truncate(size)


def clear(param_file: str) -> None:
    try:
        pointer_path(param_file).unlink()
    except OSError:
        pass


def pid_alive(pid: int) -> bool:
    """True when process `pid` is still running (never signals/kills it)."""
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == 259                # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def find_interrupted(root: str) -> list[Checkpoint]:
    """Runs under `root` that stopped before the end and are not running any more."""
    found = []
    for p in Path(root).rglob("*" + POINTER_SUFFIX):
        ckpt = _read(p)
        if ckpt is None or not ckpt.resumable or pid_alive(ckpt.pid):
            continue
        if Path(ckpt.param_file).is_file() and Path(ckpt.output_dir).is_dir():
            found.append(ckpt)
    return sorted(found, key=lambda c: c.updated, reverse=True)
