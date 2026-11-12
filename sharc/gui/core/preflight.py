"""Pre-run review: scenario summary, resource estimate and a real test run (no Qt).

`build_plan` turns the YAML dict and the engine scene into numbers the user can review before
starting. Every figure carries its source: "estimated" (a heuristic from the scene size) until
`run_probe` has executed a few real snapshots in a throw-away folder, then "measured".
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Used only until a test run replaces them with measurements.
# Measured 2026-11-12 (Windows, Python 3.14, default GUI scenario, MACROCELL, 57 BS): the engine's peak RSS
# was 218-220 MB for 57, 171 and 570 UEs, so the matrix term below is negligible at that size.
_BASE_RSS_MB = 220.0
_MATRICES = 10                 # float64 (BS x UE) matrices assumed alive at once; unmeasured, matters only for huge scenes
# Same scenario: the engine flushes result CSVs only every 10 snapshots (model.py: `not current_snapshot % 10`).
# Runs of 4-8 snapshots left just sharc_checkpoint.json + simulation_log (11.4 KB); 10 -> 101.8 KB, 12 -> 101.8 KB,
# 40 -> 371.7 KB, i.e. ~9.0 KB of CSV per snapshot written in blocks of 10. A test must therefore run 10 snapshots.
_FIXED_OUT_BYTES = 11_500
_FLUSH_EVERY = 10
PROBE_SNAPSHOTS = 10
# Measured wall time of a 10-snapshot probe on the default scenario: 6.5 s (start-up 5.1 s). Only paces the bar.
DEFAULT_PROBE_SECONDS = 7.0

_PROGRESS = re.compile(r"(?:snapshot|step|snap).*?(\d+)\s*(?:/|of)\s*(\d+)", re.IGNORECASE)
# The engine logs "YYYY-MM-DD HH:MM:SS,mmm - sharc.model - INFO - ..." (local time) just before the snapshot
# loop and "FINISHED!" right after it; their gap is the loop time, everything before is start-up.
_LOG_TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) - sharc\.model - INFO - (.*)")


@dataclass
class Plan:
    runs: int
    snapshots: int
    parallel: int
    system: str
    topology: str
    n_bs: int
    n_ue: int
    seed: str
    freq_mhz: Optional[float]
    bw_mhz: Optional[float]
    out_dir: str
    free_disk_bytes: int
    total_ram_bytes: int
    avail_ram_bytes: int
    ram_per_proc_bytes: float
    out_per_snapshot_bytes: Optional[float]      # None until a test run measures CSV growth
    seconds_per_snapshot: Optional[float] = None
    setup_seconds: Optional[float] = None
    measured: bool = False
    work_root: str = ""
    notes: List[str] = field(default_factory=list)

    @property
    def workers(self) -> int:
        return max(1, min(self.parallel, self.runs))

    @property
    def ram_total_bytes(self) -> float:
        return self.ram_per_proc_bytes * self.workers

    @property
    def disk_total_bytes(self) -> float:
        """Fixed files per run, plus CSV growth once it is known."""
        flushed = self.snapshots // _FLUSH_EVERY * _FLUSH_EVERY      # CSVs are written in blocks of 10
        grow = (self.out_per_snapshot_bytes or 0.0) * flushed
        return (_FIXED_OUT_BYTES + grow) * self.runs

    @property
    def time_seconds(self) -> Optional[float]:
        """Wall-clock estimate; None until a test run has measured the snapshot cost."""
        if self.seconds_per_snapshot is None:
            return None
        rounds = -(-self.runs // self.workers)           # ceil: runs go in waves of `workers`
        return rounds * ((self.setup_seconds or 0.0) + self.snapshots * self.seconds_per_snapshot)


@dataclass
class ProbeResult:
    ok: bool
    snapshots: int = 0
    wall_seconds: float = 0.0
    setup_seconds: float = 0.0
    seconds_per_snapshot: float = 0.0
    peak_rss_bytes: int = 0
    out_bytes: int = 0
    returncode: Optional[int] = None
    error: str = ""
    log_tail: str = ""
    cancelled: bool = False


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _memory() -> tuple:
    try:
        import psutil
        vm = psutil.virtual_memory()
        return int(vm.total), int(vm.available)
    except Exception:  # noqa: BLE001 - psutil missing: report unknown as 0
        return 0, 0


def _existing_parent(path: str) -> str:
    p = Path(path or ".").expanduser().resolve()
    while not p.exists() and p != p.parent:
        p = p.parent
    return str(p)


def count_sweep_runs(rows: List[tuple]) -> int:
    """rows = [(n_tags, n_values), ...] of the sweep table; same rule as General._internal_save_logic."""
    total = 1
    for n_tags, n_vals in rows:
        if n_tags == n_vals and n_tags > 0:
            total *= n_tags
    return total


def build_plan(data: Dict[str, Any], scene: Any, runs: int, parallel: int, out_root: str) -> Plan:
    gen = data.get("general", {}) or {}
    imt = data.get("imt", {}) or {}
    topo = (imt.get("topology") or {}).get("type", "")
    n_bs = int(getattr(scene.bs, "num_stations", 0) or 0)
    n_ue = int(getattr(scene.ue, "num_stations", 0) or 0)
    total_ram, avail_ram = _memory()
    ram = _BASE_RSS_MB * 2**20 + _MATRICES * 8.0 * n_bs * max(n_ue, 1)
    out_dir = str(gen.get("output_dir") or "") or out_root
    return Plan(
        runs=max(1, runs), snapshots=int(_num(gen.get("num_snapshots")) or 0), parallel=max(1, parallel),
        system=str(gen.get("system", "") or ""), topology=str(topo), n_bs=n_bs, n_ue=n_ue,
        seed=str(gen.get("seed", "")), freq_mhz=_num(imt.get("frequency")), bw_mhz=_num(imt.get("bandwidth")),
        out_dir=out_dir, free_disk_bytes=shutil.disk_usage(_existing_parent(out_dir)).free,
        total_ram_bytes=total_ram, avail_ram_bytes=avail_ram, ram_per_proc_bytes=ram,
        out_per_snapshot_bytes=None, work_root=out_root,
    )


def resource_checks(plan: Plan) -> List[tuple]:
    """(severity, text) pairs about RAM and disk."""
    out: List[tuple] = []
    if plan.avail_ram_bytes and plan.ram_total_bytes > plan.avail_ram_bytes:
        out.append(("warning", f"Needs about {fmt_bytes(plan.ram_total_bytes)} of RAM but only "
                               f"{fmt_bytes(plan.avail_ram_bytes)} are free. Lower the parallel jobs."))
    if plan.disk_total_bytes > plan.free_disk_bytes:
        out.append(("warning", f"Output may need {fmt_bytes(plan.disk_total_bytes)} but only "
                               f"{fmt_bytes(plan.free_disk_bytes)} are free on the output drive."))
    return out


def engine_command(yaml_path: str) -> List[str]:
    sharc_dir = Path(__file__).resolve().parents[2]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--sharc-cli", "-p", yaml_path]
    return [sys.executable, str(sharc_dir / "main_cli.py"), "-p", yaml_path]


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def run_probe(data: Dict[str, Any], cancel: threading.Event,
              on_progress: Optional[Callable[[int, int], None]] = None,
              snapshots: int = PROBE_SNAPSHOTS, timeout: float = 900.0,
              work_root: str = "", on_phase: Optional[Callable[[str], None]] = None) -> ProbeResult:
    """Run the real engine for a few snapshots in a temp folder and measure time, peak RAM and output size."""
    import yaml
    try:
        import psutil
    except Exception:  # noqa: BLE001
        psutil = None

    # The engine resolves relative paths (database, shapefiles) from the YAML's folder, so the probe
    # lives beside the real run folders (same depth), not in the system temp dir.
    if work_root:
        os.makedirs(work_root, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="_probe_", dir=work_root or None)
    try:
        cfg = copy.deepcopy(data)
        total = int(_num((cfg.get("general") or {}).get("num_snapshots")) or snapshots)
        n = max(1, min(snapshots, total))
        gen = cfg.setdefault("general", {})
        gen.update({"num_snapshots": n, "output_dir": os.path.join(tmp, "out"),
                    "output_dir_prefix": "probe", "overwrite_output": True})
        ypath = os.path.join(tmp, "probe.yaml")
        with open(ypath, "w", encoding="utf-8") as fh:
            yaml.safe_dump(cfg, fh)

        sharc_dir = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(sharc_dir.parent) + os.pathsep + env.get("PYTHONPATH", "")
        t0 = time.time()
        proc = subprocess.Popen(engine_command(ypath), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, env=env, cwd=str(sharc_dir.parent))

        peak = [0]
        stop = threading.Event()

        def sample():
            ps = None
            while not stop.is_set():
                try:
                    if psutil is not None:
                        ps = ps or psutil.Process(proc.pid)
                        rss = ps.memory_info().rss + sum(
                            c.memory_info().rss for c in ps.children(recursive=True))
                        peak[0] = max(peak[0], rss)
                except Exception:  # noqa: BLE001 - process ended between calls
                    pass
                stop.wait(0.1)

        threading.Thread(target=sample, daemon=True).start()

        def watchdog():
            while proc.poll() is None:
                if cancel.is_set() or time.time() - t0 > timeout:
                    proc.kill()
                    return
                time.sleep(0.2)

        threading.Thread(target=watchdog, daemon=True).start()

        stamps: Dict[int, float] = {}
        tail: List[str] = []
        loop_start: List[float] = []
        loop_end: List[float] = []
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                tail = (tail + [line])[-25:]
            if on_phase and "Simulation is running" in line:    # printed once start-up is over
                on_phase("running")
            lm = _LOG_TS.match(line)
            if lm:
                ts = datetime.strptime(lm.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + int(lm.group(2)) / 1000.0
                if not loop_start:
                    loop_start.append(ts)
                if "FINISHED!" in lm.group(3):
                    loop_end.append(ts)
            m = _PROGRESS.search(line)
            if m:
                cur = int(m.group(1))
                stamps.setdefault(cur, time.time())
                if on_progress:
                    on_progress(cur, int(m.group(2)))
        proc.wait()
        stop.set()
        wall = time.time() - t0
        res = ProbeResult(ok=proc.returncode == 0 and not cancel.is_set(), snapshots=n, wall_seconds=wall,
                          peak_rss_bytes=peak[0], returncode=proc.returncode, log_tail="\n".join(tail),
                          cancelled=cancel.is_set())
        if res.cancelled:
            return res
        if not res.ok:
            res.error = f"the engine exited with code {proc.returncode}"
            return res
        res.out_bytes = _dir_size(os.path.join(tmp, "out"))
        if loop_start and loop_end and loop_end[0] > loop_start[0]:
            res.seconds_per_snapshot = (loop_end[0] - loop_start[0]) / n
            res.setup_seconds = max(0.0, loop_start[0] - t0)
        elif len(stamps) >= 2:
            keys = sorted(stamps)
            res.seconds_per_snapshot = (stamps[keys[-1]] - stamps[keys[0]]) / (keys[-1] - keys[0])
            res.setup_seconds = max(0.0, stamps[keys[0]] - t0)
        else:                                    # nothing to split start-up from the loop: wall time is an upper bound
            res.seconds_per_snapshot = wall / n
        return res
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def apply_probe(plan: Plan, res: ProbeResult) -> None:
    """Replace the heuristics with what the test run measured."""
    if not res.ok:
        return
    plan.measured = True
    plan.seconds_per_snapshot = res.seconds_per_snapshot
    plan.setup_seconds = res.setup_seconds
    if res.peak_rss_bytes:
        plan.ram_per_proc_bytes = float(res.peak_rss_bytes)
    if res.snapshots:
        flushed = res.snapshots // _FLUSH_EVERY * _FLUSH_EVERY
        # fewer than 10 snapshots were probed: the engine wrote no CSV, so there is no slope to learn
        plan.out_per_snapshot_bytes = (max(0.0, res.out_bytes - _FIXED_OUT_BYTES) / flushed) if flushed else None


def fmt_bytes(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def fmt_duration(sec: Optional[float]) -> str:
    if sec is None:
        return "run the test to estimate"
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else (f"{m}m {s:02d}s" if m else f"{s}s")
