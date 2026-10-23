"""User-chosen look of the ground heat maps: palette, range, opacity, iso-lines and discrete bands.

The 3D view (`app.js`, `setHeatStyle`) draws with the style, the Qt legend copies the stops the view reports, and
`figure_export` uses the matching matplotlib colour map, so the screen, the legend and the exported figure agree.

The colours themselves live in one place, `HEAT_STOPS` in `web/cesium_preview/app.js`; this module only knows the
palette *names* (a test keeps the two lists equal) and the settings. "auto" is the default: viridis for levels and
magma for I/N, as before.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional

AUTO = "auto"
# palette name -> matplotlib colour map of the same name (None = no equivalent, falls back to viridis)
PALETTES: Dict[str, str] = {
    "auto": "", "viridis": "viridis", "magma": "magma", "inferno": "inferno", "plasma": "plasma",
    "cividis": "cividis", "turbo": "turbo", "jet": "jet", "coolwarm": "coolwarm", "gray": "gray",
}
PALETTE_LABELS = {"auto": "Auto (viridis, magma for I/N)", "viridis": "Viridis", "magma": "Magma", "inferno": "Inferno",
                  "plasma": "Plasma", "cividis": "Cividis (colour-blind safe)", "turbo": "Turbo", "jet": "Jet (rainbow)",
                  "coolwarm": "Cool-warm (diverging)", "gray": "Grayscale"}
SETTINGS_GROUP = "heat_style"
MAX_BANDS = 16


@dataclass
class HeatStyle:
    palette: str = AUTO
    reverse: bool = False
    auto_range: bool = True                 # False: use vmin / vmax for every map
    vmin: float = -120.0
    vmax: float = 0.0
    opacity: float = 0.85                   # 0.2 .. 1
    isolines: bool = True
    bands: int = 0                          # 0 = smooth; n >= 2 = n discrete colour bands
    threshold_on: bool = True               # protection contour on the I/N map
    threshold_db: float = -6.0

    def sanitized(self) -> "HeatStyle":
        """A copy with every field in its valid range (settings may hold anything)."""
        s = HeatStyle(**{f.name: getattr(self, f.name) for f in fields(self)})
        if s.palette not in PALETTES:
            s.palette = AUTO
        s.opacity = min(1.0, max(0.2, _num(s.opacity, 0.85)))
        s.bands = 0 if _num(s.bands, 0) < 2 else int(min(MAX_BANDS, _num(s.bands, 0)))
        s.vmin, s.vmax = _num(s.vmin, -120.0), _num(s.vmax, 0.0)
        if s.vmax <= s.vmin:
            s.vmax = s.vmin + 1.0
        s.threshold_db = _num(s.threshold_db, -6.0)
        s.reverse, s.auto_range, s.isolines, s.threshold_on = (
            _flag(s.reverse), _flag(s.auto_range), _flag(s.isolines), _flag(s.threshold_on))
        return s

    def to_js(self) -> str:
        """The JSON `setHeatStyle` takes: range and threshold are null when they are off."""
        s = self.sanitized()
        return json.dumps({
            "palette": s.palette, "reverse": s.reverse,
            "vmin": None if s.auto_range else s.vmin, "vmax": None if s.auto_range else s.vmax,
            "opacity": s.opacity, "isolines": s.isolines, "bands": s.bands,
            "threshold": s.threshold_db if s.threshold_on else None,
        })

    def mpl_cmap(self, quantity: str) -> str:
        """matplotlib colour map name for a map (`quantity` = 'psd', 'power' or 'inr')."""
        name = PALETTES.get(self.sanitized().palette, "") or ("magma" if quantity == "inr" else "viridis")
        return name + "_r" if self.reverse else name

    # ------------------------------------------------------------- settings
    def save(self, settings) -> None:
        for k, v in asdict(self.sanitized()).items():
            settings.setValue(f"{SETTINGS_GROUP}/{k}", v)

    @classmethod
    def load(cls, settings) -> "HeatStyle":
        base = cls()
        kwargs: Dict[str, Any] = {}
        for f in fields(cls):
            raw = settings.value(f"{SETTINGS_GROUP}/{f.name}", None)
            if raw is not None:
                kwargs[f.name] = raw
        return cls(**{**asdict(base), **kwargs}).sanitized()


def _num(v: Any, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _flag(v: Any) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)


def default_style() -> HeatStyle:
    return HeatStyle()


def _gui_settings():
    from PySide6.QtCore import QSettings          # resolved at call time: tests can swap it for an isolated store
    return QSettings("SHARC", "GUI")


def load_style(settings: Optional[Any] = None) -> HeatStyle:
    """The saved style (QSettings of the GUI by default)."""
    return HeatStyle.load(settings if settings is not None else _gui_settings())


def save_style(style: HeatStyle, settings: Optional[Any] = None) -> None:
    """Save the style (QSettings of the GUI by default)."""
    style.save(settings if settings is not None else _gui_settings())
