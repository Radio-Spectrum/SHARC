# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Literal
from sharc.parameters.parameters_base import ParametersBase
from pathlib import Path
import os


@dataclass
class ParametersCountries(ParametersBase):
    """
    Parameters to generate topology by countries with (optional) population-weighted sampling.

    Main fields:
      - country_names: list of countries (names according to your shapefile/NE)
      - num_bs_total: total number of BS (if bs_per_country is not used)
      - bs_per_country: (optional) map country->n_BS (if defined, ignores num_bs_total)
      - cell_radius: cell radius (m) (size of the "pizza" in the plot)
      - countries_shapefile: path to countries shapefile (WGS84); if None, tries cartopy/geodatasets
      - population_raster: path to SEDAC raster (or equivalent). If None -> uniform distribution
      - raster_encoding: "density" (value = ppl/km²) or "indexed" (value 0-255 with log10 scale between sedac_min/sedac_max)
      - sedac_min, sedac_max: log scale limits for "indexed" raster (e.g.: 1 <-> 10^0 and 1e4 <-> 10^4)
      - mask_inland_water: if True, treats water values (0/nodata) as non-populated
      - dist_type: None|"Urban"|"Suburban"|"Rural" -> filters pixels by density range
      - density_ranges: ranges (ppl/km²) by type (used when dist_type is not None)
      - sector_half_bw_deg: sector half-width (deg) for the "pizza plot"
    """
    country_names: List[str] = field(
        default_factory=lambda: ["Brazil", "Argentina"]
    )
    num_bs_total: int = 1000
    cell_radius: float = 400
    fixed_azimuth: Optional[float] = None
    countries_shapefile: Optional[str] = None
    population_raster: Optional[str] = None
    height: float = 18

    raster_encoding: Literal["density", "indexed"] = "indexed"
    sedac_palette_mode: Literal["log", "linear"] = "log"
    sedac_min: float = 1.0
    sedac_max: float = 1e4
    index_nodata: Tuple[int, ...] = (0, 255)

    mask_inland_water: bool = True
    sedac_palette_mode: str = 'log'
    pixel_area_method: str = "spherical"

    dist_type: Optional[Literal["Urban", "Suburban", "Rural"]] = None
    dist_density_min: float = None
    dist_density_max: float = None
    density_ranges: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "Urban": (1500.0, 5000.0),
        "Suburban": (300.0, 1500.0),
        "Rural": (10.0, 100.0),
    })
    act_colormap_path: Path = field(
        default_factory=lambda: Path.cwd() / "sharc" / "topology" / "map" / "sedac_pop.act"
    )
    shapefile_path: Path = field(
        default_factory=lambda: Path.cwd() / "sharc" / "topology" / "map" / "ne_110m_admin_0_countries.shp"
    )
    population_raster_path: Path = field(
        default_factory=lambda: Path.cwd() / "sharc" / "topology" / "map" / "SEDAC_map2.tiff"
    )

    bs_per_country: Optional[Dict[str, int]] = None

    sector_half_bw_deg: float = 60.0

    min_density_threshold: float = 0.0  # ppl/km² cutoff in sampling
    density_exponent: float = 1.0       # >1 bias toward dense areas

    def validate(self, ctx: str = "") -> None:
        """Validates the fields and raises ValueError if anything is inconsistent."""
        prefix = f"{ctx}: " if ctx else ""

        if not isinstance(self.country_names, list) or len(self.country_names) == 0:
            raise ValueError(f"{prefix}country_names must be a non-empty list of country names.")

        if not (isinstance(self.cell_radius, (int, float)) and self.cell_radius > 0):
            raise ValueError(f"{prefix}cell_radius must be positive (in meters).")
        if not (0.0 < float(self.sector_half_bw_deg) <= 180.0):
            raise ValueError(f"{prefix}sector_half_bw_deg must be in (0, 180].")

        if self.bs_per_country is not None:
            if not isinstance(self.bs_per_country, dict) or len(self.bs_per_country) == 0:
                raise ValueError(f"{prefix}bs_per_country, if defined, must be a dict mapping country->integer >=0.")

            unknown = [k for k in self.bs_per_country.keys() if k not in self.country_names]
            if unknown:
                raise ValueError(f"{prefix}bs_per_country contains countries not listed in country_names: {unknown}")

            bad = {k: v for k, v in self.bs_per_country.items() if (not isinstance(v, int)) or v < 0}
            if bad:
                raise ValueError(f"{prefix}bs_per_country values must be integers >=0: {bad}")
        else:
            if not (isinstance(self.num_bs_total, int) and self.num_bs_total > 0):
                raise ValueError(f"{prefix}num_bs_total must be an integer > 0 when bs_per_country is not provided.")

        if self.countries_shapefile is not None:
            if not isinstance(self.countries_shapefile, str) or not os.path.exists(self.countries_shapefile):
                raise ValueError(f"{prefix}countries_shapefile not found: {self.countries_shapefile}")

        if self.population_raster is not None:
            if not isinstance(self.population_raster, str) or not os.path.exists(self.population_raster):
                raise ValueError(f"{prefix}population_raster not found: {self.population_raster}")
            if self.raster_encoding not in ("density", "indexed"):
                raise ValueError(f"{prefix}raster_encoding must be 'density' or 'indexed'.")
            if self.raster_encoding == "indexed":
                if not (self.sedac_min > 0 and self.sedac_max > self.sedac_min):
                    raise ValueError(f"{prefix}For 'indexed' raster, sedac_min>0 and sedac_max>sedac_min must be valid.")

        if self.dist_type is not None:
            if self.dist_type not in ("Urban", "Suburban", "Rural"):
                raise ValueError(f"{prefix}dist_type, if defined, must be 'Urban', 'Suburban' or 'Rural'.")
            if self.dist_type not in self.density_ranges:
                raise ValueError(f"{prefix}density_ranges must contain the key '{self.dist_type}'.")
            lo, hi = self.density_ranges[self.dist_type]
            if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and hi > lo and lo >= 0):
                raise ValueError(f"{prefix}Invalid density range for {self.dist_type}: {(lo, hi)}.")
