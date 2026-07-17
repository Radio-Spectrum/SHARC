"""Generate the offline world basemap texture for the CesiumJS Preview spike.

Rasterizes the Natural Earth 110m countries shapefile already bundled with
SHARC (``sharc/topology/map/ne_110m_admin_0_countries.shp`` — Natural Earth
data is public domain, no attribution required) into a plain equirectangular
JPEG, which ``sharc/gui/web/cesium_preview/app.js`` loads as a
``Cesium.SingleTileImageryProvider``. This is what makes the globe show land
and ocean instead of a flat solid color, with zero network access and zero
new external assets.

Output is small (~80KB) and checked into
``sharc/gui/web/cesium_preview/assets/world_basemap.jpg`` — re-run this only
if you want to regenerate/restyle it:

    python sharc/gui/tools/generate_world_basemap.py
"""

from __future__ import annotations

import os

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.dirname(_TOOLS_DIR)
_SHARC_DIR = os.path.dirname(_GUI_DIR)

SHAPEFILE = os.path.join(_SHARC_DIR, "topology", "map", "ne_110m_admin_0_countries.shp")
OUTPUT = os.path.join(_GUI_DIR, "web", "cesium_preview", "assets", "world_basemap.jpg")

WIDTH, HEIGHT = 2048, 1024
DPI = 100
OCEAN_COLOR = "#0d3b66"
LAND_COLOR = "#3a6b35"
EDGE_COLOR = "#274d24"


def main() -> None:
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

    gdf = gpd.read_file(SHAPEFILE)

    fig = plt.figure(figsize=(WIDTH / DPI, HEIGHT / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_axis_off()
    fig.patch.set_facecolor(OCEAN_COLOR)
    ax.set_facecolor(OCEAN_COLOR)

    gdf.plot(ax=ax, facecolor=LAND_COLOR, edgecolor=EDGE_COLOR, linewidth=0.3)

    fig.savefig(OUTPUT, dpi=DPI, facecolor=OCEAN_COLOR)
    plt.close(fig)
    print(f"Wrote {OUTPUT} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
