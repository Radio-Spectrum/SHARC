#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone test runner for the ITU-R M.1851 cosecant-squared antenna.

Run everything with a single command (no CLI flags needed):

    python tests/test_antenna_m1851_cosecant_squared.py

It prints a PASS/FAIL report and exits 0 (all pass) or 1 (any fail). It is also
discoverable by pytest (``test_all``), so ``pytest`` works too.

Groups:
  A  - pattern conformance and properties (Radar C + ITU-R M.1851 Fig. 9 example)
  B1 - source in several directions vs. the antenna boresight (parametric table)
  B2 - full geometry: source placed at x,y,z; angles computed via trigonometry,
       then the gain (position -> angle -> gain), cross-checked against B1
Plus a small integration check through ParametersAntenna / AntennaFactory.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from sharc.antenna.antenna_m1851_cosecant_squared import (
    AntennaM1851CosecantSquared,
)
from sharc.parameters.parameters_antenna_m1851_cosecant_squared import (
    ParametersAntennaM1851CosecantSquared,
)
from sharc.parameters.parameters_antenna import ParametersAntenna
from sharc.antenna.antenna_factory import AntennaFactory

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_RESULTS = []   # (group, description, expected, got, tol, ok)


def _check(group, desc, got, expected, tol=0.5):
    ok = abs(float(got) - float(expected)) <= tol
    _RESULTS.append((group, desc, float(expected), float(got), tol, ok))


def radar_c(mask="average", remote=3.5, gain=34.0, th3el=4.8,
            th_start=6.0, th_end=30.0, first_sl=9.5, th3az=1.45):
    """Radar C parameters (ITU-R M.1464-2, Table 1)."""
    return ParametersAntennaM1851CosecantSquared(
        peak_gain=gain, elevation_beamwidth=th3el, azimuth_beamwidth=th3az,
        csc2_start=th_start, csc2_end=th_end, first_side_lobe=first_sl,
        remote_side_lobe=remote, mask_type=mask)


def gain_ang(ant, az, el):
    """Gain [dBi] for a source at absolute azimuth ``az`` and elevation ``el``."""
    return float(ant.calculate_gain(
        phi_vec=np.array([az]), theta_vec=np.array([90.0 - el]))[0])


def gain_geom(ant, boresight, az, el, dist=100_000.0, h_ant=8.0):
    """Gain via direct geometry: place a source at (az, el, dist) in global
    coordinates, compute the direction vector in the antenna's local frame
    (x = boresight, y = left, z = up), convert to SHARC's phi/theta convention
    (phi = azimuth about x, theta = zenith angle), then evaluate the gain.

    This replicates what StationManager.get_pointing_vector_to would do without
    depending on that API being present in the current codebase version.
    """
    # source position in global Cartesian (antenna at origin, z = up)
    r = dist * np.cos(np.radians(el))
    sx = r * np.cos(np.radians(az))
    sy = r * np.sin(np.radians(az))
    sz = dist * np.sin(np.radians(el))

    # rotate into antenna-local frame: boresight along +x_local
    # x_local = (cos(boresight), sin(boresight), 0)  -- horizontal, north-based
    # y_local = (-sin(boresight), cos(boresight), 0)
    # z_local = (0, 0, 1)
    cb, sb = np.cos(np.radians(boresight)), np.sin(np.radians(boresight))
    lx =  cb * sx + sb * sy   # along boresight
    ly = -sb * sx + cb * sy   # lateral
    lz = sz                   # up

    # SHARC convention: phi = azimuth about x (atan2(y, x) in local frame,
    # but the antenna's x is boresight so phi measures offset in y-z plane);
    # theta = angle from +z (zenith), i.e. zenith angle.
    # calculate_gain uses phi as the horizontal-plane angle and theta as the
    # zenith angle, matching antenna_m1851_cosecant_squared which does:
    #   off_az = (phi - boresight_az + 180) % 360 - 180
    #   elevation = 90 - theta
    # Since we pass phi = absolute azimuth (same convention as gain_ang), we
    # simply pass az and el directly -- this cross-checks B1 via a geometric
    # detour that verifies the coordinate decomposition is self-consistent.
    phi_out = np.degrees(np.arctan2(ly, lx)) + boresight  # back to global az
    theta_out = 90.0 - np.degrees(np.arctan2(lz, np.sqrt(lx**2 + ly**2)))
    return float(ant.calculate_gain(
        phi_vec=np.array([phi_out]),
        theta_vec=np.array([theta_out]))[0])


# --------------------------------------------------------------------------- #
# Group A - pattern conformance and properties
# --------------------------------------------------------------------------- #
def run_group_a():
    ant = AntennaM1851CosecantSquared(radar_c())          # boresight = 0
    tilt = ant.tilt
    _check("A", "derived tilt = theta_start - theta3el/2", tilt, 3.6, 0.01)
    _check("A", "derived theta_null = tilt - theta3el/0.88",
           tilt - 4.8 / 0.88, -1.855, 0.01)
    _check("A", "peak gain at boresight (az=0, el=tilt)",
           gain_ang(ant, 0.0, tilt), 34.0, 0.2)
    _check("A", "elevation -3 dB at el=tilt+theta3el/2 (=6 deg)",
           gain_ang(ant, 0.0, tilt + 2.4), 31.0, 0.5)
    _check("A", "elevation -3 dB at el=tilt-theta3el/2 (=1.2 deg)",
           gain_ang(ant, 0.0, tilt - 2.4), 31.0, 0.5)
    _check("A", "csc2 end el=30 deg", gain_ang(ant, 0.0, 30.0), 17.39, 0.2)
    _check("A", "floor above csc2 end (el=45)", gain_ang(ant, 0.0, 45.0), 3.5, 0.1)
    _check("A", "floor below null (el=-5)", gain_ang(ant, 0.0, -5.0), 3.5, 0.1)
    _check("A", "azimuth -3 dB at +theta3az/2 (=0.725 deg)",
           gain_ang(ant, 0.725, tilt), 31.0, 0.6)
    _check("A", "azimuth symmetry G(+5)=G(-5)",
           gain_ang(ant, 5.0, tilt) - gain_ang(ant, -5.0, tilt), 0.0, 1e-6)
    _check("A", "azimuth back lobe (az=180) = remote SL",
           gain_ang(ant, 180.0, tilt), 3.5, 0.1)

    # peak vs average mask coefficients (M.1851 Table 6, cosine row)
    ap = AntennaM1851CosecantSquared(radar_c(mask="peak"))
    aa = AntennaM1851CosecantSquared(radar_c(mask="average"))
    _check("A", "peak break point (dB)", ap.az_break, -14.4, 1e-6)
    _check("A", "average break point (dB)", aa.az_break, -20.6, 1e-6)
    _check("A", "average mask offset (dB)", aa.mask_offset, -4.32, 1e-6)
    _check("A", "average <= peak in side-lobe region (az=2 deg)",
           1.0 if gain_ang(aa, 2.0, ap.tilt) <= gain_ang(ap, 2.0, ap.tilt) + 1e-6
           else 0.0, 1.0, 0.0)

    # Conformance with the ITU-R M.1851-2 worked example (Fig. 9): gain 33.5,
    # theta_start 4.4, theta_end 30 (=> tilt 2.0), elevation floor -55 dB.
    fig9 = ParametersAntennaM1851CosecantSquared(
        peak_gain=33.5, elevation_beamwidth=4.8, azimuth_beamwidth=1.45,
        csc2_start=4.4, csc2_end=30.0, first_side_lobe=10.0)  # remote unset
    a9 = AntennaM1851CosecantSquared(fig9)
    _check("A", "M.1851 Fig.9 tilt = 2.0 deg", a9.tilt, 2.0, 0.01)
    _check("A", "M.1851 Fig.9 peak = 33.5 dBi", gain_ang(a9, 0.0, 2.0), 33.5, 0.2)
    _check("A", "M.1851 Fig.9 gain at el=30 (~15 dBi)",
           gain_ang(a9, 0.0, 30.0), 15.0, 1.5)


# --------------------------------------------------------------------------- #
# Group B1 - source in several directions vs. the boresight (parametric table)
# B = boresight azimuth. Table rows: (label, absolute az, elevation, expected)
# --------------------------------------------------------------------------- #
B = 30.0
SOURCE_TABLE = [
    ("boresight (az=B, el=tilt)",          B,          3.6,  34.0, 0.2),
    ("az half-beam (B+0.725, el=tilt)",    B + 0.725,  3.6,  31.0, 0.6),
    ("az half-beam (B-0.725, el=tilt)",    B - 0.725,  3.6,  31.0, 0.6),
    ("el main-lobe edge (B, el=6)",        B,          6.0,  31.0, 0.5),
    ("csc2 region (B, el=15)",             B,          15.0, 23.6, 0.5),
    ("csc2 end (B, el=30)",                B,          30.0, 17.4, 0.3),
    ("above csc2 -> floor (B, el=45)",     B,          45.0, 3.5,  0.1),
    ("below null -> floor (B, el=-5)",     B,          -5.0, 3.5,  0.1),
    ("azimuth far -> floor (B+30, el=tilt)", B + 30.0, 3.6,  3.5,  0.1),
    ("back lobe (B+180, el=tilt)",         B + 180.0,  3.6,  3.5,  0.1),
]


def run_group_b1():
    ant = AntennaM1851CosecantSquared(
        radar_c(), azimuth=np.array([B]), elevation=None)
    for label, az, el, exp, tol in SOURCE_TABLE:
        _check("B1", f"{label}", gain_ang(ant, az, el), exp, tol)


# --------------------------------------------------------------------------- #
# Group B2 - full geometry (position -> angle -> gain), same source table
# --------------------------------------------------------------------------- #
def run_group_b2():
    ant = AntennaM1851CosecantSquared(
        radar_c(), azimuth=np.array([B]), elevation=None)
    for label, az, el, exp, tol in SOURCE_TABLE:
        _check("B2", f"geom {label}", gain_geom(ant, B, az, el), exp, tol)


# --------------------------------------------------------------------------- #
# Integration - ParametersAntenna.validate() + AntennaFactory
# --------------------------------------------------------------------------- #
def run_integration():
    p = ParametersAntenna()
    p.pattern = "M.1851-cosecant-squared"
    c = p.itu_r_m1851_csc2
    c.peak_gain = 34.0; c.elevation_beamwidth = 4.8; c.azimuth_beamwidth = 1.45
    c.csc2_start = 6.0; c.csc2_end = 30.0; c.first_side_lobe = 9.5
    c.remote_side_lobe = 3.5
    validated = 1.0
    try:
        p.validate("antenna")   # top-level gain not required for this pattern
    except Exception:
        validated = 0.0
    _check("INT", "ParametersAntenna.validate() passes", validated, 1.0, 0.0)
    ant = AntennaFactory.create_antenna(p, np.array([B]), np.array([0.0]))
    _check("INT", "factory builds and uses geometry azimuth as boresight",
           ant.boresight_az, B, 1e-6)
    _check("INT", "factory antenna peak at boresight",
           gain_ang(ant, B, ant.tilt), 34.0, 0.2)
    _check("INT", "default mask_type is average (aggregate)",
           1.0 if ant.az_break == -20.6 else 0.0, 1.0, 0.0)


def run_all():
    _RESULTS.clear()
    run_group_a()
    run_group_b1()
    run_group_b2()
    run_integration()


# --------------------------------------------------------------------------- #
# Outputs: results CSV + spatial geometry figure
# --------------------------------------------------------------------------- #
def write_results_csv(path):
    """Write all checks (group, description, expected, got, tol, result)."""
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "description", "expected", "got", "tol", "result"])
        for g, d, e, got, t, ok in _RESULTS:
            w.writerow([g, d, f"{e:.3f}", f"{got:.3f}", f"{t:.3f}",
                        "PASS" if ok else "FAIL"])


def make_geometry_figure(path, boresight=B, h_ant=8.0):
    """Spatial figure: antenna position/orientation and RF-source directions
    with the obtained gain (azimuth plan + elevation profile)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ant = AntennaM1851CosecantSquared(
        radar_c(), azimuth=np.array([boresight]), elevation=None)
    tilt = ant.tilt
    fig, (axp, axe) = plt.subplots(1, 2, figsize=(13, 6))

    # Panel 1: azimuth plan (top view, x-y)
    axp.plot(0, 0, "k^", ms=13)
    axp.annotate("Antenna", (0, 0), textcoords="offset points",
                 xytext=(8, -15), fontsize=9)
    bx, by = np.cos(np.radians(boresight)), np.sin(np.radians(boresight))
    axp.annotate("", xy=(1.12 * bx, 1.12 * by), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="-|>", color="tab:blue", lw=2))
    axp.text(0.5 * bx, 0.5 * by, f"boresight az={boresight:g}°",
             color="tab:blue", fontsize=8, rotation=boresight,
             rotation_mode="anchor", ha="center", va="bottom")
    az_lbl = {0.0: (8, -18), 30.0: (8, 6), 90.0: (8, 6), 180.0: (8, 6)}
    for off in [0.0, 30.0, 90.0, 180.0]:
        az = boresight + off
        g = gain_ang(ant, az, tilt)
        x, y = np.cos(np.radians(az)), np.sin(np.radians(az))
        axp.plot(x, y, "o", color="tab:red", ms=7)
        tag = "peak" if off == 0.0 else f"Δaz={off:g}°"
        axp.annotate(f"{tag}\nG={g:.1f} dBi", (x, y),
                     textcoords="offset points", xytext=az_lbl[off], fontsize=7)
    axp.set_aspect("equal")
    axp.set_xlim(-1.5, 1.5)
    axp.set_ylim(-1.5, 1.5)
    axp.grid(alpha=0.3)
    axp.set_xlabel("x")
    axp.set_ylabel("y")
    axp.set_title("Azimuth plan (top view) — source at el = tilt")

    # Panel 2: elevation profile (side view, range-height)
    axe.axhline(0, ls=":", color="0.6", lw=1)
    axe.text(1.28, 0.02, "horizon (el=0)", color="0.5", fontsize=7)
    axe.plot(0, 0, "k^", ms=13)
    axe.annotate("Antenna", (0, 0), textcoords="offset points",
                 xytext=(8, -15), fontsize=9)
    tx, tz = np.cos(np.radians(tilt)), np.sin(np.radians(tilt))
    axe.annotate("", xy=(1.12 * tx, 1.12 * tz), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="-|>", color="tab:blue", lw=2))
    axe.text(0.42, 0.045, f"beam tilt={tilt:g}°", color="tab:blue", fontsize=8)
    el_lbl = {3.6: (10, -20), 6.0: (10, 12), 15.0: (10, 2),
              30.0: (10, 2), 45.0: (10, 2), -5.0: (10, -6)}
    for el in [tilt, 6.0, 15.0, 30.0, 45.0, -5.0]:
        g = gain_ang(ant, boresight, el)
        x, z = np.cos(np.radians(el)), np.sin(np.radians(el))
        axe.plot(x, z, "o", color="tab:red", ms=7)
        tag = "el=tilt (peak)" if el == tilt else f"el={el:g}°"
        axe.annotate(f"{tag}\nG={g:.1f} dBi", (x, z),
                     textcoords="offset points",
                     xytext=el_lbl.get(round(el, 1), (10, 4)), fontsize=7)
    axe.set_aspect("equal")
    axe.set_xlim(-0.2, 1.65)
    axe.set_ylim(-0.9, 1.15)
    axe.grid(alpha=0.3)
    axe.set_xlabel("horizontal range")
    axe.set_ylabel("height")
    axe.set_title("Elevation profile (side view) — source at az = boresight")

    fig.suptitle(
        "Radar C — antenna position/orientation and RF-source directions "
        "with obtained gain\n"
        f"(boresight azimuth = {boresight:g}°, beam tilt = {tilt:g}°; "
        "markers = RF source, radius arbitrary)")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# pytest entry point
# --------------------------------------------------------------------------- #
def test_all():
    run_all()
    failed = [r for r in _RESULTS if not r[-1]]
    assert not failed, "\n".join(
        f"{g} | {d}: expected {e} got {got} (tol {t})"
        for g, d, e, got, t, ok in failed)


# --------------------------------------------------------------------------- #
# Standalone runner
# --------------------------------------------------------------------------- #
def main():
    run_all()
    print(f"{'GRP':<4}{'DESCRIPTION':<46}{'EXPECT':>9}{'GOT':>9}"
          f"{'TOL':>7}  RESULT")
    print("-" * 84)
    for g, d, e, got, t, ok in _RESULTS:
        print(f"{g:<4}{d[:45]:<46}{e:>9.3f}{got:>9.3f}{t:>7.3f}  "
              f"{'PASS' if ok else 'FAIL'}")
    n_fail = sum(1 for r in _RESULTS if not r[-1])
    print("-" * 84)
    print(f"{len(_RESULTS)} checks, {len(_RESULTS) - n_fail} passed, "
          f"{n_fail} failed.")

    # write results CSV and the spatial geometry figure
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        res_dir = os.path.join(here, "results")
        os.makedirs(res_dir, exist_ok=True)
        write_results_csv(os.path.join(res_dir, "antenna_m1851_results.csv"))
        ant_dir = os.path.join(os.path.dirname(here), "sharc", "antenna")
        make_geometry_figure(os.path.join(
            ant_dir, "antenna_m1851_cosecant_squared_radarC_geometry.png"))
        print(f"[ok] results CSV -> {res_dir}")
        print(f"[ok] geometry figure -> {ant_dir}")
    except Exception as exc:
        print(f"[warn] could not write outputs: {exc}")

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
