# -*- coding: utf-8 -*-
"""
IMT BS gain-probability map toward a victim point, using Monte Carlo beam
sampling with the SHARC beamforming antenna model.

Main goals
----------
1. Compute the gain samples / CCDF of each IMT BS toward a victim direction.
2. Build spatial maps such as:
   - probability that gain exceeds G_th
   - percentile gain map (e.g. 95th, 99th)
   - mean gain map

This is the first step before a full GVD / France-like study, where the gain
CCDF is later combined with the interference model.

Author: OpenAI
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import matplotlib.pyplot as plt

from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt


# =============================================================================
# Helper data structures
# =============================================================================

@dataclass
class VictimPoint:
    x_m: float
    y_m: float
    z_m: float
    name: str = "victim"


@dataclass
class BaseStationSet:
    """
    Minimal BS container for this study.
    You can adapt this wrapper to your existing StationManager / topology object.
    """
    x_m: np.ndarray
    y_m: np.ndarray
    z_m: np.ndarray
    azimuth_deg: np.ndarray   # physical azimuth of each BS sector
    elevation_deg: np.ndarray # physical elevation reference of antenna object
    names: Optional[List[str]] = None

    def __len__(self) -> int:
        return len(self.x_m)


# =============================================================================
# Main class
# =============================================================================

class ImtGainProbabilityMap:
    """
    Compute gain samples and probability maps for IMT BSs toward a victim point.
    """

    def __init__(
        self,
        antenna_param: ParametersAntennaImt,
        bs_load_probability: float = 0.5,
        rng_seed: int = 12345,
    ):
        self.antenna_param = antenna_param
        self.bs_load_probability = float(bs_load_probability)
        self.rng = np.random.RandomState(rng_seed)

        if not (0.0 <= self.bs_load_probability <= 1.0):
            raise ValueError("bs_load_probability must be in [0, 1].")

    # -------------------------------------------------------------------------
    # Geometry helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _wrap_to_180(angle_deg: np.ndarray) -> np.ndarray:
        return (angle_deg + 180.0) % 360.0 - 180.0

    @staticmethod
    def _global_phi_theta_from_bs_to_target(
        bs_x: np.ndarray,
        bs_y: np.ndarray,
        bs_z: np.ndarray,
        tx_x: np.ndarray,
        tx_y: np.ndarray,
        tx_z: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Returns:
            phi_deg   : azimuth in global frame, [-180, 180]
            theta_deg : theta in SHARC/global spherical convention, [0, 180],
                        with 90 at horizon, <90 above horizon, >90 below horizon
            distance_m
        """
        dx = tx_x - bs_x
        dy = tx_y - bs_y
        dz = tx_z - bs_z

        d_h = np.sqrt(dx**2 + dy**2)
        d_3d = np.sqrt(dx**2 + dy**2 + dz**2)

        phi_deg = np.degrees(np.arctan2(dy, dx))

        # elevation angle relative to local horizontal
        elev_deg = np.degrees(np.arctan2(dz, np.maximum(d_h, 1e-9)))

        # Convert to theta with 90 = horizon, 0 = zenith, 180 = nadir
        theta_deg = 90.0 - elev_deg

        return phi_deg, theta_deg, d_3d

    # -------------------------------------------------------------------------
    # Sampling helpers
    # -------------------------------------------------------------------------
    def _sample_beam_pointing_angles(
        self,
        n_samples: int,
        phi_center_deg: float,
        theta_center_deg: float,
        horiz_range_deg: float = 60.0,
        vert_range_deg: Tuple[float, float] = (90.0, 100.0),
        vertical_limit_deg: Optional[float] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Monte Carlo beam-pointing sampling.

        Interpretation:
        - horizontal steering is sampled around the sector boresight
        - vertical steering is sampled inside the allowed coverage range
        - optionally, impose a hard lower pointing limit such as -10 deg
          relative to horizontal, which corresponds to theta <= 100 deg

        Parameters
        ----------
        phi_center_deg : sector boresight azimuth
        theta_center_deg : usually not used as center; kept for future extension
        horiz_range_deg : half-range, e.g. 60 => [-60, +60]
        vert_range_deg  : global theta range, e.g. (90, 100)
        vertical_limit_deg : if set to -10, lower limit becomes theta <= 100 deg
        """
        # Horizontal beam steering around sector azimuth
        phi_s = phi_center_deg + self.rng.uniform(
            low=-horiz_range_deg,
            high=+horiz_range_deg,
            size=n_samples,
        )

        theta_min, theta_max = vert_range_deg

        # Example: vertical_limit_deg = -10 means max down-pointing 10 deg below
        # horizon -> theta <= 100
        if vertical_limit_deg is not None:
            theta_limit = 90.0 - vertical_limit_deg
            theta_max = min(theta_max, theta_limit)

        theta_s = self.rng.uniform(
            low=theta_min,
            high=theta_max,
            size=n_samples,
        )

        return phi_s, theta_s

    def _sample_load_mask(self, n_samples: int) -> np.ndarray:
        """
        Bernoulli activity mask. If BS inactive, contribution can be suppressed.
        """
        return self.rng.rand(n_samples) < self.bs_load_probability

    # -------------------------------------------------------------------------
    # Antenna helpers
    # -------------------------------------------------------------------------
    def _build_bs_antenna(
        self,
        physical_azimuth_deg: float,
        physical_elevation_deg: float = 0.0,
    ) -> AntennaBeamformingImt:
        par = self.antenna_param.get_antenna_parameters()
        ant = AntennaBeamformingImt(
            par=par,
            azimuth=physical_azimuth_deg,
            elevation=physical_elevation_deg,
        )
        ant.reset_beams()
        return ant

    def _gain_samples_toward_direction(
        self,
        antenna: AntennaBeamformingImt,
        victim_phi_deg: float,
        victim_theta_deg: float,
        beam_phi_samples_deg: np.ndarray,
        beam_theta_samples_deg: np.ndarray,
        load_mask: Optional[np.ndarray] = None,
        inactive_gain_db: float = -200.0,
    ) -> np.ndarray:
        """
        For each sampled beam, compute BS array gain in the fixed victim direction.
        """
        n_samples = len(beam_phi_samples_deg)
        antenna.reset_beams()

        for phi_b, theta_b in zip(beam_phi_samples_deg, beam_theta_samples_deg):
            antenna.add_beam(phi_b, theta_b)

        gains = antenna.calculate_gain(
            phi_vec=np.full(n_samples, victim_phi_deg, dtype=float),
            theta_vec=np.full(n_samples, victim_theta_deg, dtype=float),
            beams_l=np.arange(n_samples, dtype=int),
            co_channel=True,
        )

        if load_mask is not None:
            gains = np.where(load_mask, gains, inactive_gain_db)

        return gains

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def compute_gain_statistics_for_bs_set(
        self,
        bs_set: BaseStationSet,
        victim: VictimPoint,
        n_samples: int = 2000,
        horiz_range_deg: float = 60.0,
        vert_range_deg: Tuple[float, float] = (90.0, 100.0),
        vertical_limit_deg: Optional[float] = -10.0,
        gain_threshold_db: float = 10.0,
        percentile_list: Tuple[float, ...] = (50.0, 90.0, 95.0, 99.0),
    ) -> Dict[str, Any]:
        """
        Returns per-BS statistics of gain toward the victim.
        """
        n_bs = len(bs_set)

        mean_gain_db = np.zeros(n_bs, dtype=float)
        prob_exceed = np.zeros(n_bs, dtype=float)
        victim_phi_deg = np.zeros(n_bs, dtype=float)
        victim_theta_deg = np.zeros(n_bs, dtype=float)
        distance_km = np.zeros(n_bs, dtype=float)

        percentile_maps = {
            p: np.zeros(n_bs, dtype=float) for p in percentile_list
        }

        gain_samples_all = []

        phi_v, theta_v, d_m = self._global_phi_theta_from_bs_to_target(
            bs_set.x_m, bs_set.y_m, bs_set.z_m,
            victim.x_m, victim.y_m, victim.z_m
        )

        for i in range(n_bs):
            victim_phi_deg[i] = phi_v[i]
            victim_theta_deg[i] = theta_v[i]
            distance_km[i] = d_m[i] / 1000.0

            ant = self._build_bs_antenna(
                physical_azimuth_deg=float(bs_set.azimuth_deg[i]),
                physical_elevation_deg=float(bs_set.elevation_deg[i]),
            )

            beam_phi_s, beam_theta_s = self._sample_beam_pointing_angles(
                n_samples=n_samples,
                phi_center_deg=float(bs_set.azimuth_deg[i]),
                theta_center_deg=90.0,
                horiz_range_deg=horiz_range_deg,
                vert_range_deg=vert_range_deg,
                vertical_limit_deg=vertical_limit_deg,
            )

            load_mask = self._sample_load_mask(n_samples)

            g_s = self._gain_samples_toward_direction(
                antenna=ant,
                victim_phi_deg=float(victim_phi_deg[i]),
                victim_theta_deg=float(victim_theta_deg[i]),
                beam_phi_samples_deg=beam_phi_s,
                beam_theta_samples_deg=beam_theta_s,
                load_mask=load_mask,
                inactive_gain_db=self.antenna_param.minimum_array_gain,
            )

            gain_samples_all.append(g_s)
            mean_gain_db[i] = np.mean(g_s)
            prob_exceed[i] = np.mean(g_s > gain_threshold_db)

            for p in percentile_list:
                percentile_maps[p][i] = np.percentile(g_s, p)

        return {
            "victim_phi_deg": victim_phi_deg,
            "victim_theta_deg": victim_theta_deg,
            "distance_km": distance_km,
            "mean_gain_db": mean_gain_db,
            "prob_exceed": prob_exceed,
            "percentiles_db": percentile_maps,
            "gain_samples_db": gain_samples_all,
            "gain_threshold_db": gain_threshold_db,
            "victim": victim,
        }

    def plot_bs_probability_map(
        self,
        bs_set: BaseStationSet,
        stat_values: np.ndarray,
        victim: VictimPoint,
        title: str,
        cbar_label: str,
        terrain_extent: Optional[Tuple[float, float, float, float]] = None,
        terrain_image: Optional[np.ndarray] = None,
        figsize: Tuple[float, float] = (10, 8),
        save_path: Optional[str] = None,
    ):
        """
        Scatter map of BS positions over optional terrain raster.
        terrain_extent = (xmin, xmax, ymin, ymax)
        """
        fig, ax = plt.subplots(figsize=figsize)

        if terrain_image is not None and terrain_extent is not None:
            ax.imshow(
                terrain_image,
                extent=terrain_extent,
                origin="upper",
                alpha=0.75,
                cmap="terrain",
            )

        sc = ax.scatter(
            bs_set.x_m / 1000.0,
            bs_set.y_m / 1000.0,
            c=stat_values,
            s=35,
            edgecolors="k",
        )

        ax.scatter(
            victim.x_m / 1000.0,
            victim.y_m / 1000.0,
            marker="*",
            s=250,
            edgecolors="k",
            label=victim.name,
        )

        ax.set_xlabel("x [km]")
        ax.set_ylabel("y [km]")
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend()

        cb = plt.colorbar(sc, ax=ax)
        cb.set_label(cbar_label)

        if save_path is not None:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")

        return fig, ax

    def plot_gain_ccdf(
        self,
        gain_samples_db: np.ndarray,
        title: str = "Gain CCDF toward victim",
        save_path: Optional[str] = None,
    ):
        """
        Plot CCDF for one BS.
        """
        x = np.sort(gain_samples_db)
        n = len(x)
        ccdf = 1.0 - np.arange(1, n + 1) / n

        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(x, ccdf)
        ax.set_xlabel("Gain toward victim [dBi]")
        ax.set_ylabel("CCDF = P(G > g)")
        ax.set_yscale("log")
        ax.grid(True, which="both", alpha=0.3)
        ax.set_title(title)

        if save_path is not None:
            fig.savefig(save_path, dpi=200, bbox_inches="tight")

        return fig, ax
    
    import numpy as np
import matplotlib.pyplot as plt
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt


def generate_gain_ccdf_heatmap(antenna_param, path_test, n_samples=10000):

    ant = AntennaBeamformingImt(
        par=antenna_param.get_antenna_parameters(),
        azimuth=0,
        elevation=0
    )

    elev_angles = np.arange(0, 90, 1)  # 0–90°
    prob = np.logspace(-2, 2, 120)     # 0.01% → 100%

    gain_map = np.zeros((len(prob), len(elev_angles)))

    rng = np.random.RandomState(42)

    for i, theta in enumerate(elev_angles):

        ant.reset_beams()

        # Monte Carlo beam steering
        phi_beams = rng.uniform(-60, 60, n_samples)
        theta_beams = rng.uniform(90, 100, n_samples)

        for p, t in zip(phi_beams, theta_beams):
            ant.add_beam(p, t)

        gains = ant.calculate_gain(
            phi_vec=np.zeros(n_samples),
            theta_vec=np.full(n_samples, theta),
            beams_l=np.arange(n_samples),
            co_channel=True
        )

        gains = np.sort(gains)

        for j, p in enumerate(prob):

            idx = int((1 - p/100.0) * (n_samples - 1))
            idx = np.clip(idx, 0, n_samples-1)

            gain_map[j, i] = gains[idx]

    # plot
    fig, ax = plt.subplots(figsize=(9,6))

    im = ax.imshow(
        gain_map,
        extent=[0, 90, prob[0], prob[-1]],
        origin="lower",
        aspect='auto',
        cmap='viridis',
        vmin=-50,
        vmax=22
    )

    ax.set_yscale("log")

    ax.set_xlabel("Elevation angle in °")
    ax.set_ylabel("Probability to exceed gain in %")

    cbar = plt.colorbar(im)
    cbar.set_label("Gain (dBi)")

    plt.tight_layout()
    plt.savefig(path_test / "imt_gain_ccdf_heatmap.png", dpi=300)

    return gain_map