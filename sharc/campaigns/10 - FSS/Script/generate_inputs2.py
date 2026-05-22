from pathlib import Path
from ruamel.yaml import YAML
from copy import deepcopy
import math
import random
import numpy as np

# ===== Caminhos =====
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_YAML = SCRIPT_DIR / "Base_6GHz.yaml"
OUT_DIR = SCRIPT_DIR.parent / "input"

# ===== Cenários =====
ENVIRONMENTS = {
    "urban": {
        "dist_type": "Urban",
        "cell_radius": 400.0,
        "bs_height": 18.0,
        "below_rooftop": 65.0,
    },
    "suburban": {
        "dist_type": "Suburban",
        "cell_radius": 800.0,
        "bs_height": 20.0,
        "below_rooftop": 15.0,
    },
}

POPULATION_VARIANTS = {
    "": None,
    #"_uniform": None,
}

SSS_LONGITUDES = np.linspace(-150, -15, 11).tolist()

REFERENCE_BANDWIDTH_MHZ = 200.0
ARRAY_POWER_200MHZ = [
    #(8, 33.997),
    (16, 30.9691),
]


def scale_conducted_power_dbm(power_200mhz_dbm, bandwidth_mhz):
    return power_200mhz_dbm + 10.0 * math.log10(bandwidth_mhz / REFERENCE_BANDWIDTH_MHZ)


def longitude_label(longitude_deg):
    return f"m{abs(longitude_deg)}" if longitude_deg < 0 else f"p{longitude_deg}"


yaml = YAML(typ="rt")
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# ---- Carrega o template ----
data = yaml.load(BASE_YAML.read_text(encoding="utf-8"))

OUT_DIR.mkdir(parents=True, exist_ok=True)

total_files = 0

for env_name, env_cfg in ENVIRONMENTS.items():
    for population_suffix, population_raster in POPULATION_VARIANTS.items():
        scenario_name = f"{env_name}{population_suffix}"
        for n_array, conducted_power_200mhz in ARRAY_POWER_200MHZ:
            for sss_bandwidth in [54]:
                for sss_longitude in SSS_LONGITUDES:
                    # ---- gera cópia e edita parâmetros do cenário, array, banda e longitude ----
                    doc = deepcopy(data)
                    doc["imt"]["bs"]["antenna"]["array"]["n_columns"] = n_array
                    doc["imt"]["bs"]["conducted_power"] = scale_conducted_power_dbm(
                        conducted_power_200mhz,
                        sss_bandwidth,
                    )
                    doc["imt"]["bs"]["height"] = env_cfg["bs_height"]
                    doc["imt"]["topology"]["macrocell_countries"]["cell_radius"] = env_cfg["cell_radius"]
                    doc["imt"]["topology"]["macrocell_countries"]["dist_type"] = env_cfg["dist_type"]
                    doc["imt"]["topology"]["macrocell_countries"]["height"] = env_cfg["bs_height"]
                    if population_suffix:
                        doc["imt"]["topology"]["macrocell_countries"]["population_raster"] = population_raster
                    doc["single_space_station"]["bandwidth"] = sss_bandwidth
                    doc["single_space_station"]["geometry"]["location"]["fixed"]["long_deg"] = sss_longitude
                    doc["imt"]["bandwidth"] = sss_bandwidth
                    doc["single_space_station"]["param_p619"]["below_rooftop"] = env_cfg["below_rooftop"]
                    doc["general"]["seed"] = random.randint(0, 1000)

                    sss_longitude_label = longitude_label(sss_longitude)
                    if "general" in doc and isinstance(doc["general"], dict):
                        doc["general"]["output_dir_prefix"] = (
                            f"6G_{scenario_name}_array_{n_array}_sss_bw_{sss_bandwidth}_sss_lon_{sss_longitude_label}"
                        )

                    out = OUT_DIR / (
                        f"6G_input_{scenario_name}_array_{n_array}_sss_bw_{sss_bandwidth}_"
                        f"sss_lon_{sss_longitude_label}.yaml"
                    )
                    with out.open("w", encoding="utf-8") as f:
                        yaml.dump(doc, f)

                    total_files += 1

print(f"OK! Gerados {total_files} arquivos em {OUT_DIR}")
