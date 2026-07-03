# -*- coding: utf-8 -*-
"""Parameters for the ITU-R M.1851 cosecant-squared radar antenna pattern.

The pattern is built from two principal-plane cuts (Rec. ITU-R M.1851-2):
  - elevation (vertical): cosecant-squared ground-radar pattern (Section 2.2,
    eqs (22), (26), (27));
  - azimuth (horizontal): rectangular-aperture theoretical main lobe plus the
    peak/average side-lobe mask (Section 2.1, Tables 4 and 6), the taper being
    selected from the first side-lobe level;
  - total pattern: summing method (Section 5): G = Gmax + Gaz + Gel.

Primary inputs are the angles given by the radar Recommendation (theta_start,
theta_end) and the side-lobe levels in dBi; the beam tilt, the null angle and
the relative side-lobe levels are derived internally. The boresight azimuth and
the elevation are NOT antenna parameters: for a single_earth_station they come
from the station geometry (single_earth_station.geometry.azimuth/elevation),
which is what the antenna factory passes to the constructor.

Default values (used by the antenna __main__) correspond to Radar C of
Rec. ITU-R M.1464-2, Table 1.
"""
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaM1851CosecantSquared(ParametersBase):
    """Cosecant-squared radar antenna parameters (Rec. ITU-R M.1851-2)."""

    # Peak (boresight) antenna gain [dBi]
    peak_gain: float = None
    # Elevation (vertical) 3 dB beamwidth, theta_3,el [degrees]
    elevation_beamwidth: float = None
    # Azimuth (horizontal) 3 dB beamwidth, theta_3,az [degrees]
    azimuth_beamwidth: float = None
    # Elevation where the cosecant-squared region starts, theta_start [degrees].
    # The beam tilt is derived as tilt = theta_start - elevation_beamwidth/2.
    csc2_start: float = None
    # Elevation where the cosecant-squared region ends, theta_end [degrees]
    csc2_end: float = None
    # First (near-in) side-lobe level [dBi]. The relative SLL (dB) is computed
    # internally as first_side_lobe - peak_gain and selects the aperture taper.
    first_side_lobe: float = None
    # Remote (far) side-lobe level [dBi], optional. If set, the floor of the
    # pattern (azimuth mask, elevation G0 and global front-to-back) is set to
    # remote_side_lobe - peak_gain [dB]; otherwise the ITU-R M.1851 default
    # mask floors are used.
    remote_side_lobe: float = None
    # Side-lobe mask: "average" (aggregate of multiple interferers -- the usual
    # ITU-R sharing case, default) or "peak" (single-entry, worst case).
    # Rec. ITU-R M.1851-2 §2.1.3.
    mask_type: str = "average"

    def validate(self, ctx):
        """Validate the cosecant-squared antenna parameters."""
        required = {
            "peak_gain": self.peak_gain,
            "elevation_beamwidth": self.elevation_beamwidth,
            "azimuth_beamwidth": self.azimuth_beamwidth,
            "csc2_start": self.csc2_start,
            "csc2_end": self.csc2_end,
            "first_side_lobe": self.first_side_lobe,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(f"{ctx} needs the parameters {missing} to be set")
        for name in ("elevation_beamwidth", "azimuth_beamwidth"):
            val = getattr(self, name)
            if (not isinstance(val, (int, float))) or val <= 0:
                raise ValueError(f"{ctx}.{name} must be a positive number")
        if self.csc2_end <= self.csc2_start:
            raise ValueError(f"{ctx}.csc2_end must be greater than csc2_start")
        if str(self.mask_type).lower() not in ("peak", "average"):
            raise ValueError(
                f"{ctx}.mask_type must be 'peak' or 'average'",
            )
