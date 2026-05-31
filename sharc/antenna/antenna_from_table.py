from sharc.antenna.antenna import Antenna

import numpy as np


class AntennaFromTable(Antenna):
    """
    Rotationally symmetric antenna pattern defined by a user-supplied CSV table.

    The table maps elevation angle (degrees, -90 to 90) to gain (dBi). The gain
    is the same for all azimuths at a given elevation. Gain for angles not in
    the table is obtained via linear interpolation.

    CSV format (with header row):
        elevation_deg,gain_dBi
        -90,-10.0
        -45,5.0
        0,28.5
        45,5.0
        90,-10.0
    """

    def __init__(self, param):
        super().__init__()
        # Arrays are pre-loaded once in ParametersAntennaFromTable.validate()
        # and reused here — no disk I/O per snapshot.
        self._elevation = param._elevation   # degrees, -90 to 90
        self._gain      = param._gain        # dBi

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculate antenna gain based on elevation angle.

        Parameters
        ----------
        **kwargs : dict
            Expects 'theta_vec': zenith angle in degrees (0 = up, 90 = horizontal,
            180 = down), as returned by the simulator geometry. Azimuth (phi_vec)
            is ignored since the pattern is rotationally symmetric.

        Returns
        -------
        np.array
            Antenna gain in dBi for each input angle.
        """
        # theta_vec is zenith angle (0=up, 180=down); convert to elevation
        theta = np.asarray(kwargs["theta_vec"], dtype=float)
        elevation = 90.0 - theta

        elevation = np.clip(elevation, self._elevation[0], self._elevation[-1])
        return np.interp(elevation, self._elevation, self._gain)


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # ------------------------------------------------------------------
    # Set the path to your CSV file here (leave as None to use the
    # built-in demo pattern).
    # ------------------------------------------------------------------
    CSV_FILE = "/home/matheus/Documents/unb/6g/SHARC/sharc/campaigns/arns/antenna_gain_real_data.csv"
    # CSV_FILE = None   # use demo cosine pattern
    # ------------------------------------------------------------------

    if CSV_FILE is not None:
        class _Param:
            table_file = CSV_FILE
    else:
        import os
        import tempfile

        el_demo = np.linspace(-90, 90, 181)
        gain_demo = 30 * np.cos(np.deg2rad(el_demo)) - 5

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write("elevation_deg,gain_dBi\n")
            for e, g in zip(el_demo, gain_demo):
                f.write(f"{e:.1f},{g:.4f}\n")
            _tmp = f.name

        class _Param:
            table_file = _tmp

    antenna = AntennaFromTable(_Param())

    # elevation from -90 to 90, sampled densely for smooth curves
    elevation_plot = np.linspace(-90, 90, 1000)
    theta_plot = 90.0 - elevation_plot   # zenith angles for calculate_gain
    gain_plot = antenna.calculate_gain(theta_vec=theta_plot)

    fig = plt.figure(figsize=(12, 5), facecolor="w")

    # --- Cartesian plot ---
    ax_cart = fig.add_subplot(121)
    ax_cart.plot(elevation_plot, gain_plot, "-b")
    ax_cart.axhline(gain_plot.max(), color="r", linestyle="--", linewidth=0.8,
                    label=f"Max: {gain_plot.max():.2f} dBi")
    ax_cart.set_title("Antenna pattern (table-based)")
    ax_cart.set_xlabel("Elevation angle [deg]")
    ax_cart.set_ylabel("Gain [dBi]")
    ax_cart.set_xlim(-90, 90)
    ax_cart.legend()
    ax_cart.grid(True)

    # --- Polar plot ---
    # Convention: 0° (top) = zenith (elev 90°), 90° (right) = horizon (elev 0°),
    # 180° (bottom) = nadir (elev -90°). Mirror left side for full circle.
    polar_angle = np.deg2rad(90.0 - elevation_plot)   # 0→π for elev 90→-90
    gain_floor = gain_plot.min()
    gain_shifted = gain_plot - gain_floor              # all positive for radius

    # mirror to produce a symmetric full-circle cross-section
    polar_full = np.concatenate([polar_angle, 2 * np.pi - polar_angle[::-1]])
    gain_full  = np.concatenate([gain_shifted, gain_shifted[::-1]])

    ax_pol = fig.add_subplot(122, projection="polar")
    ax_pol.plot(polar_full, gain_full, "-b")
    ax_pol.set_theta_zero_location("N")   # 0° at top = zenith
    ax_pol.set_theta_direction(-1)        # clockwise

    # relabel radial ticks to show actual dBi
    rticks = ax_pol.get_yticks()
    ax_pol.set_yticklabels([f"{r + gain_floor:.1f}" for r in rticks])
    ax_pol.set_title("Radiation pattern (polar)\n[radial = dBi]", pad=20)

    plt.tight_layout()
    plt.show()

    if CSV_FILE is None:
        os.unlink(_tmp)
