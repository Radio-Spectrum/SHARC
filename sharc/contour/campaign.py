"""A contour campaign: every ray of a site, for each base-station off-axis angle.

``ContourConfig`` holds everything as plain values (it can be pickled, so rays run in worker processes), and
``run_campaign`` evaluates the rays in parallel with progress and cancellation. Results are rows, one per (ray, off-axis).
"""
from __future__ import annotations

import csv
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from sharc.contour import geometry
from sharc.contour.budget import Budget, ReferenceBs
from sharc.contour.calculator import ContourCalculator, Sweep
from sharc.contour.criterion import Criterion
from sharc.contour.region import Region
from sharc.contour.site import RasSite

DEFAULT_P452 = {"percentage_p": 2.0, "delta_N": 45.0, "N0": 325.0, "air_temperature": 293.15,
                "atmospheric_pressure": 1013.0, "polarization": "horizontal", "clutter_loss": False,
                "clutter_type": "both_ends", "is_terrain": True, "Dct": 500.0, "Dcr": 500.0}
COLUMNS = ["az_enu_deg", "az_north_deg", "off_axis_deg", "contour_m", "marker", "ray_end_m", "ray_end_reason",
           "evaluations", "lat", "lon"]


@dataclass
class ContourConfig:
    site: RasSite
    region: Region
    bs: ReferenceBs = field(default_factory=ReferenceBs)
    criterion: Criterion = field(default_factory=Criterion)
    p452: Dict = field(default_factory=lambda: dict(DEFAULT_P452))
    propagation_frequency_mhz: float = 3500.0
    sweep: Sweep = field(default_factory=Sweep)
    bs_height_m: float = 30.0                      # constant height, used when there is no database
    database_csv: str = ""                         # latitude, longitude, altura (m): height = median of a ring of BSs
    height_window: float = 0.10
    height_n_min: int = 20
    polygon_geojson: str = ""                      # optional boundary of the study area; rays end at its edge
    ray_step_deg: float = 10.0
    off_axis_deg: Sequence[float] = (0.0, 90.0, 135.0)

    def build(self) -> ContourCalculator:
        from sharc.contour.domain import Domain
        from sharc.contour.heights import HeightTable, constant_height
        height_fn = (HeightTable(self.database_csv, self.site.lat_deg, self.site.lon_deg, self.height_window,
                                 self.height_n_min) if self.database_csv else constant_height(self.bs_height_m))
        domain = Domain(self.region.terrain, self.region.zones, self.polygon_geojson)
        return ContourCalculator(Budget(self.site, self.bs, self.criterion), self.region, self.p452, height_fn,
                                 self.propagation_frequency_mhz, domain, self.sweep)

    def azimuths(self) -> np.ndarray:
        return geometry.ray_azimuths(self.ray_step_deg)


_WORKER: Dict[str, object] = {}


def _init_worker(config: ContourConfig) -> None:
    _WORKER["calc"], _WORKER["cfg"] = config.build(), config


def _one_ray(az: float) -> List[dict]:
    return evaluate_ray(_WORKER["calc"], _WORKER["cfg"], az)


def evaluate_ray(calc: ContourCalculator, cfg: ContourConfig, az_enu: float) -> List[dict]:
    """Rows (one per off-axis angle) of the contour of one ray."""
    d_end, reason = calc.ray_end(az_enu)
    rows = []
    for off in cfg.off_axis_deg:
        if d_end < calc.sweep.d_min_m:
            found = {"contour_m": float("nan"), "marker": "no_points", "evaluations": 0}
        else:
            found = calc.contour_distance(az_enu, float(off), d_end)
        lat = lon = float("nan")
        if np.isfinite(found["contour_m"]):
            la, lo = geometry.points_on_ray(cfg.site.lat_deg, cfg.site.lon_deg, az_enu, found["contour_m"])
            lat, lon = float(la[0]), float(lo[0])
        rows.append({"az_enu_deg": float(az_enu), "az_north_deg": float(geometry.enu_to_north(az_enu)),
                     "off_axis_deg": float(off), "contour_m": float(found["contour_m"]), "marker": found["marker"],
                     "ray_end_m": float(d_end), "ray_end_reason": reason, "evaluations": int(found["evaluations"]),
                     "lat": lat, "lon": lon})
    return rows


def run_campaign(config: ContourConfig, processes: int = 1, progress: Optional[Callable[[int, int], None]] = None,
                 cancelled: Optional[Callable[[], bool]] = None) -> List[dict]:
    """Rows of every ray. `progress(done, total)` after each ray; `cancelled()` is polled between rays (the rows done
    so far are returned). With `processes` > 1 the rays run in worker processes, each loading the rasters once."""
    config.region.check()
    azimuths = [float(a) for a in config.azimuths()]
    total, rows = len(azimuths), []

    def tick(done):
        if progress:
            progress(done, total)
    if processes > 1:
        try:
            with ProcessPoolExecutor(max_workers=processes, initializer=_init_worker, initargs=(config,)) as pool:
                futures = [pool.submit(_one_ray, az) for az in azimuths]
                for i, fut in enumerate(futures, 1):
                    if cancelled and cancelled():
                        for f in futures:
                            f.cancel()
                        break
                    rows += fut.result()
                    tick(i)
            return sorted(rows, key=lambda r: (r["az_enu_deg"], r["off_axis_deg"]))
        except (OSError, RuntimeError, ImportError):              # no process pool (frozen app, restricted host): serial
            rows = []
    calc = config.build()
    for i, az in enumerate(azimuths, 1):
        if cancelled and cancelled():
            break
        rows += evaluate_ray(calc, config, az)
        tick(i)
    return rows


def write_csv(rows: Sequence[dict], path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in COLUMNS})
    return path


def summary(rows: Sequence[dict]) -> Dict[float, Dict[str, float]]:
    """Per off-axis angle: number of rays, median / min / max contour distance [m] and the count of each marker."""
    out: Dict[float, Dict[str, float]] = {}
    for off in sorted({r["off_axis_deg"] for r in rows}):
        sel = [r for r in rows if r["off_axis_deg"] == off]
        d = np.array([r["contour_m"] for r in sel], float)
        d = d[np.isfinite(d)]
        entry = {"rays": len(sel), "median_m": float(np.median(d)) if d.size else float("nan"),
                 "min_m": float(d.min()) if d.size else float("nan"), "max_m": float(d.max()) if d.size else float("nan")}
        for marker in sorted({r["marker"] for r in sel}):
            entry[marker] = sum(1 for r in sel if r["marker"] == marker)
        out[float(off)] = entry
    return out
