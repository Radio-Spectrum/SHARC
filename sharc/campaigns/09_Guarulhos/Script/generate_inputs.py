from pathlib import Path
from ruamel.yaml import YAML
from copy import deepcopy
import math
import random


# ===== Caminhos =====
BASE_YAML = Path(r"C:\Achiles\SHARC\sharc\campaigns\09_Guarulhos\Script\Base.yaml")
OUT_DIR   = Path(r"C:\Achiles\SHARC\sharc\campaigns\09_Guarulhos\input")

# ===== Parâmetros =====
N               = 15          # número de simulações
GLIDESLOPE_DEG  = 3.0         # rampa (graus)
START_DIST_M    = 30_000      # distância inicial até o CENTRO da pista (m)
APPROACH_SIGN   = -1          # +1 vindo do Leste; -1 do Oeste
x0, y0          = -2000.0, 10000.0    # offsets locais em metros

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
for n_array in [4,8]:
    data["imt"]["bs"]["antenna"]["array"]["n_rows"] = n_array
    for i in range(N):
        frac = i / (N - 1) if N > 1 else 0.0

        # Distância ao centro (m)
        s_m  = (1.0 - frac) * START_DIST_M
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
            doc["general"]["output_dir_prefix"] = f"FS_array_{n_array}_approach_{int(s_m)}m"

        # salva com nome pela distância
        out = OUT_DIR / f"input_FS_air_approach_array_{n_array}_{int(s_m)}m.yaml"
        with out.open("w", encoding="utf-8") as f:
            yaml.dump(doc, f)

print(f"OK! Gerados {N} arquivos em {OUT_DIR}")
