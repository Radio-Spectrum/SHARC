import numpy as np
import scipy.io
import os

data = scipy.io.loadmat(os.path.join(os.path.dirname(__file__), 'constants/sys4_lut2.mat'))
LUT = data['LUT'].astype(np.float32)
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

ival = np.abs(LUT[0, 2])
lut_res = np.abs(LUT[0, 2]) - np.abs(LUT[1, 2])

grid_size = int(1 + (2 * ival) / lut_res)
LUT_vals = np.ascontiguousarray(LUT[:, 3:], dtype=np.float32)
del LUT


import line_profiler

@line_profiler.profile
def get_weights_vectorized(az, elev):
    az = np.asarray(az)
    elev = np.asarray(elev)

    N = az.size

    beamAz = az
    beamEl = elev

    # ---- Branch mask
    # check if any outside LUT range
    mask = (beamAz > 60.0) | (beamAz < -60.0)

    taperVal = np.zeros((N, 7680))

    if np.any(mask):
        az_sel = beamAz[mask]
        el_sel = beamEl[mask]

        a1 = np.round(az_sel / lut_res) * lut_res
        a2 = np.where(a1 < az_sel, a1 + lut_res, a1 - lut_res)

        e1 = np.round(el_sel / lut_res) * lut_res
        e2 = np.where(e1 < el_sel, e1 + lut_res, e1 - lut_res)

        az1 = np.minimum(a1, a2)
        el1 = np.minimum(e1, e2)

        bid1 = (
            np.round((az1 + ival) / lut_res) * grid_size +
            np.round((el1 + ival) / lut_res)
        ).astype(int)

        bid2 = bid1 + grid_size
        bid3 = bid1 + 1
        bid4 = bid2 + 1

        x = np.abs(az1 - az_sel) / lut_res
        y = np.abs(el1 - el_sel) / lut_res

        # Broadcast multiply
        w1 = (1 - x) * (1 - y)
        w2 = x * (1 - y)
        w3 = (1 - x) * y
        w4 = x * y

        # all_bids = np.stack([bid1, bid2, bid3, bid4], axis=1)
        interp = LUT_vals[bid1].copy()
        interp *= w1[:, None]
        interp += LUT_vals[bid2] * w2[:, None]
        interp += LUT_vals[bid3] * w3[:, None]
        interp += LUT_vals[bid4] * w4[:, None]

        taperVal[mask] = interp

    if np.any(~mask):
        az_sel = beamAz[~mask]
        el_sel = beamEl[~mask]

        bid = (
            np.round((az_sel + ival) / lut_res) * grid_size +
            np.round((el_sel + ival) / lut_res)
        ).astype(int)

        if not np.any(mask):
            # prevent costly memory copying
            order = np.argsort(bid)
            sorted_bid = bid[order]

            tmp_sorted = LUT_vals[sorted_bid]

            result = np.empty_like(tmp_sorted)
            result[order] = tmp_sorted
            return result
            # return LUT_vals[np.sort(bid)]

        taperVal[~mask] = LUT_vals[bid]

    return taperVal

def taper_fn(az, elev):
    return get_weights_vectorized(az, elev)

# taper_fn = get_weights_2
890, 1500, 2000, 2300, 2500

if __name__ == "__main__":
    print("n_columns: ", maxNx)
    print("n_rows: ", maxNy)
    print("element_horiz_spacing: ", dx)
    print("element_vert_spacing: ", dy)
    print("element_max_g: ", 20 * np.log10(lingain))
