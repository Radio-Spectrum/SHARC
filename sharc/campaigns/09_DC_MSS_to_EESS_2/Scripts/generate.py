#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import copy
import numpy as np
from pathlib import Path

# ============================================================
# ===================== VARIÁVEIS GERAIS =====================
# ============================================================

try:
    SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    SCRIPT_DIR = Path.cwd()

CAMPAIGN_DIR = SCRIPT_DIR.parent 

BASE_YAML_PATH = CAMPAIGN_DIR / "Scripts" / "base_input.yaml"
INPUT_DIR = CAMPAIGN_DIR / "input"
OUTPUT_DIR = CAMPAIGN_DIR / "output"


# Sweep — service grid

LOAD_FACTORS = [0.2, 0.5]
MASK = ["Spu"]   #["STEP", "MSS"]
EESS_systems = ["EESS_D"] #["EESS_B", "EESS_D"]
EESS_pos = ['P'] # P - Paraguay; B - Bolivia; C - Colombia
MARGIN = [0, 60]
DCMSS_systems = ["system_525km"] #["system_340km", "system_525km"]
COVERAGES = {
    #"uBR": {
    #    "countries": ["Brazil"],
    #},
    "BR_AR": {
        "countries": ["Brazil", "Argentina"],
    },
    #"SA": {
    #    "countries": [
    #        "Argentina", "Bolivia", "Brazil", "Chile", "Colombia",
    #        "Ecuador", "Paraguay", "Peru", "Uruguay",
    #    ],
    #},
}



def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_cfg, yaml_backend = load_yaml(BASE_YAML_PATH)

    for sistema in DCMSS_systems:
        for mascara in MASK:
                for system_EESS in EESS_systems:
                    for lf in LOAD_FACTORS:
                        for margin in MARGIN:
                            for cov_key, cov in COVERAGES.items():
                                for es_pos in EESS_pos:

                                    cfg = copy.deepcopy(base_cfg)

                                    # ===== Sistema MSS =====
                                    dc_mss = cfg["imt"]["topology"]["mss_dc"]
                                    orbit = dc_mss["orbits"][0]

                                    if sistema == "system_340km":
                                        orbit["n_planes"] = 48
                                        orbit["perigee_alt_km"] = 340
                                        orbit["apogee_alt_km"] = 340
                                        orbit["sats_per_plane"] = 110
                                        orbit["phasing_deg"] = 1.636
                                        dc_mss["N_max_beam"] = 105
                                        dc_mss["beam_radius"] = 26195
                                        cfg["imt"]["bs"]["height"] = 340000
                                    else:
                                        orbit["n_planes"] = 28
                                        orbit["perigee_alt_km"] = 525
                                        orbit["apogee_alt_km"] = 525
                                        orbit["sats_per_plane"] = 120
                                        orbit["phasing_deg"] = 1.5
                                        dc_mss["beam_radius"] = 40448
                                        dc_mss["N_max_beam"] = 90
                                        cfg["imt"]["bs"]["height"] = 525000

                                    # ===== Mask =====
                                    if mascara == "MSS":
                                        cfg["imt"]["spectral_mask"] = "MSS"
                                        cfg["imt"].pop("spectral_mask_steps", None)
                                        cfg["imt"]["bs"]["use_oob_antenna"] = False
                                        cfg["imt"]["bs"].pop("oob_antenna", None)
                                        cfg["imt"]["frequency"] = 2197.5
                                        cfg["imt"]["bs"]["antenna"]["itu_r_s_1528"]["frequency"] = 2197.5 
                                    elif mascara == "Spu":
                                        cfg["imt"]["spectral_mask"] = "MSS"
                                        cfg["imt"].pop("spectral_mask_steps", None)
                                        cfg["imt"]["bs"]["use_oob_antenna"] = False
                                        cfg["imt"]["bs"].pop("oob_antenna", None)
                                        cfg["imt"]["frequency"] = 2187.5 
                                        cfg["imt"]["bs"]["antenna"]["itu_r_s_1528"]["frequency"] = 2187.5 
                                        
                                    else:
                                        cfg["imt"]["spectral_mask"] = "STEPPED"
                                        cfg["imt"]["spectral_mask_steps"] = [
                                            34.875334439154976,
                                            16.87533443915498,
                                            6.87533443915498
                                        ]
                                        cfg["imt"]["frequency"] = 2197.5
                                        cfg["imt"]["bs"]["antenna"]["itu_r_s_1528"]["frequency"] = 2197.5 

                                    # ===== EESS =====
                                    earth = cfg["single_earth_station"]

                                    if system_EESS == "EESS_B":
                                        f = 2202
                                        earth["bandwidth"] = 4
                                        earth["noise_temperature"] = 190
                                        G_dBi = 45.8
                                    else:
                                        f = 2203
                                        earth["bandwidth"] = 6
                                        earth["noise_temperature"] = 120
                                        G_dBi = 39

                                    earth["frequency"] = f
                                    earth["antenna"]["gain"] = G_dBi
                                    earth["antenna"]["itu_r_s_465"]["antenna_gain"] = G_dBi

                                    G_linear = 10**(G_dBi / 10)
                                    lam = 2.998e8 / (f * 1e6)
                                    diam = float(np.round(lam * np.sqrt(G_linear / 0.9) / np.pi, 2))
                                    earth["antenna"]["itu_r_s_465"]["diameter"] = diam

                                    # ===== Load factor =====
                                    cfg["imt"]["bs"]["load_probability"] = lf

                                    # ===== Margin type =====
                                    dc_mss_from_con = dc_mss["beam_positioning"]["service_grid"]["grid_in_zone"]["from_countries"]
                                    dc_mss_from_con["margin_from_border"] = margin

                                    # ===== Coverage =====
                                    dc_mss["sat_is_active_if"]["lat_long_inside_country"]["country_names"] = list(cov["countries"])
                                    dc_mss_from_con["country_names"] = list(cov["countries"])

                                    # ===== ES position =====
                                    if es_pos == "P":
                                        cfg["imt"]["topology"]["central_latitude"] = -25.5549751
                                        cfg["imt"]["topology"]["central_longitude"] = -54.5746686
                                        cfg["imt"]["topology"]["central_altitude"] = 200
                                        cfg["single_earth_station"]["param_p619"]["earth_station_lat_deg"] = -25.5549751
                                        cfg["single_earth_station"]["param_p619"]["earth_station_alt_m"] = 200
                                    elif es_pos == "C":
                                        cfg["imt"]["topology"]["central_latitude"] = -4.214
                                        cfg["imt"]["topology"]["central_longitude"] = -69.94
                                        cfg["imt"]["topology"]["central_altitude"] = 88
                                        cfg["single_earth_station"]["param_p619"]["earth_station_lat_deg"] = -4.214
                                        cfg["single_earth_station"]["param_p619"]["earth_station_alt_m"] = 88
                                    elif es_pos == "B":
                                        cfg["imt"]["topology"]["central_latitude"] = -11.025
                                        cfg["imt"]["topology"]["central_longitude"] = -68.765
                                        cfg["imt"]["topology"]["central_altitude"] = 240
                                        cfg["single_earth_station"]["param_p619"]["earth_station_lat_deg"] = -11.025
                                        cfg["single_earth_station"]["param_p619"]["earth_station_alt_m"] = 240                                   


                                    # ===== Output name =====
                                    name = f"{sistema}_{system_EESS}_{cov_key}_{es_pos}_{mascara}_OM_{margin}_lf_{lf}"
                                    cfg["general"]["output_dir_prefix"] = name
                                    cfg["general"]["output_dir"] = str(OUTPUT_DIR)

                                    output_file = INPUT_DIR / f"{name}.yaml"

                                    dump_yaml(cfg, output_file, yaml_backend)


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
