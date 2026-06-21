# -*- coding: utf-8 -*-
"""Statistical terrain and clutter synthesis for the ITU-R P.1812 model.

In a Monte Carlo system simulation the base stations are placed generically, so
a *path-specific* real-terrain profile (e.g. SRTM) is not meaningful. Instead,
following ITU-R WP5D contribution 5D/1059 (Brazilian statistical terrain model),
a **synthetic terrain profile** is generated per snapshot from fitted
distributions and fed to the diffraction model:

* the height deviation of terrain peaks/valleys relative to the local mean line
  follows a **Student's t-distribution** (location 0);
* the horizontal distance between consecutive peaks/valleys follows a
  **lognormal distribution**.

This module also provides a *simple statistical clutter-over-terrain* model:
a representative clutter height drawn from a **lognormal distribution**, which
P.1812 can use at the terminals (representative-clutter height-gain, Section 4.7).

Default parameters are those estimated from 20 radials of 50 km around
Campinas-SP (see ``tools/estimate_terrain_params_campinas.py``). The published
5D/1059 border values are kept as a named reference.
"""
import numpy as np

# --- Parameter sets ----------------------------------------------------------
# Estimated from 20x50 km radials around Campinas-SP (-22.9049, -47.0603)
CAMPINAS_TERRAIN = {
    "height_sigma_m": 36.27,
    "height_nu": 2.93,
    "dist_mu": -0.652,      # underlying-normal mean of ln(distance/km)
    "dist_sigma": 0.720,    # underlying-normal std
}
CAMPINAS_CLUTTER = {
    "clutter_mu": 1.846,    # underlying-normal mean of ln(clutter/m)
    "clutter_sigma": 1.179,
}

# Published reference values from ITU-R WP5D 5D/1059 (Brazilian borders)
BORDER_5D1059_TERRAIN = {
    "height_sigma_m": 24.25,
    "height_nu": 1.525,
    "dist_mu": 1.06,
    "dist_sigma": 0.84,
}


class StatisticalTerrainModel:
    """Synthesize random terrain profiles from fitted height/spacing distributions.

    Parameters
    ----------
    height_sigma_m : float
        Scale (sigma) of the Student's t-distribution of peak/valley height
        deviations (m), relative to the local mean line.
    height_nu : float
        Degrees of freedom (nu) of the Student's t-distribution.
    dist_mu, dist_sigma : float
        Parameters of the lognormal distribution of the horizontal distance
        (km) between consecutive extrema: distance = exp(N(dist_mu, dist_sigma)).
    baseline_m : float, optional
        Constant elevation added to the whole profile (m amsl). Does not affect
        diffraction (both terminals shift equally); default 0.
    smoothing_km : float, optional
        Moving-average length (km) applied to the synthesized profile to emulate
        the roundness of real terrain. Piecewise-linear interpolation between
        random nodes produces knife-edges sharper than real hills, which
        over-predicts diffraction loss; smoothing over ~the terrain correlation
        length removes that bias. Default 1.6 km (calibrated against the real
        Campinas-SP profiles). Set to 0 to disable.
    """

    def __init__(
        self,
        height_sigma_m: float = CAMPINAS_TERRAIN["height_sigma_m"],
        height_nu: float = CAMPINAS_TERRAIN["height_nu"],
        dist_mu: float = CAMPINAS_TERRAIN["dist_mu"],
        dist_sigma: float = CAMPINAS_TERRAIN["dist_sigma"],
        baseline_m: float = 0.0,
        smoothing_km: float = 1.6,
    ):
        self.height_sigma_m = float(height_sigma_m)
        self.height_nu = float(height_nu)
        self.dist_mu = float(dist_mu)
        self.dist_sigma = float(dist_sigma)
        self.baseline_m = float(baseline_m)
        self.smoothing_km = float(smoothing_km)

    def synthesize(self, total_km: float, n_points: int, rng: np.random.RandomState):
        """Generate one synthetic terrain profile over a path of ``total_km``.

        The profile endpoints (the two terminals) lie on the local mean line
        (deviation 0), consistent with the per-segment detrending used to fit
        the model; random peaks/valleys are placed in between.

        Parameters
        ----------
        total_km : float
            Path length (km).
        n_points : int
            Number of equally-spaced samples in the returned profile (>= 4).
        rng : np.random.RandomState
            Random generator (for Monte Carlo reproducibility).

        Returns
        -------
        tuple(np.ndarray, np.ndarray)
            ``(d_km, h_m)`` distance and terrain-height profiles.
        """
        n_points = max(int(n_points), 4)
        total_km = float(total_km)

        # Node positions: cumulative lognormal spacings until the path is covered
        node_d = [0.0]
        pos = 0.0
        # cap iterations defensively
        for _ in range(100000):
            step = float(np.exp(rng.normal(self.dist_mu, self.dist_sigma)))
            step = max(step, 1e-3)
            pos += step
            if pos >= total_km:
                break
            node_d.append(pos)
        node_d.append(total_km)
        node_d = np.array(node_d)

        # Node heights: Student-t deviations; endpoints anchored to mean line (0)
        node_h = self.height_sigma_m * rng.standard_t(self.height_nu, size=node_d.size)
        node_h[0] = 0.0
        node_h[-1] = 0.0

        d_km = np.linspace(0.0, total_km, n_points)
        h_m = np.interp(d_km, node_d, node_h)

        # Smooth to emulate the roundness of real terrain (remove knife-edges)
        if self.smoothing_km > 0 and n_points > 2:
            step = total_km / (n_points - 1)
            win = int(round(self.smoothing_km / step))
            # Cap the window to the profile length; np.convolve(mode="same")
            # would otherwise return an array as long as the (larger) kernel.
            win = min(win, n_points)
            if win > 1:
                kernel = np.ones(win) / win
                h_m = np.convolve(h_m, kernel, mode="same")
                # Re-anchor terminals to the local mean line after smoothing
                h_m[0] = 0.0
                h_m[-1] = 0.0

        return d_km, h_m + self.baseline_m


class StatisticalClutterModel:
    """Simple statistical clutter-over-terrain model (lognormal clutter heights).

    Represents the representative clutter height ``R`` (m) around a terminal as a
    lognormal random variable ``R = exp(N(mu, sigma))``. P.1812 uses ``R`` in the
    representative-clutter height-gain correction (Section 4.7) at each terminal.

    Parameters
    ----------
    clutter_mu, clutter_sigma : float
        Parameters of the underlying normal: clutter_height = exp(N(mu, sigma)).
    """

    def __init__(
        self,
        clutter_mu: float = CAMPINAS_CLUTTER["clutter_mu"],
        clutter_sigma: float = CAMPINAS_CLUTTER["clutter_sigma"],
    ):
        self.clutter_mu = float(clutter_mu)
        self.clutter_sigma = float(clutter_sigma)

    def sample(self, rng: np.random.RandomState, size=None):
        """Draw representative clutter height(s) in metres."""
        return np.exp(rng.normal(self.clutter_mu, self.clutter_sigma, size=size))

    @property
    def mean_m(self):
        """Mean clutter height (m)."""
        return float(np.exp(self.clutter_mu + 0.5 * self.clutter_sigma ** 2))

    @property
    def median_m(self):
        """Median clutter height (m)."""
        return float(np.exp(self.clutter_mu))
