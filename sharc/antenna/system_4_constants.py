import numpy as np
import scipy.io
import os

data = scipy.io.loadmat(os.path.join(os.path.dirname(__file__), 'constants/sys4_lut2.mat'))
LUT = data['LUT']
# # pattern_data = scipy.io.loadmat(os.path.join(os.path.dirname(__file__), 'E_H_Pattern_0deg_az_45deg_el.mat'))
pattern_data = scipy.io.loadmat(os.path.join(os.path.dirname(__file__), 'constants/sys4_EH_pattern_0azim_0elev2.mat'))
E_pattern_data = pattern_data['E_pattern'].flatten()
H_pattern_data = pattern_data['H_pattern'].flatten()

fc = 2.5e3  # MHz
from sharc.parameters.constants import SPEED_OF_LIGHT
lmbda = SPEED_OF_LIGHT / (fc * 1e6)
maxNx = 96
maxNy = 80
# dx = 0.161  # wavelength spacing (adjust as needed)
# dx = dx / lmbda
dx = 0.5
# dy = 0.161  # wavelength spacing (adjust as needed)
# dy = dy / lmbda
dy = 0.5
lingain = 1.75

def get_weights_2(az, elev):
    radiatingAngle = np.array([az, elev]).reshape(2, 1)
    beamAzEl_LUT = radiatingAngle
    beamAzEl = radiatingAngle
    wts = np.zeros((7680, 1))
    taperVal = np.zeros((7680, 1))
    ival = np.abs(LUT[0, 2])  # lower value for elevation in the table
    lut_res = np.abs(LUT[0, 2]) - np.abs(LUT[1, 2])  # Beamformer LUT resolution (2.5 deg.)

    # Assuming radiatingAngle, beamAzEl_LUT, beamAzEl, range, th_range are inputs
    # and taperVal, wts, wts_taper are outputs to be initialized

    # beamAzEl is the Az and El towards the Earth (can be a victim)
    # beamAzEl_LUT is beamAzEl rotated by roll, yaw and pitch - those are rotations to the antenna - based on local
    # antenna coordinate system

    for i in range(radiatingAngle.shape[0]):
        # TODO: In the original code th_range is a threshold for slant path length. We need to convert to elevation
        # look angle
        # if range[i] > th_range:
        if i > 60.0 or i < -60.0:
            # Just find two LUT bounds arround the actual az and el
            a1 = np.round(beamAzEl_LUT[0, i] / lut_res) * lut_res
            a2 = a1 + lut_res if a1 < beamAzEl_LUT[0, i] else a1 - lut_res
            e1 = np.round(beamAzEl_LUT[1, i] / lut_res) * lut_res
            e2 = e1 + lut_res if e1 < beamAzEl_LUT[1, i] else e1 - lut_res

            az1 = min(a1, a2)
            az2 = max(a1, a2)
            el1 = min(e1, e2)
            el2 = max(e1, e2)

            bid1 = int(np.round((az1 + ival) / lut_res) * (1 + (2 * ival) / lut_res) + np.round((el1 + ival) / lut_res))
            bid2 = bid1 + int(1 + (2 * ival / lut_res))
            bid3 = bid1 + 1
            bid4 = bid2 + 1

            x = np.abs(az1 - beamAzEl_LUT[0, i]) / lut_res
            y = np.abs(el1 - beamAzEl_LUT[1, i]) / lut_res
            inp_taper = (LUT[bid1, 3:] * (1 - x) * (1 - y) +
                         LUT[bid2, 3:] * x * (1 - y) +
                         LUT[bid3, 3:] * (1 - x) * y +
                         LUT[bid4, 3:] * x * y)
            taperVal[:, i] = inp_taper
        else:
            bid = int(np.round((beamAzEl_LUT[0, i] + ival) / lut_res) * (1 + (2 * ival) / lut_res) +
                      np.round((beamAzEl_LUT[1, i] + ival) / lut_res))
            taperVal[:, i] = LUT[bid, 3:]
        # # Compute weights
        # delay = (1 / SPEED_OF_LIGHT) * pos.T @ np.array([
        #     np.sin(np.deg2rad(beamAzEl[1, i])),
        #     np.cos(np.deg2rad(beamAzEl[1, i])) * np.sin(np.deg2rad(beamAzEl[0, i])),
        #     np.cos(np.deg2rad(beamAzEl[1, i])) * np.cos(np.deg2rad(beamAzEl[0, i]))
        # ])
        # new_wts = np.exp(1j * 2 * np.pi * fc * delay)
        # wts[:, i] = new_wts
        # wts_taper = new_wts * taperVal[:, i]

        return taperVal.flatten()

taper_fn = get_weights_2
890, 1500, 2000, 2300, 2500

if __name__ == "__main__":
    print("n_columns: ", maxNx)
    print("n_rows: ", maxNy)
    print("element_horiz_spacing: ", dx)
    print("element_vert_spacing: ", dy)
    print("element_max_g: ", 20 * np.log10(lingain))
