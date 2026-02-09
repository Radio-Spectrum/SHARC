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
MASK = ["STEPPED", "DC_MSS"]
TYPE_SIMULATION = ["Adj", "Spu"]
EESS_systems = ["System_B", "System_D"]
DCMSS_systems = ["System_340km", "System_525km"]


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_cfg, yaml_backend = load_yaml(BASE_YAML_PATH)

    for sistema in DCMSS_systems:

        for mascara in MASK:

            for type_sim in TYPE_SIMULATION:

                for system_EESS in EESS_systems:

                    for lf in LOAD_FACTORS:

                        cfg = copy.deepcopy(base_cfg)

                        # ===== MSS =====
                        dc_mss = cfg["imt"]["topology"]["mss_dc"]
                        orbit = dc_mss["orbits"][0]

                        if sistema == "system_340km":
                            orbit["n_planes"] = 48
                            orbit["perigee_alt_km"] = 340
                            orbit["apogee_alt_km"] = 340
                            orbit["sats_per_plane"] = 110
                            orbit["phasing_deg"] = 1.636
                            dc_mss["beam_radius"] = 25803
                            cfg["imt"]["bs"]["height"] = 340000
                        else:
                            orbit["n_planes"] = 28
                            orbit["perigee_alt_km"] = 525
                            orbit["apogee_alt_km"] = 525
                            orbit["sats_per_plane"] = 120
                            orbit["phasing_deg"] = 1.5
                            dc_mss["beam_radius"] = 36712
                            cfg["imt"]["bs"]["height"] = 525000

                        # ===== Mask =====
                        if mascara == "DC_MSS":
                            cfg["imt"]["spectral_mask"] = "DC_MSS"
                            cfg["imt"].pop("spectral_mask_steps", None)
                        else:
                            cfg["imt"]["spectral_mask"] = "STEPPED"
                            cfg["imt"]["spectral_mask_steps"] = [
                                34.875334439154976,
                                16.87533443915498,
                                6.87533443915498
                            ]

                        # ===== Simulation type =====
                        cfg["imt"]["frequency"] = 2187.5 if type_sim == "Spu" else 2197.5

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

                        # ===== Output name =====
                        name = f"{sistema}_{system_EESS}_{mascara}_{type_sim}_lf_{lf}"
                        cfg["general"]["output_dir_prefix"] = name

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
