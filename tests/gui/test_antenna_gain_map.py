"""Mapa de ganho do preview: cada padrão de antena do motor, vindo dos parâmetros da GUI."""
import json
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

from core.antenna_service import PATTERN_SPECS  # noqa: E402


@pytest.mark.parametrize("pattern", list(PATTERN_SPECS))
def test_gain_map_uses_selected_pattern(win, pattern):
    editor = win.tab_victim.ant_section.editor
    editor.combo.setCurrentText(pattern)
    # Uma antena pequena (1 m) enxerga a Terra inteira dentro do lóbulo principal
    # (ganho constante, correto fisicamente); com 8 m o mapa tem estrutura.
    spec = PATTERN_SPECS[pattern]
    if any(f.key == "diameter" for f in spec.fields):
        editor._var_for(pattern, "diameter").set("8.0")
    win.var_show_gainmap.set(True)
    win.var_gain_vmin.set("-10")
    win.var_gain_vmax.set("50")
    scene = json.loads(win.tab_preview._cesium_scene_provider("SINGLE_SPACE_STATION"))
    assert not scene.get("error"), f"{pattern}: {scene.get('error')}"
    gm = scene.get("gain_map")
    assert gm and len(gm["cells"]) > 10, f"{pattern}: mapa de ganho vazio"
    values = [c["v"] for c in gm["cells"]]
    if pattern != "OMNI":   # OMNI é uniforme por definição
        assert max(values) > min(values), f"{pattern}: mapa sem variação (parábola/zeros?)"
    win.var_show_gainmap.set(False)
