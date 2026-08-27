"""Generate the offline world basemap texture for the CesiumJS Preview spike.

Rasterizes the Natural Earth 110m countries shapefile already bundled with
SHARC (``sharc/topology/map/ne_110m_admin_0_countries.shp``) into an
equirectangular JPEG with country borders, terrain-like coloring, and major
city markers.

Output goes to ``sharc/gui/web/cesium_preview/assets/world_basemap.jpg``.

    python sharc/gui/tools/generate_world_basemap.py
"""

from __future__ import annotations

import os

import numpy as np
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patheffects as patheffects  # noqa: E402

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.dirname(_TOOLS_DIR)
_SHARC_DIR = os.path.dirname(_GUI_DIR)

SHAPEFILE = os.path.join(
    _SHARC_DIR, "topology", "map", "ne_110m_admin_0_countries.shp")
OUTPUT = os.path.join(
    _GUI_DIR, "web", "cesium_preview", "assets", "world_basemap.jpg")

WIDTH, HEIGHT = 4096, 2048
DPI = 150

OCEAN_COLOR = "#0a2744"
LAND_COLORS = ["#2d5a27", "#3a6b35", "#4a7c3f", "#5a8d4a"]
EDGE_COLOR = "#1a3d18"
BORDER_WIDTH = 0.4
COASTLINE_COLOR = "#1a4a1a"
COASTLINE_WIDTH = 0.6

MAJOR_CITIES = [
    ("New York", 40.71, -74.01),
    ("Los Angeles", 34.05, -118.24),
    ("Mexico City", 19.43, -99.13),
    ("São Paulo", -23.55, -46.63),
    ("Buenos Aires", -34.60, -58.38),
    ("Brasília", -15.79, -47.88),
    ("Lima", -12.05, -77.04),
    ("Bogotá", 4.71, -74.07),
    ("London", 51.51, -0.13),
    ("Paris", 48.86, 2.35),
    ("Berlin", 52.52, 13.41),
    ("Moscow", 55.76, 37.62),
    ("Madrid", 40.42, -3.70),
    ("Rome", 41.90, 12.50),
    ("Istanbul", 41.01, 28.98),
    ("Cairo", 30.04, 31.24),
    ("Lagos", 6.52, 3.38),
    ("Johannesburg", -26.20, 28.05),
    ("Nairobi", -1.29, 36.82),
    ("Cape Town", -33.93, 18.42),
    ("Tokyo", 35.68, 139.69),
    ("Beijing", 39.90, 116.40),
    ("Shanghai", 31.23, 121.47),
    ("Mumbai", 19.08, 72.88),
    ("Delhi", 28.61, 77.21),
    ("Seoul", 37.57, 126.98),
    ("Singapore", 1.35, 103.82),
    ("Dubai", 25.20, 55.27),
    ("Bangkok", 13.76, 100.50),
    ("Jakarta", -6.21, 106.85),
    ("Sydney", -33.87, 151.21),
    ("Toronto", 43.65, -79.38),
    ("Santiago", -33.45, -70.67),
    ("Lisbon", 38.72, -9.14),
    ("Tehran", 35.69, 51.39),
    ("Auckland", -36.85, 174.76),
]


def _latitude_color(lat: float) -> str:
    abs_lat = abs(lat)
    if abs_lat > 60:
        return "#506850"
    elif abs_lat > 40:
        return "#4a7c3f"
    elif abs_lat > 20:
        return "#3a6b35"
    else:
        return "#2d6830"


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

    # Ocean gradient (darker at poles, slightly lighter at equator)
    ocean_gradient = np.zeros((200, 1, 4))
    for i in range(200):
        lat_frac = abs(i - 100) / 100.0
        r, g, b = 0.04, 0.15 + 0.06 * (1 - lat_frac), 0.27 + 0.08 * (1 - lat_frac)
        ocean_gradient[i, 0] = [r, g, b, 1.0]
    ax.imshow(ocean_gradient, extent=[-180, 180, -90, 90],
              aspect='auto', zorder=0, interpolation='bilinear')

    # Country polygons with latitude-based coloring
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        centroid = geom.centroid
        color = _latitude_color(centroid.y)

        if geom.geom_type == 'Polygon':
            xs, ys = geom.exterior.coords.xy
            ax.fill(xs, ys, facecolor=color, edgecolor=EDGE_COLOR,
                    linewidth=BORDER_WIDTH, zorder=2)
        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                xs, ys = poly.exterior.coords.xy
                ax.fill(xs, ys, facecolor=color, edgecolor=EDGE_COLOR,
                        linewidth=BORDER_WIDTH, zorder=2)

    # Coastlines (slightly stronger than internal borders)
    gdf.boundary.plot(ax=ax, color=COASTLINE_COLOR,
                      linewidth=COASTLINE_WIDTH, zorder=3)

    # Graticule (subtle grid lines)
    for lat in range(-60, 61, 30):
        ax.axhline(lat, color='white', alpha=0.06, linewidth=0.3, zorder=4)
    for lon in range(-150, 151, 30):
        ax.axvline(lon, color='white', alpha=0.06, linewidth=0.3, zorder=4)

    # Major cities
    for name, lat, lon in MAJOR_CITIES:
        ax.plot(lon, lat, 'o', color='#ffd54f', markersize=1.8,
                markeredgecolor='#c68400', markeredgewidth=0.3, zorder=6)
        ax.annotate(name, (lon, lat), fontsize=2.8,
                    color='white', alpha=0.85,
                    fontweight='bold',
                    xytext=(2.5, 2.5), textcoords='offset points',
                    zorder=7,
                    path_effects=[
                        patheffects.withStroke(
                            linewidth=1.2, foreground='black')
                    ])

    fig.savefig(OUTPUT, dpi=DPI, facecolor=OCEAN_COLOR)
    plt.close(fig)
    sz = os.path.getsize(OUTPUT) / 1024
    print(f"Wrote {OUTPUT} ({WIDTH}x{HEIGHT}, {sz:.0f} KB)")


if __name__ == "__main__":
    main()
