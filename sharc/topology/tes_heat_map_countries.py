import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd

from sharc.topology.topology_countries import ParametersCountries, TopologyCountries
from sharc.support.sharc_geom import GeometryConverter

# ----------------- CONFIGURAÇÕES -----------------
num_runs = 200         # quantas vezes rodar a simulação
bs_per_run = 2000       # número de estações por simulação
rng_seed = 42          # semente inicial
cell_radius_m = 10000  # raio da célula em metros

shapefile_path = r"C:\Achiles\SHARC\sharc\topology\map\ne_110m_admin_0_countries.shp"
population_raster_path = r"C:\Achiles\SHARC\sharc\topology\map\SEDAC_map2.tiff"  # set to None for uniform
# Coloque None para usar distribuição uniforme:
# population_raster_path = None

# Países das Américas
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

    # Caribbean (alguns exemplos)
    "Cuba", "Haiti", "Dominican Republic", "Jamaica",
    "Trinidad and Tobago"
]

# Referência de coordenadas (Brasília)
geoconv = GeometryConverter()
geoconv.set_reference(-15.793889, -47.882778, 0.0)

# ----------------- ACUMULAR RESULTADOS -----------------
all_lons, all_lats = [], []

for run in range(num_runs):
    params = ParametersCountries(
        country_names=countries_americas,
        num_bs_total=bs_per_run,
        rng_seed=rng_seed + run,   # muda a semente a cada rodada
        cell_radius=cell_radius_m,
        countries_shapefile=shapefile_path,
        population_raster=population_raster_path
    )
    topo = TopologyCountries(params, geoconv)
    all_lons.extend(topo.lons)
    all_lats.extend(topo.lats)

all_lons = np.array(all_lons)
all_lats = np.array(all_lats)

# ----------------- HEATMAP -----------------
fig, ax = plt.subplots(figsize=(12, 14))

# Plotar fronteiras
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

# Criar histograma 2D (densidade espacial)
bins = 200  # resolução do grid
density, xedges, yedges = np.histogram2d(all_lons, all_lats, bins=bins)

# Plotar heatmap
im = ax.imshow(
    density.T,
    origin="lower",
    extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]],
    cmap="hot",
    alpha=0.6
)

# Colorbar
cbar = plt.colorbar(im, ax=ax)
cbar.set_label("Número de BS (acumulado)")

ax.set_xlabel("Longitude [°]")
ax.set_ylabel("Latitude [°]")
ax.set_title(f"Distribuição simulada de {num_runs * bs_per_run} estações base nas Américas")
plt.tight_layout()
plt.show()
