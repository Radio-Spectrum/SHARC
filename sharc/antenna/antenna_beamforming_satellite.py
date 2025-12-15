import numpy as np
import matplotlib.pyplot as plt
from sharc.support.geometry import SimulatorGeometry
from sharc.support.sharc_geom import polar_to_cartesian, cartesian_to_polar
from sharc.antenna.antenna import Antenna
from sharc.parameters.constants import SPEED_OF_LIGHT
from sharc.antenna.ast import get_weights_2
# from line_profiler import profile


# @profile
class _ExpLUT:
    def __init__(self, L: int, dtype=np.complex64):
        self.L = int(L)
        assert np.log2(self.L) - int(np.log2(self.L)) == 0
        self.dtype = dtype

        phases = np.linspace(0, 2*np.pi, self.L, endpoint=True)
        self._lut = np.exp(1j * phases).astype(dtype)

        self._inv_2pi = self.L / (2 * np.pi)

    def get(self, v: np.ndarray) -> np.ndarray:
        """
        Fast exp(1j*v) via LUT.
        Assumes v is float32/float64.
        """
        # Scale directly to indices
        idx = (v * self._inv_2pi).astype(np.int32)

        # Wrap indices (much cheaper than mod on floats)
        # idx %= self.L
        # if L is 2^k, then same as masking:
        idx &= self.L - 1

        return np.take(self._lut, idx)

ExpLut = _ExpLUT(32768)

class AntennaBeamformingSatellite(Antenna):
    """Implements beamforming without taper.

    Considers the geometry for transforming the antenna
    array position and beam direction to the global coord system

    Notes:
    -----
    Only supports one beam, the first beam.
    It is always used in calculations
    """
    def __init__(
        self,
        sat_geom: SimulatorGeometry,
        associated_station_index: int,
        num_el_x: int,
        num_el_y: int,
        dx: float,
        dy: float,
        frequency_MHz: float,
        lingain=1.0,
        taper_fn=None,
    ):
        """Takes a stations full SimulatorGeometry
        and what stations index they should consider inside that geometry
        """
        super().__init__()
        self.taper_fn = taper_fn
        self.sat_geom = sat_geom
        # TODO: have a SingleStationGeometry instead of this hack
        self.associated_station_index = associated_station_index

        self.lingain = lingain
        self.beam_phi = None
        self.beam_theta = None
        wavelength = SPEED_OF_LIGHT / (frequency_MHz * 1e6)
        self.wavenumber = 2 * np.pi / wavelength

        self.calculated_beam_w = None

        x = dx * np.arange(-(num_el_x - 1) / 2, (num_el_x - 1) / 2 + 1)
        y = dy * np.arange(-(num_el_y - 1) / 2, (num_el_y - 1) / 2 + 1)
        X, Y = np.meshgrid(x, y, indexing="ij")
        # we want to make it so that array is in the satellite y-z plane
        beam_pos_local = np.stack((np.zeros((num_el_x * num_el_y)), X.flatten(), Y.flatten()))
        # TODO: use rigid body frame for correct fixed axis pointing
        # NOTE: using the current kind of mapping means that the antenna rotates
        # as the satellite moves. This is WRONG
        # local (down, west, north) to ENU
        # x = -y; y = z; z = -x
        beam_pos_enu = np.array([-beam_pos_local[1], beam_pos_local[2], -beam_pos_local[0]])

        # geometry holds many stations geometries. We need to specify the station
        # we should get with `associated_station_index`
        # TODO: better reference?
        beam_pos_simulator = sat_geom._vec_local2global(
            beam_pos_enu.T, translate=False,
            specific_index=associated_station_index,
            permutate=True
        )
        beam_pos_simulator = beam_pos_simulator.T # to get (3, N)

        self.beam_pos = beam_pos_simulator

    def add_beam(self, simulator_phi, simulator_theta):
        if len(self.beams_list) != 0:
            # NOTE: DANGEROUS BEHAVIOR
            # TODO: make this more obvious to the user OR integrate with other parts
            return

        self.beams_list.append((simulator_phi, simulator_theta))
        self.beam_phi = simulator_phi
        self.beam_theta = simulator_theta

    def get_beam_weight(self):
        assert len(self.beams_list) == 1
        if self.calculated_beam_w is not None:
            return self.calculated_beam_w

        pointn_vec = np.array(polar_to_cartesian(1, self.beam_phi, self.beam_theta))
        assert pointn_vec.shape == (3,)
        beam_w = ExpLut.get(
            -1 * self.wavenumber * self.beam_pos.T @ pointn_vec
        )
        # beam_w = np.exp(
        #     -1j * self.wavenumber * self.beam_pos.T @ pointn_vec
        # )

        if self.taper_fn is not None:
            ##### Simulator global -> ENU
            assert pointn_vec.shape == (3,)

            global_pointn = pointn_vec
            enu = self.sat_geom._vec_global2local(
                global_pointn, translate=False,
                specific_index=self.associated_station_index
            )
            enu = enu.T
            # TODO: use rigid body frame for correct fixed axis pointing
            # NOTE: using ENU as reference means the antenna rotates along orbit
            # ENU to local (down, west, north)
            # x = -z; y = -x; z = y
            local = (-enu[2], -enu[0], enu[1])

            _, phi_local, theta_local = cartesian_to_polar(
                local[0],
                local[1],
                local[2],
            )

            # however, the azimuth we really want to consider is angle
            # from the line perpendicular to antenna plane
            # which is y axis, pointing down and 90deg away from
            antenna_off_azim = phi_local
            antenna_off_elev = theta_local

            # pases azim and elev in local coords
            taper = self.taper_fn(antenna_off_azim, antenna_off_elev)
        else:
            taper = 1

        beam_w_taper = taper * beam_w

        # using less bits on complex for better performance
        self.calculated_beam_w = beam_w_taper.astype(np.complex64)

        return self.calculated_beam_w

    def calculate_gain(self, **kwargs):
        """
        phi_vec (np.array): azimuth angles [degrees]
        theta_vec (np.array): elevation angles [degrees]
        """
        # (M,)
        phi = kwargs["phi_vec"]
        # (M,)
        theta = kwargs["theta_vec"]

        lingain = self.lingain
        beam_w_taper = self.get_beam_weight()

        directions = np.stack(polar_to_cartesian(
            np.ones_like(theta),
            phi,
            theta,
        ))

        phase = ExpLut.get(
            self.wavenumber * self.beam_pos.T @ directions
        )
        # phase = np.exp(
        #     1j * self.wavenumber * self.beam_pos.T @ directions
        # )
        AF = lingain * (beam_w_taper @ phase)

        # Normalize and convert to dB
        AF_mag = np.abs(AF)
        AF_dB = 20 * np.log10(AF_mag + 1e-12)

        return AF_dB


if __name__ == "__main__":
    # victim_geoms = SimulatorGeometry(1000)
    victim_geoms = SimulatorGeometry(1)
    target_geom = SimulatorGeometry(1)
    target_geom.set_global_coords(
        np.array([0.]),
        np.array([0.]),
        np.array([0.]),
    )
    victim_geoms.set_global_coords(
        np.array([0.]),
        np.array([0.]),
        np.array([0.]),
    )

    # aligning ECEF and ENU
    global_lla = (-90., 90., 0.)
    ##########################################################
    # what the satellite needs to do:
    sat_geom = SimulatorGeometry(
        1, True, global_cs=global_lla
    )

    # in GLOBAL coordinates
    # e.g. if we have satellite right above the global reference, then that
    # antenna will be pointing downwards
    # and beamforming pointing forwards is globally pointing dowards
    # WE CAN ALSO ALIGN LOCAL TO GLOBAL
    sat_geom.set_local_coord_sys(
        np.array([0.]),
        np.array([0.]),
        np.array([0.]),
    )
    local = np.array([1, 2, 3])
    enu = np.stack((-local[1], local[2], -local[0]))
    glob = sat_geom._vec_local2global(np.array([enu]), translate=False)

    sat_geom.set_local_coords(
        np.array([0.]),
        np.array([0.]),
        np.array([5e3]),
        np.array([0.]),
        np.array([-90.]), # pointing at nadir
    )
    local = np.array([1, 2, 3])
    enu = np.stack((-local[1], local[2], -local[0]))
    glob = sat_geom._vec_local2global(np.array([enu]), translate=False)

    # target_azim, target_elev = 180., 0.
    # target_azim, target_elev = 0., 0.
    target_azim, target_elev = sat_geom.pointn_azim_global[0], sat_geom.pointn_elev_global[0]

    # print("sat_geom.pointn_azim_global", sat_geom.pointn_azim_global)
    # print("sat_geom.pointn_elev_global", sat_geom.pointn_elev_global)

    fc = 890 # MHz
    from sharc.antenna.ast import maxNx, maxNy, dx, dy, lingain

    antenna = AntennaBeamformingSatellite(
        sat_geom, 0,
        maxNx, maxNy, dx, dy,
        fc,
        lingain,
        taper_fn=get_weights_2
    )
    antenna.add_beam(
        target_azim,
        target_elev,
    )
    ##########################################################

    resolution = 0.5
    theta = np.arange(-90., 90. + resolution, resolution)
    phi = np.zeros_like(theta)
    gains = antenna.calculate_gain(
        phi_vec=phi,
        theta_vec=theta
    )
    # theta_lut = np.linspace(-90., 90., 361)
    from sharc.antenna.ast import E_pattern_data, H_pattern_data
    plt.figure(figsize=(10, 6))
    plt.plot(theta, gains, label='Array Factor')
    plt.plot((theta), E_pattern_data, label='Reference E-Pattern')
    plt.axvline(x=target_elev, color='r', linestyle='--', label=f'Target Elevation ({target_elev}°)')
    plt.xlabel('Theta (degrees)')
    plt.ylabel('Magnitude (dB)')
    plt.title('Array Factor')
    plt.legend()
    plt.grid(True)
    # plt.show()

    phi = np.linspace(-90., +90., 361)

    theta = np.zeros_like(phi)
    gains = antenna.calculate_gain(
        phi_vec=phi,
        theta_vec=theta
    )

    plt.figure(figsize=(10, 6))
    plt.plot(phi, gains, label='Array Factor')
    plt.plot((phi), H_pattern_data, label='Reference H-Pattern')
    plt.axvline(x=target_azim, color='r', linestyle='--', label=f'Target Azimuth ({target_azim}°)')
    plt.xlabel('Phi (degrees)')
    plt.ylabel('Magnitude (dB)')
    plt.title('Array Factor')
    plt.legend()
    plt.grid(True)
    plt.show()
