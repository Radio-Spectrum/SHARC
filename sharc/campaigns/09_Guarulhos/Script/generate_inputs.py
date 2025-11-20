from pathlib import Path
from ruamel.yaml import YAML
from copy import deepcopy
import math
import random

# ===== Caminhos =====
BASE_YAML = Path(r"C:\Achiles\SHARC\sharc\campaigns\09_Guarulhos\Script\Base.yaml")
OUT_DIR   = Path(r"C:\Achiles\SHARC\sharc\campaigns\09_Guarulhos\input")

# ===== Parâmetros =====
GLIDESLOPE_DEG  = 3.0         # rampa (graus)
APPROACH_SIGN   = -1          # +1 vindo do Leste; -1 do Oeste
x0, y0          = -2000.0, 10000.0    # offsets locais em metros

# >>> AQUI: vetor de distâncias até o CENTRO da pista (m)
DISTANCES_M = [
    1000,
    2000,
    6000,
    10000,
    15000,
    20000,
    25000,
    30000,
]

yaml = YAML(typ="rt")
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# ---- Carrega o template ----
data = yaml.load(BASE_YAML.read_text(encoding="utf-8"))

# Acessos conforme o Base.yaml
sss   = data["single_space_station"]
geom  = sss["geometry"]
loc   = geom["location"]
fixed = loc["fixed"]

# ===== Centro do grid (lido do YAML) =====
lat0_deg = float(geom.get("es_lat_deg", 0.0))
lon0_deg = float(geom.get("es_long_deg", 0.0))

# ===== Conversões esféricas =====
meters_per_deg_lat = 111_132.0
meters_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0_deg))
if meters_per_deg_lon <= 0:
    meters_per_deg_lon = 1.0

OUT_DIR.mkdir(parents=True, exist_ok=True)

total_files = 0

for n_array in [4, 8]:
    data["imt"]["bs"]["antenna"]["array"]["n_rows"] = n_array

    # loop direto nas distâncias
    for s_m in DISTANCES_M:
        # altura na rampa
        h_m  = math.tan(math.radians(GLIDESLOPE_DEG)) * s_m

        # posição local em metros
        x_m = x0 + APPROACH_SIGN * s_m
        y_m = y0

        # conversão em graus
        dlon = x_m / meters_per_deg_lon
        dlat = y_m / meters_per_deg_lat

        lon_i = lon0_deg + dlon
        lat_i = lat0_deg + dlat

        # ---- gera cópia e edita ----
        doc = deepcopy(data)

        g   = doc["single_space_station"]["geometry"]
        fx  = g["location"]["fixed"]

        g["altitude"]   = float(f"{h_m:.2f}")
        fx["lat_deg"]   = float(f"{lat_i:.6f}")
        fx["long_deg"]  = float(f"{lon_i:.6f}")
        num = random.randint(0, 1000)
        doc["general"]["seed"] = num

        # muda também o prefixo
        if "general" in doc and isinstance(doc["general"], dict):
            doc["general"]["output_dir_prefix"] = f"array_{n_array}_approach_{int(s_m)}m"

        # salva com nome pela distância
        out = OUT_DIR / f"input_air_approach_array_{n_array}_{int(s_m)}m.yaml"
        with out.open("w", encoding="utf-8") as f:
            yaml.dump(doc, f)

        total_files += 1

print(f"OK! Gerados {total_files} arquivos em {OUT_DIR}")
