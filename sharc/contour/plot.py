"""Figure of a contour campaign: the protection contour of each off-axis angle around the station, in km (East, North).

Matplotlib's object API (no pyplot): the same figure is shown in the GUI and saved for papers (PNG / PDF / SVG).
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from matplotlib.figure import Figure

COLORS = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]
M_PER_DEG = 111_320.0


def contour_figure(rows: Sequence[dict], station_name: str = "Station", width_in: float = 6.0, dpi: int = 100,
                   fig: Figure = None) -> Figure:
    """Contours (one closed curve per off-axis angle) and the end of the rays, on equal km axes.

    Draws into `fig` when given (a GUI canvas keeps its own size), else into a new figure."""
    import math
    if fig is None:
        fig = Figure(figsize=(width_in, width_in * 0.95), dpi=dpi, facecolor="white", layout="constrained")
    else:
        fig.clear()
        fig.set_facecolor("white")
        fig.set_layout_engine("constrained")
    ax = fig.add_subplot(111)
    if not rows:
        ax.text(0.5, 0.5, "No results yet", ha="center", va="center", transform=ax.transAxes, color="0.4")
        ax.set_axis_off()
        return fig
    for i, off in enumerate(sorted({r["off_axis_deg"] for r in rows})):
        sel = sorted((r for r in rows if r["off_axis_deg"] == off), key=lambda r: r["az_enu_deg"])
        d = np.array([r["contour_m"] for r in sel], float) / 1000.0
        az = np.radians([r["az_enu_deg"] for r in sel])
        x, y = d * np.cos(az), d * np.sin(az)                    # ENU azimuth: 0 = east, counter-clockwise
        ok = np.isfinite(d)
        if ok.sum() >= 2:
            ax.plot(np.append(x[ok], x[ok][0]), np.append(y[ok], y[ok][0]), color=COLORS[i % len(COLORS)], lw=1.4,
                    label=f"BS off-axis {off:g}°")
        open_ended = np.array([r["marker"] == "not_met_at_end" for r in sel])
        if open_ended.any():                                     # the criterion is still violated where the ray ends
            ax.scatter(x[open_ended], y[open_ended], s=14, marker="x", color=COLORS[i % len(COLORS)])
    ends = sorted({(r["az_enu_deg"], r["ray_end_m"]) for r in rows})
    ex = [e[1] / 1000.0 * math.cos(math.radians(e[0])) for e in ends]
    ey = [e[1] / 1000.0 * math.sin(math.radians(e[0])) for e in ends]
    ax.plot(ex, ey, color="0.6", lw=0.8, ls=":", label="End of the rays (sea, boundary or terrain edge)")
    ax.plot([0], [0], marker="^", color="black", ms=9, ls="", label=station_name)
    ax.set_aspect("equal")
    ax.set_xlabel("East [km]")
    ax.set_ylabel("North [km]")
    ax.set_title("Protection contour", fontsize=10, loc="left")
    ax.grid(True, lw=0.3, alpha=0.5)
    fig.legend(*ax.get_legend_handles_labels(), loc="outside lower center", fontsize=7, ncol=1, frameon=False)
    return fig
