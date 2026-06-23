# -*- coding: utf-8 -*-
"""Validate the statistical terrain/clutter model for ITU-R P.1812.

Compares the P.1812 basic transmission loss obtained with:
  * flat (smooth-Earth) terrain,
  * the synthetic statistical terrain (Monte-Carlo realizations),
  * the 20 real Campinas-SP radial profiles (path-specific, truncated),
at several distances. If the statistical-model loss distribution brackets the
real path-specific losses, the synthesis is validated.

Run with:  python -m sharc.propagation.tools.validate_statistical_terrain
"""
import os
import json

import numpy as np
from pyproj import Geod

from sharc.parameters.parameters_p1812 import ParametersP1812
from sharc.propagation.propagation_p1812 import PropagationP1812
from sharc.propagation.terrain_srtm import SRTMReader

FREQ_GHZ = 3.5
HTE = 30.0
HRE = 1.5
DISTANCES_KM = [10.0, 20.0, 30.0, 50.0]
N_MC = 1000
N_RADIALS = 20
START_LAT = -22.9048878490284
START_LON = -47.06032221390534
FINE_STEP_KM = 0.1   # ground-truth real profiles use fine sampling (true diffraction)


def _out_dir():
    return os.environ.get(
        "CLAUDE_SCRATCH",
        os.path.join(os.path.dirname(__file__), "_campinas_out"),
    )


def _loss_for_profile(prop, d_km, h_m):
    """P.1812 loss for one explicit (d_km, h_m) profile via the terrain stash."""
    prop._terrain_profiles = [(np.asarray(d_km), np.asarray(h_m))]
    try:
        d = np.array([[d_km[-1]]])
        f = FREQ_GHZ * np.ones((1, 1))
        ind = np.zeros((1, 1), dtype=bool)
        el = np.zeros((1, 1))
        return float(np.ravel(prop.get_loss(d, f, ind, el,
                                            np.array([20.0]), np.array([0.0])))[0])
    finally:
        prop._terrain_profiles = None


def _make_prop(terrain_profile, clutter_mode="none", clutter_statistical=False, seed=0):
    par = ParametersP1812()
    par.terrain_profile = terrain_profile
    par.clutter_mode = clutter_mode
    par.clutter_statistical = clutter_statistical
    par.Hte = HTE
    par.Hre = HRE
    par.profile_resolution = 100
    return PropagationP1812(np.random.RandomState(seed), par)


def _real_profile(reader, geod, az_deg, dist_km):
    """Finely-sampled (100 m) real SRTM profile from the centre along an azimuth."""
    n = int(round(dist_km / FINE_STEP_KM)) + 1
    end_lon, end_lat, _ = geod.fwd(START_LON, START_LAT, az_deg, dist_km * 1000.0)
    return reader.path_profile(START_LAT, START_LON, end_lat, end_lon, n)


def main():
    out = _out_dir()
    # Ground-truth real profiles are generated at fine (100 m) sampling so they
    # carry the true terrain diffraction (independent of the 1 km step used to
    # FIT the extrema distributions).
    reader = SRTMReader(os.path.join(out, "srtm"), auto_download=True)
    geod = Geod(ellps="WGS84")
    n_rad = N_RADIALS

    flat_prop = _make_prop("flat")

    print(f"{'dist':>6} | {'flat':>7} | {'real profiles (20)':>34} | {'statistical (MC)':>30}")
    print(f"{'km':>6} | {'dB':>7} | {'p5      p50      mean     p95':>34} | "
          f"{'p5      p50      mean     p95':>30}")
    print("-" * 90)

    rows = []
    for dist in DISTANCES_KM:
        # Flat reference
        flat = _loss_for_profile(
            flat_prop, np.linspace(0, dist, 100), np.zeros(100),
        )

        # Real path-specific profiles (fine 100 m sampling, true diffraction)
        real = []
        for k in range(n_rad):
            d_km, h_m = _real_profile(reader, geod, 360.0 * k / n_rad, dist)
            real.append(_loss_for_profile(flat_prop, d_km, h_m))
        real = np.array(real)

        # Statistical Monte-Carlo realizations
        stat = []
        for seed in range(N_MC):
            p = _make_prop("statistical", seed=seed)
            d = np.array([[dist]])
            f = FREQ_GHZ * np.ones((1, 1))
            stat.append(float(np.ravel(p.get_loss(
                d, f, np.zeros((1, 1), dtype=bool), np.zeros((1, 1)),
                np.array([20.0]), np.array([0.0])))[0]))
        stat = np.array(stat)

        def q(a):
            return (np.percentile(a, 5), np.percentile(a, 50), a.mean(), np.percentile(a, 95))

        rp = q(real)
        sp = q(stat)
        print(f"{dist:>6.0f} | {flat:>7.1f} | "
              f"{rp[0]:>7.1f} {rp[1]:>7.1f} {rp[2]:>7.1f} {rp[3]:>7.1f}  | "
              f"{sp[0]:>7.1f} {sp[1]:>7.1f} {sp[2]:>7.1f} {sp[3]:>7.1f}")
        rows.append({"dist_km": dist, "flat": flat,
                     "real": {"p5": rp[0], "p50": rp[1], "mean": rp[2], "p95": rp[3]},
                     "stat": {"p5": sp[0], "p50": sp[1], "mean": sp[2], "p95": sp[3]}})

    with open(os.path.join(out, "validation_results.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    print(f"\nSaved -> {os.path.join(out, 'validation_results.json')}")


if __name__ == "__main__":
    main()
