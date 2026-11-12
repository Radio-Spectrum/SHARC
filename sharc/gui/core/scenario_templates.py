"""Scenario templates offered by the Start Page: the documented scenarios of the user manual (Volume 2).

Each template only sets the interface variables that define the scenario family (victim system, IMT link and the
IMT topology values); every other parameter keeps the value the user already has, exactly as a user would do by hand.
The module has no Qt dependency so the catalogue and the apply step can be unit-tested without a window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional, Protocol, Tuple


class _Settable(Protocol):
    def set(self, value) -> None: ...


class _StateLike(Protocol):
    def get(self, key: str) -> _Settable: ...


@dataclass(frozen=True)
class ScenarioTemplate:
    key: str
    title: str
    summary: str
    system: str                      # value of the global "system" variable (victim / other service)
    link: str                        # IMT link: DOWNLINK or UPLINK
    imt: Mapping[str, str] = field(default_factory=dict)   # IMT tab state keys -> values
    glyph: str = "mdi.radio-tower"   # qtawesome icon name shown on the card
    tags: Tuple[str, ...] = ()
    manual_section: str = ""         # section of the scenario guide (Volume 2) that documents it


TEMPLATES: Tuple[ScenarioTemplate, ...] = (
    ScenarioTemplate(
        key="s1_countries", title="Country-wide IMT vs earth station",
        summary="Macro sites over whole countries from a base-station grid, interfering into a fixed earth station.",
        system="SINGLE_EARTH_STATION", link="DOWNLINK", imt={"topo_type": "Macro_countries"},
        glyph="mdi.earth", tags=("Macro_countries", "FSS/SES"), manual_section="S1",
    ),
    ScenarioTemplate(
        key="s2_macro_ses", title="Macrocell vs earth station",
        summary="Hexagonal macro layout, 750 m inter-site distance, downlink into a single earth station.",
        system="SINGLE_EARTH_STATION", link="DOWNLINK", imt={"topo_type": "MACROCELL", "macro_intersite": "750"},
        glyph="mdi.hexagon-multiple-outline", tags=("MACROCELL", "FSS/SES"), manual_section="S2",
    ),
    ScenarioTemplate(
        key="s3_sss", title="Macrocell uplink vs space station",
        summary="User equipment transmitting towards a satellite receiver; 1500 m inter-site distance.",
        system="SINGLE_SPACE_STATION", link="UPLINK", imt={"topo_type": "MACROCELL", "macro_intersite": "1500"},
        glyph="mdi.satellite-variant", tags=("MACROCELL", "Uplink", "Space station"), manual_section="S3",
    ),
    ScenarioTemplate(
        key="s4_mss_d2d", title="MSS direct-to-device",
        summary="Mobile-satellite direct-to-device system sharing the band with a macro IMT network.",
        system="MSS_D2D", link="DOWNLINK", imt={"topo_type": "MACROCELL"},
        glyph="mdi.cellphone-wireless", tags=("MSS D2D", "MACROCELL"), manual_section="S4",
    ),
    ScenarioTemplate(
        key="s5_haps", title="HAPS platform",
        summary="High-altitude platform station as the other service, macro IMT network on the ground.",
        system="HAPS", link="DOWNLINK", imt={"topo_type": "MACROCELL"},
        glyph="mdi.airballoon-outline", tags=("HAPS", "MACROCELL"), manual_section="S5",
    ),
    ScenarioTemplate(
        key="s6_ntn", title="NTN cells vs space station",
        summary="Non-terrestrial IMT cells served from orbit, evaluated against a space station receiver.",
        system="SINGLE_SPACE_STATION", link="DOWNLINK", imt={"topo_type": "NTN"},
        glyph="mdi.orbit", tags=("NTN", "Space station"), manual_section="S6",
    ),
    ScenarioTemplate(
        key="s6_mss_dc", title="MSS direct-connect constellation",
        summary="Satellite constellation serving IMT directly (MSS DC) with a space station as the victim.",
        system="SINGLE_SPACE_STATION", link="DOWNLINK", imt={"topo_type": "MSS_DC"},
        glyph="mdi.satellite-uplink", tags=("MSS DC", "Constellation"), manual_section="S6",
    ),
)


def find_template(key: str, templates: Iterable[ScenarioTemplate] = TEMPLATES) -> Optional[ScenarioTemplate]:
    return next((t for t in templates if t.key == key), None)


def apply_template(template: ScenarioTemplate, *, system_var: _Settable, link_var: _Settable,
                   imt_state: _StateLike) -> None:
    """Set the scenario family on the interface variables. The order matters: the system first (it decides which
    pages are visible), then the link, then the IMT topology keys."""
    system_var.set(template.system)
    link_var.set(template.link)
    for key, value in template.imt.items():
        imt_state.get(key).set(value)
