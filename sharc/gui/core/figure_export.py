"""Publication-quality figures from the preview scene: ground heat maps and the PSD / CDF plots.

Works on the scene dict that the preview already builds (`heat` from `core.heatmap`, `plots` from
`core.preview_extras`), so it needs neither the engine nor Qt. Figures use matplotlib's object API (no pyplot,
so no global state and no GUI backend), a perceptually uniform colour map that survives grayscale printing and
colour-blindness, and are saved as PNG (raster, 300 dpi) plus PDF/SVG (vector) for papers and ITU-R documents.
"""
from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
from matplotlib.figure import Figure

SINGLE_COLUMN_IN = 3.5      # IEEE / most journals, one column
DOUBLE_COLUMN_IN = 7.16     # full page width
M_PER_DEG = 111_320.0
_STYLE = {"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
          "legend.fontsize": 7, "axes.linewidth": 0.6, "xtick.direction": "in", "ytick.direction": "in",
          "pdf.fonttype": 42, "svg.fonttype": "none"}                   # editable text in PDF/SVG


def _find(scene: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    """`key` at the top level of the scene or inside its `imt` block (composite scenes)."""
    for holder in (scene, scene.get("imt") or {}):
        if isinstance(holder, dict) and holder.get(key):
            return holder[key]
    return None


def _nice_length_km(span_km: float) -> float:
    """A round scale-bar length (1, 2 or 5 x 10^k km) of about a fifth of `span_km`."""
    target = span_km / 5.0
    mag = 10.0 ** math.floor(math.log10(max(target, 1e-6)))
    return min((m * mag for m in (1, 2, 5, 10)), key=lambda v: abs(v - target))


def _figure(width_in: float, height_in: float) -> Figure:
    return Figure(figsize=(width_in, height_in), dpi=300, facecolor="white", layout="constrained")


class _rc:
    """Apply the figure style only while building a figure (matplotlib's rc is global)."""

    def __enter__(self):
        import matplotlib as mpl
        self._ctx = mpl.rc_context(_STYLE)
        return self._ctx.__enter__()

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)


def heatmap_figure(heat: Dict[str, Any], quantity: str, width_in: float = SINGLE_COLUMN_IN, style=None) -> Figure:
    """One ground map (`psd`, `power` or `inr`) with km axes, colour bar, contours and a scale bar.

    `style` (core.heat_style.HeatStyle) sets the palette, range, bands, iso-lines and I/N contour like the 3D view."""
    from core.heat_style import HeatStyle
    st = (style or HeatStyle()).sanitized()
    m = heat["maps"][quantity]
    vmin, vmax = (m["vmin"], m["vmax"]) if st.auto_range else (st.vmin, st.vmax)
    n = int(heat["n"])
    z = np.asarray(m["values"], dtype=float).reshape(n, n)                 # row 0 = south
    lat0 = 0.5 * (heat["south"] + heat["north"])
    half_x = 0.5 * (heat["east"] - heat["west"]) * M_PER_DEG * math.cos(math.radians(lat0)) / 1000.0
    half_y = 0.5 * (heat["north"] - heat["south"]) * M_PER_DEG / 1000.0

    with _rc():
        fig = _figure(width_in, width_in * 0.92)
        ax = fig.add_subplot(111)
        cmap, norm = _colormap(st, quantity, vmin, vmax)
        im = ax.imshow(z, origin="lower", extent=(-half_x, half_x, -half_y, half_y), cmap=cmap, norm=norm,
                       interpolation="nearest" if st.bands >= 2 else "bilinear")
        xs, ys = np.linspace(-half_x, half_x, n), np.linspace(-half_y, half_y, n)
        if st.isolines:
            levels = np.linspace(vmin, vmax, st.bands + 1)[1:-1] if st.bands >= 2 else np.linspace(vmin, vmax, 7)[1:-1]
            cs = ax.contour(xs, ys, z, levels=levels, colors="white", linewidths=0.4, alpha=0.7)
            ax.clabel(cs, fmt="%.0f", fontsize=5.5, inline=True)
        if quantity == "inr" and st.threshold_on and vmin < st.threshold_db < vmax:
            ax.contour(xs, ys, z, levels=[st.threshold_db], colors="#00e5ff", linewidths=1.0, linestyles="--")
            ax.plot([], [], color="#00e5ff", ls="--", lw=1.0, label=f"I/N = {st.threshold_db:g} dB")
        bs = np.asarray(heat.get("bs_km") or [], dtype=float).reshape(-1, 2)
        if len(bs):
            ax.scatter(bs[:, 0], bs[:, 1], marker="^", s=14, c="white", edgecolors="black", linewidths=0.5,
                       label=f"Base stations ({len(bs)})", zorder=5)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(loc="upper right", framealpha=0.85, fancybox=False, edgecolor="0.6")
        cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.02)
        cb.set_label(f"{m['title']} [{m['unit']}]")
        cb.outline.set_linewidth(0.5)
        ax.set_xlabel("East [km]")
        ax.set_ylabel("North [km]")
        ax.set_aspect("equal")
        ax.set_title(f"{m['title']}  ({heat['freq_mhz']:g} MHz, {heat['bandwidth_mhz']:g} MHz BW)", loc="left")
        length = _nice_length_km(2 * half_x)
        x0, y0 = -half_x * 0.92, -half_y * 0.90
        ax.plot([x0, x0 + length], [y0, y0], color="white", lw=2.2, solid_capstyle="butt")
        ax.text(x0 + length / 2, y0 + half_y * 0.04, f"{length:g} km", color="white", ha="center", va="bottom", fontsize=7,
                bbox={"boxstyle": "round,pad=0.15", "fc": "black", "ec": "none", "alpha": 0.45})
    return fig


def _colormap(style, quantity: str, vmin: float, vmax: float):
    """(colormap, norm) of a map: the user's palette (reversed when asked), as discrete bands when `bands` >= 2."""
    import matplotlib as mpl
    from matplotlib.colors import BoundaryNorm, Normalize
    cmap = mpl.colormaps[style.mpl_cmap(quantity)]
    if style.bands >= 2:
        return cmap.resampled(style.bands), BoundaryNorm(np.linspace(vmin, vmax, style.bands + 1), style.bands)
    return cmap, Normalize(vmin=vmin, vmax=vmax)


def plots_figure(plots: Dict[str, Any], width_in: float = DOUBLE_COLUMN_IN, style=None) -> Figure:
    """IMT PSD against the victim band (left) and CDF of I/N over the ground map (right), with the I/N line of the style."""
    from core.heat_style import HeatStyle
    st = (style or HeatStyle()).sanitized()
    with _rc():
        fig = _figure(width_in, width_in * 0.36)
        ax_psd, ax_cdf = fig.subplots(1, 2)
        imt, victim = plots["imt"], plots.get("victim")
        f, bw, psd = imt["freq_mhz"], imt["bandwidth_mhz"], imt["psd_dbm_mhz"]
        ax_psd.fill_between([f - bw / 2, f + bw / 2], -200, psd, color="#3b6fb6", alpha=0.85, label="IMT BS PSD")
        lo, hi = f - bw * 1.2, f + bw * 1.2
        if victim:
            vf, vb = victim["freq_mhz"], victim["bandwidth_mhz"]
            ax_psd.axvspan(vf - vb / 2, vf + vb / 2, color="#d9822b", alpha=0.35, label=f"{victim['name']} band")
            lo, hi = min(lo, vf - vb * 1.2), max(hi, vf + vb * 1.2)
        ax_psd.set_xlim(lo, hi)
        ax_psd.set_ylim(psd - 30, psd + 22)
        ax_psd.set_xlabel("Frequency [MHz]")
        ax_psd.set_ylabel("PSD [dBm/MHz]")
        ax_psd.set_title("Spectrum", loc="left")
        ax_psd.legend(loc="upper left", fancybox=False, edgecolor="0.6", framealpha=0.9)
        ax_psd.grid(True, lw=0.3, alpha=0.5)

        cdf = plots.get("cdf")
        if cdf:
            ax_cdf.step(cdf["x"], cdf["p"], where="post", color="#3b6fb6", lw=1.3)
            if st.threshold_on:
                ax_cdf.axvline(st.threshold_db, color="#c0392b", ls="--", lw=0.9, label=f"I/N = {st.threshold_db:g} dB")
            ax_cdf.set_xlabel(f"I/N [{cdf.get('unit', 'dB')}]")
            ax_cdf.set_ylabel("CDF")
            ax_cdf.set_ylim(0, 1.02)
            ax_cdf.set_title("I/N over the ground map", loc="left")
            if st.threshold_on:
                ax_cdf.legend(loc="lower right", fancybox=False, edgecolor="0.6")
            ax_cdf.grid(True, lw=0.3, alpha=0.5)
        else:
            ax_cdf.axis("off")
    return fig


def export_figures(scene: Dict[str, Any], folder: str, dpi: int = 300,
                   formats: Iterable[str] = ("png", "pdf", "svg"), prefix: str = "sharc", style=None) -> List[str]:
    """Save every available figure of `scene` into `folder`; returns the written paths.

    `style` (core.heat_style.HeatStyle) is the heat-map look chosen in the View panel."""
    os.makedirs(folder, exist_ok=True)
    figures: Dict[str, Figure] = {}
    heat = _find(scene, "heat")
    if heat:
        for q in heat["maps"]:
            figures[f"heatmap_{q}"] = heatmap_figure(heat, q, style=style)
    plots = _find(scene, "plots")
    if plots:
        figures["plots"] = plots_figure(plots, style=style)
    paths: List[str] = []
    for name, fig in figures.items():
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{prefix}_{name}")
        for ext in formats:
            path = os.path.join(folder, f"{stem}.{ext}")
            fig.savefig(path, dpi=dpi, facecolor="white", bbox_inches="tight", pad_inches=0.05)
            paths.append(path)
    return paths
