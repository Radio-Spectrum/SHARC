#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import copy
import csv
from pathlib import Path

# ============================================================
# ===================== VARIÁVEIS GERAIS =====================
# ============================================================

try:
    SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    SCRIPT_DIR = Path.cwd()

CAMPAIGN_DIR = SCRIPT_DIR.parent   # 09_Guarulhos

BASE_YAML_PATH = CAMPAIGN_DIR / "Script" / "Base.yaml"
INPUT_DIR = CAMPAIGN_DIR / "INPUT"
OUTPUT_DIR = CAMPAIGN_DIR / "output"


# Sweep — service grid
<<<<<<< HEAD
MARGINS_KM = [0, 30, 60, 90]
MIN_SERVICE_ANGLE_DEG = [40]
LOAD_FACTORS = [0.1, 0.2, 0.5]
=======
MARGINS_KM = [0]
MIN_SERVICE_ANGLE_DEG = [40]
LOAD_FACTORS = [0.5]
>>>>>>> 638cb0dfe20fd9832b837dbfa617302ec214764e

# ------------------------------------------------------------
# Perfis da estação vítima (Systems B e D)
# Cada vítima tem UMA altura fixa
# Ajustar SOMENTE:
#  - single_earth_station.antenna.gain
#  - single_earth_station.antenna.itu_r_s_465.antenna_gain
#  - single_earth_station.geometry.height
#  - single_earth_station.geometry.elevation.uniform_dist.min
# ------------------------------------------------------------
VICTIM_STATIONS = {
    "B": {"antenna_gain": 45.8, "height_m": 15, "min_elevation_deg": 5, "bandwidth": 4},
    "D": {"antenna_gain": 39.0, "height_m": 15, "min_elevation_deg": 5, "bandwidth": 6},
}

# ------------------------------------------------------------
# Coberturas
# pb_margin_if_zero = margem a aplicar SOMENTE na zona com power_backoff_db = 0.0
# dentro de: imt.topology.mss_dc.power_control_zones.zones[*]
# ------------------------------------------------------------
COVERAGES = {
<<<<<<< HEAD
    "BR": {
        "countries": ["Brazil", "Argentina"],
=======
    "BR_PB150": {
        "countries": ["Brazil"],
>>>>>>> 638cb0dfe20fd9832b837dbfa617302ec214764e
        "pb_margin_if_zero": 150,  # BR: você pediu 150 quando power_backoff_db=0
    },
    "BR_PB100": {
        "countries": ["Brazil"],
        "pb_margin_if_zero": 100,  # BR: você pediu 150 quando power_backoff_db=0
    },
    "BR_PB50": {
        "countries": ["Brazil"],
        "pb_margin_if_zero": 50,  # BR: você pediu 150 quando power_backoff_db=0
    },
    "BR_AR_PB150": {
        "countries": ["Brazil","Argentina"],
        "pb_margin_if_zero": 150,  # BR: você pediu 150 quando power_backoff_db=0
    },
    "BR_AR_PB100": {
        "countries": ["Brazil","Argentina"],
        "pb_margin_if_zero": 100,  # BR: você pediu 150 quando power_backoff_db=0
    },
    "SA_PB50": {
        "countries": ["Brazil","Argentina"],
        "pb_margin_if_zero": 50,  # BR: você pediu 150 quando power_backoff_db=0
    },  
    "SA_PB150": {
        "countries": ["Brazil", "Argentina", "Uruguay", "Paraguay", "Bolivia", "Chile", "Peru"],
        "pb_margin_if_zero": 150,  # BR: você pediu 150 quando power_backoff_db=0
    },
    "SA_PB100": {
        "countries": ["Brazil", "Argentina", "Uruguay", "Paraguay", "Bolivia", "Chile", "Peru"],
        "pb_margin_if_zero": 100,  # BR: você pediu 150 quando power_backoff_db=0
    },
    "SA_PB50": {
        "countries": ["Brazil", "Argentina", "Uruguay", "Paraguay", "Bolivia", "Chile", "Peru"],
        "pb_margin_if_zero": 50,  # BR: você pediu 150 quando power_backoff_db=0
    }, 
}

# ------------------------------------------------------------
# Estações IMT (localização)
# ------------------------------------------------------------
STATIONS = {
    "PA": None,  # lido do Base.yaml
    "BO": {"lat": -11.025, "lon": -68.765, "alt_m": 240},
    "CO": {"lat": -4.214, "lon": -69.94,  "alt_m": 88},
}

# ============================================================
# ========================== MAIN =============================
# ============================================================

def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_cfg, yaml_backend = load_yaml(BASE_YAML_PATH)

    # Paraguai a partir do Base.yaml
    topo_base = base_cfg["imt"]["topology"]
    STATIONS["PA"] = {
        "lat": float(topo_base["central_latitude"]),
        "lon": float(topo_base["central_longitude"]),
        "alt_m": float(topo_base["central_altitude"]),
    }

    manifest_path = INPUT_DIR / "manifest.csv"

    with manifest_path.open("w", newline="", encoding="utf-8") as mf:
        writer = csv.writer(mf)
        writer.writerow([
            "file",
            "station", "coverage",
            "victim_system",
            "victim_height_m",
            "sg_margin_km",
            "min_service_angle",
            "load_factor",
            "pb_margin_if_zero",
            "pb_applied",
        ])

        n_files = 0

        for st_key, st in STATIONS.items():
            for cov_key, cov in COVERAGES.items():
                for victim_key, victim in VICTIM_STATIONS.items():

                    countries = cov["countries"]
                    pb_margin_if_zero = cov["pb_margin_if_zero"]

                    for margin in MARGINS_KM:
                        for angle in MIN_SERVICE_ANGLE_DEG:
                            for lf in LOAD_FACTORS:

                                cfg = copy.deepcopy(base_cfg)

                                # -------------------------------
                                # Local da estação IMT
                                # -------------------------------
                                topo = cfg["imt"]["topology"]
                                topo["central_latitude"] = st["lat"]
                                topo["central_longitude"] = st["lon"]
                                topo["central_altitude"] = st["alt_m"]
                                cfg["single_earth_station"]["param_p619"]["earth_station_lat_deg"] = st["lat"]
                                cfg["single_earth_station"]["param_p619"]["earth_station_lat_deg"] = st["alt_m"]

                                # -------------------------------
                                # Ângulo mínimo de serviço
                                # -------------------------------
                                cfg["imt"]["topology"]["mss_dc"]["beam_positioning"] \
                                   ["service_grid"]["minimum_service_angle"] = float(angle)

                                # -------------------------------
                                # Load factor
                                # -------------------------------
                                cfg["imt"]["bs"]["load_probability"] = float(lf)

                                # -------------------------------
                                # Atualiza country_names (somente dentro de topology)
                                # -------------------------------
                                patch_country_names(cfg["imt"]["topology"], countries)

                                # -------------------------------
                                # Service grid margin (LOCAL CORRETO)
                                # -------------------------------
                                update_service_grid_margin(cfg, countries, float(margin))

                                # -------------------------------
                                # Power control zones (LOCAL CORRETO)
                                #   imt.topology.mss_dc.power_control_zones.zones[*]
                                #   aplicar pb_margin_if_zero SOMENTE quando power_backoff_db == 0.0
                                # -------------------------------
                                pb_applied = update_power_control_zone_margin_if_zero(
                                    cfg, countries, float(pb_margin_if_zero)
                                )

                                # -------------------------------
                                # Estação vítima — AJUSTE FINAL
                                # -------------------------------
                                ses = cfg["single_earth_station"]

                                # Ganho da antena (duplo)
                                ses["antenna"]["gain"] = float(victim["antenna_gain"])
                                ses["antenna"]["itu_r_s_465"]["antenna_gain"] = float(victim["antenna_gain"])

                                # Altura
                                ses["geometry"]["height"] = float(victim["height_m"])
                                ses["bandwidth"] = float(victim["bandwidth"])

                                # Elevação mínima (min dentro de elevation.uniform_dist)
                                elev = ses["geometry"]["elevation"]
                                if elev.get("type") != "UNIFORM_DIST":
                                    raise ValueError("Esperado single_earth_station.geometry.elevation.type = UNIFORM_DIST")
                                elev["uniform_dist"]["min"] = float(victim["min_elevation_deg"])

                                # -------------------------------
                                # Prefixo / arquivo
                                # (tirar ST e COV, mas manter st_key e cov_key)
                                # -------------------------------
                                prefix = (
                                    f"Vic{victim_key}"
                                    f"_{st_key}"
                                    f"_{cov_key}"
                                    f"_MB{margin}"
                                    f"_A{angle}"
                                    f"_LF{int(lf*100)}"
                                )

                                cfg["general"]["output_dir_prefix"] = prefix
                                cfg["general"]["output_dir"] = str(OUTPUT_DIR)

                                out_file = INPUT_DIR / f"{prefix}.yaml"
                                dump_yaml(cfg, out_file, yaml_backend)

                                writer.writerow([
                                    out_file.name,
                                    st_key, cov_key,
                                    victim_key,
                                    victim["height_m"],
                                    margin,
                                    angle,
                                    lf,
                                    pb_margin_if_zero,
                                    pb_applied,
                                ])

                                n_files += 1

    print(f"✔ {n_files} arquivos gerados em {INPUT_DIR}")
    print(f"✔ Manifest: {manifest_path}")

# ============================================================
# ======================= FUNÇÕES ============================
# ============================================================

def patch_country_names(node, countries: list[str]):
    """
    Atualiza apenas chaves 'country_names' que já existam, dentro do dicionário passado.
    Aqui chamamos com cfg['imt']['topology'] para NÃO mexer em outras seções.
    """
    if isinstance(node, dict):
        if "country_names" in node and isinstance(node["country_names"], list):
            node["country_names"] = list(countries)
        for v in node.values():
            patch_country_names(v, countries)
    elif isinstance(node, list):
        for it in node:
            patch_country_names(it, countries)


def update_service_grid_margin(cfg: dict, countries: list[str], margin_km: float):
    """
    Atualiza apenas:
      imt.topology.mss_dc.beam_positioning.service_grid.grid_in_zone.from_countries
    """
    fc = (
        cfg["imt"]["topology"]["mss_dc"]["beam_positioning"]
           ["service_grid"]["grid_in_zone"]["from_countries"]
    )
    fc["country_names"] = list(countries)
    fc["margin_from_border"] = float(margin_km)


def update_power_control_zone_margin_if_zero(cfg: dict, countries: list[str], pb_margin_if_zero: float) -> bool:
    """
    Atualiza SOMENTE a(s) zona(s) com power_backoff_db == 0.0 em:
      imt.topology.mss_dc.power_control_zones.zones
    Não cria nenhuma chave nova em imt.bs.
    """
    zones = cfg["imt"]["topology"]["mss_dc"].get("power_control_zones", {}).get("zones", [])
    if not isinstance(zones, list):
        raise ValueError("Esperado power_control_zones.zones como lista")

    applied = False
    for z in zones:
        try:
            if float(z.get("power_backoff_db", -999)) != 0.0:
                continue
        except Exception:
            continue

        geom = z.get("geometry", {})
        if geom.get("type") != "FROM_COUNTRIES":
            continue

        fc = geom.get("from_countries", {})
        fc["country_names"] = list(countries)
        fc["margin_from_border"] = float(pb_margin_if_zero)
        applied = True

    return applied


def load_yaml(path: Path):
    try:
        from ruamel.yaml import YAML
        yaml = YAML()
        yaml.preserve_quotes = True
        with path.open("r", encoding="utf-8") as f:
            data = yaml.load(f)
        return data, ("ruamel", yaml)
    except Exception:
        import yaml as pyyaml
        with path.open("r", encoding="utf-8") as f:
            data = pyyaml.safe_load(f)
        return data, ("pyyaml", None)


def dump_yaml(data: dict, path: Path, backend):
    kind, yaml_obj = backend
    if kind == "ruamel":
        with path.open("w", encoding="utf-8") as f:
            yaml_obj.dump(data, f)
    else:
        import yaml as pyyaml
        with path.open("w", encoding="utf-8") as f:
            pyyaml.safe_dump(
                data,
                f,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
                width=120,
            )

# ============================================================
# ========================= RUN ==============================
# ============================================================

if __name__ == "__main__":
    main()
