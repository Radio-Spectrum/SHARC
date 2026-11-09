"""Every section in the Scenario tree gets a line icon (mdi), chosen from its title."""
import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.mark.parametrize("title,glyph", [
    ("Interference Channels", "mdi.waveform"),
    ("Offline Region (cache for offline use)", "mdi.cloud-off-outline"),
    ("BS – Parameters", "mdi.antenna"),
    ("UE – Parameters", "mdi.cellphone"),
    ("Base-Station Database", "mdi.database-outline"),
    ("Real Terrain", "mdi.terrain"),
    ("Something unknown", "mdi.circle-small"),
])
def test_section_glyph_by_title(title, glyph):
    from ui.shell.workbench import section_glyph
    assert section_glyph(title) == glyph


def test_every_tree_section_has_a_real_icon(win):
    import qtawesome as qta
    from ui.shell.workbench import _SECTION_GLYPHS, section_glyph
    assert win._section_icon_items
    for _, glyph in [(None, g) for _, g in _SECTION_GLYPHS] + [(None, "mdi.circle-small")]:
        qta.icon(glyph)                                   # raises if the glyph name does not exist
    for item, glyph in win._section_icon_items:
        assert not item.icon(0).isNull(), item.text(0)
        assert glyph == section_glyph(item.toolTip(0) or item.text(0))
