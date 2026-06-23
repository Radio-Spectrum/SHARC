# -*- coding: utf-8 -*-
"""Off-axis angle statistics between the FS ES antenna and each IMT BS site.

The ES azimuth tracks the IMT cluster centre (POINTING_AT_IMT_CENTER); each BS
sits off the centre, so the ES sees it at a non-zero off-axis angle. This script
reconstructs the geometry per snapshot (same StationFactory the simulator uses)
and reports the off-axis decomposed into azimuth (delta-phi) and elevation
(delta-theta), plus the total off-axis (cross-checked against
StationManager.get_off_axis_angle).
"""
import os
import io
import json
import base64

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sharc.parameters.parameters import Parameters
from sharc.topology.topology_factory import TopologyFactory
from sharc.station_factory import StationFactory
from sharc.support.sharc_geom import CoordinateSystem
from sharc.support.enumerations import StationType

CAMPAIGN_YAML = ("sharc/campaigns/FS_8000_MHz_stat_terrain_clutter/input/"
                 "parameters_FS_8000_MHz_stat_terrain_clutter.yaml")
N_SNAP = 200


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def _wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def main():
    out = _out()
    par = Parameters()
    par.set_file_name(CAMPAIGN_YAML)
    par.read_params()

    coord = CoordinateSystem()
    topo = TopologyFactory.createTopology(par, coord)

    dphi_all, dtheta_all, psi_all, psi_sm_all = [], [], [], []
    rng = np.random.RandomState(2024)
    for _ in range(N_SNAP):
        topo.calculate_coordinates(rng)
        bs = StationFactory.generate_imt_base_stations(
            par.imt, par.imt.bs.antenna.array, topo, rng)
        es = StationFactory.generate_single_earth_station(
            par.single_earth_station, rng, StationType.SINGLE_EARTH_STATION, topo)

        ex, ey, ez = float(es.x[0]), float(es.y[0]), float(es.z[0])
        az0 = float(es.azimuth[0])
        el0 = float(es.elevation[0])

        dx = bs.x - ex
        dy = bs.y - ey
        dz = bs.z - ez
        horiz = np.hypot(dx, dy)
        az_los = np.degrees(np.arctan2(dy, dx))
        el_los = np.degrees(np.arctan2(dz, horiz))

        dphi = _wrap180(az0 - az_los)          # azimuth off-axis
        dtheta = el0 - el_los                   # elevation off-axis

        # Total off-axis (spherical angle between boresight and LOS)
        cos_psi = (np.sin(np.radians(el0)) * np.sin(np.radians(el_los))
                   + np.cos(np.radians(el0)) * np.cos(np.radians(el_los))
                   * np.cos(np.radians(dphi)))
        psi = np.degrees(np.arccos(np.clip(cos_psi, -1.0, 1.0)))

        dphi_all.extend(dphi.tolist())
        dtheta_all.extend(dtheta.tolist())
        psi_all.extend(psi.tolist())
        # cross-check with the simulator's own method
        psi_sm_all.extend(np.ravel(es.get_off_axis_angle(bs)).tolist())

    dphi = np.array(dphi_all); dtheta = np.array(dtheta_all)
    psi = np.array(psi_all); psi_sm = np.array(psi_sm_all)

    def stats(a):
        return dict(min=float(np.min(a)), p5=float(np.percentile(a, 5)),
                    p50=float(np.median(a)), mean=float(np.mean(a)),
                    p95=float(np.percentile(a, 95)), max=float(np.max(a)),
                    std=float(np.std(a)))

    res = {"n_pairs": int(dphi.size), "n_snapshots": N_SNAP,
           "delta_phi_deg": stats(dphi), "delta_theta_deg": stats(dtheta),
           "off_axis_total_deg": stats(psi),
           "off_axis_total_deg_get_off_axis_angle": stats(psi_sm)}
    json.dump(res, open(os.path.join(out, "es_offaxis_stats.json"), "w"), indent=2)

    print(f"N = {dphi.size} pares ES-BS ({N_SNAP} snapshots)")
    for name, a in [("Delta-phi (azimute) ", dphi), ("Delta-theta (elev.) ", dtheta),
                    ("Off-axis total psi  ", psi), ("psi (get_off_axis)  ", psi_sm)]:
        print(f"  {name}: min={np.min(a):7.2f}  p50={np.median(a):7.2f}  "
              f"med|.|={np.median(np.abs(a)):6.2f}  p95|.|={np.percentile(np.abs(a),95):6.2f}  "
              f"max={np.max(a):7.2f} deg")

    # Plots
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.4))
    ax[0].hist(dphi, bins=60, color="#7fb3d5", edgecolor="white", lw=0.2)
    ax[0].set_title("Off-axis em azimute  Δφ (graus)")
    ax[0].set_xlabel("Δφ (deg)"); ax[0].set_ylabel("contagem"); ax[0].grid(alpha=0.3)
    ax[1].hist(dtheta, bins=60, color="#82c596", edgecolor="white", lw=0.2)
    ax[1].set_title("Off-axis em elevação  Δθ (graus)")
    ax[1].set_xlabel("Δθ (deg)"); ax[1].grid(alpha=0.3)
    ax[2].hist(psi, bins=60, color="#e8a87c", edgecolor="white", lw=0.2)
    ax[2].set_title("Off-axis total  ψ (graus)")
    ax[2].set_xlabel("ψ (deg)"); ax[2].grid(alpha=0.3)
    fig.suptitle("Off-axis ES (boresight no centro IMT) -> cada site de BS  "
                 f"(Campinas, ES a 5 km, {N_SNAP} snapshots)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(out, "es_offaxis.png"), dpi=120)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, "es_offaxis_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)
    print("figure ->", os.path.join(out, "es_offaxis.png"))


if __name__ == "__main__":
    main()
