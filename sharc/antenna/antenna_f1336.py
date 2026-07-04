# -*- coding: utf-8 -*-

from sharc.antenna.antenna import Antenna

import numpy as np
import math


class AntennaF1336(Antenna):
    """
    Implements reference radiation patterns for system antennas for use in
    coordination studies and interference assessment (ITU-R F.1336-5),
    Section 2.1 -- omnidirectional (in azimuth) antenna:
      * peak side-lobe pattern    : eq. (1a);
      * average side-lobe pattern : eq. (1d)  (aggregate / multiple-interferer
        case -- the usual ITU-R sharing case, taken here as the default).

    CORRECTION (vs the original antenna_f1336.py):
    ----------------------------------------------
    Rec. ITU-R F.1336-5 Section 2.1 defines an antenna that is OMNIDIRECTIONAL
    in azimuth: the pattern is a function ONLY of the elevation angle theta
    (relative to the horizontal plane of maximum gain), -90 deg to +90 deg, and
    it is symmetric (the equations use |theta|). The peak is always at the
    horizon (theta = 0), regardless of any configured boresight.

    The original version read 'off_axis_angle_vec', which in SHARC is the
    great-circle angle from the antenna boresight (it mixes azimuth and
    elevation and depends on the configured boresight). That caused two bugs:
      1) the pattern was not omnidirectional (it fell off in azimuth);
      2) the orientation could be INVERTED (with the boresight pointing at the
         zenith, the peak landed at the zenith instead of the horizon).

    Fix: compute the gain from the physical elevation angle, elevation =
    90 - theta_vec (theta_vec = zenith angle: 0 = up, 90 = horizon, 180 = down,
    per StationManager.get_pointing_vector_to), take |elevation| (Section 2.1
    uses |theta|), and IGNORE the azimuth (omnidirectional). The result is then
    independent of azimuth and of the configured boresight, with the peak locked
    at the horizon.
    """

    def __init__(self, param):
        super().__init__()
        self.gain = getattr(param, 'gain', 12.0)
        self.k = getattr(param, 'k', 0.7)
        self.cable_loss = getattr(param, 'cable_loss', 2.0)
        # >>> FIX: side-lobe mask -- "average" (eq. 1d, aggregate of multiple
        #     interferers, the usual ITU-R sharing case -> default) or "peak"
        #     (eq. 1a, single-entry worst case). F.1336-5 recommends 2.1/2.2.
        self.mask_type = str(getattr(param, 'mask_type', 'average')).lower()
        # <<< FIX

        # theta_3: 3 dB beamwidth in the elevation plane, eq. (1b)
        self.theta_3 = 107.6 * math.pow(10, -0.1 * self.gain)
        # theta_4: break angle for the PEAK pattern, eq. (1c)
        self.theta_4 = self.theta_3 * math.sqrt(1 - (1 / 1.2) * math.log10(self.k + 1))
        # >>> FIX: theta_5: break angle for the AVERAGE pattern, eq. (1d)
        self.theta_5 = self.theta_3 * math.sqrt(1.25 - (1 / 1.2) * math.log10(self.k + 1))
        # <<< FIX

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculate the antenna gain for the given directions.

        Parameters
        ----------
        *args : tuple
            Positional arguments (not used).
        **kwargs : dict
            Expects 'theta_vec': the zenith angle in degrees (0 = up/zenith,
            90 = horizon, 180 = down/nadir), as returned by the simulator
            geometry (StationManager.get_pointing_vector_to). The azimuth
            ('phi_vec') is ignored because the pattern is omnidirectional in
            azimuth (ITU-R F.1336-5 Section 2.1).

        Returns
        -------
        np.array
            Antenna gain in dBi for each input direction (minus the cable loss).
        """
        # >>> FIX (F.1336 Section 2.1): use the physical ELEVATION angle, not the
        #     off-axis angle. theta_vec is the zenith angle => elevation above the
        #     horizon is (90 - theta_vec). Section 2.1 uses |theta| and the pattern
        #     is omnidirectional in azimuth, so the azimuth (phi_vec) is ignored.
        elevation = 90.0 - np.asarray(kwargs["theta_vec"], dtype=float)
        theta = np.absolute(elevation)
        # <<< FIX  (original code read: theta = np.absolute(kwargs["off_axis_angle_vec"]))

        pattern = np.zeros(theta.shape)

        # >>> FIX: select peak (eq. 1a) or average (eq. 1d) side-lobe pattern.
        # The two masks have DIFFERENT region breaks:
        #   peak    (1a): parabola for |th|<theta_4, flat [theta_4,theta_3),
        #                 tail |th|>=theta_3, side-lobe offset 12 dB;
        #   average (1d): parabola for |th|<theta_3, flat [theta_3,theta_5),
        #                 tail |th|>=theta_5, side-lobe offset 15 dB.
        if self.mask_type == "peak":
            th_a, th_b, offset = self.theta_4, self.theta_3, 12.0
        else:
            th_a, th_b, offset = self.theta_3, self.theta_5, 15.0

        # region 1: main-lobe parabola (common to both masks)
        idx_0 = np.where(theta < th_a)[0]
        pattern[idx_0] = self.gain - 12 * np.power(theta[idx_0] / self.theta_3, 2)

        # region 2: constant side-lobe shoulder
        idx_1 = np.where((th_a <= theta) & (theta < th_b))[0]
        pattern[idx_1] = self.gain - offset + 10 * math.log10(self.k + 1)

        # region 3: decaying side-lobe tail up to 90 deg (theta_3 normaliser)
        idx_2 = np.where((th_b <= theta) & (theta <= 90))[0]
        pattern[idx_2] = self.gain - offset + 10 * np.log10(
            np.power(theta[idx_2] / self.theta_3, -1.5) + self.k)
        # <<< FIX

        # Se houver valores acima de 90 passados para a função (caso ocorra fora do escopo)
        # não haverá cálculo de ganho e ficarão em 0. Como o SHARC restringe
        # a elevação de -90 a 90, o módulo |theta| será sempre <= 90.

        # Aplica a atenuação do cabo (cable_loss)
        pattern -= self.cable_loss

        return pattern


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    class ParametersF1336Mock:
        pass

    param_mock = ParametersF1336Mock()
    param_mock.gain = 12.0
    param_mock.k = 0.7
    param_mock.cable_loss = 2.0
    param_mock.mask_type = "average"   # >>> FIX: default average (eq. 1d)

    antenna = AntennaF1336(param_mock)

    # >>> FIX: the demo now feeds theta_vec (zenith angle). Sweeping the elevation
    #     from -90 to +90 corresponds to theta_vec = 90 - elevation.
    elevation_plot = np.linspace(-90, 90, num=100000)
    theta_vec = 90.0 - elevation_plot
    gain_vec = antenna.calculate_gain(theta_vec=theta_vec)
    # <<< FIX  (original demo: calculate_gain(off_axis_angle_vec=linspace(-90,90)))

    fig = plt.figure(figsize=(8, 7), facecolor='w', edgecolor='k')
    plt.plot(elevation_plot, gain_vec, "-b",
             label=f"$G_0={param_mock.gain}$ dBi, $k={param_mock.k}$, "
                   f"mask={param_mock.mask_type}, loss={param_mock.cable_loss} dB")
    plt.title("ITU-R F.1336-5 antenna radiation pattern (Section 2.1)")
    plt.xlabel(r"Elevation angle $\theta$ [deg]")
    plt.ylabel("Gain [dBi]")
    plt.legend(loc="lower center")
    plt.xlim((elevation_plot[0], elevation_plot[-1]))
    plt.grid(True)
    plt.show()
