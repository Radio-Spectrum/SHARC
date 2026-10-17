"""Biblioteca de antenas do GUI: todos os padrões do motor, com parâmetros e cortes de ganho.

Cada padrão usa a classe real do simulador (`AntennaFactory`), então o ganho
mostrado é exatamente o que a simulação calcula. A lista de padrões e os campos
de cada um vêm de `PATTERN_SPECS` (nome legível, unidade, valor típico).

Uso:
    spec = PATTERN_SPECS["ITU-R S.672"]
    ant = build_antenna("ITU-R S.672", {"antenna_gain": 40, "antenna_3_dB_bw": 1.5, "antenna_l_s": -20})
    g = gain_at(ant, np.linspace(-30, 30, 721))     # dBi, em função do ângulo fora do eixo
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class Field:
    key: str            # nome do atributo no motor
    label: str          # nome legível
    unit: str = ""
    default: Optional[float] = None
    help: str = ""


@dataclass(frozen=True)
class PatternSpec:
    name: str                      # valor de `pattern` no motor
    group: str                     # família (para a UI)
    attr: Optional[str]            # sub-bloco de ParametersAntenna ('' = gain direto)
    fields: List[Field] = field(default_factory=list)
    axisymmetric: bool = True      # ganho depende só do ângulo fora do eixo
    description: str = ""


_F = Field
_FREQ = _F("frequency", "Frequency", "MHz", 3500.0)
_DIAM = _F("diameter", "Diameter", "m", 1.0)
_GAIN = _F("antenna_gain", "Peak gain", "dBi", 30.0)

_LIST = [
    PatternSpec("OMNI", "Basic", None, [_F("gain", "Gain", "dBi", 0.0)],
                description="Isotropic/omnidirectional pattern with constant gain."),
    PatternSpec("ITU-R S.672", "Satellite (GSO)", "itu_r_s_672", [
        _F("antenna_gain", "Peak gain", "dBi", 40.0),
        _F("antenna_3_dB_bw", "3 dB beamwidth", "deg", 1.5),
        _F("antenna_l_s", "Side-lobe level Ls", "dB", -20.0, "Relative to peak: -20, -25, -30"),
    ], description="Space-station antenna, Recommendation ITU-R S.672."),
    PatternSpec("ITU-R-S.1528-Section1.2", "Satellite (NGSO)", "itu_r_s_1528", [
        _FREQ, _F("bandwidth", "Bandwidth", "MHz", 20.0), _F("antenna_gain", "Peak gain", "dBi", 35.0),
        _F("antenna_l_s", "Side-lobe level Ls", "dB", -20.0), _F("antenna_3_dB_bw", "3 dB beamwidth", "deg", 4.0),
        _F("major_minor_axis_ratio", "Major/minor axis ratio", "", 1.0),
        _F("far_out_side_lobe", "Far-out side-lobe level", "dBi", -20.0),
    ], description="Recommendation ITU-R S.1528, section 1.2."),
    PatternSpec("ITU-R-S.1528-LEO", "Satellite (NGSO)", "itu_r_s_1528", [
        _FREQ, _F("bandwidth", "Bandwidth", "MHz", 20.0), _F("antenna_gain", "Peak gain", "dBi", 35.0),
        _F("antenna_l_s", "Side-lobe level Ls", "dB", -20.0), _F("antenna_3_dB_bw", "3 dB beamwidth", "deg", 4.0),
    ], description="Recommendation ITU-R S.1528, LEO pattern."),
    PatternSpec("ITU-R-S.1528-Taylor", "Satellite (NGSO)", "itu_r_s_1528", [
        _FREQ, _F("bandwidth", "Bandwidth", "MHz", 20.0), _F("antenna_gain", "Peak gain", "dBi", 35.0),
        _F("antenna_l_s", "Side-lobe level Ls", "dB", -20.0), _F("antenna_3_dB_bw", "3 dB beamwidth", "deg", 4.0),
        _F("slr", "Taylor SLR", "dB", 20.0), _F("n_side_lobes", "Taylor side lobes", "", 4),
        _F("l_r", "Radial aperture size", "m", 1.6), _F("l_t", "Transverse aperture size", "m", 1.6),
    ], description="S.1528 with Taylor aperture distribution."),
    PatternSpec("ITU-R F.699", "Fixed service", "itu_r_f_699", [_GAIN, _FREQ, _DIAM],
                description="Reference radiation pattern for fixed-service antennas, ITU-R F.699."),
    PatternSpec("ITU-R F.1245_fs", "Fixed service", "itu_r_f_1245_fs", [_GAIN, _FREQ, _DIAM],
                description="Fixed-service antenna, ITU-R F.1245."),
    PatternSpec("ITU-R S.465", "Earth station", "itu_r_s_465", [_GAIN, _FREQ, _DIAM],
                description="Earth-station reference pattern, ITU-R S.465."),
    PatternSpec("MODIFIED ITU-R S.465", "Earth station", "itu_r_s_465_modified", [
        _GAIN, _F("envelope_gain", "Envelope gain", "dBi", 0.0)],
        description="Modified S.465 with envelope gain."),
    PatternSpec("ITU-R S.580", "Earth station", "itu_r_s_580", [_GAIN, _FREQ, _DIAM],
                description="Earth-station pattern, ITU-R S.580."),
    PatternSpec("ITU-R S.1855", "Earth station", "itu_r_s_1855", [
        _GAIN, _F("frequency", "Frequency", "MHz", 6000.0),
        _F("diameter", "Diameter", "m", 3.0, "Defined for D/lambda >= 15")],
                description="Earth-station pattern, ITU-R S.1855."),
    PatternSpec("ITU-R Reg. RR. Appendice 7 Annex 3", "Earth station", "itu_reg_rr_a7_3", [
        _GAIN, _F("frequency", "Frequency", "MHz", 6000.0), _F("diameter", "Diameter", "m", 3.0,
                                                               "The pattern is defined for D/lambda >= 35")],
                description="Radio Regulations Appendix 7, Annex 3."),
    PatternSpec("ITU-R SA.509", "Radio astronomy", "itu_r_sa_509", [
        _DIAM, _F("antenna_efficiency", "Efficiency", "", 0.7), _FREQ],
        description="Radio-astronomy antenna, ITU-R SA.509."),
    PatternSpec("MSS Adjacent", "MSS", "mss_adjacent", [_FREQ],
                description="MSS adjacent-band pattern."),
    PatternSpec("HibleoX", "MSS", "hibleo_x", [_F("frequency", "Frequency", "MHz", 2490.0,
                                                  "Valid for 2483-2500 MHz")],
                description="HIBLEO-X user-terminal pattern."),
]

PATTERN_SPECS: Dict[str, PatternSpec] = {p.name: p for p in _LIST}


def pattern_names() -> List[str]:
    return [p.name for p in _LIST]


def defaults(pattern: str) -> Dict[str, float]:
    return {f.key: f.default for f in PATTERN_SPECS[pattern].fields if f.default is not None}


def build_antenna(pattern: str, values: Optional[Dict[str, Any]] = None):
    """Cria a antena real do motor para `pattern` com os `values` (chave -> número)."""
    from sharc.antenna.antenna_factory import AntennaFactory
    from sharc.parameters.parameters_antenna import ParametersAntenna

    spec = PATTERN_SPECS[pattern]
    vals = {**defaults(pattern), **(values or {})}
    if pattern == "MODIFIED ITU-R S.465":
        # A fábrica do motor instancia AntennaS465 com estes parâmetros (erro conhecido);
        # usa-se a classe correta diretamente.
        from types import SimpleNamespace
        from sharc.antenna.antenna_modified_s465 import AntennaModifiedS465
        return AntennaModifiedS465(SimpleNamespace(
            antenna_gain=float(vals["antenna_gain"]),
            antenna_envelope_gain=float(vals["envelope_gain"])))
    p = ParametersAntenna()
    p.pattern = pattern
    if spec.attr is None:                       # OMNI: ganho direto
        p.gain = float(vals.get("gain", 0.0))
    else:
        sub = getattr(p, spec.attr)
        for key, val in vals.items():
            if val is not None and hasattr(sub, key):
                setattr(sub, key, val)
        # alguns padrões lêem o ganho do bloco-pai
        if "antenna_gain" in vals:
            p.gain = float(vals["antenna_gain"])
    return AntennaFactory.create_antenna(p, 0.0, 0.0)


def gain_at(antenna, off_axis_deg, theta_deg=None) -> np.ndarray:
    """Ganho [dBi] para ângulos fora do eixo `off_axis_deg` (e `theta_deg`, se o padrão
    não for simétrico em torno do eixo, como S.1855 e S.1528-Taylor)."""
    ang = np.atleast_1d(np.asarray(off_axis_deg, dtype=float))
    th = np.zeros_like(ang) if theta_deg is None else np.atleast_1d(np.asarray(theta_deg, dtype=float))
    out = None
    for kwargs in ({"off_axis_angle_vec": np.abs(ang), "theta_vec": th},
                   {"off_axis_angle_vec": np.abs(ang)}):
        try:
            out = antenna.calculate_gain(**kwargs)
            break
        except (KeyError, TypeError):
            continue
    if out is None:
        out = antenna.calculate_gain(np.abs(ang))
    out = np.asarray(out, dtype=float)
    if out.shape != ang.shape:
        out = np.broadcast_to(out, ang.shape).copy()
    return out
