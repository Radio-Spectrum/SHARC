"""Ray evaluation and protection contour of a site.

``ContourCalculator`` ties together the site, the terrain region, the link budget, the P.452 loss, the land domain of
the rays and the height of the reference base station. Nothing in it belongs to one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from sharc.contour import geometry, horizon, search
from sharc.contour.budget import Budget
from sharc.contour.domain import Domain
from sharc.contour.link import P452Link
from sharc.contour.region import Region
from sharc.contour.site import RasSite


@dataclass(frozen=True)
class Sweep:
    """Distances along a ray: from `d_min_m` to `d_max_m` in steps of `step_m` (also the grid of the contour search)."""
    step_m: float = 50.0
    d_min_m: float = 100.0
    d_max_m: float = 600000.0
    tol_m: float = 1.0


class NoTerrainData(Exception):
    """A terrain profile touches a pixel without data (carries the distance of the point)."""

    def __init__(self, distance_m: float):
        super().__init__(f"terrain profile without data at {distance_m:.0f} m")
        self.distance_m = float(distance_m)


class ContourCalculator:
    def __init__(self, budget: Budget, region: Region, p452: Optional[dict], height_fn: Callable[[float], float],
                 propagation_frequency_mhz: float = 3500.0, domain: Optional[Domain] = None, sweep: Sweep = Sweep()):
        self.budget, self.site = budget, budget.site
        self.link = P452Link(budget.site, region, p452, propagation_frequency_mhz)
        self.height_fn = height_fn
        self._terms_cache: Dict[tuple, Dict[str, object]] = {}
        self.sweep = sweep
        self.domain = domain or Domain(region.terrain, region.zones)
        self.ae_km = horizon.effective_earth_radius_km(float(self.link.params.delta_N))

    # ----------------------------------------------------------------- rays
    def ray_end(self, az_enu: float):
        """(last valid distance [m], reason) of the ray."""
        s = self.sweep
        return self.domain.ray_end(self.site.lat_deg, self.site.lon_deg, az_enu, s.d_max_m, s.step_m)

    def evaluate(self, az_enu: float, d_m, heights_m, off_axis_deg: Sequence[float]) -> Dict[str, np.ndarray]:
        """Margin of the reference base station at the distances `d_m` [m] of the ray with ENU azimuth `az_enu`.

        Returns arrays; ``margin_db_<off>`` > 0 means the criterion is not met. The gains are taken along the straight
        line between the antennas (``geometric``) and along the P.452 horizon directions (``horizon_margin_db_<off>``)."""
        d_m, heights_m = np.asarray(d_m, float), np.asarray(heights_m, float)
        if heights_m.shape != d_m.shape or not np.all(np.isfinite(heights_m)) or np.any(heights_m <= 0):
            raise ValueError("invalid base station heights (one per distance, finite and > 0)")
        lat, lon = geometry.points_on_ray(self.site.lat_deg, self.site.lon_deg, az_enu, d_m)
        n = d_m.size
        loss, ground, d_profile = np.empty(n), np.empty(n), np.empty(n)
        el_station, el_bs = np.empty(n), np.empty(n)
        cut_at = None
        for i in range(n):
            try:                       # a profile can still touch an empty pixel near the terrain edge: cut the ray there
                dist_km, elev, with_clutter, zone = self.link.profiles.profile(self.site.lat_deg, self.site.lon_deg,
                                                                               lat[i], lon[i])
            except ValueError as exc:
                if "without data" not in str(exc) or i == 0:
                    raise
                cut_at, n = float(d_m[i]), i
                break
            loss[i], ground[i] = self.link.loss_db(lat[i], lon[i], heights_m[i])
            d_profile[i] = dist_km[-1]
            el_station[i], el_bs[i] = horizon.path_angles_deg(dist_km, elev, self.site.height_m, heights_m[i], self.ae_km)
        out = {"d_m": d_m[:n], "lat": lat[:n], "lon": lon[:n], "height_m": heights_m[:n], "bs_ground_m": ground[:n],
               "d_profile_km": d_profile[:n], "loss_db": loss[:n], "el_station_horizon_deg": el_station[:n],
               "el_bs_horizon_deg": el_bs[:n], "cut_at_m": cut_at}
        if n == 0:
            return out
        phi_r, theta_r, phi_b, theta_b = self.budget.directions(lat[:n], lon[:n], heights_m[:n], ground[:n],
                                                                self.link.ground_m)
        g_station, psi = self.budget.station_gain(theta_r)
        g_station_h, _ = self.budget.station_gain(90.0 - el_station[:n])
        out.update(phi_r_deg=phi_r, theta_r_deg=theta_r, phi_b_deg=phi_b, theta_b_deg=theta_b, psi_station_deg=psi,
                   g_station_dbi=g_station)
        for off in off_axis_deg:
            g_bs = self.budget.bs_gain(phi_b, theta_b, off)
            out[f"g_bs_dbi_{off:g}"] = g_bs
            out[f"margin_db_{off:g}"] = self.budget.margin_db(loss[:n], g_station, g_bs)
            out[f"horizon_margin_db_{off:g}"] = self.budget.margin_db(
                loss[:n], g_station_h, self.budget.bs_gain(phi_b, 90.0 - el_bs[:n], off))
        return out

    # -------------------------------------------------------------- contour
    @staticmethod
    def contour_from_margins(d_m, margin_db) -> Dict[str, float]:
        """Contour of a ray from its margins on a distance grid: the first distance after the LAST point that does not
        meet the criterion (margin > 0)."""
        d = np.asarray(d_m, float)
        if d.size == 0:
            return {"contour_m": np.nan, "marker": "no_points", "first_met_m": np.nan, "n_sections": 0}
        met = np.asarray(margin_db) <= 0
        bad = np.flatnonzero(~met)
        if bad.size == 0:
            contour, marker = d[0], search.MET_EVERYWHERE
        elif bad[-1] == d.size - 1:
            contour, marker = d[-1], search.NOT_MET_AT_END
        else:
            contour, marker = d[bad[-1] + 1], search.OK
        edges = np.diff(np.concatenate([[0], met.astype(int), [0]]))
        return {"contour_m": float(contour), "marker": marker,
                "first_met_m": float(d[np.argmax(met)]) if met.any() else np.nan, "n_sections": int((edges == 1).sum())}

    # ------------------------------------------------------ one point of a ray, shared by the off-axis angles
    def _terms(self, az_enu: float, d: float) -> Dict[str, object]:
        """Loss and directions at distance `d` of a ray: the part that does not depend on the BS off-axis angle. Cached
        per ray (the search of each off-axis angle visits many of the same distances)."""
        key = (round(float(az_enu), 9), float(d))
        hit = self._terms_cache.get(key)
        if hit is not None:
            return hit
        height = self.height_fn(d)
        lat, lon = geometry.points_on_ray(self.site.lat_deg, self.site.lon_deg, az_enu, d)
        try:
            dist_km, elev, with_clutter, zone = self.link.profiles.profile(self.site.lat_deg, self.site.lon_deg, lat[0], lon[0])
        except ValueError as exc:
            if "without data" in str(exc):
                raise NoTerrainData(d) from exc
            raise
        loss, ground = self.link.loss_from_profile(dist_km, elev, with_clutter, zone, height)
        phi_r, theta_r, phi_b, theta_b = self.budget.directions(lat, lon, [height], [ground], self.link.ground_m)
        g_station, _ = self.budget.station_gain(theta_r)
        terms = {"loss": loss, "g_station": g_station, "phi_b": phi_b, "theta_b": theta_b}
        if len(self._terms_cache) > 4096:
            self._terms_cache.clear()
        self._terms_cache[key] = terms
        return terms

    def margin_at(self, az_enu: float, d: float, off_axis_deg: float) -> float:
        """Margin [dB] (> 0: criterion not met) of the reference BS at distance `d` of a ray; geometric gains."""
        t = self._terms(az_enu, d)
        g_bs = self.budget.bs_gain(t["phi_b"], t["theta_b"], off_axis_deg)
        return float(self.budget.margin_db(t["loss"], t["g_station"], g_bs)[0])

    def contour_distance(self, az_enu: float, off_axis_deg: float, d_end_m: Optional[float] = None) -> Dict[str, float]:
        """Smallest distance that meets the criterion on a ray (see `search.search_ray`), geometric gains.

        When the terrain profile of a point touches an empty pixel (near the edge of the data), the ray is cut there: the
        search runs again up to the last distance that has data, instead of failing the whole campaign."""
        s = self.sweep
        if d_end_m is None:
            d_end_m, _ = self.ray_end(az_enu)
        cut = None
        for _ in range(100):
            try:
                d, marker, n = search.search_ray(lambda d: self.margin_at(az_enu, d, off_axis_deg), d_end_m, s.d_min_m,
                                                 s.step_m, s.tol_m)
                out = {"contour_m": d, "marker": marker, "evaluations": n}
                if cut is not None:
                    out["cut_at_m"] = cut
                return out
            except NoTerrainData as exc:
                cut = d_end_m = max(0.0, exc.distance_m - s.step_m)
                if d_end_m < s.d_min_m:
                    return {"contour_m": float("nan"), "marker": "no_points", "evaluations": 0, "cut_at_m": cut}
        raise RuntimeError("the terrain profile keeps touching empty pixels; the data of this region is too patchy")
