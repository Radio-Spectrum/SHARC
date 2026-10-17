"""Biblioteca de antenas: todos os padrões do motor devem produzir ganho finito e coerente."""
import os
import sys

import numpy as np
import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.antenna_service import PATTERN_SPECS, build_antenna, gain_at  # noqa: E402


@pytest.mark.parametrize("pattern", list(PATTERN_SPECS))
def test_pattern_gives_finite_gain(pattern):
    ant = build_antenna(pattern)
    off = np.linspace(0, 90, 361)
    gain = gain_at(ant, off, np.zeros_like(off))
    assert np.isfinite(gain).all(), pattern
    assert gain[0] >= gain[-1] - 1e-9, f"{pattern}: ganho no eixo deve ser >= ganho longe do eixo"


def test_all_engine_patterns_with_params_are_listed():
    from sharc.antenna.antenna_factory import AntennaFactory  # noqa: F401
    import inspect
    src = inspect.getsource(AntennaFactory.create_antenna)
    # padrões do motor que usam sub-parâmetros (ARRAY e ARRAY2 ficam fora: são arranjos IMT)
    for name in PATTERN_SPECS:
        assert f'"{name}"' in src, f"{name} não existe mais na fábrica do motor"
