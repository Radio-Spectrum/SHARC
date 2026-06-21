# -*- coding: utf-8 -*-
"""Estimate statistical terrain & clutter parameters from real terrain (Campinas-SP).

This reproduces, for the ITU-R P.1812 statistical-terrain approach, the method
of ITU-R WP5D contribution 5D/1059 (Brazilian statistical terrain model):

  * extract a set of elevation cross-sections (radials),
  * segment each into 10 km intervals and detrend against the segment's
    straight reference line,
  * detect peaks/valleys of the residual and collect
        - height deviations of extrema relative to the local mean line,
        - horizontal distances between consecutive extrema,
  * fit a Student's t-distribution to the heights and a lognormal to the
    distances.

It additionally estimates a *simple statistical clutter-over-terrain* model
(see ``terrain_statistical.py``) from the sub-kilometre roughness residual.

Run with:  python -m sharc.propagation.tools.estimate_terrain_params_campinas
Outputs fitted parameters (JSON) and diagnostic figures.
"""
import os
import json

import numpy as np
from scipy import stats
from scipy.signal import find_peaks

from sharc.propagation.terrain_srtm import SRTMReader

# ----------------------------------------------------------------------
# Configuration (steps 2-4 of the task)
# ----------------------------------------------------------------------
START_LAT = -22.9048878490284
START_LON = -47.06032221390534
N_RADIALS = 20
RADIAL_LENGTH_KM = 50.0
# Profile sampling: SRTMGL1 is ~30 m; use ~100 m spacing along the radial
PROFILE_STEP_KM = 0.1
SEGMENT_KM = 10.0           # detrending segment length (per 5D/1059)
CLUTTER_SMOOTH_KM = 1.6     # terrain correlation length -> separates clutter roughness
# Minimum prominence (m) for a residual extremum to count as a terrain feature.
# Without it, find_peaks captures sub-100 m SRTM noise and grossly underestimates
# the spacing between true terrain peaks/valleys.
TERRAIN_PROMINENCE_M = 10.0


def _output_dir():
    scratch = os.environ.get(
        "CLAUDE_SCRATCH",
        os.path.join(os.path.dirname(__file__), "_campinas_out"),
    )
    os.makedirs(scratch, exist_ok=True)
    return scratch


def extract_radials(srtm_dir):
    """Generate the 20 radial terrain profiles of 50 km from the start point."""
    n_points = int(round(RADIAL_LENGTH_KM / PROFILE_STEP_KM)) + 1
    reader = SRTMReader(srtm_dir, auto_download=True)

    from pyproj import Geod
    geod = Geod(ellps="WGS84")

    radials = []
    for k in range(N_RADIALS):
        az = 360.0 * k / N_RADIALS
        # End point of the radial along azimuth az
        end_lon, end_lat, _ = geod.fwd(START_LON, START_LAT, az, RADIAL_LENGTH_KM * 1000.0)
        d_km, h_m = reader.path_profile(START_LAT, START_LON, end_lat, end_lon, n_points)
        radials.append({"azimuth": az, "d_km": d_km, "h_m": h_m})
    return radials


def extract_terrain_descriptors(radials):
    """Collect peak/valley height deviations and inter-extrema distances.

    Returns
    -------
    tuple(np.ndarray, np.ndarray)
        heights (m, signed deviation from the local reference line) and
        distances (km) between consecutive extrema, pooled over all radials.
    """
    heights = []
    distances = []

    for prof in radials:
        d = prof["d_km"]
        h = prof["h_m"]
        step = np.median(np.diff(d))
        seg_pts = max(int(round(SEGMENT_KM / step)), 4)

        for s0 in range(0, len(d) - 1, seg_pts):
            s1 = min(s0 + seg_pts, len(d) - 1)
            if s1 - s0 < 4:
                continue
            ds = d[s0:s1 + 1]
            hs = h[s0:s1 + 1]
            # Straight reference line between segment endpoints
            ref = np.interp(ds, [ds[0], ds[-1]], [hs[0], hs[-1]])
            resid = hs - ref

            # Detect peaks (maxima) and valleys (minima) of the residual,
            # keeping only prominent (terrain-scale) features.
            pk, _ = find_peaks(resid, prominence=TERRAIN_PROMINENCE_M)
            vl, _ = find_peaks(-resid, prominence=TERRAIN_PROMINENCE_M)
            ext = np.sort(np.concatenate([pk, vl]))
            if ext.size < 2:
                continue

            heights.extend(resid[ext].tolist())
            distances.extend(np.diff(ds[ext]).tolist())

    heights = np.asarray(heights, dtype=float)
    distances = np.asarray(distances, dtype=float)
    distances = distances[distances > 0]
    return heights, distances


def extract_clutter_residual(radials):
    """Sub-kilometre roughness used as a simple clutter-height proxy.

    The terrain is smoothed with a moving median over ``CLUTTER_SMOOTH_KM`` to
    remove the broad undulation captured by the terrain model; the positive
    part of the residual (surface above the smoothed bare-ish terrain) is taken
    as a proxy for representative clutter height.
    """
    clutter = []
    for prof in radials:
        d = prof["d_km"]
        h = prof["h_m"]
        step = np.median(np.diff(d))
        win = max(int(round(CLUTTER_SMOOTH_KM / step)) | 1, 3)  # odd window
        # Moving median (robust to terrain edges)
        smooth = np.array([
            np.median(h[max(0, i - win // 2):min(len(h), i + win // 2 + 1)])
            for i in range(len(h))
        ])
        resid = h - smooth
        clutter.extend(resid[resid > 0].tolist())
    return np.asarray(clutter, dtype=float)


def fit_terrain(heights, distances):
    """Fit Student-t to heights (mu fixed at 0) and lognormal to distances."""
    # Student-t with location fixed at 0 (per 5D/1059: mu = 0)
    nu, _, sigma = stats.t.fit(heights, floc=0.0)
    # Lognormal: shape s = sigma_ln, scale = exp(mu_ln); loc fixed at 0
    s, _, scale = stats.lognorm.fit(distances, floc=0.0)
    mu_ln = float(np.log(scale))
    return {
        "height_student_t": {"mu_m": 0.0, "sigma_m": float(sigma), "nu": float(nu)},
        "distance_lognormal": {
            "mu": mu_ln, "sigma": float(s),
            "mean_km": float(np.exp(mu_ln + 0.5 * s ** 2)),
        },
    }


def fit_clutter(clutter):
    """Fit a lognormal to the positive clutter-height proxy."""
    clutter = clutter[clutter > 0.1]  # drop near-zero noise
    s, _, scale = stats.lognorm.fit(clutter, floc=0.0)
    mu_ln = float(np.log(scale))
    return {
        "clutter_lognormal": {
            "mu": mu_ln, "sigma": float(s),
            "mean_m": float(np.exp(mu_ln + 0.5 * s ** 2)),
            "median_m": float(np.exp(mu_ln)),
        },
        "n_samples": int(clutter.size),
    }


def main():
    out = _output_dir()
    srtm_dir = os.path.join(out, "srtm")

    print(f"Extracting {N_RADIALS} radials of {RADIAL_LENGTH_KM} km from "
          f"({START_LAT}, {START_LON}) ...")
    radials = extract_radials(srtm_dir)

    elevs = np.concatenate([r["h_m"] for r in radials])
    print(f"  terrain elevation over all radials: "
          f"min={elevs.min():.0f} m, mean={elevs.mean():.0f} m, max={elevs.max():.0f} m")

    heights, distances = extract_terrain_descriptors(radials)
    clutter = extract_clutter_residual(radials)
    print(f"  extrema collected: {heights.size} heights, {distances.size} distances")
    print(f"  clutter-proxy samples: {clutter.size}")

    terrain_fit = fit_terrain(heights, distances)
    clutter_fit = fit_clutter(clutter)

    result = {
        "start_point": {"lat": START_LAT, "lon": START_LON},
        "n_radials": N_RADIALS,
        "radial_length_km": RADIAL_LENGTH_KM,
        "terrain_model": terrain_fit,
        "clutter_model": clutter_fit,
    }

    json_path = os.path.join(out, "campinas_terrain_clutter_params.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("\nFitted parameters:")
    print(json.dumps(result, indent=2))
    print(f"\nSaved -> {json_path}")

    # Save raw samples for plotting/inspection
    np.savez(
        os.path.join(out, "campinas_samples.npz"),
        heights=heights, distances=distances, clutter=clutter,
        **{f"radial_{i}_d": r["d_km"] for i, r in enumerate(radials)},
        **{f"radial_{i}_h": r["h_m"] for i, r in enumerate(radials)},
    )
    return result


if __name__ == "__main__":
    main()
