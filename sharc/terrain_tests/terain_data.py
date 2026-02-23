import os
import random
import numpy as np
import requests
import rasterio
import matplotlib.pyplot as plt

from tqdm import tqdm
from scipy.signal import find_peaks, savgol_filter
from geopy import Point
import gzip
from geopy.distance import distance

from rasterio.warp import transform, transform_bounds
from scipy import stats

# =============================
# CONFIG
# =============================
N_PATHS = 2
PATH_LENGTH_KM = 300
N_SAMPLES = 300

TILE_DIR = "terrain_tests/op90_tiles"
BASE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/"

os.makedirs(TILE_DIR, exist_ok=True)

# =============================
# TILE NAME (COP90)
# =============================
def tile_name(lat, lon):
    lat_deg = int(np.floor(lat))
    lon_deg = int(np.floor(lon))

    ns = "N" if lat_deg >= 0 else "S"
    ew = "E" if lon_deg >= 0 else "W"

    # pasta
    folder = f"{ns}{abs(lat_deg):02d}"

    # arquivo
    file = f"{ns}{abs(lat_deg):02d}{ew}{abs(lon_deg):03d}.hgt.gz"

    return folder, file

# =============================
# DOWNLOAD TILE
# =============================
def download_tile(folder, file):
    path_gz = os.path.join(TILE_DIR, file)
    path = path_gz.replace(".gz", "")

    if os.path.exists(path):
        return path

    url = BASE_URL + f"{folder}/{file}"

    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            with open(path_gz, "wb") as f:
                f.write(r.content)

            # unzip
            with gzip.open(path_gz, "rb") as f_in:
                with open(path, "wb") as f_out:
                    f_out.write(f_in.read())

            return path
        else:
            print("404:", url)

    except Exception as e:
        print("download error:", e)

    return None

# =============================
# PATH UTILS
# =============================
def random_point():
    return random.uniform(-60, 60), random.uniform(-180, 180)

def destination_point(lat, lon, distance_km, bearing):
    origin = Point(lat, lon)
    dest = distance(kilometers=distance_km).destination(origin, bearing)
    return dest.latitude, dest.longitude

def interpolate_path(start, end, n):
    lats = np.linspace(start[0], end[0], n)
    lons = np.linspace(start[1], end[1], n)
    return list(zip(lats, lons))

# =============================
# PREP TILE METADATA (bounds in EPSG:4326)
# =============================
def bounds_lonlat(ds):
    # transforma bounds do CRS do raster para EPSG:4326
    return transform_bounds(ds.crs, "EPSG:4326", *ds.bounds, densify_pts=21)

# =============================
# SAMPLE ELEVATION (robusto)
# =============================
def sample_elevation(path_latlon, tiles_ds):
    elev = np.full(len(path_latlon), np.nan, dtype=float)

    for i, (lat, lon) in enumerate(path_latlon):
        folder, file = tile_name(lat, lon)
        ds = tiles_ds.get(file, None)

        if ds is None:
            continue

        x, y = lon, lat

        if ds.crs and str(ds.crs).upper() != "EPSG:4326":
            x, y = transform("EPSG:4326", ds.crs, [x], [y])
            x, y = x[0], y[0]

        v = list(ds.sample([(x, y)]))[0][0]

        if ds.nodata is not None and v == ds.nodata:
            continue

        elev[i] = float(v)

    return elev

# =============================
# FIT DISTRIBUTIONS (AIC + KS)
# =============================
def fit_best_distribution(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    x = x[x > 0]  # distâncias/alturas devem ser positivas

    if len(x) < 50:
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
            # para variáveis estritamente positivas, ajuda forçar loc=0 (quando faz sentido)
            if name in ["expon", "gamma", "weibull_min", "lognorm"]:
                params = dist.fit(x, floc=0)
            else:
                params = dist.fit(x)

            ll = np.sum(dist.logpdf(x, *params))
            k = len(params)
            aic = 2 * k - 2 * ll

            # KS
            D, p = stats.kstest(x, name, args=params)

            results.append((aic, name, params, D, p))
        except Exception:
            continue

    if not results:
        return None

    results.sort(key=lambda t: t[0])  # menor AIC
    best = results[0]
    return best, results

def plot_fit_on_hist(x, best_tuple, title):
    aic, name, params, D, p = best_tuple
    dist = getattr(stats, name)

    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    x = x[x > 0]

    plt.figure()
    plt.hist(x, bins=120, density=True, alpha=0.6)
    plt.title(f"{title}\nBest fit: {name} | AIC={aic:.1f} | KS D={D:.3f}, p={p:.3g}")

    xs = np.linspace(np.min(x), np.percentile(x, 99.5), 800)
    ys = dist.pdf(xs, *params)
    plt.plot(xs, ys, linewidth=2)
    plt.xlabel(title)
    plt.ylabel("PDF")

# =============================
# GENERATE PATHS
# =============================
print("\nGenerating paths...")
paths = []
tiles = set()

for _ in tqdm(range(N_PATHS), desc="Paths"):
    start = random_point()
    end = destination_point(*start, PATH_LENGTH_KM, random.uniform(0, 360))
    path = interpolate_path(start, end, N_SAMPLES)
    paths.append(path)

    for lat, lon in path:
        folder, file = tile_name(lat, lon)
        tiles.add((folder, file))
# =============================
# DOWNLOAD / OPEN TILES
# =============================
print(f"\nDownloading tiles ({len(tiles)} needed)...")
tiles_ds = {}
tiles_bounds4326 = {}

for folder, file in tqdm(list(tiles), desc="Tiles"):
    p = download_tile(folder, file)
    if p:
        tiles_ds[file] = rasterio.open(p)

# =============================
# PROFILING
# =============================
print("\nProcessing terrain profiles...")
all_d, all_h = [], []

# também guardo os perfis pra depurar/visualizar se quiser
debug_profiles = 0

for path in tqdm(paths, desc="Profiles"):
    elev = sample_elevation(path, tiles_ds)

    # remove NaNs (mas mantém alinhamento via mask)
    valid = np.isfinite(elev)
    if valid.sum() < max(50, N_SAMPLES // 4):
        continue

    e = elev.copy()

    # interpola buracos pequenos
    idx = np.arange(len(e))
    e[~valid] = np.interp(idx[~valid], idx[valid], e[valid])

    # suavização com janela adaptativa (sempre ímpar e <= len)
    win = min(51, len(e) // 2 * 2 - 1)
    win = max(win, 11)
    if win >= len(e):
        win = len(e) - 1 if (len(e) % 2 == 0) else len(e)
    if win < 7:
        continue

    e_s = savgol_filter(e, win, 3)

    # picos/vales com proeminência adaptativa
    relief = np.nanpercentile(e_s, 95) - np.nanpercentile(e_s, 5)
    prom = max(5.0, 0.05 * relief)   # pelo menos 5 m ou 5% do relevo típico
    dist_min = max(3, int(0.02 * N_SAMPLES))  # 2% do comprimento amostrado

    peaks, _ = find_peaks(e_s, prominence=prom, distance=dist_min)
    valleys, _ = find_peaks(-e_s, prominence=prom, distance=dist_min)
    extrema = np.sort(np.concatenate([peaks, valleys]))

    if len(extrema) < 2:
        # se o terreno for muito “liso”, relaxa um pouco
        peaks, _ = find_peaks(e_s, prominence=max(2.0, 0.02 * relief), distance=max(2, dist_min // 2))
        valleys, _ = find_peaks(-e_s, prominence=max(2.0, 0.02 * relief), distance=max(2, dist_min // 2))
        extrema = np.sort(np.concatenate([peaks, valleys]))

    if len(extrema) < 2:
        continue

    step_km = PATH_LENGTH_KM / (N_SAMPLES - 1)

    for i in range(len(extrema) - 1):
        i0, i1 = extrema[i], extrema[i + 1]
        d = step_km * (i1 - i0)
        h = abs(e_s[i1] - e_s[i0])
        if np.isfinite(d) and np.isfinite(h) and d > 0 and h > 0:
            all_d.append(d)
            all_h.append(h)

# =============================
# REPORT + PLOTS
# =============================
all_d = np.array(all_d, dtype=float)
all_h = np.array(all_h, dtype=float)

print("\n=== RESULTS ===")
print(f"Segments (distance): {len(all_d)}")
print(f"Segments (height):   {len(all_h)}")

if len(all_d) == 0 or len(all_h) == 0:
    print("\nNada foi extraído. Normalmente é CRS/tiles fora do ponto, ou thresholds muito altos.")
    print("Com as correções acima, isso costuma resolver; se ainda der zero, a URL/tiles pode não corresponder ao nome.")
else:
    def basic_stats(x):
        return {
            "N": len(x),
            "mean": float(np.mean(x)),
            "median": float(np.median(x)),
            "std": float(np.std(x)),
            "p95": float(np.percentile(x, 95)),
            "p99": float(np.percentile(x, 99)),
            "min": float(np.min(x)),
            "max": float(np.max(x)),
        }

    print("\nDistance stats (km):", basic_stats(all_d))
    print("Height stats (m):   ", basic_stats(all_h))

    # Hist
    plt.figure()
    plt.hist(all_d, bins=120)
    plt.title("Peak-Valley distance (km)")
    plt.xlabel("Distance (km)")
    plt.ylabel("Count")

    plt.figure()
    plt.hist(all_h, bins=120)
    plt.title("Peak-Valley height (m)")
    plt.xlabel("Height (m)")
    plt.ylabel("Count")

    # Fits
    fit_d = fit_best_distribution(all_d)
    fit_h = fit_best_distribution(all_h)

    if fit_d:
        best_d, all_res_d = fit_d
        print("\nBest fit for distance by AIC:", best_d[1], "| AIC=", round(best_d[0], 2), "| KS p=", best_d[4])
        plot_fit_on_hist(all_d, best_d, "Peak-Valley distance (km)")
    else:
        print("\nNot enough data to fit distance distributions.")

    if fit_h:
        best_h, all_res_h = fit_h
        print("Best fit for height by AIC:", best_h[1], "| AIC=", round(best_h[0], 2), "| KS p=", best_h[4])
        plot_fit_on_hist(all_h, best_h, "Peak-Valley height (m)")
    else:
        print("Not enough data to fit height distributions.")

# =============================
# MAP WITH RANDOM CUTS + COUNTRIES
# =============================
import geopandas as gpd

# carregar shapefile global Natural Earth
world = gpd.read_file(
    "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
)
fig, ax = plt.subplots(figsize=(10,6))

# ⭐ contornos dos países
world.boundary.plot(ax=ax, color="black", linewidth=0.5)

# ⭐ opcional: preencher países
# world.plot(ax=ax, color="lightgray", edgecolor="white")

# ⭐ paths
for path in paths:
    lats = [p[0] for p in path]
    lons = [p[1] for p in path]
    ax.plot(lons, lats, linewidth=1, alpha=0.8)

ax.set_title("Random terrain cuts over countries")
ax.set_xlabel("Longitude (deg)")
ax.set_ylabel("Latitude (deg)")
ax.grid(True, alpha=0.3)



# ============================================================
# ======================= P452 ANALYSIS ======================
# ============================================================

print("\n==============================================")
print("Running P.452 comparison (DEM vs flat)")
print("==============================================")

from sharc.propagation.propagation_clear_air_452 import PropagationClearAir
from sharc.parameters.parameters_p452 import ParametersP452

# ------------------------------------------------------------
# Setup P452
# ------------------------------------------------------------
rng = np.random.RandomState(1234)
params_p452 = ParametersP452()
prop452 = PropagationClearAir(rng, params_p452)

DISTANCES_TEST = [50, 100, 150, 200, 250]

loss_real = {d: [] for d in DISTANCES_TEST}
loss_flat = {}

# ------------------------------------------------------------
# Helper function
# ------------------------------------------------------------
def compute_p452_loss(D_km, d_prof, h_prof):

    distance = np.array([[D_km]])
    freq = np.array([[6.0]])       # ajuste frequência se quiser
    indoor = np.array([[False]])
    elev = np.array([[0]])
    txg = np.array([[0]])
    rxg = np.array([[0]])

    # ---------- com terreno ----------
    params_p452.terrain_d = d_prof
    params_p452.terrain_h = h_prof
    loss_r = prop452.get_loss(distance, freq, indoor, elev, txg, rxg)[0, 0]

    # ---------- sem terreno ----------
    params_p452.terrain_d = None
    params_p452.terrain_h = None
    loss_f = prop452.get_loss(distance, freq, indoor, elev, txg, rxg)[0, 0]

    return float(loss_r), float(loss_f)

# ------------------------------------------------------------
# Loop sobre perfis DEM
# ------------------------------------------------------------
print("\nProcessing DEM profiles with P.452...")

for path in tqdm(paths, desc="P452 DEM profiles"):

    # -------- extrair perfil DEM --------
    elev = sample_elevation(path, tiles_ds)

    valid = np.isfinite(elev)
    if valid.sum() < 30:
        continue

    e = elev.copy()
    idx = np.arange(len(e))
    e[~valid] = np.interp(idx[~valid], idx[valid], e[valid])

    # suavização leve
    e_s = savgol_filter(e, 11, 3)

    # -------- construir perfil d/h --------
    d_profile = np.linspace(0, PATH_LENGTH_KM, len(e_s))
    h_profile = e_s.copy()

    # -------- truncar para distâncias alvo --------
    for D in DISTANCES_TEST:

        mask = d_profile <= D
        if mask.sum() < 5:
            continue

        d_sub = d_profile[mask]
        h_sub = h_profile[mask]

        # garantir último ponto exatamente D
        d_sub[-1] = D

        lr, lf = compute_p452_loss(D, d_sub, h_sub)

        loss_real[D].append(lr)
        loss_flat[D] = lf

# ------------------------------------------------------------
# Plot results
# ------------------------------------------------------------
print("\nPlotting P.452 distributions...")

fig, axs = plt.subplots(1, len(DISTANCES_TEST), figsize=(18,4), sharey=True)

for i, D in enumerate(DISTANCES_TEST):

    if len(loss_real[D]) == 0:
        continue

    axs[i].hist(loss_real[D], bins=25, density=True, alpha=0.7)
    axs[i].axvline(loss_flat[D], color='r', lw=2)
    axs[i].set_title(f"{D} km")

axs[0].set_ylabel("PDF")
plt.tight_layout()
plt.show()

# ------------------------------------------------------------
# Envelope statistics
# ------------------------------------------------------------
print("\nP.452 statistics (DEM terrain):")

for D in DISTANCES_TEST:
    if len(loss_real[D]) == 0:
        continue

    arr = np.array(loss_real[D])
    print(
        f"{D} km -> "
        f"mean={arr.mean():.2f}, "
        f"p10={np.percentile(arr,10):.2f}, "
        f"p50={np.percentile(arr,50):.2f}, "
        f"p90={np.percentile(arr,90):.2f}"
    )

print("\nDone.")


plt.show()

# =============================
# CLEANUP
# =============================
for ds in tiles_ds.values():
    try:
        ds.close()
    except Exception:
        pass