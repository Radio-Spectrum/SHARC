"""
Spectrum & Link-Budget widget for the Preview tab.

Renders an interactive Plotly chart showing:
  - IMT transmit band (filled region)
  - Victim / interfered-with system band (contrasting overlay)
  - Spectral emission mask (step trace from SpectralMask* classes)
  - Spurious-emission floor (dashed reference line)
  - Guard-band regions (semi-transparent strips)
  - One-shot link-budget summary (EIRP → FSPL → Rx power → I/N)

All data is derived live from the GUI's SharcVar state — no simulation
run is needed.
"""

from __future__ import annotations

import math
import os
import tempfile
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

from PySide6.QtWidgets import QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt, QTimer, QUrl

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

# ── Mask imports (graceful) ──────────────────────────────────────────
try:
    from sharc.mask.spectral_mask_imt import SpectralMaskImt
    from sharc.mask.spectral_mask_3gpp import SpectralMask3Gpp
    from sharc.mask.spectral_mask_mss import SpectralMaskMSS
    from sharc.mask.spectral_mask_imt2030 import SpectralMaskImt2030
    from sharc.support.enumerations import StationType
    HAS_MASKS = True
except ImportError:
    HAS_MASKS = False


# =====================================================================
#  Colour palette — matches the SHARC GUI theme tokens
# =====================================================================
_COLORS = {
    "dark": {
        "bg":          "#0B0E14",
        "grid":        "#1B212E",
        "text":        "#9AA4B8",
        "text_strong": "#E8ECF4",
        "imt":         "#3AC8E8",
        "imt_fill":    "rgba(58,200,232,0.12)",
        "victim":      "#F5B841",
        "victim_fill": "rgba(245,184,65,0.10)",
        "mask":        "#A78BFA",
        "mask_fill":   "rgba(167,139,250,0.08)",
        "spurious":    "#F16A6A",
        "guard":       "rgba(245,184,65,0.08)",
        "guard_line":  "rgba(245,184,65,0.35)",
        "link_good":   "#3DDC97",
        "link_warn":   "#F5B841",
        "link_bad":    "#F16A6A",
        "card_bg":     "#141926",
        "card_border": "#242C3D",
    },
    "light": {
        "bg":          "#FFFFFF",
        "grid":        "#E3E8EF",
        "text":        "#525E72",
        "text_strong": "#171E2B",
        "imt":         "#0E6E9E",
        "imt_fill":    "rgba(14,110,158,0.10)",
        "victim":      "#B07C14",
        "victim_fill": "rgba(176,124,20,0.08)",
        "mask":        "#7C3AED",
        "mask_fill":   "rgba(124,58,237,0.06)",
        "spurious":    "#C24545",
        "guard":       "rgba(176,124,20,0.06)",
        "guard_line":  "rgba(176,124,20,0.30)",
        "link_good":   "#188A5E",
        "link_warn":   "#B07C14",
        "link_bad":    "#C24545",
        "card_bg":     "#F8FAFC",
        "card_border": "#D5DCE6",
    },
}

# System type → human-readable label for the victim
_SYSTEM_LABELS = {
    "SINGLE_SPACE_STATION": "Space Station",
    "SINGLE_EARTH_STATION": "Earth Station",
    "MSS_SS":   "MSS Space Station",
    "MSS_D2D":  "MSS D2D",
    "HAPS":     "HAPS",
    "FSS_SS":   "FSS Space Station",
    "FSS_ES":   "FSS Earth Station",
    "EESS_SS":  "EESS Space Station",
    "METSAT_SS":"MetSat Space Station",
    "RNS":      "RNS",
    "RAS":      "RAS",
}


# =====================================================================
#  Helper: build spectral-mask data arrays
# =====================================================================

def _build_mask_arrays(
    mask_type: str,
    freq_mhz: float,
    bw_mhz: float,
    p_tx_dbm: float,
    spurious: float,
    scenario: str = "OUTDOOR",
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Return (freq_array, mask_dbm_array) ready for step plotting.

    SpectralMask classes produce ``freq_lim`` (N breakpoints) and
    ``mask_dbm`` (N+1 levels: one per region between/outside
    breakpoints).  We expand these into paired x/y arrays suitable
    for a step trace.
    """
    if not HAS_MASKS:
        return None

    try:
        if mask_type == "IMT-2020":
            msk = SpectralMaskImt(
                StationType.IMT_BS, freq_mhz, bw_mhz, spurious, scenario)
        elif mask_type == "3GPP E-UTRA":
            msk = SpectralMask3Gpp(
                StationType.IMT_BS, freq_mhz, bw_mhz, spurious)
        elif mask_type == "MSS":
            if freq_mhz < 15000:
                # SpectralMaskMSS uses 4 kHz resolution below 15 GHz,
                # producing millions of breakpoints — too slow for a
                # live preview. Skip the mask trace; the band diagram
                # and link budget are still shown.
                return None
            msk = SpectralMaskMSS(freq_mhz, bw_mhz, spurious)
        elif mask_type == "IMT-2030":
            msk = SpectralMaskImt2030(
                StationType.IMT_BS, freq_mhz, bw_mhz, spurious,
                scenario=scenario)
        else:
            return None

        msk.set_mask(p_tx_dbm)
        if msk.mask_dbm is None or msk.freq_lim is None:
            return None

        fl = np.array(msk.freq_lim, dtype=float)
        mv = np.array(msk.mask_dbm, dtype=float)

        margin = max(bw_mhz * 0.8, 50)
        xs, ys = [fl[0] - margin], [mv[0]]
        for i, f in enumerate(fl):
            xs.append(f)
            ys.append(mv[i])      # level to the left of breakpoint
            xs.append(f)
            ys.append(mv[i + 1])  # level to the right of breakpoint
        xs.append(fl[-1] + margin)
        ys.append(mv[-1])

        xs_arr = np.array(xs)
        ys_arr = np.array(ys)

        # Downsample if too many points (MSS masks at low freq can
        # produce 100k+ breakpoints with a smooth curve). Uniform
        # decimation is enough — the curve is monotonic between the
        # band edges and the spurious boundary, so we won't miss
        # any sharp transitions.
        MAX_PLOT_PTS = 2000
        if len(xs_arr) > MAX_PLOT_PTS:
            step = len(xs_arr) / MAX_PLOT_PTS
            keep = np.round(np.arange(0, len(xs_arr), step)).astype(int)
            keep = np.clip(keep, 0, len(xs_arr) - 1)
            keep = np.union1d(keep, [0, len(xs_arr) - 1])
            xs_arr = xs_arr[keep]
            ys_arr = ys_arr[keep]

        return xs_arr, ys_arr
    except Exception:
        return None


# =====================================================================
#  Helper: one-shot link budget
# =====================================================================

def _link_budget(
    p_tx_dbm: float,
    g_tx_dbi: float,
    freq_mhz: float,
    dist_km: float,
    g_rx_dbi: float,
    rx_noise_temp_k: float,
    rx_bw_mhz: float,
) -> Dict[str, float]:
    """Compute a simplified free-space link budget."""
    eirp = p_tx_dbm + g_tx_dbi

    if dist_km > 0 and freq_mhz > 0:
        fspl = (20 * math.log10(dist_km)
                + 20 * math.log10(freq_mhz)
                + 32.45)
    else:
        fspl = 0.0

    rx_power = eirp - fspl + g_rx_dbi

    k_boltzmann = -228.6  # dBW/K/Hz
    noise_power = (k_boltzmann
                   + 10 * math.log10(max(rx_noise_temp_k, 1))
                   + 10 * math.log10(max(rx_bw_mhz, 0.001) * 1e6)
                   + 30)  # +30 → dBm
    i_over_n = rx_power - noise_power

    return {
        "eirp_dbm": round(eirp, 2),
        "fspl_db": round(fspl, 2),
        "rx_power_dbm": round(rx_power, 2),
        "noise_dbm": round(noise_power, 2),
        "i_over_n_db": round(i_over_n, 2),
    }


# =====================================================================
#  Main widget
# =====================================================================

class SpectrumWidget(QWidget):
    """Plotly-based spectral-mask and link-budget visualisation."""

    _DEBOUNCE_MS = 350

    def __init__(self, app: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.app = app
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._do_render)

        self._tmp_html: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_WEBENGINE and HAS_PLOTLY:
            self._web = QWebEngineView()
            self._web.setContextMenuPolicy(Qt.NoContextMenu)
            layout.addWidget(self._web)
        else:
            missing = []
            if not HAS_PLOTLY:
                missing.append("plotly")
            if not HAS_WEBENGINE:
                missing.append("PySide6-WebEngine")
            lbl = QLabel(
                f"Spectrum view requires: {', '.join(missing)}")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setObjectName("StatusMsg")
            layout.addWidget(lbl)
            self._web = None

        self._connect_signals()
        self.schedule_render()

    # ── Signal wiring ──────────────────────────────────────────────

    def _connect_signals(self):
        """Listen to every SharcVar that affects the spectrum view.

        IMT and Victim tabs own their own state managers with separate
        SharcVar instances.  We must watch those *in addition* to the
        AppState-level vars (which cover General and Earth-Station tabs).
        """
        # AppState-level vars (General tab + Earth Station tab)
        app_watched = [
            "var_system", "var_imt_link", "var_adj", "var_coch",
            "se_frequency", "se_bandwidth", "se_noise_temperature",
            "se_ant_gain",
        ]
        for name in app_watched:
            var = getattr(self.app, name, None)
            if var is not None and hasattr(var, "value_changed"):
                var.value_changed.connect(self.schedule_render)

        # IMT tab state manager vars
        imt_watched = [
            "imt_freq", "imt_bw", "imt_spec_mask", "imt_spurious",
            "imt_guard_ratio", "bs_power",
        ]
        try:
            imt_vars = self.app.tab_imt.state.vars
            for name in imt_watched:
                var = imt_vars.get(name)
                if var is not None and hasattr(var, "value_changed"):
                    var.value_changed.connect(self.schedule_render)
        except AttributeError:
            pass

        # Victim tab state manager vars
        victim_watched = [
            "v_freq", "v_bw", "v_ant_gain", "v_tnoise", "v_alt",
        ]
        try:
            victim_vars = self.app.tab_victim.state.vars
            for name in victim_watched:
                var = victim_vars.get(name)
                if var is not None and hasattr(var, "value_changed"):
                    var.value_changed.connect(self.schedule_render)
        except AttributeError:
            pass

    def schedule_render(self, _=None):
        self._debounce_timer.start(self._DEBOUNCE_MS)

    # ── Data extraction from GUI state ─────────────────────────────

    def _get_tab_var(self, tab_name: str, var_name: str, default: Any = None) -> Any:
        """Read a var from a tab's state manager, falling back to AppState."""
        try:
            tab = getattr(self.app, f"tab_{tab_name}")
            var = tab.state.get(var_name)
            return var.get()
        except (AttributeError, KeyError, TypeError):
            pass
        var = getattr(self.app, var_name, None)
        if var is not None and hasattr(var, "get"):
            return var.get()
        return default

    def _read_state(self) -> Dict[str, Any]:
        """Pull all needed values from the correct state sources."""
        def _f(tab, name, default=0.0):
            raw = self._get_tab_var(tab, name, default)
            try:
                return float(raw)
            except (ValueError, TypeError):
                return default

        def _s(tab, name, default=""):
            val = self._get_tab_var(tab, name, default)
            return val if val is not None else default

        system = _s("general", "var_system", "SINGLE_SPACE_STATION")
        imt_link = _s("general", "var_imt_link", "DOWNLINK")

        imt_freq = _f("imt", "imt_freq", 8150)
        imt_bw = max(_f("imt", "imt_bw", 100), 0.01)
        mask_type = _s("imt", "imt_spec_mask", "IMT-2020")
        spurious = _f("imt", "imt_spurious", -13)
        guard_ratio = _f("imt", "imt_guard_ratio", 0.1)
        bs_power = _f("imt", "bs_power", 22)

        is_earth_station = "EARTH" in system.upper()

        if is_earth_station:
            victim_freq = _f("station", "se_frequency", 3800)
            victim_bw = max(_f("station", "se_bandwidth", 100), 0.01)
            victim_gain = _f("station", "se_ant_gain", 30)
            victim_noise_temp = max(_f("station", "se_noise_temperature", 290), 1)
        else:
            victim_freq = _f("victim", "v_freq", 8150)
            victim_bw = max(_f("victim", "v_bw", 40), 0.01)
            victim_gain = _f("victim", "v_ant_gain", 30)
            victim_noise_temp = max(_f("victim", "v_tnoise", 500), 1)

        victim_label = _SYSTEM_LABELS.get(system, system.replace("_", " ").title())

        if is_earth_station:
            dist_km = 1.0
        else:
            alt_m = _f("victim", "v_alt", 35786000)
            dist_km = max(alt_m / 1000.0, 0.001)

        return {
            "system": system,
            "imt_link": imt_link,
            "imt_freq": imt_freq,
            "imt_bw": imt_bw,
            "mask_type": mask_type,
            "spurious": spurious,
            "guard_ratio": guard_ratio,
            "bs_power": bs_power,
            "bs_gain": 0.0,
            "victim_freq": victim_freq,
            "victim_bw": victim_bw,
            "victim_gain": victim_gain,
            "victim_noise_temp": victim_noise_temp,
            "victim_label": victim_label,
            "dist_km": dist_km,
            "is_earth_station": is_earth_station,
        }

    # ── Plotly figure construction ─────────────────────────────────

    def _build_figure(self, s: Dict[str, Any], theme: str = "dark") -> go.Figure:
        c = _COLORS[theme]

        imt_lo = s["imt_freq"] - s["imt_bw"] / 2
        imt_hi = s["imt_freq"] + s["imt_bw"] / 2
        victim_lo = s["victim_freq"] - s["victim_bw"] / 2
        victim_hi = s["victim_freq"] + s["victim_bw"] / 2
        guard_w = s["imt_bw"] * s["guard_ratio"]

        p_tx_per_mhz = s["bs_power"] - 10 * math.log10(s["imt_bw"])

        # Frequency range: encompass both bands with margin
        all_edges = [imt_lo - guard_w, imt_hi + guard_w, victim_lo, victim_hi]
        f_min = min(all_edges) - max(s["imt_bw"] * 0.5, 50)
        f_max = max(all_edges) + max(s["imt_bw"] * 0.5, 50)

        y_min = s["spurious"] - 15
        y_max = p_tx_per_mhz + 12

        fig = go.Figure()

        # ── Guard bands ──
        for g_lo, g_hi, label in [
            (imt_lo - guard_w, imt_lo, "Guard Band"),
            (imt_hi, imt_hi + guard_w, None),
        ]:
            fig.add_vrect(
                x0=g_lo, x1=g_hi,
                fillcolor=c["guard"], line=dict(color=c["guard_line"], width=1),
                layer="below",
                annotation_text=label,
                annotation_position="top left" if label else None,
                annotation_font=dict(size=9, color=c["text"]),
            )

        # ── IMT band (filled area) ──
        fig.add_trace(go.Scatter(
            x=[imt_lo, imt_lo, imt_hi, imt_hi, imt_lo],
            y=[y_min, p_tx_per_mhz, p_tx_per_mhz, y_min, y_min],
            fill="toself",
            fillcolor=c["imt_fill"],
            line=dict(color=c["imt"], width=2),
            name=f"IMT Band ({s['imt_bw']:.0f} MHz)",
            hovertemplate=(
                "IMT System<br>"
                "Freq: %{x:.1f} MHz<br>"
                "PSD: %{y:.1f} dBm/MHz<extra></extra>"
            ),
        ))

        # IMT center annotation
        fig.add_annotation(
            x=s["imt_freq"], y=p_tx_per_mhz,
            text=(
                f"<b>IMT {s['imt_link']}</b><br>"
                f"{s['imt_freq']:.0f} MHz · {s['imt_bw']:.0f} MHz BW<br>"
                f"P<sub>tx</sub> = {s['bs_power']:.1f} dBm "
                f"({p_tx_per_mhz:.1f} dBm/MHz)"
            ),
            showarrow=True, arrowhead=0, arrowcolor=c["imt"],
            ax=0, ay=-55,
            font=dict(size=11, color=c["imt"]),
            bordercolor=c["imt"], borderwidth=1, borderpad=5,
            bgcolor=c["bg"], opacity=0.95,
        )

        # ── Victim band ──
        fig.add_trace(go.Scatter(
            x=[victim_lo, victim_lo, victim_hi, victim_hi, victim_lo],
            y=[y_min, y_max, y_max, y_min, y_min],
            fill="toself",
            fillcolor=c["victim_fill"],
            line=dict(color=c["victim"], width=2, dash="dot"),
            name=f"{s['victim_label']} ({s['victim_bw']:.0f} MHz)",
            hovertemplate=(
                f"{s['victim_label']}<br>"
                "Freq: %{x:.1f} MHz<extra></extra>"
            ),
        ))

        fig.add_annotation(
            x=s["victim_freq"], y=y_max - 2,
            text=(
                f"<b>{s['victim_label']}</b><br>"
                f"{s['victim_freq']:.0f} MHz · {s['victim_bw']:.0f} MHz BW"
            ),
            showarrow=False,
            font=dict(size=11, color=c["victim"]),
            bgcolor=c["bg"], opacity=0.92,
            bordercolor=c["victim"], borderwidth=1, borderpad=4,
        )

        # ── Spectral mask ──
        mask_data = _build_mask_arrays(
            s["mask_type"], s["imt_freq"], s["imt_bw"],
            s["bs_power"], s["spurious"],
        )
        if mask_data is not None:
            mf, mv = mask_data
            vis = (mf >= f_min - 10) & (mf <= f_max + 10)
            mf_vis = mf[vis]
            mv_vis = mv[vis]

            if len(mf_vis) > 0:
                fig.add_trace(go.Scatter(
                    x=np.concatenate([[mf_vis[0]], mf_vis, [mf_vis[-1]]]),
                    y=np.concatenate([[y_min], mv_vis, [y_min]]),
                    fill="toself",
                    fillcolor=c["mask_fill"],
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                ))

                fig.add_trace(go.Scatter(
                    x=mf_vis, y=mv_vis,
                    mode="lines",
                    line=dict(color=c["mask"], width=2),
                    name=f"Mask ({s['mask_type']})",
                    hovertemplate=(
                        "Spectral Mask<br>"
                        "Freq: %{x:.1f} MHz<br>"
                        "Limit: %{y:.1f} dBm/MHz<extra></extra>"
                    ),
                ))

        # ── Spurious floor ──
        fig.add_hline(
            y=s["spurious"],
            line=dict(color=c["spurious"], width=1.5, dash="dash"),
            annotation_text=f"Spurious floor: {s['spurious']:.0f} dBm/MHz",
            annotation_position="bottom right",
            annotation_font=dict(size=10, color=c["spurious"]),
        )

        # ── Frequency separation annotation ──
        freq_sep = abs(s["imt_freq"] - s["victim_freq"])
        band_overlap = not (imt_hi <= victim_lo or victim_hi <= imt_lo)
        sep_color = c["link_bad"] if band_overlap else c["link_good"]
        sep_text = "CO-CHANNEL" if band_overlap else f"Δf = {freq_sep:.0f} MHz"

        fig.add_annotation(
            x=(s["imt_freq"] + s["victim_freq"]) / 2,
            y=y_min + 5,
            text=f"<b>{sep_text}</b>",
            showarrow=False,
            font=dict(size=12, color=sep_color),
            bgcolor=c["bg"], borderpad=3,
        )

        # ── Link budget summary ──
        lb = _link_budget(
            p_tx_dbm=s["bs_power"],
            g_tx_dbi=s["bs_gain"],
            freq_mhz=s["imt_freq"],
            dist_km=s["dist_km"],
            g_rx_dbi=s["victim_gain"],
            rx_noise_temp_k=s["victim_noise_temp"],
            rx_bw_mhz=s["victim_bw"],
        )
        in_color = (c["link_bad"] if lb["i_over_n_db"] > -6
                    else c["link_warn"] if lb["i_over_n_db"] > -10
                    else c["link_good"])

        lb_text = (
            f"EIRP = {lb['eirp_dbm']:.1f} dBm  │  "
            f"FSPL = {lb['fspl_db']:.1f} dB  │  "
            f"P<sub>rx</sub> = {lb['rx_power_dbm']:.1f} dBm  │  "
            f"N = {lb['noise_dbm']:.1f} dBm  │  "
            f"<b>I/N = {lb['i_over_n_db']:.1f} dB</b>"
        )

        # ── Layout ──
        fig.update_layout(
            template=None,
            paper_bgcolor=c["bg"],
            plot_bgcolor=c["bg"],
            font=dict(
                family="Inter, Segoe UI, Roboto, sans-serif",
                color=c["text"],
            ),
            margin=dict(l=65, r=20, t=50, b=100),
            xaxis=dict(
                title=dict(text="Frequency (MHz)", font=dict(size=12)),
                range=[f_min, f_max],
                gridcolor=c["grid"],
                gridwidth=1,
                zeroline=False,
                showline=True,
                linecolor=c["grid"],
                tickfont=dict(size=10),
            ),
            yaxis=dict(
                title=dict(
                    text="Power Spectral Density (dBm/MHz)",
                    font=dict(size=12),
                ),
                range=[y_min, y_max],
                gridcolor=c["grid"],
                gridwidth=1,
                zeroline=False,
                showline=True,
                linecolor=c["grid"],
                tickfont=dict(size=10),
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="center", x=0.5,
                font=dict(size=11),
                bgcolor="rgba(0,0,0,0)",
            ),
            hoverlabel=dict(
                bgcolor=c["card_bg"],
                bordercolor=c["card_border"],
                font_size=12,
                font_color=c["text_strong"],
            ),
            annotations=fig.layout.annotations + (
                dict(
                    x=0.5, y=-0.17,
                    xref="paper", yref="paper",
                    text=lb_text,
                    showarrow=False,
                    font=dict(size=12, color=c["text_strong"]),
                    bgcolor=c["card_bg"],
                    bordercolor=in_color,
                    borderwidth=2,
                    borderpad=8,
                ),
                dict(
                    x=0.5, y=-0.26,
                    xref="paper", yref="paper",
                    text=(
                        f"<span style='color:{in_color}'>●</span> "
                        f"I/N = {lb['i_over_n_db']:.1f} dB  —  "
                        + ("⚠ Potential interference"
                           if lb["i_over_n_db"] > -10
                           else "✓ Below typical protection criteria")
                    ),
                    showarrow=False,
                    font=dict(size=11, color=c["text"]),
                ),
            ),
        )

        return fig

    # ── Render pipeline ────────────────────────────────────────────

    def _do_render(self):
        if self._web is None:
            return
        try:
            state = self._read_state()
            fig = self._build_figure(state, theme="dark")

            html = fig.to_html(
                include_plotlyjs=True,
                full_html=True,
                config={
                    "displayModeBar": True,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                    "displaylogo": False,
                    "responsive": True,
                },
            )

            # Write to temp file and load via URL — avoids
            # QWebEngineView.setHtml() 2 MB limit and works offline
            # (plotly.js is inlined).
            if self._tmp_html is None:
                fd, path = tempfile.mkstemp(
                    suffix=".html", prefix="sharc_spectrum_")
                os.close(fd)
                self._tmp_html = path

            with open(self._tmp_html, "w", encoding="utf-8") as f:
                f.write(html)

            self._web.setUrl(QUrl.fromLocalFile(self._tmp_html))

        except Exception as e:
            if self._web is not None:
                self._web.setHtml(
                    f"<html><body style='background:#0B0E14;color:#F16A6A;"
                    f"font-family:monospace;padding:2em'>"
                    f"<h3>Spectrum render error</h3><pre>{e}</pre>"
                    f"</body></html>"
                )

    def _cleanup_tmp(self):
        if self._tmp_html and os.path.exists(self._tmp_html):
            try:
                os.unlink(self._tmp_html)
            except OSError:
                pass

    def closeEvent(self, event):
        self._cleanup_tmp()
        super().closeEvent(event)
