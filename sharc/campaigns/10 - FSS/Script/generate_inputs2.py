from pathlib import Path
from ruamel.yaml import YAML
from copy import deepcopy
import random

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

yaml = YAML(typ="rt")
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# ---- Carrega o template ----
data = yaml.load(BASE_YAML.read_text(encoding="utf-8"))

OUT_DIR.mkdir(parents=True, exist_ok=True)

total_files = 0

for env_name, env_cfg in ENVIRONMENTS.items():
    for n_array in [8, 16]:
        for sss_bandwidth in [36, 54]:
            # ---- gera cópia e edita parâmetros do cenário, array e banda ----
            doc = deepcopy(data)
            doc["imt"]["bs"]["antenna"]["array"]["n_columns"] = n_array
            doc["imt"]["bs"]["conducted_power"] = 33.997 if n_array == 8 else 30.9691
            doc["imt"]["bs"]["height"] = env_cfg["bs_height"]
            doc["imt"]["topology"]["macrocell_countries"]["cell_radius"] = env_cfg["cell_radius"]
            doc["imt"]["topology"]["macrocell_countries"]["dist_type"] = env_cfg["dist_type"]
            doc["imt"]["topology"]["macrocell_countries"]["height"] = env_cfg["bs_height"]
            doc["single_space_station"]["bandwidth"] = sss_bandwidth
            doc["imt"]["bandwidth"] = sss_bandwidth
            doc["single_space_station"]["param_p619"]["below_rooftop"] = env_cfg["below_rooftop"]
            doc["general"]["seed"] = random.randint(0, 1000)

            if "general" in doc and isinstance(doc["general"], dict):
                doc["general"]["output_dir_prefix"] = (
                    f"6G_{env_name}_array_{n_array}_sss_bw_{sss_bandwidth}"
                )

            out = OUT_DIR / f"6G_input_{env_name}_array_{n_array}_sss_bw_{sss_bandwidth}.yaml"
            with out.open("w", encoding="utf-8") as f:
                yaml.dump(doc, f)

            total_files += 1

print(f"OK! Gerados {total_files} arquivos em {OUT_DIR}")
