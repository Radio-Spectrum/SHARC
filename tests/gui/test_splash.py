"""Start-up checks run headless and report every item."""
import ui.shell.splash as sp


def test_startup_checks_all_report(monkeypatch):
    monkeypatch.setenv("SHARC_GUI_NO_SPLASH", "1")
    splash, report = sp.run_startup(None)
    assert splash is None
    assert len(report.results) == len(sp.CHECKS)
    assert not [r for r in report.results if r[1] == sp.FAIL], report.summary()


def test_a_failing_check_does_not_block(monkeypatch):
    monkeypatch.setenv("SHARC_GUI_NO_SPLASH", "1")
    monkeypatch.setattr(sp, "CHECKS", [("boom", lambda: 1 / 0), ("fine", lambda: (sp.OK, ""))])
    _, report = sp.run_startup(None)
    assert [r[1] for r in report.results] == [sp.FAIL, sp.OK]
    assert "boom" in report.summary()


def test_pixmap_paints_background(qapp=None):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    img = sp._pixmap().toImage()
    assert img.pixelColor(5, 5).lightness() < 80          # dark gradient, not the default fill
