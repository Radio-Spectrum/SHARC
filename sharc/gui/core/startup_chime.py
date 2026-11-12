"""Start-up chime: a dark, dramatic, interstellar swell played when the splash finishes loading.

Built to sit with the interface (graphite surfaces, steel-blue accent, orbital splash) and to feel
like waking something enormous in deep space. About 8 s of a synthesised "orchestra":

  build (0 to 4.3 s)  a sub-bass drone with a slow beat, a string cluster in tension (D, Eb, A) that
                      swells, low horns and a minor choir rising, sparse sonar pings far left and
                      right, a slow heartbeat of timpani that accelerates, a dark reverse cymbal
  impact (4.3 s)      a deep boom with a noise hit; the tension resolves into one wide D-minor(add9)
                      chord struck by horns, strings, choir, bells and low timpani at once
  after (4.3 to 8 s)  star glints twinkling far apart in the dark, and a long, cavernous reverb tail

Everything is generated here (numpy + scipy), so no audio asset has to ship. It is written once to
the temp folder (in the background while the splash loads) and played without blocking. On Windows
it uses `winsound`; elsewhere it falls back to QtMultimedia when present. It can be turned off in
Settings > Preferences > Sound ("Play a chime when SHARC finishes loading"), separately from the
sound effects for simulator events (see `sound_fx.py`).
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, lfilter

RATE = 44100
LENGTH_S = 8.4
D1 = 36.708                                                # D1 in Hz (sub-bass root)
HIT = 4.3                                                  # time of the impact [s]
CLUSTER = (293.66, 311.13, 440.00)                         # D4 Eb4 A4: the tension that resolves at the hit
MINOR_LOW = (73.42, 110.00, 146.83, 174.61)                # D2 A2 D3 F3
MINOR_MID = (220.00, 293.66, 349.23, 440.00, 659.26)       # A3 D4 F4 A4 E5 (the add9)
CHORD_BELLS = (293.66, 440.00, 659.26, 698.46, 880.00, 1174.66)   # D4 A4 E5 F5 A5 D6
PINGS = ((0.9, 880.00, -0.9), (1.9, 1318.51, 0.9), (3.0, 659.26, -0.6))          # (time, Hz, pan): distant sonar
BUILD = ((2.4, 587.33), (2.8, 698.46), (3.2, 880.00), (3.6, 1046.50), (3.95, 1174.66))   # rising D minor figure
TIMPANI = ((2.2, 0.35), (3.0, 0.45), (3.5, 0.55), (3.85, 0.70), (4.05, 0.90))   # a heartbeat that accelerates
GLINTS = ((0.5, 1318.51, -0.8), (1.1, 880.00, 0.6), (1.8, 1396.91, -0.4), (2.5, 1174.66, 0.8), (3.2, 1760.00, -0.2))
SETTING_KEY = "startup/chime"


def enabled() -> bool:
    from PySide6.QtCore import QSettings
    value = QSettings("SHARC", "GUI").value(SETTING_KEY, True)
    return str(value).lower() in ("true", "1", "yes")


def set_enabled(on: bool) -> None:
    from PySide6.QtCore import QSettings
    QSettings("SHARC", "GUI").setValue(SETTING_KEY, bool(on))


# --------------------------------------------------------------------------- building blocks
def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _swell(t, start, peak, release):
    """Crescendo from `start` to `peak`, then an exponential release (rate `release` per second)."""
    return _smooth((t - start) / (peak - start)) * np.exp(-release * np.clip(t - peak, 0.0, None))


def _stack(t, freq, harmonics, rolloff, detune=0.0, vibrato=0.0, bright_from=None):
    """Additive voice: harmonics 1..n with 1/k^rolloff amplitudes; optional detune, vibrato and a
    harmonic-by-harmonic opening (bright_from = time at which upper partials start to appear)."""
    vib = 1.0 + vibrato * np.sin(2 * np.pi * 5.2 * t)
    out = np.zeros_like(t)
    for k in range(1, harmonics + 1):
        amp = 1.0 / k ** rolloff
        if bright_from is not None:
            amp = amp * _smooth((t - bright_from - 0.15 * k) / 2.0)
        out += amp * np.sin(2 * np.pi * freq * (1.0 + detune) * k * t * vib + 0.7 * k)
    return out


def _bell(t, start, freq, decay, level, index0=1.6):
    tt = np.clip(t - start, 0.0, None)
    env = (t >= start) * np.minimum(1.0, tt / 0.004) * np.exp(-decay * tt)
    index = index0 * np.exp(-6.0 * tt)
    tone = np.sin(2 * np.pi * freq * tt + index * np.sin(2 * np.pi * freq * 1.41 * tt))   # inharmonic ratio: cold, metallic
    return level * env * (tone + 0.10 * np.sin(2 * np.pi * freq * 2.76 * tt))


def _timpani(t, start, freq, level):
    tt = np.clip(t - start, 0.0, None)
    gate = (t >= start) * np.minimum(1.0, tt / 0.003)
    f = freq * (1.0 + 0.55 * np.exp(-14.0 * tt))             # pitch drops into the note: the "thud"
    phase = 2 * np.pi * np.cumsum(f) / RATE
    body = np.sin(phase) + 0.45 * np.sin(1.5 * phase) * np.exp(-6.0 * tt)
    return level * gate * body * np.exp(-3.0 * tt)


def _pan(sig, pos, left, right):
    left += sig * (0.5 - 0.5 * pos)
    right += sig * (0.5 + 0.5 * pos)


def _reverb(x, delays_ms, gain):
    """Parallel feedback combs (Schroeder-style): a wide, soft tail.

    y[n] = x[n] + gain * y[n - d] is evaluated one block of d samples at a time (each block only
    needs the finished previous block), which is orders of magnitude faster than a d-tap filter."""
    out = np.zeros_like(x)
    for ms in delays_ms:
        d = int(ms * RATE / 1000)
        y = x.copy()
        for s in range(d, len(x), d):
            e = min(s + d, len(x))
            y[s:e] += gain * y[s - d:e - d]
        out += y
    return out / len(delays_ms)


def write_wav(path: Path, samples: np.ndarray) -> None:
    """Write float samples ((n,) mono or (n, 2) stereo) as 16-bit PCM, atomically."""
    samples = np.asarray(samples)
    channels = 1 if samples.ndim == 1 else samples.shape[1]
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    with wave.open(str(tmp), "wb") as fh:
        fh.setnchannels(channels)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes(pcm)
    os.replace(tmp, path)


def silenced() -> bool:
    """True when the environment asks for no sound (tests, screenshot tools, CI)."""
    return any(os.environ.get(k) for k in ("SHARC_GUI_NO_SOUND", "SHARC_GUI_NO_CHIME", "SHARC_GUI_NO_SPLASH",
                                           "SHARC_GUI_NO_RESTORE"))


# --------------------------------------------------------------------------- the piece
def synthesize() -> np.ndarray:
    """Stereo samples in [-1, 1], shape (n, 2)."""
    n = int(RATE * LENGTH_S)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(11)                         # fixed seed: the same sound every launch
    left, right = np.zeros(n), np.zeros(n)
    release = 1.0 - _smooth((t - HIT) / 0.10)               # tension voices end as the impact lands

    # drone: D1 + D2 + A1 with a slow beat, rising to the impact and carrying it
    drone = _swell(t, 0.0, HIT, 0.30)
    d = (0.50 * np.sin(2 * np.pi * D1 * t) + 0.28 * np.sin(2 * np.pi * 2 * D1 * t)
         + 0.20 * np.sin(2 * np.pi * (D1 * 1.4983 + 0.55) * t))
    left += drone * d
    right += drone * d

    # string cluster D-Eb-A: the minor second grinds and swells, then resolves at the hit
    tension = _smooth((t - 0.6) / (HIT - 0.6)) * release
    for f, pos in zip(CLUSTER, (-0.5, 0.0, 0.5)):
        for det, p in ((-0.0025, -0.7), (0.0025, 0.7)):
            _pan(0.040 * tension * _stack(t, f, 9, 1.15, detune=det, vibrato=0.004, bright_from=0.8), (pos + p) / 2, left, right)

    # horns: low, menacing swell into the hit, then a sustained minor chord
    horns = _swell(t, 1.8, HIT, 0.42)
    for f, pos in zip(MINOR_LOW, (-0.2, 0.2, -0.4, 0.4)):
        _pan(0.060 * horns * _stack(t, f, 12, 0.95, detune=0.0010, vibrato=0.0015, bright_from=1.8), pos, left, right)

    # strings: the resolved D-minor(add9) chord, wide, sustained after the hit
    chord = _swell(t, HIT - 0.15, HIT + 0.2, 0.30)
    for f in MINOR_MID:
        for det, pos in ((-0.0020, -0.65), (0.0020, 0.65)):
            _pan(0.034 * chord * _stack(t, f, 9, 1.15, detune=det, vibrato=0.003, bright_from=HIT - 0.2), pos, left, right)

    # choir "ooh": low formants (~400 Hz and ~800 Hz), minor voicing
    choir = _swell(t, 1.2, HIT + 0.15, 0.30)
    for f, pos in zip((110.00, 146.83, 174.61, 220.00), (-0.3, 0.3, -0.15, 0.15)):
        voice = np.zeros(n)
        for k in range(1, 15):
            hz = f * k
            w = np.exp(-((hz - 400) / 240) ** 2) + 0.5 * np.exp(-((hz - 800) / 330) ** 2) + 0.10 / k
            voice += w * np.sin(2 * np.pi * hz * (1 + 0.0025 * np.sin(2 * np.pi * 4.6 * t)) * t + 1.3 * k)
        _pan(0.036 * choir * voice, pos, left, right)

    # dark reverse cymbal into the impact
    b, a = butter(2, 1800 / (RATE / 2), btype="high")
    cym = lfilter(b, a, rng.standard_normal(n))
    cym_env = _smooth((t - 2.8) / (HIT - 2.8)) ** 2.5 * (t < HIT)
    left += 0.070 * cym_env * cym
    right += 0.070 * cym_env * np.roll(cym, 173)

    # slow cosmic whoosh at the start
    b, a = butter(2, [200 / (RATE / 2), 2600 / (RATE / 2)], btype="band")
    noise = lfilter(b, a, rng.standard_normal(n))
    wh = _smooth(t / 2.0) * (1.0 - _smooth((t - 2.0) / 2.0))
    left += 0.060 * wh * noise
    right += 0.060 * wh * np.roll(noise, 211)

    # distant sonar pings, far left and far right
    for ts, f, pos in PINGS:
        _pan(_bell(t, ts, f, 0.9, 0.12, index0=0.6), pos, left, right)

    # rising D-minor figure, quiet and cold, heading for the impact
    for i, (ts, f) in enumerate(BUILD):
        _pan(_bell(t, ts, f, 1.0, 0.16, index0=1.0), -0.6 + i * 0.3, left, right)

    # heartbeat of timpani that accelerates, plus the low timpani on the hit
    for ts, lv in TIMPANI:
        _pan(_timpani(t, ts, 73.42, 0.42 * lv), 0.0, left, right)
    for f in MINOR_LOW[:2]:
        _pan(_timpani(t, HIT, f, 0.60), 0.0, left, right)

    # THE HIT: boom (pitch-dropping sine), noise burst, bells on every chord tone
    tt = np.clip(t - HIT, 0.0, None)
    boom_f = 36.0 + 80.0 * np.exp(-5.0 * tt)
    boom = (t >= HIT) * np.sin(2 * np.pi * np.cumsum(boom_f) / RATE) * np.exp(-1.5 * tt) * np.minimum(1.0, tt / 0.003)
    b, a = butter(2, 1000 / (RATE / 2), btype="low")
    burst = (t >= HIT) * lfilter(b, a, rng.standard_normal(n)) * np.exp(-6.0 * tt)
    left += 0.85 * boom + 0.42 * burst
    right += 0.85 * boom + 0.42 * np.roll(burst, 97)
    for i, f in enumerate(CHORD_BELLS):
        _pan(_bell(t, HIT + 0.012 * i, f, 0.50, 0.15), -0.7 + i * 0.28, left, right)

    # after the impact: star glints, far apart in the dark
    for dt, f, pos in GLINTS:
        _pan(_bell(t, HIT + dt, f, 0.85, 0.12, index0=0.8), pos, left, right)

    # space: long, cavernous reverb, different comb delays per side
    wet_l = _reverb(left, (61.0, 71.0, 83.0, 97.0, 109.0, 127.0), 0.90)
    wet_r = _reverb(right, (67.0, 73.0, 89.0, 101.0, 113.0, 131.0), 0.90)
    left = left + 1.1 * wet_l
    right = right + 1.1 * wet_r

    fade = np.minimum(1.0, (LENGTH_S - t) / 1.6) * np.minimum(1.0, t / 0.08)
    out = np.stack([left * fade, right * fade], axis=1)
    out = np.tanh(1.3 * out / max(1e-9, float(np.max(np.abs(out)))))        # soft limiter: loud, never harsh
    return out * (0.8 / max(1e-9, float(np.max(np.abs(out)))))


def wav_path() -> Path:
    path = Path(tempfile.gettempdir()) / "sharc_startup_chime_v5.wav"
    if not path.is_file() or path.stat().st_size < 1000:
        write_wav(path, synthesize())
    return path


def prepare() -> None:
    """Render the chime in the background so it is ready (cached) when the splash needs it."""
    def work():
        try:
            wav_path()
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=work, daemon=True).start()


_effect = None   # keeps the QtMultimedia fallback alive while it plays


def play_file(path: Path, volume: float = 0.6) -> bool:
    """Start playing a WAV without blocking. Never raises."""
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            return True
        global _effect
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect
        _effect = QSoundEffect()
        _effect.setSource(QUrl.fromLocalFile(str(path)))
        _effect.setVolume(volume)
        _effect.play()
        return True
    except Exception:  # noqa: BLE001 - sound is a nicety, never a reason to fail
        return False


def play(force: bool = False) -> bool:
    """Play the chime if enabled (or `force`). Returns True when playback started."""
    if not force and (silenced() or not enabled()):
        return False
    path = Path(tempfile.gettempdir()) / "sharc_startup_chime_v5.wav"
    if path.is_file() and path.stat().st_size > 1000:
        return play_file(path)

    def render_then_play():                      # first launch: never block the interface while rendering
        try:
            play_file(wav_path())
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=render_then_play, daemon=True).start()
    return True
