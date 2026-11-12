"""Sound feedback for simulator events, in the same cold, deep-space voice as the start-up chime.

Events (all synthesised here, cached as small WAV files in the temp folder):

  started   a simulation begins        two soft rising glass notes, "engaged"
  finished  a simulation completed     a short, resolved fanfare: rising D-minor figure, low swell, bloom
  failed    a simulation failed        a low, falling pair with a dull thud: serious, not shrill
  blocked   Run refused (errors)       two short low taps, "denied"
  warning   scenario has warnings      one mid ping
  saved     a file or figure was saved a tiny bright tick

One switch turns them all off (Settings > Preferences > Sound), independent of the start-up chime
(`startup_chime.enabled`). `play(name)` never raises and never blocks.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from core import startup_chime as base

RATE = base.RATE
SETTING_KEY = "sounds/effects"
EVENTS = ("started", "finished", "failed", "blocked", "warning", "saved")
LABELS = {
    "started": "Simulation started", "finished": "Simulation finished", "failed": "Simulation failed",
    "blocked": "Run blocked by errors", "warning": "Scenario has warnings", "saved": "File saved",
}


def enabled() -> bool:
    from PySide6.QtCore import QSettings
    value = QSettings("SHARC", "GUI").value(SETTING_KEY, True)
    return str(value).lower() in ("true", "1", "yes")


def set_enabled(on: bool) -> None:
    from PySide6.QtCore import QSettings
    QSettings("SHARC", "GUI").setValue(SETTING_KEY, bool(on))


def _stereo(length_s: float):
    n = int(RATE * length_s)
    return np.arange(n) / RATE, np.zeros(n), np.zeros(n)


def _finish(t, left, right, tail: float, wet: float = 0.6) -> np.ndarray:
    wl = base._reverb(left, (41.0, 53.0, 67.0, 79.0), tail)
    wr = base._reverb(right, (43.0, 59.0, 71.0, 83.0), tail)
    left, right = left + wet * wl, right + wet * wr
    n = len(t)
    fade = np.minimum(1.0, (t[-1] - t) / 0.25) * np.minimum(1.0, t / 0.004)
    out = np.stack([left * fade, right * fade], axis=1)
    return out * (0.65 / max(1e-9, float(np.max(np.abs(out))))) if n else out


def _started() -> np.ndarray:
    t, l, r = _stereo(0.9)
    for ts, f, pos in ((0.00, 440.00, -0.3), (0.13, 659.26, 0.3)):
        base._pan(base._bell(t, ts, f, 4.5, 0.5, index0=0.9), pos, l, r)
    return _finish(t, l, r, 0.6, 0.45)


def _finished() -> np.ndarray:
    t, l, r = _stereo(3.2)
    swell = base._swell(t, 0.0, 0.9, 1.1)
    for f in (73.42, 110.00, 146.83):                                    # low D-minor swell under the figure
        base._pan(0.05 * swell * base._stack(t, f, 8, 1.0, detune=0.001, bright_from=0.0), 0.0, l, r)
    figure = ((0.00, 587.33, -0.5), (0.16, 698.46, -0.2), (0.32, 880.00, 0.2), (0.48, 1174.66, 0.5))   # D5 F5 A5 D6
    for ts, f, pos in figure:
        base._pan(base._bell(t, ts, f, 1.5, 0.30, index0=1.0), pos, l, r)
    for i, f in enumerate((293.66, 440.00, 659.26, 880.00)):             # the chord blooms on the last note
        base._pan(base._bell(t, 0.62 + 0.01 * i, f, 1.1, 0.16), -0.5 + i * 0.33, l, r)
    base._pan(base._timpani(t, 0.62, 73.42, 0.45), 0.0, l, r)
    return _finish(t, l, r, 0.85, 0.9)


def _failed() -> np.ndarray:
    t, l, r = _stereo(1.5)
    for ts, f in ((0.00, 196.00), (0.22, 138.59)):                       # G3 then C#3: a falling tritone
        tt = np.clip(t - ts, 0.0, None)
        env = (t >= ts) * np.minimum(1.0, tt / 0.01) * np.exp(-2.6 * tt)
        tone = np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * 2 * f * tt) + 0.25 * np.sin(2 * np.pi * 3 * f * tt)
        base._pan(0.4 * env * tone, 0.0, l, r)
    base._pan(base._timpani(t, 0.22, 55.0, 0.7), 0.0, l, r)
    return _finish(t, l, r, 0.7, 0.6)


def _blocked() -> np.ndarray:
    t, l, r = _stereo(0.7)
    for ts in (0.00, 0.14):
        base._pan(base._timpani(t, ts, 110.0, 0.55), 0.0, l, r)
        base._pan(base._bell(t, ts, 330.0, 9.0, 0.18, index0=0.4), 0.0, l, r)
    return _finish(t, l, r, 0.5, 0.35)


def _warning() -> np.ndarray:
    t, l, r = _stereo(0.9)
    base._pan(base._bell(t, 0.0, 622.25, 3.6, 0.5, index0=0.5), 0.0, l, r)       # Eb5: neither bright nor dark
    return _finish(t, l, r, 0.6, 0.5)


def _saved() -> np.ndarray:
    t, l, r = _stereo(0.45)
    base._pan(base._bell(t, 0.0, 1567.98, 11.0, 0.5, index0=0.3), 0.15, l, r)
    return _finish(t, l, r, 0.4, 0.3)


_BUILDERS = {"started": _started, "finished": _finished, "failed": _failed,
             "blocked": _blocked, "warning": _warning, "saved": _saved}
VERSION = 1


def wav_path(name: str) -> Path:
    path = Path(tempfile.gettempdir()) / f"sharc_fx_{name}_v{VERSION}.wav"
    if not path.is_file() or path.stat().st_size < 500:
        base.write_wav(path, _BUILDERS[name]())
    return path


def prepare() -> None:
    """Render every effect in the background so the first event does not wait for synthesis."""
    import threading

    def work():
        for name in EVENTS:
            try:
                wav_path(name)
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=work, daemon=True).start()


def play(name: str, force: bool = False) -> bool:
    """Play an event sound if effects are enabled (or `force`). Returns True when playback started."""
    if name not in _BUILDERS or (not force and (base.silenced() or not enabled())):
        return False
    try:
        return base.play_file(wav_path(name), volume=0.6)
    except Exception:  # noqa: BLE001
        return False
