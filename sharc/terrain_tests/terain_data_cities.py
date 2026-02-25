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

# ---- SHARC / P.452
from sharc.propagation.propagation_clear_air_452 import PropagationClearAir
from sharc.parameters.parameters_p452 import ParametersP452


# ============================================================
# CONFIG
# ============================================================
TILES_250_DIR = r"sharc/terrain_tests/global_dem/tiles_250m_tif"
NODATA_I16 = np.int16(-32768)

PATH_LENGTH_KM = 300.0
STEP_KM = 1.0
N_SAMPLES = int(PATH_LENGTH_KM / STEP_KM) + 1  # 301

REGION = "World"  #"America", "Europe", "Asia", "Africa", "Oceania", "World"

N_WORKERS = 10
TARGET_PATHS = 50000
INFLIGHT = 4 * N_WORKERS
UPDATE_EVERY = 5000

SG_WIN = 11
SG_POLY = 3
MIN_EXTREMA = 2

# Fig2 will create one subplot per distance here
DISTANCES_TEST = [100, 200, 300]
FREQ_GHZ = 8.0

# Histogram bins (counts stored). Density computed at plot time.
D_BINS = np.linspace(0, 60, 61)
H_BINS = np.linspace(0, 2500, 251)
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
def compute_p452_losses(d_profile, h_profile, distances_test, freq_ghz):
    rng = np.random.RandomState()
    params_p452 = ParametersP452()
    prop452 = PropagationClearAir(rng, params_p452)
    params_p452.clutter_loss = False
    params_p452.percentage_p = 'RANDOM'

    def loss_for(D_km, d_prof, h_prof, terrain_mode="real"):
        distance = np.array([[float(D_km)]], dtype=float)
        freq = np.array([[float(freq_ghz)]], dtype=float)
        indoor = np.array([[False]])
        elev = np.array([[0]])
        txg = np.array([[0]])
        rxg = np.array([[0]])

        if terrain_mode == "real":
            params_p452.terrain_d = d_prof
            params_p452.terrain_h = h_prof
        elif terrain_mode == "none":
            params_p452.terrain_d = None
            params_p452.terrain_h = None
        else:
            raise ValueError("terrain_mode must be 'real' or 'none'")

        lr = prop452.get_loss(distance, freq, indoor, elev, txg, rxg)[0, 0]
        return float(lr)

    out_real, out_none = {}, {}

    for D in distances_test:
        mask = d_profile <= (D + 1e-9)
        d_sub = d_profile[mask].copy()
        h_sub = h_profile[mask].copy()

        if d_sub.size < 4:
            out_real[D] = np.nan
            out_none[D] = np.nan
            continue

        if d_sub[-1] < D:
            d_sub = np.append(d_sub, D)
            h_sub = np.append(h_sub, h_sub[-1])
        else:
            d_sub[-1] = D

        if not np.all(np.diff(d_sub) > 0):
            out_real[D] = np.nan
            out_none[D] = np.nan
            continue

        out_real[D] = loss_for(D, d_sub, h_sub, "real")
        out_none[D] = loss_for(D, d_sub, h_sub, "none")

    return out_real, out_none


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
def fit_best_distribution(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    x = x[x > 0]
    if x.size < 300:
        return None

    candidates = {
        "expon": stats.expon,
        "lognorm": stats.lognorm,
        "norm": stats.norm,
        "gamma": stats.gamma,
        "weibull_min": stats.weibull_min,
        "t": stats.t,
    }

    results = []
    for name, dist in candidates.items():
        try:
            if name in ["expon", "gamma", "weibull_min", "lognorm"]:
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
# Worker: generate ONE valid path and return streaming contributions
# ============================================================
def worker_one(seed: int,
               available_tiles_list,
               city_lats, city_lons, city_w,
               d_bins, h_bins, loss_bins,
               distances_test, freq_ghz):

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
            # Peak/valley segments
            relief = np.percentile(e_s, 95) - np.percentile(e_s, 5)
            prom = max(5.0, 0.05 * relief)
            dist_min = max(3, int(0.02 * len(e_s)))

            peaks, _ = find_peaks(e_s, prominence=prom, distance=dist_min)
            valleys, _ = find_peaks(-e_s, prominence=prom, distance=dist_min)
            extrema = np.sort(np.concatenate([peaks, valleys]))

            if extrema.size < MIN_EXTREMA:
                peaks, _ = find_peaks(e_s, prominence=max(2.0, 0.02 * relief), distance=max(2, dist_min // 2))
                valleys, _ = find_peaks(-e_s, prominence=max(2.0, 0.02 * relief), distance=max(2, dist_min // 2))
                extrema = np.sort(np.concatenate([peaks, valleys]))

            if extrema.size < MIN_EXTREMA:
                dseg = np.array([], dtype=float)
                hseg = np.array([], dtype=float)
            else:
                dseg = STEP_KM * np.diff(extrema.astype(float))
                hseg = np.abs(np.diff(e_s[extrema].astype(float)))
                mask = (dseg > 0) & (hseg > 0) & np.isfinite(dseg) & np.isfinite(hseg)
                dseg = dseg[mask]
                hseg = hseg[mask]

            d_hist = np.histogram(dseg, bins=d_bins)[0].astype(np.int64)
            h_hist = np.histogram(hseg, bins=h_bins)[0].astype(np.int64)

            # P.452 at distances_test
            d_prof = np.arange(0.0, PATH_LENGTH_KM + 1e-9, STEP_KM, dtype=float)
            if d_prof.size != e_s.size:
                d_prof = np.linspace(0.0, PATH_LENGTH_KM, e_s.size, dtype=float)

            losses_real, losses_none = compute_p452_losses(d_prof, e_s, distances_test, freq_ghz)

            loss_hist_real = {D: np.zeros((len(loss_bins) - 1,), dtype=np.int64) for D in distances_test}
            loss_hist_none = {D: np.zeros((len(loss_bins) - 1,), dtype=np.int64) for D in distances_test}

            loss_samples_real = {}
            loss_samples_none = {}

            for D in distances_test:
                v = losses_real.get(D, np.nan)
                if np.isfinite(v):
                    loss_hist_real[D] = np.histogram([v], bins=loss_bins)[0].astype(np.int64)
                    loss_samples_real[D] = float(v)

                v2 = losses_none.get(D, np.nan)
                if np.isfinite(v2):
                    loss_hist_none[D] = np.histogram([v2], bins=loss_bins)[0].astype(np.int64)
                    loss_samples_none[D] = float(v2)

            # Reservoir samples (downsample segments)
            max_take = 512
            if dseg.size > max_take:
                idx = rng.choice(dseg.size, size=max_take, replace=False)
                d_take = dseg[idx]
                h_take = hseg[idx]
            else:
                d_take = dseg
                h_take = hseg

            path_line = (float(s_lat), float(s_lon), float(e_lat), float(e_lon))

            return {
                "d_hist": d_hist,
                "h_hist": h_hist,
                "loss_hist_real": loss_hist_real,
                "loss_hist_none": loss_hist_none,
                "d_samp": d_take.astype(float),
                "h_samp": h_take.astype(float),
                "loss_samp_real": loss_samples_real,
                "loss_samp_none": loss_samples_none,
                "path_line": path_line,
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

    return (fig1, ax_map, ax_d, ax_h), (fig2, axs)


def update_plots(fig1_pack, fig2_pack,
                 d_counts, h_counts,
                 loss_counts_real, loss_counts_none,
                 res_d, res_h,
                 res_loss_real,
                 n_paths_done):

    (fig1, ax_map, ax_d, ax_h) = fig1_pack
    (fig2, axs_loss) = fig2_pack

    # ---- Fits (distance/height on reservoirs; P.452 GMM ONLY on TERRAIN reservoir)
    d_fit = fit_best_distribution(res_d.get())
    h_fit = fit_best_distribution(res_h.get())
    gmm_real = {D: fit_gmm2(res_loss_real[D].get()) for D in DISTANCES_TEST}

    # ---- FIG1: distance density + best-fit PDF (RED)
    ax_d.clear()
    centers_d = 0.5 * (D_BINS[:-1] + D_BINS[1:])
    dens_d = counts_to_density(d_counts, D_BINS)
    ax_d.bar(centers_d, dens_d, width=np.diff(D_BINS), align="center")
    ax_d.set_xlabel("km")
    ax_d.set_ylabel("density")
    ax_d.set_title(f"Peak–Valley distance (km)\nNseg={int(np.sum(d_counts))} | Npaths={n_paths_done}")
    overlay_bestfit_pdf(ax_d, d_fit, D_BINS, color=FIT_COLOR)

    # ---- FIG1: height density + best-fit PDF (RED)
    ax_h.clear()
    centers_h = 0.5 * (H_BINS[:-1] + H_BINS[1:])
    dens_h = counts_to_density(h_counts, H_BINS)
    ax_h.bar(centers_h, dens_h, width=np.diff(H_BINS), align="center")
    ax_h.set_xlabel("m")
    ax_h.set_ylabel("density")
    ax_h.set_title(f"Peak–Valley height (m)\nNseg={int(np.sum(h_counts))} | Npaths={n_paths_done}")
    overlay_bestfit_pdf(ax_h, h_fit, H_BINS, color=FIT_COLOR)

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

        # ===== LOG SCALE =====
        ax.set_yscale("log")
        ax.set_ylim(1e-4, 1)

        ax.set_xlabel("dB")
        ax.set_ylabel("CDF (log)")
        ax.set_title(
            f"P.452 loss @ {D} km\n"
            f"Nterrain={int(np.sum(loss_counts_real[D]))} | Nno={int(np.sum(loss_counts_none[D]))}"
        )

        ax.legend(fontsize=8, loc="best")

    fig2.tight_layout()
    fig2.canvas.draw_idle()

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
    cities_gdf = load_cities_over_pop(min_pop=10_000)
    tiles_set = set(available_tiles_list)

    city_lats, city_lons, city_w = filter_cities_by_bbox_and_tiles(cities_gdf, tiles_set)

    print(f"Cities used (>100k, filtered): {len(city_lats)}")
    print(f"Tiles available: {len(available_tiles_list)}")
    print(f"Workers: {N_WORKERS} | Target paths: {TARGET_PATHS} | Update every: {UPDATE_EVERY}")
    print(f"Fig2 subplots = {len(DISTANCES_TEST)} distances: {DISTANCES_TEST}")

    # streaming histogram counts
    d_counts = np.zeros((len(D_BINS) - 1,), dtype=np.int64)
    h_counts = np.zeros((len(H_BINS) - 1,), dtype=np.int64)

    loss_counts_real = {D: np.zeros((len(LOSS_BINS) - 1,), dtype=np.int64) for D in DISTANCES_TEST}
    loss_counts_none = {D: np.zeros((len(LOSS_BINS) - 1,), dtype=np.int64) for D in DISTANCES_TEST}

    # reservoirs for fitting
    res_d = Reservoir(RESERVOIR_MAX_DH, seed=RESERVOIR_SEED + 0)
    res_h = Reservoir(RESERVOIR_MAX_DH, seed=RESERVOIR_SEED + 1)

    # IMPORTANT: P.452 fit is ONLY for TERRAIN
    res_loss_real = {D: Reservoir(RESERVOIR_MAX_LOSS, seed=RESERVOIR_SEED + 10 + i)
                     for i, D in enumerate(DISTANCES_TEST)}

    # figures
    fig1_pack, fig2_pack = init_figures()
    (_, ax_map, _, _) = fig1_pack

    # async pipeline
    seed_rng = np.random.RandomState(777)
    inflight = {}
    accepted = 0

    def submit_one(ex):
        seed = int(seed_rng.randint(0, 2**31 - 1))
        fut = ex.submit(
            worker_one,
            seed,
            available_tiles_list,
            city_lats, city_lons, city_w,
            D_BINS, H_BINS, LOSS_BINS,
            DISTANCES_TEST, FREQ_GHZ
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

                # aggregate peak/valley hist
                d_counts += result["d_hist"]
                h_counts += result["h_hist"]

                # aggregate loss hists
                for D in DISTANCES_TEST:
                    loss_counts_real[D] += result["loss_hist_real"][D]
                    loss_counts_none[D] += result["loss_hist_none"][D]

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
                        fig1_pack, fig2_pack,
                        d_counts, h_counts,
                        loss_counts_real, loss_counts_none,
                        res_d, res_h,
                        res_loss_real,
                        accepted
                    )

                if accepted >= TARGET_PATHS:
                    break

        pbar.close()

    print("\nDone.")
    plt.ioff()
    plt.show()


if __name__ == "__main__":
    main()