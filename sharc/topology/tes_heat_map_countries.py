import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
from pathlib import Path
from sharc.topology.topology_countries import ParametersCountries, TopologyCountries
from sharc.support.sharc_geom import GeometryConverter

# ----------------- CONFIGURATIONS -----------------
num_runs = 30          # how many times to run the simulation
bs_per_run = 2000      # number of stations per simulation
rng_seed = 42          # initial seed
cell_radius_m = 10000  # cell radius in meters

# Density range filter (as implemented in topology_countries.py)
# Use ONE of the following options:
dist_type = "Suburban"      # "Urban" | "Suburban" | "Rural" | None
# dist_density_min = 800.0   # if you want an explicit range, define these and comment out dist_type
# dist_density_max = 6000.0  # (explicit range takes precedence over dist_type)

# Geographic data
shapefile_path = Path.cwd() / "sharc" / "topology" / "map" / "ne_110m_admin_0_countries.shp"
population_raster_path = Path.cwd() / "sharc" / "topology" / "map" / "SEDAC_map2.tiff"

# RASTER: choose the type that matches your GeoTIFF
#   "density" = ppl/km² (e.g.: GPWv4 density)
#   "count"   = people per pixel
#   "indexed" = 0..255 indices (e.g.: SEDAC/NEO) that will be mapped to density
raster_encoding = "indexed"        # change to "indexed" if your TIFF is palettized 0..255
sedac_palette_mode = "log"         # "log" or "linear" (only for indexed)
sedac_min = 1.0                    # ppl/km² (only for indexed)
sedac_max = 1e4                    # ppl/km² (only for indexed)
index_nodata = (0, 255)            # ignored indices (water/NoData) in indexed
act_palette_path = None            # path of .act (optional) to auto-detect "whites"

# Sampling (only for sampling; does not alter totals)
min_density_threshold = 0.0        # minimum ppl/km² for sampling
density_exponent = 1.0             # >1 pulls more towards dense areas

# Countries of the Americas
countries_americas = [
    # South America
    "Brazil", "Argentina", "Uruguay", "Paraguay", "Chile",
    "Bolivia", "Peru", "Ecuador", "Colombia", "Venezuela",
    "Guyana", "Suriname",

    # Central America
    "Belize", "Guatemala", "El Salvador", "Honduras",
    "Nicaragua", "Costa Rica", "Panama",

    # North America
    "Mexico", "United States of America", "Canada",

    # Caribbean (some examples)
    "Cuba", "Haiti", "Dominican Republic", "Jamaica",
    "Trinidad and Tobago"
]

# Coordinate reference (Brasilia)
geoconv = GeometryConverter()
geoconv.set_reference(-15.793889, -47.882778, 0.0)

# ----------------- ACCUMULATE RESULTS -----------------
all_lons, all_lats = [], []

for run in range(num_runs):
    params = ParametersCountries(
        country_names=countries_americas,
        num_bs_total=bs_per_run,
        cell_radius=cell_radius_m,
        countries_shapefile=shapefile_path,
        population_raster=population_raster_path,

        # --- NEW: density filters by type/range ---
        dist_type=dist_type,
        # dist_density_min=dist_density_min,
        # dist_density_max=dist_density_max,

        # --- Raster/legend (if using "indexed") ---
        raster_encoding=raster_encoding,
        sedac_palette_mode=sedac_palette_mode,
        sedac_min=sedac_min,
        sedac_max=sedac_max,
        index_nodata=index_nodata,
        act_colormap_path=act_palette_path,

        # --- pixel area and sampling ---
        pixel_area_method="spherical",
        min_density_threshold=min_density_threshold,
        density_exponent=density_exponent,

        # --- geometry: remove lakes from polygon ---
        mask_inland_water=True,
    )
    rng_run = np.random.RandomState(rng_seed + run)
    topo = TopologyCountries(params, geoconv, random_number_gen=rng_run)
    all_lons.extend(topo.lons)
    all_lats.extend(topo.lats)

all_lons = np.array(all_lons)
all_lats = np.array(all_lats)

# ----------------- HEATMAP -----------------
fig, ax = plt.subplots(figsize=(12, 14))

# Plot boundaries
world = gpd.read_file(shapefile_path)

if "name" in world.columns and "ADMIN" in world.columns:
    americas = world[(world["name"].isin(countries_americas)) |
                     (world["ADMIN"].isin(countries_americas))]
elif "name" in world.columns:
    americas = world[world["name"].isin(countries_americas)]
elif "ADMIN" in world.columns:
    americas = world[world["ADMIN"].isin(countries_americas)]
else:
    raise ValueError("Shapefile does not have 'name' or 'ADMIN' columns.")

americas.boundary.plot(ax=ax, linewidth=0.8, color="black")

# Create 2D histogram (spatial density)
bins = 200  # grid resolution
density, xedges, yedges = np.histogram2d(all_lons, all_lats, bins=bins)

# Plot heatmap
im = ax.imshow(
    density.T,
    origin="lower",
    extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]],
    cmap="hot",
    alpha=0.6
)

# Colorbar
cbar = plt.colorbar(im, ax=ax)
cbar.set_label("Number of BS (accumulated)")

band_txt = ""
if dist_type:
    band_txt = f" | band: {dist_type}"
# if you used explicit range:
# band_txt = f" | explicit band: [{dist_density_min}, {dist_density_max}) ppl/km²"

ax.set_xlabel("Longitude [°]")
ax.set_ylabel("Latitude [°]")
ax.set_title(
    f"Simulated distribution of {num_runs * bs_per_run} base stations in the Americas"
    f"{band_txt} | encoding={raster_encoding}"
)
plt.tight_layout()
plt.show()
