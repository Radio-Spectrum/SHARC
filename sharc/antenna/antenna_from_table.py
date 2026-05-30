from sharc.antenna.antenna import Antenna

import numpy as np


class AntennaFromTable(Antenna):
    """
    Antenna pattern defined by a user-supplied CSV table (angle_deg, gain_dBi).
    Gain for arbitrary angles is obtained via linear interpolation.
    """

    def __init__(self, param):
        super().__init__()
        data = np.loadtxt(param.table_file, delimiter=",", skiprows=1)
        self.angle = data[:, 0]
        self.gain = data[:, 1]

    def calculate_gain(self, *args, **kwargs) -> np.array:
        phi = np.array(kwargs["off_axis_angle_vec"])
        phi = np.clip(phi, self.angle[0], self.angle[-1])
        return np.interp(phi, self.angle, self.gain)
