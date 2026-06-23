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
# Estimated from 20x50 km radials around Campinas-SP (-22.9049, -47.0603),
# sampled at 1 km (terrain-scale extrema, comparable to 5D/1059).
CAMPINAS_TERRAIN = {
    "height_sigma_m": 39.04,
    "height_nu": 4.197,
    "dist_mu": 0.4268,      # underlying-normal mean of ln(distance/km)
    "dist_sigma": 0.5237,   # underlying-normal std (median 1.53 km, mode 1.17 km)
}
# Distance-dependent clutter fitted from REAL land use (ESA WorldCover) along
# 20x50 km radials around Campinas-SP. The deterministic trend is an
# exponential-with-floor fitted to the MEAN clutter height vs distance
# (R^2 = 0.98): f(d) = C + (A - C) * exp(-d / d0_km); the random spread is a
# multiplicative lognormal of log-std `sigma`. With target="mean" the model's
# mean equals f(d) (mean 22.7 m at the centre decaying to a ~7.9 m rural floor).
CAMPINAS_CLUTTER = {
    "trend_A": 22.68,        # mean clutter height at the cluster centre (m)
    "trend_C": 7.90,         # rural floor mean clutter height (m)
    "trend_d0_km": 5.97,     # decay scale (km)
    "clutter_sigma": 1.238,  # log-std of the multiplicative spread
    "target": "mean",
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
    """Distance-dependent statistical clutter-over-terrain model.

    Decomposes the representative clutter height ``R`` (m) into a deterministic
    distance trend times a multiplicative lognormal spread:

        R(d) = f(d) * exp( N(0, sigma) ) / k        (k normalises to the target)
        f(d) = C + (A - C) * exp(-d / d0)

    where ``d`` (km) is the terminal's distance from the IMT cluster centre. The
    exponential-with-floor trend ``f(d)`` is fitted to the clutter height vs
    distance from real land cover; ``A`` is the central value, ``C`` the rural
    floor and ``d0`` the decay scale. ``target`` selects whether ``f(d)`` is the
    mean (``"mean"``) or the median (``"median"``) of ``R(d)``.

    Implemented as a lognormal with location ``mu_ln(d) = ln f(d) - off``, where
    ``off = sigma^2/2`` for ``target="mean"`` (so the mean equals ``f(d)``) and
    ``off = 0`` for ``target="median"``.

    Parameters
    ----------
    trend_A, trend_C, trend_d0_km : float
        Central value, rural floor and decay scale (km) of the trend ``f(d)``.
    clutter_sigma : float
        log-std of the multiplicative lognormal spread.
    target : str
        ``"mean"`` or ``"median"`` -- which statistic of ``R(d)`` equals ``f(d)``.
    """

    def __init__(
        self,
        trend_A: float = CAMPINAS_CLUTTER["trend_A"],
        trend_C: float = CAMPINAS_CLUTTER["trend_C"],
        trend_d0_km: float = CAMPINAS_CLUTTER["trend_d0_km"],
        clutter_sigma: float = CAMPINAS_CLUTTER["clutter_sigma"],
        target: str = CAMPINAS_CLUTTER["target"],
    ):
        self.trend_A = float(trend_A)
        self.trend_C = float(trend_C)
        self.trend_d0_km = float(trend_d0_km)
        self.clutter_sigma = float(clutter_sigma)
        self.target = str(target).lower()

    def trend_m(self, distance_km=0.0):
        """Deterministic trend f(d) (m): exponential decay to the rural floor."""
        d = np.asarray(distance_km, dtype=float)
        return self.trend_C + (self.trend_A - self.trend_C) * np.exp(-d / self.trend_d0_km)

    def _mu(self, distance_km):
        """ln-location of the lognormal at a given distance (km)."""
        f = np.maximum(self.trend_m(distance_km), 1e-3)
        off = 0.5 * self.clutter_sigma ** 2 if self.target == "mean" else 0.0
        return np.log(f) - off

    def sample(self, rng: np.random.RandomState, distance_km=0.0, size=None):
        """Draw representative clutter height(s) (m) at a distance from the centre."""
        return np.exp(rng.normal(self._mu(distance_km), self.clutter_sigma, size=size))

    def mean_m(self, distance_km=0.0):
        """Mean clutter height (m) at a distance from the centre."""
        return float(np.exp(self._mu(distance_km) + 0.5 * self.clutter_sigma ** 2))

    def median_m(self, distance_km=0.0):
        """Median clutter height (m) at a distance from the centre."""
        return float(np.exp(self._mu(distance_km)))
