# antenna_ra_m2319.py
# Radio-altimeter antenna pattern (ITU-R M.2319, Eq. A-3.6)

import numpy as np
from sharc.antenna.antenna import Antenna
from sharc.parameters.parameters_base import ParametersBase

class ParametersRA(ParametersBase):
    """
    Minimal parameter holder for the RA antenna.
    - gain_isotropic_dbi : G_RA,dBi  (isotropic gain offset, in dBi)
    - phi_3db_deg        : φ_3dB     (3 dB beamwidth, in degrees)
    """
    gain_isotropic_dbi: float = 5
    phi_3db_deg: float = 20
    inband: bool = True

class AntennaRA_M2319(Antenna):
    """
    Circular-symmetric parabolic antenna for radio altimeter (Eq. A-3.6).
    Gain in dBi as a function of single incident angle φ (deg):

        G(φ) = -12/φ_3dB^2 * φ^2 + G_RA,dBi

    Notes:
    - φ is the single incident angle that combines azimuth/elevation, per M.2319.
    - φ_3dB and φ must be in DEGREES.
    - This model is purely quadratic; if you need back-lobe floors or pattern
      clipping, apply np.maximum afterwards as required by your link budget.
    """

    def __init__(self, param: ParametersRA):
        super().__init__()
        if param.phi_3db_deg <= 0:
            raise ValueError("phi_3db_deg must be > 0 (in degrees).")
        self.gain_iso_dbi = param.gain_isotropic_dbi     # G_RA,dBi
        self.phi_3db_deg = param.phi_3db_deg            # φ_3dB (deg)
        # Precompute constant factor: -12 / φ_3dB^2
        self._k = -12.0 / (self.phi_3db_deg ** 2)
        self.inband = param.inband

    def calculate_gain(self, *args, **kwargs) -> np.ndarray:
        """
        Parameters
        ----------
        off_axis_angle_vec : np.ndarray
            |φ| in DEGREES (single incident angle).

        Returns
        -------
        np.ndarray
            Gain in dBi for each φ.
        """
        phi = np.abs(np.asarray(kwargs["off_axis_angle_vec"], dtype=float))
        if self.inband:
            # Eq. (A-3.6)
            gain_dbi = self._k * (phi ** 2) + self.gain_iso_dbi
        else:
            gain_dbi = np.zeros(phi.shape)
            mask_phi = (phi < 90)
            gain_dbi[~mask_phi] = -np.abs(phi[~mask_phi] - 90)
        return gain_dbi

# ---- Example (optional, for quick check) ----

if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # Example parameters: 3 dB beamwidth = 20 deg, isotropic offset = 5 dBi
    p = ParametersRA
    p.gain_isotropic_dbi=13.0
    p.phi_3db_deg=45.0
    p.inband = False
    ant = AntennaRA_M2319(p)
    phi = np.linspace(0, 180, 181)

    g = ant.calculate_gain(off_axis_angle_vec=phi)

    plt.plot(phi, g, label="M.2319 A-3.6 (φ3dB=20°, Giso=5 dBi)")
    plt.xlabel(r"Incident angle $\phi$ [deg]")
    plt.ylabel("Gain [dBi]")
    plt.grid(True)
    plt.legend()
    plt.show()
