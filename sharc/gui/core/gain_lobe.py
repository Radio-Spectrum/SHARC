"""3D antenna gain lobes for the preview (radiation solid coloured as a heat map).

The gain comes from the engine's own antenna object (the IMT base-station array with one beam steered to the
sector boresight), sampled on a sphere. The lobe is built as a closed surface whose radius follows the gain
over a fixed dynamic range, split into translucent colour bands (cold = side lobes, hot = main beam) and
written as a GLB the 3D view instantiates once per sector.

glTF frame: +Y up, +Z along the sector azimuth, +X to the right of it (so the model heading is the sector azimuth).
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any, Dict, Optional, Tuple

import numpy as np

from core import model_factory

RANGE_DB = 30.0                     # radius covers [peak - RANGE_DB, peak]
N_BANDS = 8
D_PHI = 3.0                         # azimuth step [deg]
D_ELEV = 2.5                        # elevation step [deg]
MIN_RADIUS = 0.015                  # keeps the surface closed in deep nulls

# Turbo-like stops, cold to hot (r, g, b)
_STOPS = [(0.19, 0.07, 0.23), (0.25, 0.39, 0.76), (0.11, 0.73, 0.80), (0.36, 0.91, 0.44),
          (0.78, 0.94, 0.20), (0.98, 0.70, 0.12), (0.87, 0.30, 0.12), (0.64, 0.12, 0.11)]


def band_color(k: int) -> Tuple[float, float, float]:
    return _STOPS[min(k, len(_STOPS) - 1)]


def sample_bs_gain(es) -> Optional[Dict[str, Any]]:
    """Gain [dBi] of the first base-station sector on a (elevation, azimuth-offset) grid, from the engine antenna.

    Returns {"dphi": (P,), "elev": (E,), "gain": (E, P), "peak": float, "az": float, "el": float} or None.
    """
    bs = es.bs
    if not len(getattr(bs, "antenna", [])):
        return None
    ant = copy.deepcopy(bs.antenna[0])                      # never mutate the cached engine scene
    az = float(bs.geom.pointn_azim_global[0])
    el = float(bs.geom.pointn_elev_global[0])               # negative = pointing down
    if hasattr(ant, "beams_list"):
        ant.beams_list, ant.w_vec_list = [], []
        if hasattr(ant, "co_correction_factor_list"):
            ant.co_correction_factor_list = []
        ant.add_beam(az, 90.0 - el)                         # one beam on the sector boresight

    dphi = np.arange(-180.0, 180.0 + 1e-6, D_PHI)
    elev = np.arange(-90.0, 90.0 + 1e-6, D_ELEV)
    PH, EL = np.meshgrid(dphi, elev)
    phi_vec = (az + PH).ravel()
    theta_vec = (90.0 - EL).ravel()                         # engine theta is measured from +Z
    try:
        g = ant.calculate_gain(phi_vec=phi_vec, theta_vec=theta_vec, beams_l=np.zeros(phi_vec.size, dtype=int))
    except Exception:                                       # noqa: BLE001 - e.g. constant-gain antennas
        g = ant.calculate_gain(phi_vec=phi_vec, theta_vec=theta_vec)
    gain = np.asarray(g, dtype=float).reshape(PH.shape)
    return {"dphi": dphi, "elev": elev, "gain": gain, "peak": float(np.nanmax(gain)), "az": az, "el": el}


def lobe_range(data: Dict[str, Any]) -> Tuple[float, float]:
    """(floor [dBi], dynamic range [dB]): up to RANGE_DB below the peak, but never below the engine's own gain floor
    (the engine clamps the array gain at `minimum_array_gain`, which would otherwise draw a ball of constant radius)."""
    peak = data["peak"]
    lo = max(peak - RANGE_DB, float(np.nanmin(data["gain"])))
    return lo, max(peak - lo, 6.0)


def jet(t: np.ndarray) -> np.ndarray:
    """STK-style rainbow: dark blue -> blue -> cyan -> green -> yellow -> red -> dark red. t in [0, 1] -> (..., 3)."""
    t = np.clip(np.asarray(t, dtype=float), 0.0, 1.0)
    r = np.clip(1.5 - np.abs(4.0 * t - 3.0), 0.0, 1.0)
    g = np.clip(1.5 - np.abs(4.0 * t - 2.0), 0.0, 1.0)
    b = np.clip(1.5 - np.abs(4.0 * t - 1.0), 0.0, 1.0)
    return np.stack([r, g, b], axis=-1)


def _smooth_normals(pts: np.ndarray) -> np.ndarray:
    """Vertex normals of the (E, P, 3) grid surface, averaged across the azimuth seam and at the poles."""
    n_e, n_p, _ = pts.shape
    flat = pts.reshape(-1, 3)
    idx = np.arange(n_e * n_p).reshape(n_e, n_p)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    tris = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    fn = np.cross(flat[tris[:, 1]] - flat[tris[:, 0]], flat[tris[:, 2]] - flat[tris[:, 0]])
    normals = np.zeros_like(flat)
    for col in range(3):
        np.add.at(normals, tris[:, col], fn)
    nm = normals.reshape(n_e, n_p, 3)
    seam = nm[:, 0] + nm[:, -1]                                  # first and last column are the same meridian
    nm[:, 0] = nm[:, -1] = seam
    nm[0] = nm[0].sum(axis=0)                                    # poles collapse to one point
    nm[-1] = nm[-1].sum(axis=0)
    ln = np.linalg.norm(nm, axis=-1, keepdims=True)
    return (nm / np.where(ln == 0, 1.0, ln)).reshape(-1, 3).astype(np.float32), tris


def build_lobe_model(data: Dict[str, Any]) -> model_factory.Model:
    """Smooth radiation solid (unit radius at the peak), coloured per vertex with the rainbow scale like STK."""
    dphi, elev, gain = data["dphi"], data["elev"], data["gain"]
    lo, span = lobe_range(data)
    norm = np.clip((gain - lo) / span, 0.0, 1.0)                                # 0 = floor, 1 = peak
    r = np.maximum(norm, MIN_RADIUS)
    PH, EL = np.meshgrid(np.radians(dphi), np.radians(elev))
    # glTF axes: +Z forward (azimuth offset 0), +X to the right, +Y up
    pts = np.stack([-r * np.cos(EL) * np.sin(PH), r * np.sin(EL), r * np.cos(EL) * np.cos(PH)], axis=-1).astype(np.float32)
    normals, tris = _smooth_normals(pts)
    rgb = jet(norm.ravel())
    colors = np.concatenate([rgb, np.ones((rgb.shape[0], 1))], axis=1).astype(np.float32)
    model = model_factory.Model()
    mat = model.material((1.0, 1.0, 1.0, 1.0), metallic=0.0, roughness=0.55, emissive=(0.12, 0.12, 0.12), double_sided=True)
    model.parts.append(model_factory.Part(pts.reshape(-1, 3), normals, tris.astype(np.uint32).reshape(-1), mat, colors))
    return model


def _register(data: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    """Build and register the GLB for sampled gain `data`; returns the description the 3D view needs."""
    key = hashlib.sha1(np.round(data["gain"], 2).tobytes() + str(data["peak"]).encode()).hexdigest()[:12]
    name = f"{prefix}_{key}"
    model_factory.register(name, model_factory.to_glb(build_lobe_model(data)))
    lo, span = lobe_range(data)
    return {"uri": f"/models/{name}.glb", "peak_dbi": round(data["peak"], 1), "range_db": round(span, 1),
            "floor_dbi": round(lo, 1), "bands": N_BANDS,
            "colors": [[round(float(v), 3) for v in jet(k / (N_BANDS - 1))] for k in range(N_BANDS)]}


def sample_axisymmetric_gain(antenna) -> Optional[Dict[str, Any]]:
    """Gain [dBi] of a rotationally symmetric antenna (dish, satellite beam) on the same grid as the sector lobe,
    with the boresight at azimuth offset 0 / elevation 0. Uses the engine antenna through `antenna_service.gain_at`."""
    from core import antenna_service
    dphi = np.arange(-180.0, 180.0 + 1e-6, D_PHI)
    elev = np.arange(-90.0, 90.0 + 1e-6, D_ELEV)
    PH, EL = np.meshgrid(np.radians(dphi), np.radians(elev))
    off_axis = np.degrees(np.arccos(np.clip(np.cos(EL) * np.cos(PH), -1.0, 1.0)))
    gain = np.asarray(antenna_service.gain_at(antenna, off_axis.ravel()), dtype=float).reshape(PH.shape)
    if not np.isfinite(gain).any():
        return None
    gain = np.where(np.isfinite(gain), gain, np.nanmin(gain))
    return {"dphi": dphi, "elev": elev, "gain": gain, "peak": float(gain.max()), "az": 0.0, "el": 0.0}


def bs_lobe_for_scene(es) -> Optional[Dict[str, Any]]:
    """Register the base-station lobe GLB for this engine scene and describe it for the 3D view."""
    cached = getattr(es, "_gain_lobe", "unset")
    if cached != "unset":
        return cached
    info = None
    try:
        data = sample_bs_gain(es)
        if data is not None and np.isfinite(data["peak"]):
            info = _register(data, "lobe")
    except Exception:                                       # noqa: BLE001 - the preview must never fail because of a lobe
        info = None
    try:
        es._gain_lobe = info
    except Exception:                                       # noqa: BLE001 - frozen/slotted scene objects
        pass
    return info


def system_lobe_for_scene(es) -> Optional[Dict[str, Any]]:
    """Lobe of the victim system antenna (earth station dish or satellite beam), from the engine."""
    cached = getattr(es, "_system_lobe", "unset")
    if cached != "unset":
        return cached
    info = None
    try:
        system = getattr(es, "system", None)
        if system is not None and len(getattr(system, "antenna", [])):
            data = sample_axisymmetric_gain(system.antenna[0])
            if data is not None:
                info = _register(data, "syslobe")
    except Exception:                                       # noqa: BLE001
        info = None
    try:
        es._system_lobe = info
    except Exception:                                       # noqa: BLE001
        pass
    return info
