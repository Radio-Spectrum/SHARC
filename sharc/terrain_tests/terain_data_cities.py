#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Global terrain-only paths (300 km, 1 km spacing) using pre-generated 1°x1° tiles (250 m),
fully parallel with streaming histograms + live fit updates.

What this version fixes (per your request):
  - P.452 fit is computed ONLY for the TERRAIN data (even if we plot no-terrain hist too)
  - ALL histograms are normalized to 1 (density=True), so PDF overlays match visually
  - Fig2 has len(DISTANCES_TEST) subfigures dynamically
  - P.452 fit overlay uses the TWO-Gaussian MIXTURE CDF (w1*C1 + w2*C2), plotted in RED on a twin axis

Notes:
  - Histograms are aggregated lock-free via bin counts (workers -> main). For density plots,
    we convert counts -> density in plotting time.
  - Distance/height fits are best distribution (AIC+KS) on a bounded reservoir sample.
"""

import os
import re
import math
import numpy as np
import rasterio
import matplotlib.pyplot as plt
import geopandas as gpd

from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from shapely.geometry import Point as ShapelyPoint
from shapely.prepared import prep
from geopy.point import Point as GeopyPoint
from geopy.distance import distance as geopy_distance
from scipy.signal import find_peaks, savgol_filter
from scipy import stats
from scipy.special import digamma
from scipy.optimize import brentq

# ---- SHARC / P.452
from sharc.propagation.propagation_clear_air_452 import (
    PropagationClearAir,
    generate_terrain_profile,
)
from sharc.parameters.parameters_p452 import ParametersP452


# ============================================================
# CONFIG
# ============================================================
TILES_250_DIR = r"sharc/terrain_tests/global_dem/tiles_250m_tif"
NODATA_I16 = np.int16(-32768)

PATH_LENGTH_KM = 100.0
STEP_KM = 1.0
N_SAMPLES = int(PATH_LENGTH_KM / STEP_KM) + 1  # 301

REGION = "custom"  #"America", "Europe", "Asia", "Africa", "Oceania", "World", "custom"

N_WORKERS = 12
TARGET_PATHS = 1000
INFLIGHT = 4 * N_WORKERS
UPDATE_EVERY = 1000

SG_WIN = 11
SG_POLY = 3
MIN_EXTREMA = 2

# Fig2 will create one subplot per distance here
DISTANCES_TEST = [25, 50, 100, 200, 300]
FREQ_GHZ = 8.0

# Statistical-profile validation curve (uses P.452 with is_terrain=True)
ENABLE_STAT_VALIDATION = True
STAT_VALIDATION_LOCATION = "FINLAND"   # one of TERRAIN_PROFILE_PARAMS keys ("WORLD", "FINLAND", "FRANCE")

# Número de componentes da mistura de t-Student para a marginal de altura.
# 1 = unimodal (ex.: Finlândia); 2 = bimodal/assimétrico (ex.: França).
N_STU = 2

# Apara os outliers extremos de h_extrema ANTES de qualquer fit de altura
# (percentis inferior/superior). Evita que picos raros — que nem aparecem no
# histograma (cortado em H_BINS=±500) — inflem a cauda da mistura e gerem
# pathloss exagerada. (0.0, 100.0) desliga o trim.
H_FIT_TRIM_Q = (0.5, 95)


def trim_to_quantiles(x, q_lo_hi=H_FIT_TRIM_Q):
    """Mantém apenas valores finitos dentro do intervalo de percentis dado."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    q_lo, q_hi = q_lo_hi
    if x.size == 0 or (q_lo <= 0.0 and q_hi >= 100.0):
        return x
    lo, hi = np.percentile(x, [q_lo, q_hi])
    return x[(x >= lo) & (x <= hi)]

# Histogram bins (counts stored). Density computed at plot time.
D_BINS = np.linspace(0, 60, 61)
H_BINS = np.linspace(-500, 500, 501)   # signed h_extrema = e_s[extrema] - median(e_s)
LOSS_BINS = np.linspace(120, 260, 250)  # tune if needed

RESERVOIR_MAX_DH = 300000
RESERVOIR_MAX_LOSS = 200000
RESERVOIR_SEED = 1234

FIT_COLOR = "red"

## Latitude
def get_region_bbox(region: str):
    """
    Return geographic bounding box for continent-level sampling.

    Parameters
    ----------
    region : str
        One of:
        "America", "Europe", "Asia", "Africa", "Oceania", "World"

    Returns
    -------
    LAT_MIN, LAT_MAX, LON_MIN, LON_MAX : float
    """

    region = region.strip().lower()

    bboxes = {
        "america": (-56.0, 83.0, -170.0, -30.0),
        "europe":  ( 34.0, 72.0,  -25.0,  45.0),
        "asia":    (  0.0, 80.0,   25.0, 180.0),
        "africa":  (-35.0, 38.0,  -20.0,  55.0),
        "oceania": (-50.0, 10.0,  110.0, 180.0),
        "world":   (-60.0, 75.0, -180.0, 180.0),
        # Custom box: NW corner Äänekoski (FI), SE corner Volkhovsky (RU)
        # "custom":  (47.67, 49.45, 6.33, 8.35),
        "custom":  (60.48, 69.1, 27.4, 32.9),
    }

    if region not in bboxes:
        raise ValueError(
            f"Unknown region '{region}'. Valid options: "
            f"{', '.join([k.title() for k in bboxes.keys()])}"
        )

    return bboxes[region]

LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = get_region_bbox(REGION)

def load_cities_over_pop(min_pop=100_000):
    """
    Load GeoNames cities500 (>500 inhabitants globally) and filter by population.

    Returns
    -------
    GeoDataFrame with columns:
        lat, lon, pop, geometry (EPSG:4326)
    """

    import pandas as pd
    import geopandas as gpd

    url = "https://download.geonames.org/export/dump/cities500.zip"

    # GeoNames column schema (subset used)
    cols = [
        "geonameid", "name", "asciiname", "alt_names",
        "lat", "lon", "feature_class", "feature_code",
        "country_code", "cc2", "admin1", "admin2", "admin3", "admin4",
        "population", "elevation", "dem", "timezone", "mod_date"
    ]

    df = pd.read_csv(
        url,
        sep="\t",
        header=None,
        names=cols,
        usecols=["lat", "lon", "population"]
    )

    # filter by population
    df = df[df["population"] >= min_pop].copy()

    df.rename(columns={"population": "pop"}, inplace=True)

    # convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.lon.astype(float), df.lat.astype(float)),
        crs="EPSG:4326"
    )

    return gdf


def filter_cities_by_bbox_and_tiles(cities_gdf, tiles_set):
    """
    Keep only cities inside the region bbox AND inside available tiles (1°x1° floor check).
    """
    m = (
        (cities_gdf["lat"] >= LAT_MIN) & (cities_gdf["lat"] <= LAT_MAX) &
        (cities_gdf["lon"] >= LON_MIN) & (cities_gdf["lon"] <= LON_MAX)
    )
    cities = cities_gdf[m].copy()

    # optional: enforce land (usually ok, but keep to be safe)
    # (this is a bit slow but done once in main, so OK)
    mask_land = [is_land(lat, lon) for lat, lon in zip(cities["lat"].values, cities["lon"].values)]
    cities = cities[np.array(mask_land, dtype=bool)].copy()

    # enforce tile coverage: city must fall in a tile you have
    lat0 = np.floor(cities["lat"].values).astype(int)
    lon0 = np.floor(cities["lon"].values).astype(int)
    in_tiles = np.array([(la, lo) in tiles_set for la, lo in zip(lat0, lon0)], dtype=bool)
    cities = cities[in_tiles].copy()

    if len(cities) == 0:
        raise RuntimeError("No cities left after bbox/land/tile filtering. Check REGION bbox and tile coverage.")

    # build arrays for workers
    lats = cities["lat"].values.astype(float)
    lons = cities["lon"].values.astype(float)
    w = cities["pop"].values.astype(float)
    w = w / np.sum(w)

    return lats, lons, w


def random_city_origin_weighted(city_lats, city_lons, city_weights, rng):
    idx = rng.choice(len(city_lats), p=city_weights)
    return float(city_lats[idx]), float(city_lons[idx])

# ============================================================
# Tile naming + availability scan
# ============================================================
_TILE_RE = re.compile(r"tile_([pm]\d{2,3})_([pm]\d{3,4})_250m\.tif$", re.IGNORECASE)

def parse_tile_latlon0(filename: str):
    m = _TILE_RE.search(os.path.basename(filename))
    if not m:
        return None

    def decode(s):
        sign = -1 if s[0].lower() == "m" else +1
        return sign * int(s[1:])

    return decode(m.group(1)), decode(m.group(2))

def scan_available_tiles(tiles_dir: str):
    avail = set()
    for fn in os.listdir(tiles_dir):
        if not fn.lower().endswith(".tif"):
            continue
        parsed = parse_tile_latlon0(fn)
        if parsed is None:
            continue
        avail.add(parsed)
    return avail

def tile_filename(lat0: int, lon0: int) -> str:
    name = f"tile_{lat0:+03d}_{lon0:+04d}_250m.tif"
    return name.replace("+", "p").replace("-", "m")

def tile_path(lat: float, lon: float) -> str:
    lat0 = int(math.floor(lat))
    lon0 = int(math.floor(lon))
    return os.path.join(TILES_250_DIR, tile_filename(lat0, lon0))

def wrap_lon(lon: float) -> float:
    return ((lon + 180.0) % 360.0) - 180.0


# ============================================================
# Land mask (Natural Earth)
# ============================================================
def load_land_prepared():
    world = gpd.read_file(
        "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
    )
    land_geom = world.unary_union
    return prep(land_geom), world

LAND_PREP, WORLD = load_land_prepared()

def is_land(lat: float, lon: float) -> bool:
    return LAND_PREP.contains(ShapelyPoint(float(lon), float(lat)))


# ============================================================
# Path utils
# ============================================================
def destination_point(lat, lon, distance_km, bearing_deg):
    origin = GeopyPoint(lat, lon)
    dest = geopy_distance(kilometers=distance_km).destination(origin, bearing_deg)
    return dest.latitude, dest.longitude

def interpolate_path(start_latlon, end_latlon, n):
    lats = np.linspace(start_latlon[0], end_latlon[0], n)
    lons = np.linspace(start_latlon[1], end_latlon[1], n)
    lons = np.array([wrap_lon(x) for x in lons], dtype=float)
    return np.column_stack([lats, lons])


# ============================================================
# Tile-aware start point
# ============================================================
def pick_random_available_land_point(rng: np.random.RandomState, tiles_list):
    n = len(tiles_list)
    while True:
        lat0, lon0 = tiles_list[int(rng.randint(0, n))]
        lat = lat0 + float(rng.rand())
        lon = lon0 + float(rng.rand())
        lon = wrap_lon(lon)
        if not (LAT_MIN <= lat <= LAT_MAX):
            continue
        if not (LON_MIN <= lon <= LON_MAX):
            continue
        if is_land(lat, lon):
            return lat, lon


# ============================================================
# Raster sampling (worker local)
# ============================================================
class TileCache:
    def __init__(self, max_open=64):
        self.max_open = int(max_open)
        self._cache = {}
        self._order = []

    def get(self, path):
        ds = self._cache.get(path)
        if ds is not None:
            try:
                self._order.remove(path)
            except ValueError:
                pass
            self._order.append(path)
            return ds

        if not os.path.exists(path):
            return None

        ds = rasterio.open(path)
        self._cache[path] = ds
        self._order.append(path)

        while len(self._order) > self.max_open:
            old = self._order.pop(0)
            try:
                self._cache[old].close()
            except Exception:
                pass
            self._cache.pop(old, None)

        return ds

    def close_all(self):
        for ds in self._cache.values():
            try:
                ds.close()
            except Exception:
                pass
        self._cache.clear()
        self._order.clear()

def sample_elevation_from_tiles(path_latlon: np.ndarray, cache: TileCache):
    elev = np.full((path_latlon.shape[0],), np.nan, dtype=float)
    for i in range(path_latlon.shape[0]):
        lat, lon = float(path_latlon[i, 0]), float(path_latlon[i, 1])
        tif = tile_path(lat, lon)
        ds = cache.get(tif)
        if ds is None:
            continue
        val = next(ds.sample([(lon, lat)]))[0]
        if val == NODATA_I16:
            continue
        elev[i] = float(val)
    return elev


# ============================================================
# P.452: terrain profile vs "no-terrain"
# ============================================================
def compute_p452_losses(d_profile, h_profile, distances_test, freq_ghz,
                        rng=None, enable_stat=False, stat_location="WORLD"):
    if rng is None:
        rng = np.random.RandomState()
    params_p452 = ParametersP452()
    prop452 = PropagationClearAir(rng, params_p452)
    params_p452.clutter_loss = False
    params_p452.percentage_p = 0.2

    def loss_for(D_km, d_prof, h_prof, p_pct, terrain_mode="real"):
        distance = np.array([[float(D_km)]], dtype=float)
        freq = np.array([[float(freq_ghz)]], dtype=float)
        indoor = np.array([[False]])
        elev = np.array([[0]])
        txg = np.array([[0]])
        rxg = np.array([[0]])
        params_p452.percentage_p = float(p_pct)

        if terrain_mode == "real":
            params_p452.terrain_d = d_prof
            params_p452.terrain_h = h_prof
            params_p452.is_terrain = False
        elif terrain_mode == "none":
            params_p452.terrain_d = None
            params_p452.terrain_h = None
            params_p452.is_terrain = False
        elif terrain_mode == "stat":
            params_p452.terrain_d = None
            params_p452.terrain_h = None
            params_p452.is_terrain = True
            params_p452.terrain_profile_location = stat_location
        else:
            raise ValueError("terrain_mode must be 'real', 'none' or 'stat'")

        lr = prop452.get_loss(distance, freq, indoor, elev, txg, rxg)[0, 0]
        return float(lr)

    out_real, out_none, out_stat = {}, {}, {}

    for D in distances_test:
        mask = d_profile <= (D + 1e-9)
        d_sub = d_profile[mask].copy()
        h_sub = h_profile[mask].copy()

        if d_sub.size < 4:
            out_real[D] = np.nan
            out_none[D] = np.nan
            out_stat[D] = np.nan
            continue

        if d_sub[-1] < D:
            d_sub = np.append(d_sub, D)
            h_sub = np.append(h_sub, h_sub[-1])
        else:
            d_sub[-1] = D

        if not np.all(np.diff(d_sub) > 0):
            out_real[D] = np.nan
            out_none[D] = np.nan
            out_stat[D] = np.nan
            continue

        p_pct = 50.0 * rng.rand()
        out_real[D] = loss_for(D, d_sub, h_sub, p_pct, "real")
        out_none[D] = loss_for(D, d_sub, h_sub, p_pct, "none")
        if enable_stat:
            out_stat[D] = loss_for(D, d_sub, h_sub, p_pct, "stat")
        else:
            out_stat[D] = np.nan

    return out_real, out_none, out_stat


# ============================================================
# Reservoir sampling for bounded fit updates
# ============================================================
class Reservoir:
    def __init__(self, max_n: int, seed: int):
        self.max_n = int(max_n)
        self.rng = np.random.RandomState(int(seed))
        self.n_seen = 0
        self.data = np.empty((0,), dtype=float)

    def add(self, x):
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        if x.size == 0:
            return
        for v in x:
            self.n_seen += 1
            if self.data.size < self.max_n:
                self.data = np.append(self.data, v)
            else:
                j = int(self.rng.randint(0, self.n_seen))
                if j < self.max_n:
                    self.data[j] = v

    def get(self):
        return self.data.copy()


# ============================================================
# Best distribution fit (AIC + KS) for distance/height
# ============================================================
def fit_best_distribution(x, positive_only=False):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if positive_only:
        x = x[x > 0]
    if x.size < 300:
        return None

    if positive_only:
        candidates = {
            "expon": stats.expon,
            "lognorm": stats.lognorm,
            "norm": stats.norm,
            "gamma": stats.gamma,
            "weibull_min": stats.weibull_min,
            "t": stats.t,
        }
    else:
        candidates = {
            "norm": stats.norm,
            "laplace": stats.laplace,
            "logistic": stats.logistic,
            "t": stats.t,
        }

    results = []
    for name, dist in candidates.items():
        try:
            if positive_only and name in ["expon", "gamma", "weibull_min", "lognorm"]:
                params = dist.fit(x, floc=0)
            else:
                params = dist.fit(x)

            ll = np.sum(dist.logpdf(x, *params))
            k = len(params)
            aic = 2 * k - 2 * ll
            D, p = stats.kstest(x, name, args=params)
            results.append((aic, name, params, D, p))
        except Exception:
            continue

    if not results:
        return None
    results.sort(key=lambda t: t[0])
    return results[0]


# ============================================================
# 2-Gaussian mixture fit (EM) for P.452 (TERRAIN ONLY)
# ============================================================
def fit_gmm2(x, n_iter=60):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 200:
        return None

    mu1, mu2 = np.percentile(x, [30, 70])
    s = np.std(x)
    s1 = float(max(1e-3, 0.7 * s))
    s2 = float(max(1e-3, 0.7 * s))
    w1, w2 = 0.5, 0.5

    for _ in range(int(n_iter)):
        p1 = w1 * stats.norm.pdf(x, mu1, s1)
        p2 = w2 * stats.norm.pdf(x, mu2, s2)
        denom = (p1 + p2 + 1e-12)
        g1 = p1 / denom
        g2 = 1.0 - g1

        w1 = float(np.mean(g1))
        w1 = min(max(w1, 1e-3), 1.0 - 1e-3)
        w2 = 1.0 - w1

        mu1 = float(np.sum(g1 * x) / (np.sum(g1) + 1e-12))
        mu2 = float(np.sum(g2 * x) / (np.sum(g2) + 1e-12))

        s1 = float(np.sqrt(np.sum(g1 * (x - mu1) ** 2) / (np.sum(g1) + 1e-12)))
        s2 = float(np.sqrt(np.sum(g2 * (x - mu2) ** 2) / (np.sum(g2) + 1e-12)))

        s1 = max(s1, 1e-3)
        s2 = max(s2, 1e-3)

    return (w1, mu1, s1, w2, mu2, s2)

def mixture_cdf(xs, gmm_params):
    w1, mu1, s1, w2, mu2, s2 = gmm_params
    return w1 * stats.norm.cdf(xs, mu1, s1) + w2 * stats.norm.cdf(xs, mu2, s2)


# ============================================================
# Student-t MIXTURE fit (EM) for the signed-height marginal
# ============================================================
def tmix_pdf(xs, components):
    """PDF of a Student-t (df=inf -> Normal) mixture given [(w, loc, scale, df), ...]."""
    xs = np.asarray(xs, dtype=float)
    out = np.zeros_like(xs)
    for w, loc, scale, df in components:
        scale = max(scale, 1e-9)
        if not np.isfinite(df):
            out += w * stats.norm.pdf(xs, loc, scale)
        else:
            out += w * stats.t.pdf((xs - loc) / scale, df) / scale
    return out


def fit_tmix(x, k=2, n_iter=200, tol=1e-6, max_fit=20000, seed=0):
    """EM fit of a k-component Student-t mixture (per-component loc/scale/df).

    Each component is a Student-t (heavy tails capture the high-peak outliers),
    so the mixture handles both the skew (two locations) and the tails.

    Returns
    -------
    dict with keys:
        "components": [(w, loc, scale, df), ...] sorted by descending weight
        "loglik": final log-likelihood
        "k": number of components
    or None if there are not enough samples.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 300 or k < 1:
        return None
    rng = np.random.RandomState(seed)
    if x.size > max_fit:
        x = rng.choice(x, size=max_fit, replace=False)
    n = x.size

    # Quantile-spread init for the locations.
    mu = np.percentile(x, np.linspace(15, 85, k)).astype(float)
    sigma = np.full(k, max(np.std(x) * 0.7, 1e-3), dtype=float)
    df = np.full(k, 6.0, dtype=float)
    w = np.full(k, 1.0 / k, dtype=float)

    ll_old = -np.inf
    for _ in range(int(n_iter)):
        # E-step: responsibilities + latent scale weights u_ij
        P = np.empty((n, k))
        for j in range(k):
            s = max(sigma[j], 1e-9)
            P[:, j] = w[j] * (stats.t.pdf((x - mu[j]) / s, df[j]) / s)
        denom = P.sum(axis=1) + 1e-300
        gamma = P / denom[:, None]
        U = np.empty((n, k))
        for j in range(k):
            s = max(sigma[j], 1e-9)
            delta2 = ((x - mu[j]) / s) ** 2
            U[:, j] = (df[j] + 1.0) / (df[j] + delta2)

        # M-step
        Nk = gamma.sum(axis=0) + 1e-12
        w = Nk / n
        for j in range(k):
            gw = gamma[:, j] * U[:, j]
            sgw = np.sum(gw) + 1e-12
            mu[j] = float(np.sum(gw * x) / sgw)
            sigma[j] = float(np.sqrt(
                np.sum(gamma[:, j] * U[:, j] * (x - mu[j]) ** 2) / Nk[j]))
            sigma[j] = max(sigma[j], 1e-3)
            # df update (Liu & Rubin), solved numerically for stability
            const = (1.0
                     + (1.0 / Nk[j]) * np.sum(gamma[:, j] * (np.log(U[:, j]) - U[:, j]))
                     + digamma((df[j] + 1.0) / 2.0) - np.log((df[j] + 1.0) / 2.0))

            def f(nu):
                return -digamma(nu / 2.0) + np.log(nu / 2.0) + const
            try:
                if f(2.01) * f(200.0) < 0.0:
                    df[j] = float(brentq(f, 2.01, 200.0))
            except Exception:
                pass

        ll = float(np.sum(np.log(denom)))
        if abs(ll - ll_old) < tol * (1.0 + abs(ll_old)):
            ll_old = ll
            break
        ll_old = ll

    order = np.argsort(-w)
    comps = [(float(w[j]), float(mu[j]), float(sigma[j]), float(df[j]))
             for j in order]
    return {"components": comps, "loglik": ll_old, "k": int(k)}


# ============================================================
# Plot helpers: convert counts -> density and overlay fits (RED)
# ============================================================
def counts_to_density(counts: np.ndarray, bins: np.ndarray) -> np.ndarray:
    counts = np.asarray(counts, dtype=float)
    total = counts.sum()
    if total <= 0:
        return np.zeros_like(counts, dtype=float)
    widths = np.diff(bins).astype(float)
    return counts / (total * widths)

def overlay_bestfit_pdf(ax, fit_tuple, bins, color=FIT_COLOR):
    if fit_tuple is None:
        return
    aic, name, params, D, p = fit_tuple
    dist = getattr(stats, name)
    xs = np.linspace(float(bins[0]), float(bins[-1]), 800)
    pdf = dist.pdf(xs, *params)
    ax.plot(xs, pdf, linewidth=2, color=color)
    ax.text(
        0.02, 0.95,
        f"{name}\nAIC={aic:.1f}\nKS p={p:.3g}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(boxstyle="round", alpha=0.15),
    )

def overlay_gmm2_cdf_twin(ax_density, gmm_params, bins, color=FIT_COLOR):
    if gmm_params is None:
        return None
    ax_cdf = ax_density.twinx()
    xs = np.linspace(float(bins[0]), float(bins[-1]), 800)
    cdf = mixture_cdf(xs, gmm_params)
    ax_cdf.plot(xs, cdf, color=color, linewidth=2)
    ax_cdf.set_ylim(0.0, 1.0)
    ax_cdf.set_ylabel("CDF")
    return ax_cdf


# ============================================================
# Peak/valley pipeline (shared between real DEM and statistical profile)
# ============================================================
def extract_peak_valley_stats(e_s, step_km=STEP_KM):
    """Run the find_peaks pipeline on a 1D elevation profile.

    No minimum-distance filter (`distance` arg of find_peaks is omitted) so
    all extrema above the prominence threshold are kept.

    Returns
    -------
    dseg : np.ndarray         distances [km] between consecutive extrema
    hseg : np.ndarray         signed height deltas [m] between consecutive extrema
    h_extrema : np.ndarray    signed absolute terrain height at each extremum
                              (e_s[extrema] - median(e_s)), positive = above median
                              (peak), negative = below median (valley)
    """
    e_s = np.asarray(e_s, dtype=float)
    relief = np.percentile(e_s, 95) - np.percentile(e_s, 5)
    prom = max(5.0, 0.05 * relief)

    peaks, _ = find_peaks(e_s, prominence=prom)
    valleys, _ = find_peaks(-e_s, prominence=prom)
    extrema = np.sort(np.concatenate([peaks, valleys]))

    if extrema.size < MIN_EXTREMA:
        peaks, _ = find_peaks(e_s, prominence=max(2.0, 0.02 * relief))
        valleys, _ = find_peaks(-e_s, prominence=max(2.0, 0.02 * relief))
        extrema = np.sort(np.concatenate([peaks, valleys]))

    if extrema.size < MIN_EXTREMA:
        return (np.array([], dtype=float),
                np.array([], dtype=float),
                np.array([], dtype=float))

    baseline = float(np.median(e_s))
    h_extrema = e_s[extrema].astype(float) - baseline

    dseg = step_km * np.diff(extrema.astype(float))
    hseg = np.diff(e_s[extrema].astype(float))
    mask = (dseg > 0) & (hseg != 0) & np.isfinite(dseg) & np.isfinite(hseg)
    return dseg[mask], hseg[mask], h_extrema[np.isfinite(h_extrema)]


# ============================================================
# Worker: generate ONE valid path and return streaming contributions
# ============================================================
def worker_one(seed: int,
               available_tiles_list,
               city_lats, city_lons, city_w,
               d_bins, h_bins, loss_bins,
               distances_test, freq_ghz,
               enable_stat=False, stat_location="WORLD"):

    rng = np.random.RandomState(int(seed))
    tiles_list = available_tiles_list
    tiles_set = set(available_tiles_list)

    cache = TileCache(max_open=64)

    try:
        while True:
            # ---- origin = big city (>100k), already bbox/tile filtered
            s_lat, s_lon = random_city_origin_weighted(city_lats, city_lons, city_w, rng)

            bearing = float(rng.uniform(0, 360))
            e_lat, e_lon = destination_point(s_lat, s_lon, PATH_LENGTH_KM, bearing)
            e_lon = wrap_lon(e_lon)

            # keep endpoint inside bbox (region)
            if not (LAT_MIN <= e_lat <= LAT_MAX):
                continue
            if not (LON_MIN <= e_lon <= LON_MAX):
                continue

            path = interpolate_path((s_lat, s_lon), (e_lat, e_lon), N_SAMPLES)

            # Fast tile coverage check
            idxs = set((int(math.floor(path[i, 0])), int(math.floor(path[i, 1]))) for i in range(path.shape[0]))
            if not idxs.issubset(tiles_set):
                continue

            # Sparse land check
            ok_sparse = True
            for i in range(0, path.shape[0], 10):
                if not is_land(float(path[i, 0]), float(path[i, 1])):
                    ok_sparse = False
                    break
            if not ok_sparse:
                continue

            elev = sample_elevation_from_tiles(path, cache)
            if not np.isfinite(elev).all():
                continue

            # Strict land check ALL points
            ok_all = True
            for i in range(path.shape[0]):
                if not is_land(float(path[i, 0]), float(path[i, 1])):
                    ok_all = False
                    break
            if not ok_all:
                continue

            # Smooth
            #e_s = savgol_filter(elev, SG_WIN, SG_POLY)
            e_s = elev

            # ---- REAL: extract peak/valley stats from DEM-sampled profile
            dseg, hseg, h_extrema = extract_peak_valley_stats(e_s, STEP_KM)
            d_hist = np.histogram(dseg, bins=d_bins)[0].astype(np.int64)
            h_hist = np.histogram(h_extrema, bins=h_bins)[0].astype(np.int64)

            # ---- AR(2) stats on consecutive h_extrema (lag-1 and lag-2 autocorr)
            h_sum_x = float(np.sum(h_extrema))
            h_sum_x2 = float(np.sum(h_extrema ** 2))
            h_n = int(h_extrema.size)
            if h_extrema.size >= 2:
                h_sum_xy = float(np.sum(h_extrema[:-1] * h_extrema[1:]))
                h_n_pairs = h_extrema.size - 1
            else:
                h_sum_xy = 0.0
                h_n_pairs = 0
            if h_extrema.size >= 3:
                h_sum_xy2 = float(np.sum(h_extrema[:-2] * h_extrema[2:]))
                h_n_pairs2 = h_extrema.size - 2
            else:
                h_sum_xy2 = 0.0
                h_n_pairs2 = 0

            # ---- STAT round-trip: generate a profile from the model, run the
            # SAME pipeline on it (interp to 1-km grid first), so we can compare
            # CDFs of dseg/h_extrema from real vs. stat.
            d_hist_stat = np.zeros((len(d_bins) - 1,), dtype=np.int64)
            h_hist_stat = np.zeros((len(h_bins) - 1,), dtype=np.int64)
            if enable_stat:
                gen_rng = np.random.default_rng(int(seed))
                stat_d_ex, stat_h_ex = generate_terrain_profile(
                    gen_rng, PATH_LENGTH_KM, stat_location,
                )
                d_grid = np.arange(0.0, PATH_LENGTH_KM + 1e-9, STEP_KM, dtype=float)
                if d_grid.size != e_s.size:
                    d_grid = np.linspace(0.0, PATH_LENGTH_KM, e_s.size, dtype=float)
                e_s_stat = np.interp(d_grid, stat_d_ex, stat_h_ex)

                dseg_stat, hseg_stat, h_extrema_stat = extract_peak_valley_stats(e_s_stat, STEP_KM)
                d_hist_stat = np.histogram(dseg_stat, bins=d_bins)[0].astype(np.int64)
                h_hist_stat = np.histogram(h_extrema_stat, bins=h_bins)[0].astype(np.int64)

            # P.452 at distances_test
            d_prof = np.arange(0.0, PATH_LENGTH_KM + 1e-9, STEP_KM, dtype=float)
            if d_prof.size != e_s.size:
                d_prof = np.linspace(0.0, PATH_LENGTH_KM, e_s.size, dtype=float)

            losses_real, losses_none, losses_stat = compute_p452_losses(
                d_prof, e_s, distances_test, freq_ghz,
                rng=rng, enable_stat=enable_stat, stat_location=stat_location,
            )

            loss_hist_real = {D: np.zeros((len(loss_bins) - 1,), dtype=np.int64) for D in distances_test}
            loss_hist_none = {D: np.zeros((len(loss_bins) - 1,), dtype=np.int64) for D in distances_test}
            loss_hist_stat = {D: np.zeros((len(loss_bins) - 1,), dtype=np.int64) for D in distances_test}

            loss_samples_real = {}
            loss_samples_none = {}
            loss_samples_stat = {}
            loss_samples_delta = {}

            for D in distances_test:
                v = losses_real.get(D, np.nan)
                if np.isfinite(v):
                    loss_hist_real[D] = np.histogram([v], bins=loss_bins)[0].astype(np.int64)
                    loss_samples_real[D] = float(v)

                v2 = losses_none.get(D, np.nan)
                if np.isfinite(v2):
                    loss_hist_none[D] = np.histogram([v2], bins=loss_bins)[0].astype(np.int64)
                    loss_samples_none[D] = float(v2)

                v3 = losses_stat.get(D, np.nan)
                if np.isfinite(v3):
                    loss_hist_stat[D] = np.histogram([v3], bins=loss_bins)[0].astype(np.int64)
                    loss_samples_stat[D] = float(v3)

                if np.isfinite(v) and np.isfinite(v2):
                    dv = float(v - v2)
                    loss_samples_delta[D] = dv

            # Reservoir samples (downsample). h_take = signed h_extrema; d_take = dseg.
            max_take = 512
            if dseg.size > max_take:
                idx_d = rng.choice(dseg.size, size=max_take, replace=False)
                d_take = dseg[idx_d]
            else:
                d_take = dseg
            if h_extrema.size > max_take:
                idx_h = rng.choice(h_extrema.size, size=max_take, replace=False)
                h_take = h_extrema[idx_h]
            else:
                h_take = h_extrema

            path_line = (float(s_lat), float(s_lon), float(e_lat), float(e_lon))

            return {
                "d_hist": d_hist,
                "h_hist": h_hist,
                "d_hist_stat": d_hist_stat,
                "h_hist_stat": h_hist_stat,
                "loss_hist_real": loss_hist_real,
                "loss_hist_none": loss_hist_none,
                "loss_hist_stat": loss_hist_stat,
                "d_samp": d_take.astype(float),
                "h_samp": h_take.astype(float),
                "loss_samp_real": loss_samples_real,
                "loss_samp_none": loss_samples_none,
                "loss_samp_stat": loss_samples_stat,
                "loss_samp_delta": loss_samples_delta,
                "path_line": path_line,
                "real_profile_d": d_prof.astype(float),
                "real_profile_h": e_s.astype(float),
                "h_sum_x": h_sum_x,
                "h_sum_x2": h_sum_x2,
                "h_n": h_n,
                "h_sum_xy": h_sum_xy,
                "h_n_pairs": h_n_pairs,
                "h_sum_xy2": h_sum_xy2,
                "h_n_pairs2": h_n_pairs2,
            }

    finally:
        cache.close_all()


# ============================================================
# Figures
# ============================================================
def init_figures():
    plt.ion()

    # FIG1
    fig1, (ax_map, ax_d, ax_h) = plt.subplots(1, 3, figsize=(18, 5))
    WORLD.boundary.plot(ax=ax_map, color="black", linewidth=0.5)
    ax_map.set_title("Paths (lines only)")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.grid(True, alpha=0.2)

    # FIG2: one subplot per distance
    n = len(DISTANCES_TEST)
    fig2, axs = plt.subplots(1, n, figsize=(6 * n, 5), squeeze=False)
    axs = axs[0].tolist()

    # FIG3: one subplot per distance for delta loss = terrain - no terrain
    fig3, axs_delta = plt.subplots(1, n, figsize=(6 * n, 5), squeeze=False)
    axs_delta = axs_delta[0].tolist()

    return (fig1, ax_map, ax_d, ax_h), (fig2, axs), (fig3, axs_delta)


def update_plots(fig1_pack, fig2_pack, fig3_pack,
                 d_counts, h_counts,
                 loss_counts_real, loss_counts_none, loss_values_delta,
                 res_d, res_h,
                 res_loss_real,
                 n_paths_done,
                 loss_counts_stat=None, stat_location=None,
                 d_counts_stat_rt=None, h_counts_stat_rt=None,
                 ar1_stats=None):

    (fig1, ax_map, ax_d, ax_h) = fig1_pack
    (fig2, axs_loss) = fig2_pack
    (fig3, axs_delta) = fig3_pack

    # ---- Fits (distance/height on reservoirs; P.452 GMM ONLY on TERRAIN reservoir)
    # h reservoir stores signed h_extrema directly (peaks > 0, valleys < 0).
    # Trim the extreme tails first so rare outliers don't inflate the height fit.
    h_samples_trim = trim_to_quantiles(res_h.get())
    d_fit = fit_best_distribution(res_d.get(), positive_only=True)
    h_fit = fit_best_distribution(h_samples_trim, positive_only=False)
    tmix_h = fit_tmix(h_samples_trim, k=N_STU)
    gmm_real = {D: fit_gmm2(res_loss_real[D].get()) for D in DISTANCES_TEST}

    # ---- FIG1: distance density + best-fit PDF (RED) + CDF overlay (real vs stat)
    ax_d.clear()
    centers_d = 0.5 * (D_BINS[:-1] + D_BINS[1:])
    dens_d = counts_to_density(d_counts, D_BINS)
    ax_d.bar(centers_d, dens_d, width=np.diff(D_BINS), align="center",
             label="Real terrain hist")
    ax_d.set_xlabel("Distance between peaks/valleys (km)")
    ax_d.set_ylabel("Density")
    overlay_bestfit_pdf(ax_d, d_fit, D_BINS, color=FIT_COLOR)

    # Generated (statistical) terrain histogram overlay (same density axis)
    if d_counts_stat_rt is not None and d_counts_stat_rt.sum() > 0:
        dens_d_stat = counts_to_density(d_counts_stat_rt, D_BINS)
        stat_hist_lbl = f"Stat ({stat_location}) hist" if stat_location else "Stat hist"
        ax_d.step(centers_d, dens_d_stat, where="mid", color="green",
                  lw=1.5, alpha=0.9, label=stat_hist_lbl)
    ax_d.legend(fontsize=8, loc="upper right")

    if d_counts.sum() > 0:
        ax_d_cdf = ax_d.twinx()
        cdf_d_real = np.cumsum(d_counts) / d_counts.sum()
        ax_d_cdf.plot(centers_d, cdf_d_real, color="black", lw=2,
                      label="Real CDF")
        if d_counts_stat_rt is not None and d_counts_stat_rt.sum() > 0:
            cdf_d_stat = np.cumsum(d_counts_stat_rt) / d_counts_stat_rt.sum()
            stat_lbl = f"Stat ({stat_location}) CDF" if stat_location else "Stat CDF"
            ax_d_cdf.plot(centers_d, cdf_d_stat, color="green",
                          lw=2, linestyle="--", label=stat_lbl)
        ax_d_cdf.set_ylim(0.0, 1.0)
        ax_d_cdf.set_ylabel("CDF")
        ax_d_cdf.legend(fontsize=8, loc="lower right")

    # ---- FIG1: height density + best-fit PDF (RED) + CDF overlay (real vs stat)
    ax_h.clear()
    centers_h = 0.5 * (H_BINS[:-1] + H_BINS[1:])
    dens_h = counts_to_density(h_counts, H_BINS)
    ax_h.bar(centers_h, dens_h, width=np.diff(H_BINS), align="center",
             label="Real terrain hist")
    ax_h.set_xlabel("h_extrema = e_s[extrema] - median (m, signed)")
    ax_h.set_ylabel("Density")
    overlay_bestfit_pdf(ax_h, h_fit, H_BINS, color=FIT_COLOR)

    # Generated (statistical) terrain histogram overlay (same density axis)
    if h_counts_stat_rt is not None and h_counts_stat_rt.sum() > 0:
        dens_h_stat = counts_to_density(h_counts_stat_rt, H_BINS)
        stat_hist_lbl = f"Stat ({stat_location}) hist" if stat_location else "Stat hist"
        ax_h.step(centers_h, dens_h_stat, where="mid", color="green",
                  lw=1.5, alpha=0.9, label=stat_hist_lbl)

    # t-Student mixture fit overlay (captures skew + heavy tails)
    if tmix_h is not None:
        xs_h = np.linspace(float(H_BINS[0]), float(H_BINS[-1]), 800)
        ax_h.plot(xs_h, tmix_pdf(xs_h, tmix_h["components"]),
                  color="purple", lw=2, label=f"t-mix fit (k={tmix_h['k']})")
    ax_h.legend(fontsize=8, loc="upper right")

    if h_counts.sum() > 0:
        ax_h_cdf = ax_h.twinx()
        cdf_h_real = np.cumsum(h_counts) / h_counts.sum()
        ax_h_cdf.plot(centers_h, cdf_h_real, color="black", lw=2,
                      label="Real CDF")
        if h_counts_stat_rt is not None and h_counts_stat_rt.sum() > 0:
            cdf_h_stat = np.cumsum(h_counts_stat_rt) / h_counts_stat_rt.sum()
            stat_lbl = f"Stat ({stat_location}) CDF" if stat_location else "Stat CDF"
            ax_h_cdf.plot(centers_h, cdf_h_stat, color="green",
                          lw=2, linestyle="--", label=stat_lbl)
        ax_h_cdf.set_ylim(0.0, 1.0)
        ax_h_cdf.set_ylabel("CDF")
        ax_h_cdf.legend(fontsize=8, loc="lower right")

    fig1.tight_layout()
    fig1.canvas.draw_idle()

    # ---- FIG2: P.452 densities + TERRAIN GMM2 CDF overlay (RED)
    for i, D in enumerate(DISTANCES_TEST):

        ax = axs_loss[i]
        ax.clear()

        centers_l = 0.5 * (LOSS_BINS[:-1] + LOSS_BINS[1:])

        # ===== TERRAIN CDF =====
        counts_real = loss_counts_real[D].astype(float)
        cdf_real = np.cumsum(counts_real)
        if cdf_real[-1] > 0:
            cdf_real /= cdf_real[-1]

        # evitar zeros para log-scale
        cdf_real = np.clip(cdf_real, 1e-6, 1.0)

        ax.plot(centers_l, cdf_real, lw=2, label="terrain CDF")

       # ===== TERRAIN CDF no terrain=====
        counts_real = loss_counts_none[D].astype(float)
        cdf_real = np.cumsum(counts_real)
        if cdf_real[-1] > 0:
            cdf_real /= cdf_real[-1]

        # evitar zeros para log-scale
        cdf_real = np.clip(cdf_real, 1e-6, 1.0)

        ax.plot(centers_l, cdf_real, lw=2, color='Red', label="No Terrain")

        # ===== STATISTICAL VALIDATION CDF (P.452 + statistical profile) =====
        if loss_counts_stat is not None and np.sum(loss_counts_stat[D]) > 0:
            counts_stat = loss_counts_stat[D].astype(float)
            cdf_stat = np.cumsum(counts_stat)
            if cdf_stat[-1] > 0:
                cdf_stat /= cdf_stat[-1]
            cdf_stat = np.clip(cdf_stat, 1e-6, 1.0)
            stat_label = f"Stat ({stat_location})" if stat_location else "Stat validation"
            ax.plot(centers_l, cdf_stat, lw=2, color='green', linestyle='--', label=stat_label)

        # ===== LOG SCALE =====
        ax.set_yscale("log")
        ax.set_ylim(1e-4, 1)

        ax.set_xlabel("Path Loss (dB)")
        ax.set_ylabel("CDF (log)")
        ax.set_title(
            f"P.452 loss @ {D} km\n"
            #f"Nterrain={int(np.sum(loss_counts_real[D]))} | Nno={int(np.sum(loss_counts_none[D]))}"
        )

        ax.legend(fontsize=8, loc="best")

    fig2.tight_layout()
    fig2.canvas.draw_idle()

    # ---- FIG3: delta P.452 CDF where delta = terrain - no terrain
    for i, D in enumerate(DISTANCES_TEST):

        ax = axs_delta[i]
        ax.clear()

        delta_vals = np.asarray(loss_values_delta[D], dtype=float)
        delta_vals = delta_vals[np.isfinite(delta_vals)]

        if delta_vals.size > 0:
            xs = np.sort(delta_vals)
            cdf_delta = np.arange(1, xs.size + 1, dtype=float) / xs.size
            cdf_delta = np.clip(cdf_delta, 1e-6, 1.0)
            ax.plot(xs, cdf_delta, lw=2, color="tab:green", label="terrain - no terrain")

        ax.axvline(0.0, color="black", linewidth=1, alpha=0.4)
        ax.set_yscale("log")
        ax.set_ylim(1e-4, 1)
        ax.set_xlabel("Delta Path Loss (dB)")
        ax.set_ylabel("CDF (log)")
        ax.set_title(f"Delta P.452 loss @ {D} km\nN={delta_vals.size}")
        if delta_vals.size > 0:
            ax.legend(fontsize=8, loc="best")

    fig3.tight_layout()
    fig3.canvas.draw_idle()

    plt.pause(0.01)

    # ---- Console update
    print("\n=== UPDATE ===")
    print(f"Accepted paths: {n_paths_done}")
    print(f"Segments: distance={int(np.sum(d_counts))}, height={int(np.sum(h_counts))}")

    if d_fit is not None:
        aic, name, params, Dks, p = d_fit
        print(f"Best fit distance: {name} | AIC={aic:.1f} | KS p={p:.3g}")
    else:
        print("Best fit distance: (not enough data yet)")

    if h_fit is not None:
        aic, name, params, Dks, p = h_fit
        print(f"Best fit height:   {name} | AIC={aic:.1f} | KS p={p:.3g}")
    else:
        print("Best fit height:   (not enough data yet)")

    # ---- P.452 parameters: Normal on signed h_extrema + AR(2) lag-1 & lag-2
    # autocorrelations + lognormal on distance. Generator uses AR(2):
    #   h_t = mu + phi_1*(h_{t-1}-mu) + phi_2*(h_{t-2}-mu) + sigma_eps*Z, Z~N(0,1)
    # where (phi_1, phi_2) come from Yule-Walker on (rho_1, rho_2).
    print("\n--- P.452 parameters (copy into propagation_clear_air_452.py) ---")
    if ar1_stats is not None and ar1_stats.get("n", 0) > 0 and ar1_stats.get("n_pairs", 0) > 0:
        mean_x = ar1_stats["sum_x"] / ar1_stats["n"]
        var_x = max(ar1_stats["sum_x2"] / ar1_stats["n"] - mean_x ** 2, 0.0)
        cov_xy = ar1_stats["sum_xy"] / ar1_stats["n_pairs"] - mean_x ** 2
        rho_h_1 = float(cov_xy / var_x) if var_x > 0 else 0.0
        rho_h_1 = max(-0.999, min(0.999, rho_h_1))
        print(f"rho_h_1 = {rho_h_1:.4f}   # AR(2) lag-1 autocorrelation of h_extrema")
        if ar1_stats.get("n_pairs2", 0) > 0:
            cov_xy2 = ar1_stats["sum_xy2"] / ar1_stats["n_pairs2"] - mean_x ** 2
            rho_h_2 = float(cov_xy2 / var_x) if var_x > 0 else 0.0
            rho_h_2 = max(-0.999, min(0.999, rho_h_2))
            print(f"rho_h_2 = {rho_h_2:.4f}   # AR(2) lag-2 autocorrelation of h_extrema")
            # Yule-Walker derived parameters (for verification/debug)
            denom_yw = 1.0 - rho_h_1 ** 2
            if abs(denom_yw) > 1e-9:
                phi_2 = (rho_h_2 - rho_h_1 ** 2) / denom_yw
                phi_1 = rho_h_1 * (1.0 - phi_2)
                inn_var_fac = 1.0 - phi_1 * rho_h_1 - phi_2 * rho_h_2
                if inn_var_fac > 0:
                    sigma_eps = float(np.sqrt(var_x * inn_var_fac))
                    print(f"# Yule-Walker derived: phi_1={phi_1:.4f}, phi_2={phi_2:.4f}, sigma_eps={sigma_eps:.4f}")
                else:
                    print(f"# Yule-Walker: non-stationary AR(2) (inn_var_fac={inn_var_fac:.4f})")
    else:
        print("rho_h_1, rho_h_2 = (not enough data yet)")
    res_h_data = trim_to_quantiles(res_h.get())
    if res_h_data.size >= 300:
        # Estimadores ROBUSTOS para a marginal Normal(mu_h, sigma_h).
        # O terreno é assimétrico (cauda de picos altos) e o reservatório guarda
        # outliers que nem aparecem no histograma (cortado em ±500 m). A média/
        # desvio clássicos ficam contaminados e empurram mu_h para positivo,
        # enquanto o bulk real é negativo. A mediana centra no bulk e o MAD
        # (×1.4826) dá uma escala consistente com a Normal, sem inflar pela cauda.
        mu_h = float(np.median(res_h_data))
        mad = float(np.median(np.abs(res_h_data - mu_h)))
        sigma_h = 1.4826 * mad
        # Fallback: se o MAD degenerar (terreno quase plano), usa o std clássico.
        if not np.isfinite(sigma_h) or sigma_h <= 0.0:
            sigma_h = float(np.std(res_h_data))
        print(f"mu_h    = {mu_h:.4f}   # robust: median of signed h_extrema")
        print(f"sigma_h = {sigma_h:.4f}   # robust: 1.4826 * MAD")
    else:
        print(f"Height Normal fit: (need >=300 samples, have {res_h_data.size})")

    # Student-t MIXTURE marginal (paste into TERRAIN_PROFILE_PARAMS[location]).
    # N_stu = number of components (1 = Finland-like, 2 = France-like).
    if tmix_h is not None:
        print(f"# height marginal: {tmix_h['k']}-component Student-t mixture "
              f"(loglik={tmix_h['loglik']:.1f})")
        print('"components": [')
        for (wc, loc, scale, dfc) in tmix_h["components"]:
            df_str = "float('inf')" if not np.isfinite(dfc) else f"{dfc:.3f}"
            print(f'    {{"weight": {wc:.4f}, "mu": {loc:.3f}, '
                  f'"sigma": {scale:.3f}, "df": {df_str}}},')
        print('],')

    res_d_data = res_d.get()
    res_d_data = res_d_data[np.isfinite(res_d_data) & (res_d_data > 0)]
    if res_d_data.size >= 300:
        try:
            s_d, _, scale_d = stats.lognorm.fit(res_d_data, floc=0)
            mu_d = float(np.log(scale_d))
            sigma_d = float(s_d)
            print(f"mu_d    = {mu_d:.4f}   # mean in log-space")
            print(f"sigma_d = {sigma_d:.4f}")
        except Exception as e:
            print(f"Distance lognorm fit failed: {e}")
    else:
        print(f"Distance lognorm fit: (need >=300 samples, have {res_d_data.size})")
    print("-----------------------------------------------------------------")

    for D in DISTANCES_TEST:
        n_tr = int(np.sum(loss_counts_real[D]))
        if gmm_real[D] is None:
            print(f"P.452 {D} km terrain: N={n_tr} | GMM2 CDF: (not enough data)")
        else:
            w1, mu1, s1, w2, mu2, s2 = gmm_real[D]
            print(
                f"P.452 {D} km terrain: N={n_tr} | "
                f"GMM2: w1={w1:.2f} μ1={mu1:.1f} σ1={s1:.1f} | "
                f"w2={w2:.2f} μ2={mu2:.1f} σ2={s2:.1f}"
            )


# ============================================================
# MAIN
# ============================================================
def main():
    
    if not os.path.isdir(TILES_250_DIR):
        raise RuntimeError(f"TILES_250_DIR not found: {TILES_250_DIR}")

    available_tiles = scan_available_tiles(TILES_250_DIR)
    if not available_tiles:
        raise RuntimeError("No tiles found (check directory and naming convention).")

    available_tiles_list = list(available_tiles)
    cities_gdf = load_cities_over_pop(min_pop=500)
    tiles_set = set(available_tiles_list)

    city_lats, city_lons, city_w = filter_cities_by_bbox_and_tiles(cities_gdf, tiles_set)

    print(f"Cities used (>100k, filtered): {len(city_lats)}")
    print(f"Tiles available: {len(available_tiles_list)}")
    print(f"Workers: {N_WORKERS} | Target paths: {TARGET_PATHS} | Update every: {UPDATE_EVERY}")
    print(f"Fig2 subplots = {len(DISTANCES_TEST)} distances: {DISTANCES_TEST}")

    # streaming histogram counts (real DEM)
    d_counts = np.zeros((len(D_BINS) - 1,), dtype=np.int64)
    h_counts = np.zeros((len(H_BINS) - 1,), dtype=np.int64)
    # streaming histogram counts (stat round-trip)
    d_counts_stat_rt = np.zeros((len(D_BINS) - 1,), dtype=np.int64)
    h_counts_stat_rt = np.zeros((len(H_BINS) - 1,), dtype=np.int64)
    # AR(2) accumulators for h_extrema lag-1 and lag-2 autocorrelations
    ar1_sum_x = 0.0
    ar1_sum_x2 = 0.0
    ar1_n = 0
    ar1_sum_xy = 0.0
    ar1_n_pairs = 0
    ar1_sum_xy2 = 0.0
    ar1_n_pairs2 = 0

    loss_counts_real = {D: np.zeros((len(LOSS_BINS) - 1,), dtype=np.int64) for D in DISTANCES_TEST}
    loss_counts_none = {D: np.zeros((len(LOSS_BINS) - 1,), dtype=np.int64) for D in DISTANCES_TEST}
    loss_counts_stat = {D: np.zeros((len(LOSS_BINS) - 1,), dtype=np.int64) for D in DISTANCES_TEST}
    loss_values_delta = {D: [] for D in DISTANCES_TEST}

    # reservoirs for fitting
    res_d = Reservoir(RESERVOIR_MAX_DH, seed=RESERVOIR_SEED + 0)
    res_h = Reservoir(RESERVOIR_MAX_DH, seed=RESERVOIR_SEED + 1)

    # IMPORTANT: P.452 fit is ONLY for TERRAIN
    res_loss_real = {D: Reservoir(RESERVOIR_MAX_LOSS, seed=RESERVOIR_SEED + 10 + i)
                     for i, D in enumerate(DISTANCES_TEST)}

    # figures
    fig1_pack, fig2_pack, fig3_pack = init_figures()
    (_, ax_map, _, _) = fig1_pack

    # async pipeline
    seed_rng = np.random.RandomState(777)
    inflight = {}
    accepted = 0
    debug_profile_plotted = False

    def submit_one(ex):
        seed = int(seed_rng.randint(0, 2**31 - 1))
        fut = ex.submit(
            worker_one,
            seed,
            available_tiles_list,
            city_lats, city_lons, city_w,
            D_BINS, H_BINS, LOSS_BINS,
            DISTANCES_TEST, FREQ_GHZ,
            ENABLE_STAT_VALIDATION, STAT_VALIDATION_LOCATION,
        )
        inflight[fut] = seed

    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        for _ in range(min(INFLIGHT, TARGET_PATHS)):
            submit_one(ex)

        pbar = tqdm(total=TARGET_PATHS, desc="Accepted paths")

        while accepted < TARGET_PATHS:
            for fut in as_completed(list(inflight.keys())):
                inflight.pop(fut, None)

                try:
                    result = fut.result()
                except Exception:
                    if accepted + len(inflight) < TARGET_PATHS:
                        submit_one(ex)
                    continue

                # ---- one-shot debug figure: 1 real profile vs N statistical profiles
                if (not debug_profile_plotted
                        and "real_profile_d" in result
                        and ENABLE_STAT_VALIDATION):
                    real_d = result["real_profile_d"]
                    real_h = result["real_profile_h"]
                    real_h_centered = real_h - real_h[0]

                    debug_rng = np.random.default_rng(42)
                    n_stat = 3
                    stat_profiles = [
                        generate_terrain_profile(debug_rng, float(real_d[-1]),
                                                 STAT_VALIDATION_LOCATION)
                        for _ in range(n_stat)
                    ]

                    fig_dbg, ax_dbg = plt.subplots(1, 1, figsize=(12, 5),
                                                   facecolor='w', edgecolor='k')
                    ax_dbg.plot(real_d, real_h_centered, color='black',
                                linewidth=1.8, label="Real DEM (centered at h[0]=0)")
                    for i, (sd, sh) in enumerate(stat_profiles):
                        ax_dbg.plot(sd, sh, linewidth=1.0, alpha=0.8,
                                    label=f"Statistical ({STAT_VALIDATION_LOCATION}) #{i+1}")
                    ax_dbg.set_xlabel("Distance [km]")
                    ax_dbg.set_ylabel("Height [m]")
                    ax_dbg.set_title(
                        f"Diagnostic — Real DEM vs P.452 statistical profile\n"
                        f"Real: range={real_h.max()-real_h.min():.0f} m, "
                        f"std={real_h.std():.0f} m | "
                        f"Stat: median |hseg|={np.exp(3.2644):.0f} m"
                    )
                    ax_dbg.grid(True, alpha=0.4)
                    ax_dbg.legend(fontsize=8, loc="best")
                    fig_dbg.tight_layout()
                    fig_dbg.canvas.draw_idle()
                    plt.pause(0.01)
                    debug_profile_plotted = True

                # aggregate peak/valley hist (real DEM)
                d_counts += result["d_hist"]
                h_counts += result["h_hist"]
                # aggregate peak/valley hist (stat round-trip)
                if "d_hist_stat" in result:
                    d_counts_stat_rt += result["d_hist_stat"]
                if "h_hist_stat" in result:
                    h_counts_stat_rt += result["h_hist_stat"]
                # aggregate AR(2) lag-1 and lag-2 stats for h_extrema
                ar1_sum_x += result.get("h_sum_x", 0.0)
                ar1_sum_x2 += result.get("h_sum_x2", 0.0)
                ar1_n += result.get("h_n", 0)
                ar1_sum_xy += result.get("h_sum_xy", 0.0)
                ar1_n_pairs += result.get("h_n_pairs", 0)
                ar1_sum_xy2 += result.get("h_sum_xy2", 0.0)
                ar1_n_pairs2 += result.get("h_n_pairs2", 0)

                # aggregate loss hists
                for D in DISTANCES_TEST:
                    loss_counts_real[D] += result["loss_hist_real"][D]
                    loss_counts_none[D] += result["loss_hist_none"][D]
                    if "loss_hist_stat" in result:
                        loss_counts_stat[D] += result["loss_hist_stat"][D]
                    if D in result["loss_samp_delta"]:
                        loss_values_delta[D].append(result["loss_samp_delta"][D])

                # reservoirs
                res_d.add(result["d_samp"])
                res_h.add(result["h_samp"])

                # terrain-only reservoir for p452 fit
                for D, v in result["loss_samp_real"].items():
                    res_loss_real[D].add(np.array([v], dtype=float))

                # plot path line (only)
                lat0, lon0, lat1, lon1 = result["path_line"]
                ax_map.plot([lon0, lon1], [lat0, lat1], color="red", linewidth=1.0, alpha=0.6)

                accepted += 1
                pbar.update(1)

                if accepted + len(inflight) < TARGET_PATHS:
                    submit_one(ex)

                if (accepted % UPDATE_EVERY) == 0 or accepted == TARGET_PATHS:
                    update_plots(
                        fig1_pack, fig2_pack, fig3_pack,
                        d_counts, h_counts,
                        loss_counts_real, loss_counts_none, loss_values_delta,
                        res_d, res_h,
                        res_loss_real,
                        accepted,
                        loss_counts_stat=loss_counts_stat if ENABLE_STAT_VALIDATION else None,
                        stat_location=STAT_VALIDATION_LOCATION if ENABLE_STAT_VALIDATION else None,
                        d_counts_stat_rt=d_counts_stat_rt if ENABLE_STAT_VALIDATION else None,
                        h_counts_stat_rt=h_counts_stat_rt if ENABLE_STAT_VALIDATION else None,
                        ar1_stats={
                            "sum_x": ar1_sum_x,
                            "sum_x2": ar1_sum_x2,
                            "n": ar1_n,
                            "sum_xy": ar1_sum_xy,
                            "n_pairs": ar1_n_pairs,
                            "sum_xy2": ar1_sum_xy2,
                            "n_pairs2": ar1_n_pairs2,
                        },
                    )

                if accepted >= TARGET_PATHS:
                    break

        pbar.close()

    print("\nDone.")
    plt.ioff()
    plt.show()


if __name__ == "__main__":
    main()
