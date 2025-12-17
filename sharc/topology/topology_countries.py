# -*- coding: utf-8 -*-
"""
Distribute base stations across countries using uniform or population-weighted placement,
with optional filtering by population-density bands (Urban/Suburban/Rural or explicit).

Population-weighted mode:
  - Supports three raster encodings:
      * "density" : values are people/km²
      * "count"   : values are people per pixel
      * "indexed" : 0..255 palette indices (e.g., SEDAC/NEO browse layers)
  - For "indexed", converts index->density using SEDAC-style legend mapping
    (log or linear) via 256 bin midpoints; keeps specific palette indices
    (e.g., 0, 255) as exact zeros (water/NoData).
  - Country totals use density*pixel_area (or count), with pixel-area correction.
  - Within-country sampling uses the same weights so distribution matches totals.
  - Optional density-band filtering: only pixels with densities in a requested band
    (Urban/Suburban/Rural or explicit [min,max]) count for totals and sampling.

Requires: numpy, geopandas, shapely, rasterio (only if using population_raster).
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union

from sharc.topology.topology import Topology
from sharc.satellite.ngso.constants import EARTH_DEFAULT_CRS
from sharc.parameters.imt.parameters_Countries_imt import ParametersCountries
from sharc.support.sharc_geom_countries import GeometryConverter

_WGS84_A  = 6378137.0                 # semi-major axis [m]
_WGS84_F  = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_F * (2.0 - _WGS84_F)

# ----------------------- Topology -----------------------


class TopologyCountries(Topology):

    """
    Distributes BS positions across selected countries in WGS84 and converts to
    .
    """

    def __init__(self,
                 params: ParametersCountries,
                 geometry_converter,
                 random_number_gen: np.random.RandomState | None = None):
        self.params = params
        self.geometry_converter = geometry_converter
        self.rng = random_number_gen if random_number_gen is not None \
                   else np.random.RandomState(params.rng_seed)

        # Buffers (serão preenchidos em calculate_coordinates)
        self.countries: List[str] = list(params.country_names)
        self.country_polys: Dict[str, Polygon | MultiPolygon] = {}
        self.country_index = np.empty(0, dtype=object)

        self.lats = np.empty(0, dtype=float)
        self.lons = np.empty(0, dtype=float)

        self.x = np.empty(0, dtype=float)
        self.y = np.empty(0, dtype=float)
        self.z = np.empty(0, dtype=float)
        self.height = np.empty(0, dtype=float)
        self.azimuth = np.empty(0, dtype=float)
        self.num_base_stations: int = 0

        self.rng = random_number_gen if random_number_gen is not None \
            else np.random.RandomState(params.rng_seed)

    def calculate_coordinates(self,
                            random_number_gen: np.random.RandomState | None = None) -> "TopologyCountries":
        # Load country polygons (WGS84)
        params = self.params
        self.cell_radius = params.cell_radius
        self.height = params.height
        # Resolve shapefile path (absolute or relative to SHARC root)
        shp = params.countries_shapefile
        # 1) Se veio com caminho Windows, pega só o sufixo a partir de "\sharc\"
        if isinstance(shp, str) and ("\\sharc\\" in shp.lower() or "/sharc/" in shp.lower()):
            low = shp.lower().replace("\\", "/")
            i = low.find("/sharc/")
            shp = shp[i+1:]  # vira "sharc/topology/map/....shp"

        # 2) Se não é absoluto, resolve relativo ao root do pacote SHARC
        shp_path = Path(shp)
        if not shp_path.is_absolute():
            sharc_root = Path(sharc.__file__).resolve().parent.parent
            shp_path = sharc_root / shp_path

        ne = self._load_countries_gdf(str(shp_path))

        if not params.country_names:
            raise ValueError("TopologyCountries: 'country_names' cannot be empty.")

        has_name = "name" in ne.columns
        has_admin = "ADMIN" in ne.columns

        polys_by_country: Dict[str, MultiPolygon | Polygon] = {}
        areas: Dict[str, float] = {}

        for name in params.country_names:
            if has_name and has_admin:
                row = ne[(ne["name"] == name) | (ne["ADMIN"] == name)]
            elif has_name:
                row = ne[ne["name"] == name]
            elif has_admin:
                row = ne[ne["ADMIN"] == name]
            else:
                raise RuntimeError("Countries GeoDataFrame missing 'name'/'ADMIN' columns.")

            if row.empty:
                raise ValueError(f"Country '{name}' not found in dataset.")

            geom = unary_union(row.geometry.values)

            # Subtract lakes (geometry-level mask) to avoid inland water
            if self.params.mask_inland_water:
                geom = self._subtract_lakes(geom)

            polys_by_country[name] = geom
            areas[name] = float(geom.area)

        # Optional: extend index_nodata with "white-ish" bins from ACT
        effective_index_nodata = self._extend_index_nodata_with_white(
            self.params.index_nodata, self.params.act_colormap_path, tol=3
        )

        # NEW: resolve density band once
        density_range = self._get_density_range()

        # -------- Decide how many BS per country --------
        if params.bs_per_country:
            counts = dict(params.bs_per_country)

        else:
            if params.num_bs_total is None:
                raise ValueError("Provide either 'bs_per_country' or 'num_bs_total'.")

            # Resolve raster path (absolute, Windows-style, or relative to SHARC root)
            r = params.population_raster

            if isinstance(r, str):
                r_low = r.lower().replace("\\", "/")

                # Caso 1: veio como C:\...\sharc\...
                if "/sharc/" in r_low:
                    idx = r_low.find("/sharc/")
                    r = r[idx + 1:]  # vira "sharc/..."

            raster_path = Path(r)

            # Caso 2: relativo ao root do SHARC
            if not raster_path.is_absolute():
                SHARC_ROOT = Path(sharc.__file__).resolve().parent.parent
                raster_path = SHARC_ROOT / raster_path

            # Falha explícita se não existir
            if not raster_path.exists():
                raise FileNotFoundError(f"Population raster não encontrado: {raster_path}")

            params.population_raster = raster_path

            if params.population_raster:
                # Population-based allocation (physical totals; no gamma here)
                pop_sums = self._country_population_sums(
                    {n: polys_by_country[n] for n in params.country_names},
                    params.population_raster,
                    params.raster_encoding,
                    params.pixel_area_method,
                    thr=0.0,                 # keep totals physical
                    gamma=1.0,
                    sedac_mode=params.sedac_palette_mode,
                    sedac_min=params.sedac_min,
                    sedac_max=params.sedac_max,
                    index_nodata=effective_index_nodata,
                    density_range=density_range,  # NEW
                )
                total_pop = sum(pop_sums.values())
                if total_pop > 0:
                    shares = {n: pop_sums[n] / total_pop for n in params.country_names}
                    counts = {n: int(np.floor(shares[n] * params.num_bs_total))
                              for n in params.country_names}
                    # fix rounding to hit total exactly
                    deficit = params.num_bs_total - sum(counts.values())
                    if deficit > 0:
                        frac_list = sorted(shares.items(), key=lambda x: x[1], reverse=True)
                        for i in range(deficit):
                            counts[frac_list[i % len(frac_list)][0]] += 1
                else:
                    # fallback to area-based if population sums are zero
                    total_area = sum(areas.values())
                    counts = {n: int(np.floor((areas[n] / total_area) * params.num_bs_total))
                              for n in params.country_names}
                    deficit = params.num_bs_total - sum(counts.values())
                    if deficit > 0:
                        fracs = sorted(areas.items(), key=lambda x: x[1], reverse=True)
                        for i in range(deficit):
                            counts[fracs[i % len(fracs)][0]] += 1
            else:
                # No raster provided: area-based
                total_area = sum(areas.values())
                counts = {n: int(np.floor((areas[n] / total_area) * params.num_bs_total))
                          for n in params.country_names}
                deficit = params.num_bs_total - sum(counts.values())
                if deficit > 0:
                    fracs = sorted(areas.items(), key=lambda x: x[1], reverse=True)
                    for i in range(deficit):
                        counts[fracs[i % len(fracs)][0]] += 1

        # -------- Generate BS positions --------
        lons, lats, country_ix = [], [], []
        for name in params.country_names:
            n = int(counts.get(name, 0))
            if n <= 0:
                continue

            if params.population_raster:
                pts_lon, pts_lat = self._sample_points_from_population(
                    polys_by_country[name],
                    n,
                    params.population_raster,
                    params.raster_encoding,
                    params.pixel_area_method,
                    params.min_density_threshold,
                    params.density_exponent,
                    params.sedac_palette_mode,
                    params.sedac_min,
                    params.sedac_max,
                    effective_index_nodata,
                    density_range=density_range,  # NEW
                )
            else:
                pts_lon, pts_lat = self._random_points_in_polygon(polys_by_country[name], n)

            lons.extend(pts_lon)
            lats.extend(pts_lat)
            country_ix.extend([name] * n)

        self.num_base_stations = len(lons)
        if self.num_base_stations == 0:
            raise RuntimeError("TopologyCountries created zero base stations. Check inputs.")

        # Save geodetic positions (for plotting)
        self.lons = np.array(lons)
        self.lats = np.array(lats)
        self.country_index = np.array(country_ix)
        self.height = np.ones(self.num_base_stations) * self.height
        # Convert to transformed Cartesian (simulation coordinates)
        x, y, z = self._lla_to_ecef(self.lats, self.lons, self.height)
        self.x = np.array(x)
        self.y = np.array(y)
        self.z = np.array(z)

        # Azimuth assignment
        if params.fixed_azimuth is not None:
            self.azimuth = np.full(self.num_base_stations, float(params.fixed_azimuth))
        else:
            self.azimuth = self.rng.uniform(-180.0, 180.0, size=self.num_base_stations)

        # Placeholders for StationFactory expectations
        self.elevation = np.zeros(self.num_base_stations)

        return self
    # ---------- helpers ----------
    @staticmethod
    def _lla_to_ecef(lat_deg, lon_deg, height):
        """Vectorized geodetic (deg,deg,m) -> ECEF XYZ (m) on WGS-84."""
        lat = np.radians(np.asarray(lat_deg, dtype=float))
        lon = np.radians(np.asarray(lon_deg, dtype=float))
        h   = np.asarray(height, dtype=float)

        sl, cl = np.sin(lat), np.cos(lat)
        sb, cb = np.sin(lon), np.cos(lon)

        N = _WGS84_A / np.sqrt(1.0 - _WGS84_E2 * sl * sl)
        X = (N + h) * cl * cb
        Y = (N + h) * cl * sb
        Z = (N * (1.0 - _WGS84_E2) + h) * sl
        return X, Y, Z

    def _load_countries_gdf(self, shapefile_path: Optional[str]) -> gpd.GeoDataFrame:
        if shapefile_path:
            gdf = gpd.read_file(shapefile_path)
            return gdf.to_crs(EARTH_DEFAULT_CRS)

        # Try cartopy (auto-download Natural Earth)
        try:
            from cartopy.io import shapereader as shpreader
            shp = shpreader.natural_earth("110m", "cultural", "admin_0_countries")
            gdf = gpd.read_file(shp)
            return gdf.to_crs(EARTH_DEFAULT_CRS)
        except Exception:
            pass

        # Try geodatasets
        try:
            from geodatasets import get_path
            path = get_path("naturalearth.cultural.admin_0_countries")
            gdf = gpd.read_file(path)
            return gdf.to_crs(EARTH_DEFAULT_CRS)
        except Exception:
            pass

        raise RuntimeError(
            "Could not load country polygons. Provide 'countries_shapefile', or install cartopy/geodatasets."
        )

    def _subtract_lakes(self, poly: Polygon | MultiPolygon) -> Polygon | MultiPolygon:
        """
        Subtract Natural Earth 'lakes' (110m physical) from the given polygon.
        """
        try:
            from cartopy.io import shapereader as shpreader
            lakes_path = shpreader.natural_earth("110m", "physical", "lakes")
            lakes = gpd.read_file(lakes_path).to_crs(EARTH_DEFAULT_CRS)
        except Exception:
            # If lakes layer can't be loaded, just return the original polygon
            return poly

        # bbox filter (speed)
        minx, miny, maxx, maxy = poly.bounds
        lakes_sub = lakes.cx[minx:maxx, miny:maxy]
        if lakes_sub.empty:
            return poly

        lakes_union = unary_union(lakes_sub.geometry)
        try:
            diff = poly.difference(lakes_union)
            return diff if not diff.is_empty else poly
        except Exception:
            return poly

    def _extend_index_nodata_with_white(self,
                                        index_nodata: Tuple[int, ...],
                                        act_path: Optional[str],
                                        tol: int = 3) -> Tuple[int, ...]:
        """
        If an ACT palette is provided, add all nearly-white bins (>=255-tol) to index_nodata.
        'tol=3' means [252..255] in each channel are considered white.
        """
        if not act_path:
            return index_nodata
        try:
            with open(act_path, "rb") as f:
                buf = f.read()
            pal = np.frombuffer(buf[:256*3], dtype=np.uint8).reshape(256, 3)
            whiteish = np.where((pal >= (255 - tol)).all(axis=1))[0]
            nd = set(index_nodata)
            nd.update(int(i) for i in whiteish.tolist())
            return tuple(sorted(nd))
        except Exception:
            return index_nodata

    def _get_density_range(self) -> Optional[Tuple[float, float]]:
        """
        Return (dmin, dmax) in ppl/km² to keep during allocation & sampling,
        based on params.dist_type or explicit dist_density_min/max.
        Returns None if no filtering is requested.
        """
        p = self.params
        # explicit beats dist_type
        if (p.dist_density_min is not None) or (p.dist_density_max is not None):
            dmin = float(p.dist_density_min) if p.dist_density_min is not None else 0.0
            dmax = float(p.dist_density_max) if p.dist_density_max is not None else float("inf")
            if dmax <= dmin:
                raise ValueError("dist_density_max must be > dist_density_min")
            return (dmin, dmax)

        if not p.dist_type:
            return None

        key = str(p.dist_type).strip().lower()
        if key == "urban":
            return (1500.0, 10000.0)
        elif key == "suburban":
            return (300.0, 1500.0)
        elif key == "rural":
            return (0.0, 300.0)
        else:
            raise ValueError(f"Unknown dist_type '{p.dist_type}'. Use 'Urban', 'Suburban', or 'Rural'.")

    def _random_points_in_polygon(self, poly: Polygon | MultiPolygon, n: int) -> Tuple[np.ndarray, np.ndarray]:
        """Uniform rejection sampling inside (multi)polygon (lon/lat degrees)."""
        if isinstance(poly, MultiPolygon):
            parts = list(poly.geoms)
            areas = np.array([float(p.area) for p in parts], dtype=float)
            probs = areas / areas.sum()
            pts_lon, pts_lat = [], []
            for _ in range(n):
                pidx = self.rng.choice(len(parts), p=probs)
                lon, lat = self._random_point_in_single_polygon(parts[pidx])
                pts_lon.append(lon)
                pts_lat.append(lat)
            return np.array(pts_lon), np.array(pts_lat)
        else:
            lon, lat = zip(*[self._random_point_in_single_polygon(poly) for _ in range(n)])
            return np.array(lon), np.array(lat)

    def _random_point_in_single_polygon(self, poly: Polygon) -> Tuple[float, float]:
        minx, miny, maxx, maxy = poly.bounds
        for _ in range(20000):
            q = Point(self.rng.uniform(minx, maxx), self.rng.uniform(miny, maxy))
            if poly.contains(q):
                return (q.x, q.y)
        # Fallback for sliver polygons
        rp = poly.representative_point()
        return (rp.x, rp.y)

    # ---- Pixel-area helpers ----

    @staticmethod
    def _row_areas_km2(lat_centers_deg: np.ndarray, pixel_w_deg: float, pixel_h_deg: float,
                       method: str = "spherical") -> np.ndarray:
        """
        Pixel area per ROW (km²) for a geographic grid.
        - spherical: A = R^2 * dλ * (sin φN - sin φS), using row edges
        - coslat:   A ≈ (111.32*dlat)*(111.32*dlon*cos φcenter)
        - none:     A = 1 (no scaling)
        """
        if method == "none":
            return np.ones_like(lat_centers_deg, dtype=float)

        KM_PER_DEG = 111.32
        if method == "coslat":
            lat_rad = np.radians(lat_centers_deg)
            return (KM_PER_DEG * pixel_h_deg) * (KM_PER_DEG * pixel_w_deg * np.cos(lat_rad))

        # spherical (default)
        R = 6371.0088  # km
        dlon = np.deg2rad(pixel_w_deg)
        half_dlat = 0.5 * pixel_h_deg
        latN = np.deg2rad(lat_centers_deg + half_dlat)
        latS = np.deg2rad(lat_centers_deg - half_dlat)
        band = np.abs(np.sin(latN) - np.sin(latS))    # dimensionless
        return (R**2) * dlon * band                   # km² per pixel (per row)

    # ---- Raster reading & mapping helpers ----

    @staticmethod
    def _index_to_density(idx_arr: np.ndarray, mode: str, vmin: float, vmax: float) -> np.ndarray:
        """
        Map 0..255 palette index to density (ppl/km²) via bin MIDPOINTS.
        """
        idx = np.clip(idx_arr.astype(np.float32), 0.0, 255.0)
        x = (idx + 0.5) / 256.0  # bin midpoint
        if mode == "log":
            if vmin <= 0 or vmax <= vmin:
                raise ValueError("Invalid sedac_min/sedac_max for log mapping.")
            vmin_log, vmax_log = np.log10(vmin), np.log10(vmax)
            return np.power(10.0, vmin_log + x * (vmax_log - vmin_log), dtype=np.float32)
        else:  # "linear"
            return (vmin + x * (vmax - vmin)).astype(np.float32)

    # ---- Country totals (physical) ----

    def _country_population_sums(self,
                                 country_polys: Dict[str, Polygon | MultiPolygon],
                                 raster_path: str,
                                 encoding: str,
                                 area_method: str,
                                 thr: float,
                                 gamma: float,
                                 sedac_mode: str,
                                 sedac_min: float,
                                 sedac_max: float,
                                 index_nodata: Tuple[int, ...],
                                 density_range: Optional[Tuple[float, float]] = None
                                 ) -> Dict[str, float]:
        """
        Sum 'effective people' per country:
          - encoding == "density": sum( density * pixel_area_km2 )
          - encoding == "count"  : sum( count )
          - encoding == "indexed": map index->density using sedac_mode/min/max, then sum( density*area )
        Notes:
          * We ignore 'gamma' here to keep totals physical.
          * Prefer thr=0 for totals; use small value only to kill speckle if needed.
          * If density_range is provided, only pixels with dens in [dmin, dmax) contribute.
        """
        try:
            import rasterio
            from rasterio.mask import mask
        except Exception as e:
            raise RuntimeError(
                "Population-weighted mode requires 'rasterio'. Install it or set 'population_raster=None'."
            ) from e

        pop_sums: Dict[str, float] = {}

        with rasterio.open(raster_path) as src:
            band_dtype = src.dtypes[0] if hasattr(src, "dtypes") else None
            for name, poly in country_polys.items():
                try:
                    # filled=False -> outside polygon is mask=True (not 0)
                    out_image, out_transform = mask(src, [poly], crop=True, filled=False)
                except ValueError:
                    pop_sums[name] = 0.0
                    continue

                band = out_image[0]                   # masked array
                vals = band.data.astype(np.float32)   # raw numbers
                valid = (~band.mask) & np.isfinite(vals)

                data = np.zeros_like(vals, dtype=np.float32)

                if encoding == "count":
                    data[valid] = vals[valid]  # people per pixel

                elif encoding == "density":
                    data[valid] = np.maximum(vals[valid], 0.0)  # ppl/km²

                elif encoding == "indexed":
                    # treat specific palette indices as NoData/water
                    nodata_mask = np.isin(vals.astype(np.int16), list(index_nodata))
                    valid_idx = valid & (~nodata_mask)
                    if np.any(valid_idx):
                        mapped = self._index_to_density(vals[valid_idx], sedac_mode, sedac_min, sedac_max)
                        data[valid_idx] = mapped
                    # others remain 0

                else:
                    raise ValueError(f"Unknown raster encoding '{encoding}'.")

                # Optional tiny threshold to kill residual speckle (physical totals: keep small or zero)
                if thr > 0.0:
                    data[(data < thr) & valid] = 0.0

                # Pixel geometry -> per-row pixel area (km²)
                px_w = abs(out_transform.a)
                px_h = abs(out_transform.e)
                e = out_transform.e
                f = out_transform.f
                rows = np.arange(data.shape[0], dtype=float)
                lat_centers = f + (rows + 0.5) * e
                row_areas = self._row_areas_km2(lat_centers, px_w, px_h, method=area_method)
                area_grid = np.broadcast_to(row_areas[:, None], data.shape)  # km²

                # Build density grid (ppl/km²) for band filtering
                if encoding == "count":
                    with np.errstate(divide="ignore", invalid="ignore"):
                        dens = np.where(area_grid > 0, data / area_grid, 0.0)
                else:
                    dens = data

                # Keep only pixels in the requested density band
                if density_range is not None:
                    dmin, dmax = density_range
                    keep = (dens >= dmin) & (dens < dmax)
                    data = np.where(keep, data, 0.0)

                if encoding in ("density", "indexed"):
                    eff = data * area_grid  # ppl/km² * km² -> people
                else:  # "count"
                    eff = data              # already people per pixel

                total = float(np.nansum(eff))
                pop_sums[name] = total if np.isfinite(total) else 0.0

        return pop_sums

    # ---- Within-country sampling (matches totals mapping) ----

    def _sample_points_from_population(self,
                                       poly: Polygon | MultiPolygon,
                                       n: int,
                                       raster_path: str,
                                       encoding: str,
                                       area_method: str,
                                       thr: float,
                                       gamma: float,
                                       sedac_mode: str,
                                       sedac_min: float,
                                       sedac_max: float,
                                       index_nodata: Tuple[int, ...],
                                       density_range: Optional[Tuple[float, float]] = None
                                       ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Draw n points inside 'poly' according to weights consistent with totals:
          - "density": weight = density * pixel_area
          - "count"  : weight = count
          - "indexed": weight = (index->density) * pixel_area
        Then apply (optional) threshold/exponent for **sampling only**.
        If density_range is provided, only pixels with dens in [dmin, dmax) are used.
        """
        try:
            import rasterio
            from rasterio.mask import mask
        except Exception as e:
            raise RuntimeError(
                "Population-weighted mode requires 'rasterio'. Install it or set 'population_raster=None'."
            ) from e

        with rasterio.open(raster_path) as src:
            # Keep outside polygon masked; prevents ocean/lake leakage
            out_image, out_transform = mask(src, [poly], crop=True, filled=False)
            band = out_image[0]                   # masked array
            vals = band.data.astype(np.float32)
            valid = (~band.mask) & np.isfinite(vals)

            data = np.zeros_like(vals, dtype=np.float32)

            if encoding == "count":
                data[valid] = vals[valid]

            elif encoding == "density":
                data[valid] = np.maximum(vals[valid], 0.0)

            elif encoding == "indexed":
                nodata_mask = np.isin(vals.astype(np.int16), list(index_nodata))
                valid_idx = valid & (~nodata_mask)
                if np.any(valid_idx):
                    mapped = self._index_to_density(vals[valid_idx], sedac_mode, sedac_min, sedac_max)
                    data[valid_idx] = mapped
            else:
                raise ValueError(f"Unknown raster encoding '{encoding}'.")

            # Pixel geometry (degrees)
            px_w = abs(out_transform.a)
            px_h = abs(out_transform.e)
            e = out_transform.e
            f = out_transform.f
            rows_all = np.arange(data.shape[0], dtype=float)
            lat_centers = f + (rows_all + 0.5) * e

            # Pixel area per row (km²)
            row_areas = self._row_areas_km2(lat_centers, px_w, px_h, method=area_method)
            area_grid = np.broadcast_to(row_areas[:, None], data.shape)

            # Build density grid (ppl/km²) for band filtering
            if encoding == "count":
                with np.errstate(divide="ignore", invalid="ignore"):
                    dens = np.where(area_grid > 0, data / area_grid, 0.0)
            else:
                dens = data

            # Base weights (match totals)
            if encoding in ("density", "indexed"):
                weights = data * area_grid
            else:  # "count"
                weights = data

            # Keep only pixels within the requested density band
            if density_range is not None:
                dmin, dmax = density_range
                keep = (dens >= dmin) & (dens < dmax)
                weights = np.where(keep, weights, 0.0)

            # Apply sampling-only knobs (after building physical weights)
            if thr > 0.0:
                # Convert density threshold to people threshold if needed
                if encoding in ("density", "indexed"):
                    weights[weights < thr * area_grid] = 0.0
                else:
                    weights[weights < thr * area_grid] = 0.0

            if gamma != 1.0:
                pos = weights > 0
                weights[pos] = np.power(weights[pos], gamma, dtype=np.float32)

            rr, cc = np.nonzero(weights > 0)
            if rr.size == 0:
                # Fallback: uniform sampling inside polygon if weights empty
                return self._random_points_in_polygon(poly, n)

            w = weights[rr, cc].astype(np.float64)
            probs = w / w.sum()

            idx = self.rng.choice(len(rr), size=n, p=probs)
            r = rr[idx]; c = cc[idx]

            # Pixel centers to lon/lat
            import rasterio  # safe
            lons, lats = rasterio.transform.xy(out_transform, r, c)

            # Jitter within pixel footprint (degrees)
            res_x = out_transform.a
            res_y = -out_transform.e
            lons = np.array(lons) + self.rng.uniform(-0.5, 0.5, size=n) * res_x
            lats = np.array(lats) + self.rng.uniform(-0.5, 0.5, size=n) * res_y
            return lons, lats

    # API used by StationFactory.generate_imt_ue_outdoor
    def transform_ue_xyz(self, bs_idx: int, x_local, y_local, z_local):
        return (self.x[bs_idx] + x_local,
                self.y[bs_idx] + y_local,
                self.z[bs_idx] + z_local)


# For convenience if someone imports TopologyCountry by mistake
TopologyCountry = TopologyCountries


# ----------------------- MAIN -----------------------
if __name__ == "__main__":
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import Wedge
    from collections import Counter
    from pathlib import Path
    # ============ User-defined inputs ============
    num_bs = 5000
    rng_seed = 42
    cell_radius_m = 400.0  # 10 km
    dist_type = "Urban"         # "Urban" | "Suburban" | "Rural" | None
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

    # Sampling-only knobs
    min_density_threshold = 0.0  # ppl/km² cutoff in sampling
    density_exponent = 1.0       # >1 bias toward dense areas

    # Countries (Americas example)
    countries_americas = [
        # South America
        "Brazil"
    ]
    # countries_americas = [
    #    # Europe
    #    "Albania", "Austria", "Belgium", "Bosnia and Herzegovina",
    #    "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia",
    #    "Finland", "France", "Germany", "Greece", "Hungary", "Iceland",
    #    "Ireland", "Italy", "Latvia", "Lithuania",
    #    "Luxembourg", "Montenegro", "Netherlands",
    #    "North Macedonia", "Norway", "Poland", "Portugal", "Romania",
    #    "Slovakia", "Slovenia", "Spain", "Sweden",
    #    "Switzerland", "Ukraine", "United Kingdom",
    
    #    # Africa
    #    "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
    #    "Cameroon", "Central African Republic", "Chad",
    #    "Democratic Republic of the Congo", "Djibouti",
    #    "Egypt", "Equatorial Guinea", "Eritrea", "Ethiopia", "Gabon",
    #    "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Kenya", "Lesotho",
    #    "Liberia", "Libya", "Madagascar", "Malawi", "Mali", "Mauritania",
    #    "Morocco", "Mozambique", "Namibia", "Niger", "Nigeria",
    #    "Rwanda", "Senegal",
    #    "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Sudan",
    #    "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe",

    #    # Middle East (west of the Persian Gulf, incl. Iraq)
    #     "Iran", "Iraq", "Israel", "Jordan", "Kuwait", "Lebanon",
    #    "Oman", "Qatar", "Saudi Arabia", "Syria",
    #    "United Arab Emirates", "Yemen",

    #    # Former Soviet Union (Region 1 portion)
    #    "Armenia", "Azerbaijan", "Belarus", "Georgia", "Kazakhstan",
    #    "Kyrgyzstan", "Moldova", "Russia", "Tajikistan", "Turkmenistan",
    #    "Uzbekistan",
    # ]



    # NEW: pick a distribution band (choose ONE of the two options below)
    # Option A: use named band

    # Option B: explicit band (overrides dist_type if uncommented)
    # dist_density_min = 300.0
    # dist_density_max = 10000.0

    # ============ Build topology ============


    params = ParametersCountries(
        country_names=countries_americas,
        num_bs_total=num_bs,
        rng_seed=rng_seed,
        cell_radius=cell_radius_m,
        countries_shapefile=shapefile_path,
        population_raster=population_raster_path,
        height=18,

        raster_encoding=raster_encoding,
        sedac_palette_mode=sedac_palette_mode,
        pixel_area_method="spherical",

        # NEW: band settings
        dist_type=dist_type,
    )

    geoconv = GeometryConverter()
    geoconv.set_reference(-15.793889, -47.882778, 0.0)
    topo = TopologyCountries(params, geoconv).calculate_coordinates()
    
    # ============ Figure: Map (left) + BS-per-country (right) ============
    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(1, 2, width_ratios=[2.2, 1.0], wspace=0.22)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_bar = fig.add_subplot(gs[0, 1])

    # Draw country boundaries
    try:
        world = topo._load_countries_gdf(shapefile_path)
        has_name, has_admin = "name" in world.columns, "ADMIN" in world.columns
        if has_name and has_admin:
            subset = world[(world["name"].isin(countries_americas)) |
                           (world["ADMIN"].isin(countries_americas))]
        elif has_name:
            subset = world[world["name"].isin(countries_americas)]
        elif has_admin:
            subset = world[world["ADMIN"].isin(countries_americas)]
        else:
            subset = None
    except Exception:
        subset = None

    if subset is not None and not subset.empty:
        subset.boundary.plot(ax=ax_map, linewidth=0.8, color="black")

    # Scatter all BS
    ax_map.scatter(topo.lons, topo.lats, s=6, c="red", alpha=0.35, label="Base stations", zorder=2)

    # “Pizza” azimuth wedges for a subset (to avoid clutter)
    max_wedges = 1500
    step = max(1, topo.num_base_stations // max_wedges)  # draw every 'step' stations
    half_bw_deg = 60  # 60° sector total width

    for lon, lat, az in zip(topo.lons[::step], topo.lats[::step], topo.azimuth[::step]):
        # Convert cell radius (meters) to degrees at this latitude
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * np.cos(np.radians(lat))
        avg_km_per_deg = (km_per_deg_lat + km_per_deg_lon) / 2.0
        radius_deg = (topo.cell_radius / 1000.0) / max(avg_km_per_deg, 1e-9)

        wedge = Wedge((lon, lat), radius_deg, az - half_bw_deg, az + half_bw_deg,
                      facecolor="blue", alpha=0.18, edgecolor="blue", linewidth=0.4)
        ax_map.add_patch(wedge)

    ax_map.set_xlabel("Longitude [°]")
    ax_map.set_ylabel("Latitude [°]")
    band_txt = f"band={params.dist_type}" if params.dist_type else "no band"
    ax_map.set_title(f"{num_bs} BS across the Americas "
                     f"({'pop-weighted' if population_raster_path else 'uniform'}; "
                     f"encoding={raster_encoding}; {band_txt})")
    ax_map.legend(loc="upper right", frameon=True)

    # Histogram / bar chart: number of BS per country
    from collections import Counter
    counts = Counter(topo.country_index.tolist())
    countries_sorted = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
    values_sorted = [counts[c] for c in countries_sorted]
    total_bs = sum(values_sorted) if values_sorted else 0

    ax_bar.barh(countries_sorted, values_sorted)
    ax_bar.invert_yaxis()  # largest on top
    ax_bar.set_xlabel("Number of base stations")
    ax_bar.set_title("BS per country")

    # Annotate counts and percentages
    if total_bs > 0:
        for y, (name, v) in enumerate(zip(countries_sorted, values_sorted)):
            ax_bar.text(v, y, f" {v:,}  ({v/total_bs:.1%})", va="center", ha="left", fontsize=9)

    ax_bar.margins(x=0.10)
    for label in ax_bar.get_yticklabels():
        label.set_fontsize(9)

    fig.tight_layout()

    plt.show()