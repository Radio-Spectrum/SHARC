"""Start-up chime (synthesis, setting, silence under tests) and the photorealistic 3D set-up dialog."""
import os
import sys
import wave

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import startup_chime as chime  # noqa: E402


def test_synthesis_is_audible_bounded_and_ends_quietly():
    s = chime.synthesize()
    assert s.shape == (int(chime.RATE * chime.LENGTH_S), 2)
    assert 0.5 < float(np.max(np.abs(s))) <= 0.81         # audible, with headroom (no clipping)
    hit = int(chime.HIT * chime.RATE)                      # the impact is the loudest part and follows a quieter build
    assert np.sqrt(np.mean(s[hit:hit + 4000] ** 2)) > 2 * np.sqrt(np.mean(s[:hit // 4] ** 2))
    assert float(np.max(np.abs(s[-200:]))) < 0.01          # no click at the end
    assert float(np.max(np.abs(s[:20]))) < 0.05            # no click at the start
    assert np.all(np.isfinite(s))
    assert float(np.mean(np.abs(s[:, 0] - s[:, 1]))) > 1e-3   # genuinely stereo


def test_wav_file_is_valid_stereo_16bit():
    with wave.open(str(chime.wav_path()), "rb") as fh:
        assert (fh.getnchannels(), fh.getsampwidth(), fh.getframerate()) == (2, 2, chime.RATE)
        assert fh.getnframes() > 4 * chime.RATE


def test_setting_round_trip_and_silence(monkeypatch):
    old = chime.enabled()
    try:
        chime.set_enabled(False)
        assert chime.enabled() is False
        monkeypatch.delenv("SHARC_GUI_NO_SPLASH", raising=False)
        monkeypatch.delenv("SHARC_GUI_NO_CHIME", raising=False)
        assert chime.play() is False                       # disabled in preferences: stays silent
        chime.set_enabled(True)
        monkeypatch.setenv("SHARC_GUI_NO_CHIME", "1")
        assert chime.play() is False                       # env switch used by tests/CI
    finally:
        chime.set_enabled(old)


def test_sound_effects_are_valid_and_independent_of_the_chime(monkeypatch):
    from core import sound_fx as fx
    for name in fx.EVENTS:
        x = fx._BUILDERS[name]()
        assert x.ndim == 2 and x.shape[1] == 2 and np.all(np.isfinite(x)) and 0.3 < float(np.max(np.abs(x))) <= 0.66
        assert float(np.max(np.abs(x[-100:]))) < 0.02
    old_fx, old_chime = fx.enabled(), chime.enabled()
    try:
        monkeypatch.delenv("SHARC_GUI_NO_SOUND", raising=False)
        monkeypatch.delenv("SHARC_GUI_NO_CHIME", raising=False)
        monkeypatch.delenv("SHARC_GUI_NO_SPLASH", raising=False)
        monkeypatch.delenv("SHARC_GUI_NO_RESTORE", raising=False)
        fx.set_enabled(False)
        chime.set_enabled(True)
        assert fx.play("finished") is False            # effects off: silent even though the chime is on
        assert chime.enabled() is True
        fx.set_enabled(True)
        chime.set_enabled(False)
        assert chime.play() is False                   # chime off: silent even though effects are on
        assert fx.enabled() is True
    finally:
        fx.set_enabled(old_fx)
        chime.set_enabled(old_chime)


def test_scheduler_emits_started_and_failed():
    from core.job_scheduler import JobScheduler
    started, failed = [], []

    def boom(_p):
        raise RuntimeError("x")
    s = JobScheduler(lambda p: None, lambda p: None)
    s.job_started.connect(started.append)
    s.submit(["a.yaml"])
    s.tick()
    assert len(started) == 1
    s2 = JobScheduler(boom, lambda p: None)
    s2.job_failed.connect(failed.append)
    s2.submit(["b.yaml"])
    s2.tick()
    assert len(failed) == 1
    s2.on_status({"iid": "b.yaml", "status": "Error: again"})   # an already-failed job does not re-emit
    assert len(failed) == 1


def test_setup_dialog_saves_credentials_into_terrain_state(win):
    from PySide6.QtWidgets import QLineEdit
    from ui.components.photoreal_setup import PhotorealSetupDialog
    tab = win.tab_terrain
    old = (tab.state.get("terr_ion_token").get(), tab.state.get("terr_photoreal_key").get())
    try:
        dlg = PhotorealSetupDialog(tab, win)
        assert dlg.ed_ion.echoMode() == QLineEdit.Password       # secrets are masked by default
        dlg.ed_ion.setText("  tok123  ")
        dlg._save()
        assert tab.state.get("terr_ion_token").get() == "tok123"
        assert "Cesium ion token" in dlg.lbl.text()
    finally:
        tab.state.get("terr_ion_token").set(old[0])
        tab.state.get("terr_photoreal_key").set(old[1])
