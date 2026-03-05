from sharc.antenna.antenna import Antenna
import matplotlib.pyplot as plt
from sharc.parameters.antenna.parameters_antenna_cosecant_squared import (
    ParametersAntennaCosecantSquared
)
import numpy as np


class AntennaCosecantSquared(Antenna):
    def __init__(
        self,
        par: ParametersAntennaCosecantSquared,
        azim: float, elevation: float
    ):
        self.par = par
        self.theta_tilt_deg = elevation
        self.theta_tilt_rad = np.deg2rad(elevation)
        self.azimuth_rad = np.deg2rad(azim)

    def _calculate_elev_gain(self, theta_rad: np.ndarray):
        # floor already fills everything, we can skip first interval
        g = np.full_like(theta_rad, self.par.floor_gain_db, dtype=float)
        theta_null = np.deg2rad(self.par.theta_null(self.theta_tilt_deg))
        theta_start = np.deg2rad(self.par.theta_start(self.theta_tilt_deg))
        theta_end = np.deg2rad(self.par.theta_end)
        theta_tilt = self.theta_tilt_rad

        theta_3db_deg = self.par.elevation_beamwidth_3db

        # sin(x)/x pattern in main beam
        th_unif_mask = (theta_rad > theta_null) & (theta_rad <= theta_start)
        th_unif = theta_rad[th_unif_mask]
        mu = (np.pi * 50.8 * np.sin(th_unif - theta_tilt)) / theta_3db_deg
        g[th_unif_mask] = 20 * np.log10(np.sinc(mu / np.pi))

        # csc^2 pattern from start to end
        th_csc_mask = (theta_rad > theta_start) & (theta_rad <= theta_end)
        th_csc = theta_rad[th_csc_mask]
        mu_start = (
            np.pi * 50.8 * np.sin(theta_start - theta_tilt)
        ) / theta_3db_deg
        g[th_csc_mask] = (
            20 * np.log10(np.sin(theta_start) / np.sin(th_csc))
            + 20 * np.log10(np.sinc(mu_start / np.pi))
        )

        return np.maximum(g, self.par.floor_gain_db)

    def _calculate_azim_gain(self, phi_rad):
        # return 0
        bw = self.par.azim_beamwidth_3db
        phi_rad = np.atleast_1d(phi_rad - self.azimuth_rad)
        return -np.minimum(12 * (phi_rad / np.deg2rad(bw))**2, -self.par.floor_gain_db)

        # mu = (np.pi * 50.8 * np.sin(phi_rad)) / bw

        # g = 20 * np.log10(np.sinc(mu / np.pi))

        # return np.maximum(g, self.par.floor_gain_db)

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """Calculates the antenna gain.

        Parameters
        ----------
        phi_vec : np.ndarray
            Azimuth angles [degrees] in global coordinate system.
        theta_vec : np.ndarray
            Elevation angles [degrees] in global coordinate system.
        """
        phi_vec = np.deg2rad(np.atleast_1d(kwargs["phi_vec"]))
        # local coords theta
        theta_vec = np.deg2rad(90 - np.atleast_1d(kwargs["theta_vec"]))

        return (
            self.par.antenna_gain
            + self._calculate_elev_gain(theta_vec)
            + self._calculate_azim_gain(phi_vec)
        )


if __name__ == "__main__":
    par = ParametersAntennaCosecantSquared(
        elevation_beamwidth_3db=4.8,
        azim_beamwidth_3db=1.35,
        antenna_gain=33.5,
        theta_end=30.,
        floor_gain_db=-55.,
    )
    ant = AntennaCosecantSquared(par, 0, 2.)

    fig = plt.figure(figsize=(10, 6))
    ax1 = fig.add_subplot(111)

    # gain = antenna._element_gain(
    #     phi,
    #     theta_scan,
    # )

    # beam/electrical tilt in spherical coords
    # phi is azim
    phi_escan = 0
    # theta is elev
    theta_tilt = 90

    import numpy as np
    import plotly.graph_objects as go

    # Step 1: Create phi and theta grids
    phi = np.linspace(-180, 180, 360)  # azimuth in degrees
    theta = np.linspace(-90, 90, 180)   # elevation in degrees
    phi_grid, theta_grid = np.meshgrid(phi, theta)

    # Step 2: Convert to radians for math
    phi_rad = np.radians(phi_grid)
    theta_rad = np.radians(theta_grid)

    # Step 3: Simulate or call antenna gain function
    # Replace this with your actual function
    # def dummy_gain(phi_deg, theta_deg):
    # return np.abs(np.cos(np.radians(theta_deg))) *
    # np.abs(np.cos(np.radians(phi_deg)))

    # gain = dummy_gain(phi_grid, theta_grid)
    gain = ant.calculate_gain(
        phi_vec=np.ravel(phi_grid),
        theta_vec=90 - np.ravel(theta_grid),
        beams_l=np.zeros_like(np.ravel(phi_grid), dtype=int),
    )
    gain = np.reshape(gain, phi_grid.shape)

    default_surface_config = dict(
        colorscale='Turbo',
        # colorscale='Viridis',
        # colorscale='Jet',
        colorbar=dict(title='Gain [dB]'),
        # colorbar=None,
        showscale=False,
        # colorbar range
        cmin=-80,
        cmax=30,
        # to remove light from changing the truecolors:
        lighting=dict(
            ambient=1.0,
            diffuse=0.0,
            specular=0.0,
            roughness=1.0,
            fresnel=0.0
        ),
        lightposition=dict(
            x=0,
            y=0,
            z=0
        ),
    )
    if True:
        heat_surface = go.Surface(
            x=phi_grid,
            y=theta_grid,
            z=gain,
            # z=np.power(10, 0.1*gain),
            surfacecolor=gain,          # color mapped to gain
            **default_surface_config,
        )
        # Create wireframe lines manually
        grid_lines = []

        # Horizontal (theta constant)
        for i in range(0, theta_grid.shape[0], 2):
            grid_lines.append(go.Scatter3d(
                x=phi_grid[i, :],
                y=theta_grid[i, :],
                z=gain[i, :],
                mode='lines',
                line=dict(color='black', width=1),
                showlegend=False
            ))

        # Vertical (phi constant)
        for j in range(0, phi_grid.shape[1], 2):
            grid_lines.append(go.Scatter3d(
                x=phi_grid[:, j],
                y=theta_grid[:, j],
                z=gain[:, j],
                mode='lines',
                line=dict(color='black', width=1),
                showlegend=False
            ))

        # Combine surface and wireframe
        fig = go.Figure(data=[heat_surface] + grid_lines)

        fig.update_layout(
            title='',
            scene=dict(
                xaxis_title='Azimuth φ [deg]',
                yaxis_title='Elevation θ [deg]',
                zaxis_title='Gain',
                xaxis=dict(dtick=50, range=[-200, 200]),
                yaxis=dict(dtick=20, range=[-100, 100]),
                # zaxis=dict(nticks=5, range=[-60, 30]),
                zaxis=dict(
                           # showticklabels=False,
                           dtick=10,
                           title='',
                           range=[-80, 30]),  # clean look
                aspectratio=dict(x=1,y=4/5,z=4/5),
                camera=dict(
                    # projection=dict(type="perspective"),
                    eye=dict(x=-1.2, y=-1.2, z=0.5),
                )
            ),
            # margin=dict(l=0, r=0, t=50, b=0),
            # width=500,
            # height=500
        )
        fig.show()

# th = (0,180)
# nth = 90 - th # (90, -90)
    theta_scan = np.linspace(0., 180., num=360)
    phi = np.zeros_like(theta_scan)

    gain = ant.calculate_gain(
        phi_vec=phi,
        theta_vec=theta_scan,
        beams_l=np.zeros_like(theta_scan),
    )
    # fig = plt.figure(figsize=(15, 5), facecolor='w', edgecolor='k')

    ax1.plot(90 - theta_scan, gain)
    top_y_lim2 = np.ceil(np.max(gain) / 10) * 10
    # top_y_lim2 = np.maximum(top_y_lim1, top_y_lim2)

    ax1.set_xlim(-10, 40.)
    ax1.set_ylim(-30, 40)
    ax1.grid(True)
    ax1.set_xlabel(r"$\vartheta$ [deg]")
    ax1.set_ylabel("Gain [dBi]")

    plt.show()
