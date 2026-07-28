import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
from pathlib import Path
from sharc.topology.topology_countries import ParametersCountries, TopologyCountries
from sharc.support.sharc_geom import GeometryConverter

# ----------------- CONFIGURAÇÕES -----------------
num_runs = 30          # quantas vezes rodar a simulação
bs_per_run = 2000      # número de estações por simulação
rng_seed = 42          # semente inicial
cell_radius_m = 10000  # raio da célula em metros

# Filtro por faixa de densidade (conforme implementação em topology_countries.py)
# Use UMA das opções a seguir:
dist_type = "Suburban"      # "Urban" | "Suburban" | "Rural" | None
# dist_density_min = 800.0   # se quiser faixa explícita, defina estes e comente o dist_type
# dist_density_max = 6000.0  # (faixa explícita tem precedência sobre dist_type)

# Dados geográficos
shapefile_path = Path.cwd() / "sharc" / "topology" / "map" / "ne_110m_admin_0_countries.shp"
population_raster_path = Path.cwd() / "sharc" / "topology" / "map" / "SEDAC_map2.tiff"

# RASTER: escolha o tipo que condiz com seu GeoTIFF
#   "density" = ppl/km² (ex.: GPWv4 density)
#   "count"   = pessoas por pixel
#   "indexed" = índices 0..255 (ex.: SEDAC/NEO) que serão mapeados p/ densidade
raster_encoding = "indexed"        # mude para "indexed" se seu TIFF for paletizado 0..255
sedac_palette_mode = "log"         # "log" ou "linear" (apenas p/ indexed)
sedac_min = 1.0                    # ppl/km² (apenas p/ indexed)
sedac_max = 1e4                    # ppl/km² (apenas p/ indexed)
index_nodata = (0, 255)            # índices ignorados (água/NoData) em indexed
act_palette_path = None            # caminho do .act (opcional) para auto-detectar "brancos"

# Amostragem (apenas para sampling; não altera totais)
min_density_threshold = 0.0        # ppl/km² mínimo p/ sampling
density_exponent = 1.0             # >1 puxa mais para áreas densas

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
        population_raster=population_raster_path,

        # --- NOVO: filtros de densidade por tipo/faixa ---
        dist_type=dist_type,
        # dist_density_min=dist_density_min,
        # dist_density_max=dist_density_max,

        # --- Raster/legend (caso use "indexed") ---
        raster_encoding=raster_encoding,
        sedac_palette_mode=sedac_palette_mode,
        sedac_min=sedac_min,
        sedac_max=sedac_max,
        index_nodata=index_nodata,
        act_colormap_path=act_palette_path,

        # --- área de pixel e sampling ---
        pixel_area_method="spherical",
        min_density_threshold=min_density_threshold,
        density_exponent=density_exponent,

        # --- geometria: remove lagos do polígono ---
        mask_inland_water=True,
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

band_txt = ""
if dist_type:
    band_txt = f" | banda: {dist_type}"
# if you used explicit range:
# band_txt = f" | banda explícita: [{dist_density_min}, {dist_density_max}) ppl/km²"

ax.set_xlabel("Longitude [°]")
ax.set_ylabel("Latitude [°]")
ax.set_title(
    f"Distribuição simulada de {num_runs * bs_per_run} estações base nas Américas"
    f"{band_txt} | encoding={raster_encoding}"
)
plt.tight_layout()
plt.show()
