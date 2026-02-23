import numpy as np
import requests
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.signal import find_peaks, savgol_filter
import scipy.stats as st
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from shapely.geometry import Point
from shapely.ops import unary_union
from geopy import Point as GeoPoint
from geopy.distance import distance

# =============================
# CONFIG
# =============================
N_PATHS = 48
PATH_LENGTH_KM = 300
N_SAMPLES = 300
N_WORKERS = 4           # cuidado: API rate-limit; pode reduzir se der erro
LAND_THRESHOLD = 0.9
HIST_BINS = 210

# smoothing / peaks
SAVGOL_WINDOW = 11       # deve ser ímpar
SAVGOL_POLY = 3
PEAK_PROMINENCE = 20
PEAK_MIN_DISTANCE = 5

# API
API_URL = "https://api.open-elevation.com/api/v1/lookup"
API_TIMEOUT = 25
API_RETRIES = 4
API_THROTTLE = 0.25      # segundos
API_JITTER = 0.15        # aleatório adicional para espalhar requests

# =============================
# CCDF
# =============================
def plot_ccdf_log(data, label):
    data = np.asarray(data)
    data = data[np.isfinite(data)]
    data = data[data > 0]

    if len(data) < 3:
        print(f"[WARN] Not enough data for CCDF: {label}")
        return

    x = np.sort(data)
    ccdf = 1.0 - np.arange(1, len(x) + 1) / len(x)

    # evita log(0): corta no menor valor > 0
    mask = ccdf > 0
    x = x[mask]
    ccdf = ccdf[mask]

    plt.figure()
    plt.semilogy(x, ccdf, ".", markersize=4, label="empirical")
    plt.xlabel(label)
    plt.ylabel("CCDF (log scale)")
    plt.title(f"CCDF (log) for {label}")
    plt.grid(True, which="both", ls="--", alpha=0.4)
    plt.legend()

def plot_ccdf_with_fit(data, dist_name, params, xlabel="distance (km)"):

    data = np.asarray(data)
    data = data[data > 0]

    if len(data) < 3:
        print("[WARN] Not enough data for CCDF with fit.")
        return

    # mapping correto
    dist_map = {
        "normal": st.norm,
        "lognormal": st.lognorm,
        "gamma": st.gamma,
        "weibull": st.weibull_min,
        "tstudent": st.t
    }

    dist = dist_map[dist_name]

    x = np.sort(data)
    ccdf = 1.0 - np.arange(1, len(x) + 1) / len(x)

    x_fit = np.linspace(np.min(x), np.max(x), 500)
    ccdf_fit = dist.sf(x_fit, *params)

    mask = ccdf > 0
    plt.figure()
    plt.semilogy(x[mask], ccdf[mask], ".", label="empirical")
    plt.semilogy(x_fit, ccdf_fit, "r-", lw=2, label=f"{dist_name} fit")
    plt.xlabel(xlabel)
    plt.ylabel("CCDF (log)")
    plt.title("CCDF with fit")
    plt.grid(True, which="both")
    plt.legend()

# =============================
# LAND MASK
# =============================
land_shp = shpreader.natural_earth("50m", "physical", "land")
land_geom = unary_union(list(shpreader.Reader(land_shp).geometries()))

def is_land(lat, lon):
    return land_geom.contains(Point(lon, lat))

def random_land_point():
    while True:
        lat = random.uniform(-80, 80)
        lon = random.uniform(-180, 180)
        if is_land(lat, lon):
            return lat, lon

# =============================
# DESTINATION / PATH
# =============================
def destination_point(lat, lon, distance_km, bearing):
    origin = GeoPoint(lat, lon)
    dest = distance(kilometers=distance_km).destination(origin, bearing)
    return dest.latitude, dest.longitude

def interpolate_path(start, end, n):
    lats = np.linspace(start[0], end[0], n)
    lons = np.linspace(start[1], end[1], n)
    return list(zip(lats, lons))

def path_on_land(path):
    count = sum(is_land(lat, lon) for lat, lon in path)
    return (count / len(path)) >= LAND_THRESHOLD

# =============================
# CACHE + THREAD SAFETY
# =============================
elev_cache = {}
cache_lock = threading.Lock()

# Uma Session compartilhada pode dar dor de cabeça em multi-thread.
# Vamos criar session por thread usando thread-local:
thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session

# =============================
# ELEVATION
# =============================
def get_elevation(points):
    """
    Busca elevação com cache + retry.
    Cache key: lat/lon arredondado.
    """
    out = [None] * len(points)
    batch = []
    batch_positions = []

    # 1) tenta cache
    for i, p in enumerate(points):
        key = (round(p[0], 4), round(p[1], 4))
        with cache_lock:
            val = elev_cache.get(key, None)
        if val is not None:
            out[i] = val
        else:
            batch.append({"latitude": float(p[0]), "longitude": float(p[1])})
            batch_positions.append(i)

    # 2) consulta API só pros misses
    if batch:
        sess = get_session()
        for attempt in range(API_RETRIES):
            try:
                res = sess.post(API_URL, json={"locations": batch}, timeout=API_TIMEOUT)
                res.raise_for_status()
                data = res.json()["results"]

                # sanity check
                if len(data) != len(batch):
                    raise RuntimeError("API returned unexpected number of results.")

                for k, dct in enumerate(data):
                    val = float(dct["elevation"])
                    i = batch_positions[k]
                    out[i] = val

                    key = (round(batch[k]["latitude"], 4), round(batch[k]["longitude"], 4))
                    with cache_lock:
                        elev_cache[key] = val
                break

            except Exception as e:
                if attempt == API_RETRIES - 1:
                    print(f"[WARN] Elevation API failed after retries: {e}")
                    # fallback: preenche faltantes com 0 (ou np.nan)
                    for i in batch_positions:
                        if out[i] is None:
                            out[i] = 0.0
                else:
                    time.sleep(1.0 + 0.5 * attempt)

        # throttle para não “martelar” API
        time.sleep(API_THROTTLE + random.uniform(0, API_JITTER))

    return np.asarray(out, dtype=float)

# =============================
# WORKER
# =============================
def worker(_):
    # encontra um path majoritariamente em terra
    while True:
        start = random_land_point()
        bearing = random.uniform(0, 360)
        end = destination_point(*start, PATH_LENGTH_KM, bearing)
        path = interpolate_path(start, end, N_SAMPLES)
        if path_on_land(path):
            break

    elev = get_elevation(path)

    # smoothing
    if SAVGOL_WINDOW >= 5 and SAVGOL_WINDOW % 2 == 1 and len(elev) >= SAVGOL_WINDOW:
        elev = savgol_filter(elev, SAVGOL_WINDOW, SAVGOL_POLY)

    peaks, _ = find_peaks(elev, prominence=PEAK_PROMINENCE, distance=PEAK_MIN_DISTANCE)
    valleys, _ = find_peaks(-elev, prominence=PEAK_PROMINENCE, distance=PEAK_MIN_DISTANCE)
    extrema = np.sort(np.concatenate([peaks, valleys]))

    dist = []
    h = []

    if len(extrema) >= 2:
        step_km = PATH_LENGTH_KM / N_SAMPLES
        for i in range(len(extrema) - 1):
            d = step_km * (extrema[i + 1] - extrema[i])
            dh = abs(elev[extrema[i + 1]] - elev[extrema[i]])
            # filtros opcionais (evitar degenerados)
            if d > 0:
                dist.append(d)
            if dh > 0:
                h.append(dh)

    return path, dist, h

# =============================
# FIT
# =============================
def fit_and_compare(data, label):
    data = np.asarray(data)
    data = data[np.isfinite(data)]
    data = data[data > 0]

    if len(data) < 10:
        print(f"[WARN] Not enough data to fit {label}.")
        return None

    # nota: weibull_min é a Weibull (shape, loc, scale)
    fit_specs = {
        "normal":   (st.norm,       dict()),
        "lognormal":(st.lognorm,    dict(floc=0)),
        "gamma":    (st.gamma,      dict(floc=0)),
        "weibull":  (st.weibull_min,dict(floc=0)),
        "tstudent": (st.t,          dict()),
    }

    results = []
    for name, (dist, kwargs) in fit_specs.items():
        try:
            params = dist.fit(data, **kwargs)
            loglik = np.sum(dist.logpdf(data, *params))
            k = len(params)
            aic = 2 * k - 2 * loglik
            results.append((name, dist, params, aic))
        except Exception as e:
            print(f"[WARN] Fit failed for {name} on {label}: {e}")

    if not results:
        print(f"[WARN] No fits succeeded for {label}.")
        return None

    results.sort(key=lambda x: x[3])
    best_name, best_dist, best_params, best_aic = results[0]

    print(f"\nBest fit for {label}: {best_name} (AIC={best_aic:.2f})")
    print("Params:", best_params)

    # PDF plot
    x = np.linspace(np.min(data), np.max(data), 500)
    pdf = best_dist.pdf(x, *best_params)

    plt.figure()
    plt.hist(data, bins=HIST_BINS, density=True, alpha=0.5, label="data")
    plt.plot(x, pdf, "r-", lw=2, label=f"best {best_name}")
    plt.title(f"Fit for {label}")
    plt.legend()

    return best_name, best_dist, best_params

# =============================
# MAP SETUP
# =============================
plt.ion()
fig = plt.figure(figsize=(12, 6))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_global()
ax.add_feature(cfeature.COASTLINE)
ax.add_feature(cfeature.BORDERS, alpha=0.3)
ax.set_title("Terrain cuts (land-only, parallel)")

# =============================
# MAIN (parallel)
# =============================
all_d = []
all_h = []

with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
    futures = [ex.submit(worker, i) for i in range(N_PATHS)]

    for f in as_completed(futures):
        path, dist, h = f.result()

        all_d.extend(dist)
        all_h.extend(h)

        if len(path) >= 2:
            lats, lons = zip(*path)
            ax.plot(lons, lats, color="red", transform=ccrs.PlateCarree(), alpha=0.7)

        plt.pause(0.01)

plt.ioff()

# =============================
# HISTOGRAMS
# =============================
plt.figure()
plt.hist(all_d, bins=HIST_BINS)
plt.title("Peak-Valley Distance (km)")

plt.figure()
plt.hist(all_h, bins=HIST_BINS)
plt.title("Peak-Valley Height (m)")

# =============================
# FIT RESULTS
# =============================
best_d = fit_and_compare(all_d, "distance")
best_h = fit_and_compare(all_h, "height")

# =============================
# CCDF (log) for distances
# =============================
plot_ccdf_log(all_d, "Peak-Valley distance (km)")

# CCDF with best fit (distance), se disponível
if best_d is not None:
    best_name, best_dist, best_params = best_d
    # best_name já é "weibull" etc; usamos a survival function do scipy.stats dist
    plot_ccdf_with_fit(all_d, "weibull" if best_name == "weibull" else best_name, best_params)

plt.show()