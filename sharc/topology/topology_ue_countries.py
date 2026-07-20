# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge

from sharc.topology.topology import Topology
# NOTE: we import the BS topology class you already built
from sharc.topology.topology_countries import TopologyCountries
from sharc.support.sharc_geom import CoordinateSystem

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563

@dataclass
class ParametersUECountries:
    """UE placement parameters (per BS)."""
    num_ue_per_bs: int = 3
    sector_half_bw_deg: float = 60.0   # half beamwidth for UE sector (e.g., 30 => 60° total)
    min_dist_from_bs: float = 0.0      # optional guard radius near BS (meters)
    rng_seed: Optional[int] = None
    ue_height_m: float = 1.5


class TopologyUECountries(Topology):
    """
    Generates UE coordinates around each BS from a TopologyCountries instance.
    UEs are sampled inside a sector wedge centered at the BS azimuth, with
    max radius equal to the BS cell_radius (taken from the BS topology).
    """

    def __init__(self,
                 bs_topology: TopologyCountries,
                 params: ParametersUECountries,
                 random_number_gen: Optional[np.random.RandomState] = None):
        # Inherit the cell radius & intersite distance directly from the BS topology
        super().__init__(bs_topology.intersite_distance, bs_topology.cell_radius)
        self.bs_topology = bs_topology
        self.params = params
        self.rng = random_number_gen if random_number_gen is not None \
            else np.random.RandomState()

        # will be filled by calculate_coordinates()
        self.x = None
        self.y = None
        self.z = None
        self.num_base_stations = 0  # here: number of UEs
        self.azimuth = None         # UE azimuths
        self.indoor = None          # flag placeholder
        self.elevation = None          # flag placeholder
        self.latitude = None          # flag placeholder
        self.longitude = None          # flag placeholder

    def calculate_coordinates(self):
        # Ensure BS topology exists
        if getattr(self.bs_topology, "num_base_stations", 0) <= 0 or \
           getattr(self.bs_topology, "x", None) is None:
            self.bs_topology.calculate_coordinates()

        nb = self.bs_topology.num_base_stations
        if nb <= 0:
            raise RuntimeError("TopologyUECountries: BS topology has zero sites.")

        R = float(self.bs_topology.cell_radius)
        R_guard = float(max(0.0, self.params.min_dist_from_bs))
        if R_guard >= R:
            raise ValueError("min_dist_from_bs must be smaller than cell_radius.")

        ue_per_bs = int(self.params.num_ue_per_bs)
        total_ue = nb * ue_per_bs

        xs = np.empty(total_ue, dtype=float)
        ys = np.empty(total_ue, dtype=float)
        zs = np.empty(total_ue, dtype=float)
        az = np.empty(total_ue, dtype=float)
        latitude = np.empty(total_ue, dtype=float)
        longitude = np.empty(total_ue, dtype=float)
        height = np.empty(total_ue, dtype=float)
        elev = np.empty(total_ue, dtype=float)

        half_bw = float(self.params.sector_half_bw_deg)
        h_mu = float(self.params.ue_height_m)
        idx = 0;
        for i in range(nb):
            # Radius ~ uniform in area within [R_guard, R]
            u = self.rng.rand(ue_per_bs)
            r = np.sqrt((R**2 - R_guard**2) * u + R_guard**2)

            # Angle around BS azimuth
            center = float(self.bs_topology.azimuth[i])
            theta = np.deg2rad(center + self.rng.uniform(half_bw, -half_bw, size=ue_per_bs))
            
            cs = CoordinateSystem()
            cs.set_reference(self.bs_topology.lats[i], self.bs_topology.lons[i], 0.0)

            # Local offsets (meters)
            x_local = r * np.cos(theta)
            y_local = r * np.sin(theta)
            
            # Convert BS ECEF to ENU
            v_enu = cs.ecef2enu(self.bs_topology.x[i], self.bs_topology.y[i], self.bs_topology.z[i])

            for k in range(ue_per_bs):
                # UE height is h_mu above Earth surface
                v_ecef = cs.enu2ecef(v_enu[0] + x_local[k], v_enu[1] + y_local[k], h_mu).ravel()
                xs[idx] = v_ecef[0]
                ys[idx] = v_ecef[1]
                zs[idx] = v_ecef[2]
                az[idx] = np.rad2deg(theta[k])
                latitude[idx], longitude[idx], height[idx] = self.ecef_to_lla(
                    np.asarray(xs[idx], float), np.asarray(ys[idx], float), np.asarray(zs[idx], float)
                )
                idx = idx + 1

        self.x, self.y, self.z = xs, ys, zs
        self.azimuth = az
        self.ue_elevation_deg = 0
        self.num_base_stations = total_ue
        self.indoor = np.zeros(total_ue, dtype=bool)
        self.latitude = latitude
        self.longitude = longitude

        return self

    # Optional: quick plot helper (2D)
    def plot(self, ax=None, max_wedges: int = 1200):
        """
        Plot BS (from bs_topology), UEs, and a few sector wedges for context.
        """
        created_ax = False
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 7))
            created_ax = True

        # Plot BS from the countries topology
        ax.scatter(self.bs_topology.x, self.bs_topology.y, s=20, c="tab:red", label="BS", zorder=3)

        # Plot UEs
        ax.scatter(self.x, self.y, s=6, c="tab:blue", alpha=0.35, label="UE", zorder=2)

        # Draw a subset of BS wedges (like the “pizza”)
        step = max(1, self.bs_topology.num_base_stations // max_wedges)
        half_bw = float(self.params.sector_half_bw_deg)
        for i in range(0, self.bs_topology.num_base_stations, step):
            bx, by, baz = self.bs_topology.x[i], self.bs_topology.y[i], self.bs_topology.azimuth[i]
            wedge = Wedge((bx, by), self.bs_topology.cell_radius, baz - half_bw, baz + half_bw,
                          facecolor="tab:orange", alpha=0.10, edgecolor="tab:orange", linewidth=0.6, zorder=1)
            ax.add_patch(wedge)

        ax.set_aspect("equal")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title(f"UEs per BS: {self.params.num_ue_per_bs}  |  total UEs: {self.num_base_stations}")
        ax.legend(loc="upper right", frameon=True)
        if created_ax:
            plt.tight_layout()
            plt.show()

    @staticmethod
    def ecef_to_lla(X, Y, Z, a=WGS84_A, f=WGS84_F):
        import numpy as _np
        e2  = f * (2.0 - f)
        b   = a * (1.0 - f)
        ep2 = (a*a - b*b) / (b*b)

        X = _np.asarray(X, dtype=float)
        Y = _np.asarray(Y, dtype=float)
        Z = _np.asarray(Z, dtype=float)

        lon = _np.arctan2(Y, X)
        p   = _np.hypot(X, Y)
        lat = _np.zeros_like(Z)
        h   = _np.zeros_like(Z)

        mask = (p > 0)
        if _np.any(mask):
            Xg, Yg, Zg = X[mask], Y[mask], Z[mask]
            pg = p[mask]
            theta = _np.arctan2(a * Zg, b * pg)
            st, ct = _np.sin(theta), _np.cos(theta)
            lat_g = _np.arctan2(Zg + ep2 * b * st**3, pg - e2 * a * ct**3)
            sl = _np.sin(lat_g)
            N  = a / _np.sqrt(1.0 - e2 * sl * sl)
            h_g = pg / _np.cos(lat_g) - N
            lat[mask] = lat_g
            h[mask]   = h_g

        pole = ~mask
        if _np.any(pole):
            Zp = Z[pole]
            lat[pole] = _np.sign(Zp) * (_np.pi / 2.0)
            h[pole]   = _np.abs(Zp) - b

        lat_deg = _np.degrees(lat)
        lon_deg = _np.degrees(lon)
        lon_deg = (lon_deg + 180.0) % 360.0 - 180.0
        return lat_deg, lon_deg, h

# ----------------------- Example usage -----------------------
# ----------------------- MAIN -----------------------
if __name__ == "__main__":
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import Wedge
    from collections import Counter
    import geopandas as gpd
    from pathlib import Path
    import os
    from sharc.topology.topology_countries import TopologyCountries
    from sharc.parameters.imt.parameters_countries_imt import ParametersCountries
    from sharc.support.sharc_geom import CoordinateSystem

    # --------- User inputs ----------
      # ============ User-defined inputs ============
    num_bs = 10000
    rng_seed = 42
    cell_radius_m = 400.0  # 10 km
    dist_type = "Urban"
    # Shapefile (or set to None to auto-download Natural Earth via cartopy/geodatasets)
    shapefile_path = Path.cwd() / "sharc" / "topology" / "map" / "ne_110m_admin_0_countries.shp"

    # Population raster (set to None to sample uniformly by area)
    population_raster_path = Path.cwd() / "sharc" / "topology" / "map" / "SEDAC_map2.tiff"

    # Raster type:
    #   "density" = people per km² (e.g., GPWv4 density GeoTIFF)
    #   "count"   = people per pixel
    #   "indexed" = 0..255 palette indices (NEO-like) -> mapped via log/linear bins
    raster_encoding = "indexed"  # change to "density" if your GeoTIFF is ppl/km²

    # For "indexed" rasters only
    sedac_palette_mode = "log"   # "log" or "linear"
    sedac_min = 1.0
    sedac_max = 1e4
    index_nodata = (0, 255)

    # Optional ACT to auto-extend whites as NoData (leave None if you don't want to)
    act_palette_path = Path.cwd() / "sharc" / "topology" / "map" / "sedac_pop.act"

    # Sampling-only knobs (do not affect totals per country)
    min_density_threshold = 0.0  # ppl/km² cutoff in sampling
    density_exponent = 1.0       # >1 bias toward dense areas

    # Countries (Americas example)
    countries = [
        # South America
        "Brazil", "Argentina", "Uruguay", "Paraguay", "Chile",
        "Bolivia", "Peru", "Ecuador", "Colombia", "Venezuela",
        "Guyana", "Suriname",
        # Central America
        "Belize", "Guatemala", "El Salvador", "Honduras",
        "Nicaragua", "Costa Rica", "Panama",
        # North America
        "Mexico", "United States of America", "Canada",
        # Caribbean (sample)
        "Cuba", "Haiti", "Dominican Republic", "Jamaica",
        "Trinidad and Tobago"
    ]

    # ============ Build topology ============
    coord_sys = CoordinateSystem()
    coord_sys.set_reference(-15.793889, -47.882778, 0.0)  # Brasilia

    params = ParametersCountries(
        country_names=countries,
        num_bs_total=num_bs,
        cell_radius=cell_radius_m,
        countries_shapefile=shapefile_path,
        population_raster=population_raster_path,

        raster_encoding=raster_encoding,
        sedac_palette_mode=sedac_palette_mode,
        sedac_min=sedac_min,
        sedac_max=sedac_max,
        index_nodata=index_nodata,
        act_colormap_path=act_palette_path,

        pixel_area_method="spherical",
        min_density_threshold=min_density_threshold,
        density_exponent=density_exponent,

        mask_inland_water=True,
        dist_type=dist_type
    )

    rng_bs = np.random.RandomState(rng_seed)
    bs_topo = TopologyCountries(params, coord_sys, random_number_gen=rng_bs).calculate_coordinates(random_number_gen=rng_bs)

    # --------- Build UE topology (Cartesian) ----------
    # UE params
    num_ue_per_bs = 3
    sector_half_bw_deg = 60.0
    min_dist_from_bs_m = 0.0
    ue_rng_seed = 999
    ue_params = ParametersUECountries(
        num_ue_per_bs=num_ue_per_bs,
        sector_half_bw_deg=sector_half_bw_deg,
        min_dist_from_bs=min_dist_from_bs_m,
        rng_seed=ue_rng_seed,
    )
    ue_rng = np.random.RandomState(ue_params.rng_seed)
    ue_topo = TopologyUECountries(bs_topo, ue_params, random_number_gen=ue_rng)
    ue_topo.calculate_coordinates()

    # --------- Map plot (lon/lat): boundaries + BS + wedges + UEs ----------
    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(1, 2, width_ratios=[2.2, 1.0], wspace=0.22)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_bar = fig.add_subplot(gs[0, 1])

    # Country boundaries
    try:
        world = gpd.read_file(shapefile_path)
    except Exception:
        world = None

    subset = None
    if world is not None:
        has_name, has_admin = ("name" in world.columns), ("ADMIN" in world.columns)
        if has_name and has_admin:
            subset = world[(world["name"].isin(countries)) | (world["ADMIN"].isin(countries))]
        elif has_name:
            subset = world[world["name"].isin(countries)]
        elif has_admin:
            subset = world[world["ADMIN"].isin(countries)]

    if subset is not None and not subset.empty:
        subset.boundary.plot(ax=ax_map, linewidth=0.8, color="black", zorder=0)

    # Scatter BS
    ax_map.scatter(bs_topo.lons, bs_topo.lats, s=10, c="red", alpha=0.7, label="BS", zorder=2)

    # Draw wedges and sample UEs in lon/lat for visualization
    rng_vis = np.random.RandomState(ue_rng_seed)
    max_wedges = 1500
    step = max(1, bs_topo.num_base_stations // max_wedges)  # draw 1 every 'step'
    half_bw = float(sector_half_bw_deg)

    ue_lons_all = []
    ue_lats_all = []

    for i in range(bs_topo.num_base_stations):
        lon0 = float(bs_topo.lons[i])
        lat0 = float(bs_topo.lats[i])
        az = float(bs_topo.azimuth[i])

        # Convert cell radius to degrees at this latitude (approx)
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * np.cos(np.radians(lat0))
        avg_km_per_deg = (km_per_deg_lat + km_per_deg_lon) / 2.0
        radius_deg = (bs_topo.cell_radius / 1000.0) / max(avg_km_per_deg, 1e-6)

        # Draw wedge for a subset (to avoid clutter)
        if i % step == 0:
            ax_map.add_patch(Wedge((lon0, lat0), radius_deg, az - half_bw, az + half_bw,
                                   facecolor="blue", alpha=0.15, edgecolor="blue",
                                   linewidth=0.5, zorder=1))

        # Sample UEs (visual positions) inside the wedge
        # Uniform-in-area radius in meters -> convert to degrees
        u = rng_vis.rand(num_ue_per_bs)
        R = float(bs_topo.cell_radius)
        Rg = float(max(0.0, min_dist_from_bs_m))
        r_m = np.sqrt((R**2 - Rg**2) * u + Rg**2)
        r_deg = (r_m / 1000.0) / max(avg_km_per_deg, 1e-6)

        theta = np.deg2rad(az + rng_vis.uniform(-half_bw, +half_bw, size=num_ue_per_bs))
        dlon = r_deg * np.cos(theta)
        dlat = r_deg * np.sin(theta)

        ue_lons_all.append(lon0 + dlon)
        ue_lats_all.append(lat0 + dlat)

    if ue_lons_all:
        ue_lons_all = np.concatenate(ue_lons_all)
        ue_lats_all = np.concatenate(ue_lats_all)
        ax_map.scatter(ue_lons_all, ue_lats_all, s=5, c="tab:blue", alpha=0.5, label="UE", zorder=3)

    ax_map.set_xlabel("Longitude [°]")
    ax_map.set_ylabel("Latitude [°]")
    ax_map.set_title(f"BS + UEs inside sector wedges  |  BS={bs_topo.num_base_stations}, "
                     f"UE/BS={num_ue_per_bs}")
    ax_map.legend(loc="upper right", frameon=True)

    # --------- Bar chart: BS per country ----------
    counts = Counter(bs_topo.country_index.tolist())
    countries_sorted = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
    values_sorted = [counts[c] for c in countries_sorted]
    total_bs = sum(values_sorted) if values_sorted else 0

    ax_bar.barh(countries_sorted, values_sorted)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Number of base stations")
    ax_bar.set_title("BS per country")
    if total_bs > 0:
        for y, (name, v) in enumerate(zip(countries_sorted, values_sorted)):
            ax_bar.text(v, y, f" {v:,}  ({v/total_bs:.1%})", va="center", ha="left", fontsize=9)
    ax_bar.margins(x=0.10)
    for label in ax_bar.get_yticklabels():
        label.set_fontsize(9)

    fig.tight_layout()
    plt.show()