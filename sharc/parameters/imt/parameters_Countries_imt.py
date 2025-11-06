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
    Parâmetros para gerar topologia por países com amostragem (opcional) ponderada por população.

    Campos principais:
      - country_names: lista de países (nomes conforme seu shapefile/NE)
      - num_bs_total : número total de BS (se bs_per_country não for usado)
      - bs_per_country: (opcional) mapa país->n_BS (se definido, ignora num_bs_total)
      - rng_seed     : semente p/ reprodutibilidade
      - cell_radius  : raio da célula (m) (tamanho da “pizza” no plot)
      - countries_shapefile: caminho para shapefile de países (WGS84); se None, tenta cartopy/geodatasets
      - population_raster  : caminho para raster SEDAC (ou equivalente). Se None → distribuição uniforme
      - raster_encoding    : "density" (valor = hab/km²) ou "indexed" (valor 0–255 com escala log10 entre sedac_min/sedac_max)
      - sedac_min, sedac_max: limites da escala log para raster "indexed" (ex.: 1 ↔ 10⁰ e 1e4 ↔ 10⁴)
      - mask_inland_water  : se True, trata valores de água (0/nodata) como não-populados
      - dist_type          : None|"Urban"|"Suburban"|"Rural" → filtra pixels por faixa de densidade
      - density_ranges     : faixas (hab/km²) por tipo (usado quando dist_type não é None)
      - sector_half_bw_deg : meia-largura do setor (deg) para o “pizza plot”
    """
    country_names: List[str] = field(
        default_factory=lambda: ["Brazil", "Argentina"]
    )   
    num_bs_total: int = 1000
    rng_seed: int = 1
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

    # Filtragem por densidade (usada se dist_type não for None)
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
    # Shapefile (or set to None to auto-download Natural Earth via cartopy/geodatasets)
    shapefile_path: Path = field(
        default_factory=lambda: Path.cwd() / "sharc" / "topology" / "map" / "ne_110m_admin_0_countries.shp"
    )
    # Population raster (set to None to sample uniformly by area)
    population_raster_path: Path = field(
        default_factory=lambda: Path.cwd() / "sharc" / "topology" / "map" / "SEDAC_map2.tiff"
    )

    # (opcional) força nº de BS por país (se definido, ignora num_bs_total)
    bs_per_country: Optional[Dict[str, int]] = None

    # (opcional) largura semi-setorial (deg) para o “pizza plot”
    sector_half_bw_deg: float = 60.0

    min_density_threshold: float = 0.0  # ppl/km² cutoff in sampling
    density_exponent: float = 1.0       # >1 bias toward dense areas

    # ----------------- Validação -----------------
    def validate(self) -> None:
        """Valida os campos e lança ValueError se algo estiver inconsistente."""
        # Países
        if not isinstance(self.country_names, list) or len(self.country_names) == 0:
            raise ValueError("country_names deve ser uma lista não vazia de nomes de países.")

        # cell radius & setor
        if not (isinstance(self.cell_radius, (int, float)) and self.cell_radius > 0):
            raise ValueError("cell_radius deve ser positivo (em metros).")
        if not (0.0 < float(self.sector_half_bw_deg) <= 180.0):
            raise ValueError("sector_half_bw_deg deve estar em (0, 180].")

        # BS totals
        if self.bs_per_country is not None:
            if not isinstance(self.bs_per_country, dict) or len(self.bs_per_country) == 0:
                raise ValueError("bs_per_country, se definido, deve ser um dicionário país->inteiro >=0.")
            # chaves válidas
            unknown = [k for k in self.bs_per_country.keys() if k not in self.country_names]
            if unknown:
                raise ValueError(f"bs_per_country contém países não listados em country_names: {unknown}")
            # valores não-negativos
            bad = {k: v for k, v in self.bs_per_country.items() if (not isinstance(v, int)) or v < 0}
            if bad:
                raise ValueError(f"bs_per_country devem ser inteiros >=0: {bad}")
        else:
            if not (isinstance(self.num_bs_total, int) and self.num_bs_total > 0):
                raise ValueError("num_bs_total deve ser inteiro > 0 quando bs_per_country não é fornecido.")

        # RNG seed
        if not isinstance(self.rng_seed, int):
            raise ValueError("rng_seed deve ser inteiro.")

        # Shapefile
        if self.countries_shapefile is not None:
            if not isinstance(self.countries_shapefile, str) or not os.path.exists(self.countries_shapefile):
                raise ValueError(f"countries_shapefile não encontrado: {self.countries_shapefile}")

        # Raster
        if self.population_raster is not None:
            if not isinstance(self.population_raster, str) or not os.path.exists(self.population_raster):
                raise ValueError(f"population_raster não encontrado: {self.population_raster}")
            if self.raster_encoding not in ("density", "indexed"):
                raise ValueError("raster_encoding deve ser 'density' ou 'indexed'.")
            if self.raster_encoding == "indexed":
                if not (self.sedac_min > 0 and self.sedac_max > self.sedac_min):
                    raise ValueError("Para raster 'indexed', sedac_min>0 e sedac_max>sedac_min devem ser válidos.")

        # dist_type
        if self.dist_type is not None:
            if self.dist_type not in ("Urban", "Suburban", "Rural"):
                raise ValueError("dist_type, se definido, deve ser 'Urban', 'Suburban' ou 'Rural'.")
            if self.dist_type not in self.density_ranges:
                raise ValueError(f"density_ranges deve conter a chave '{self.dist_type}'.")
            lo, hi = self.density_ranges[self.dist_type]
            if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and hi > lo and lo >= 0):
                raise ValueError(f"Faixa de densidade inválida para {self.dist_type}: {(lo, hi)}.")
