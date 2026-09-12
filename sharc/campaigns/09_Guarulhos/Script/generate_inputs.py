"""
Gera os YAMLs de entrada da campanha 09_Guarulhos (aviao em aproximacao).

Varre distancia ao centro da pista x altura da BS x downtilt, a partir de um
template por banda. Os caminhos sao relativos a este arquivo, entao o script
roda em qualquer maquina com o repositorio clonado.

Uso (a partir de qualquer pasta):
    python generate_inputs.py --band 6g            # 6.475 GHz  (Base_6GHz.yaml, prefixo 6G_)
    python generate_inputs.py --band 3.5g          # 3.65 GHz   (Base.yaml, sem prefixo)
    python generate_inputs.py --band 6g --clean    # apaga os .yaml ja existentes em input/ antes

Atencao: o runner (start_simulations_multi_thread.py) executa TODOS os .yaml
que estiverem em input/. Deixe la apenas o lote que quer rodar.

Todos os YAMLs saem com imt_dl_intra_sinr_calculation_disabled: true.

Nomes gerados (compativeis com plot_results4.py):
    input/<prefixo>input_air_approach_array_8_<D>m_h<H>_dt<T>.yaml
    output_dir_prefix = <prefixo>array_8_approach_<D>m_h<H>_dt<T>
"""

import argparse
import math
import random
import sys
from copy import deepcopy
from pathlib import Path

from ruamel.yaml import YAML

# ===== Caminhos (relativos ao repositorio) =====
HERE = Path(__file__).resolve().parent          # .../09_Guarulhos/Script
CAMPAIGN_DIR = HERE.parent                      # .../09_Guarulhos
OUT_DIR = CAMPAIGN_DIR / "input"

# ===== Configuracao por banda =====
# n_rows/n_columns: arranjo 8x8 em ambas as bandas (mesma dimensao para
# comparacao direta 3.65 vs 6.475 GHz). conducted_power=None mantem o valor
# do template. O seed do gerador e fixo por banda para os YAMLs serem
# reproduziveis em outra maquina.
BAND_CONFIG = {
    "3.5g": dict(
        template="Base.yaml",
        prefix="",
        n_rows=8,
        n_columns=8,
        conducted_power=31.94,   # dBm, 8x8 (valor usado na campanha de 3.65 GHz)
        rng_seed=3650,
    ),
    "6g": dict(
        template="Base_6GHz.yaml",
        prefix="6G_",
        n_rows=8,
        n_columns=8,
        conducted_power=None,    # usa o do template (33.97 dBm)
        rng_seed=6475,
    ),
}

# ===== Geometria da aproximacao =====
GLIDESLOPE_DEG = 3.0            # rampa (graus)
APPROACH_SIGN = -1              # +1 vindo do Leste; -1 do Oeste
X0_M, Y0_M = -2000.0, 10000.0   # offsets locais do centro da pista (m)

# Distancias ate o CENTRO da pista (m)
DISTANCES_M = [1000, 1500, 2000, 3000, 4000, 6000, 8000, 12000, 16000, 24000, 32000]

# Sweeps da estacao base
BS_HEIGHTS_M = [15, 20, 25, 30]        # imt.bs.height (m)
DOWNTILT_DEG_LIST = [0, 6, 10]         # imt.bs.antenna.array.downtilt (graus)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--band", required=True, choices=sorted(BAND_CONFIG),
                   help="banda IMT: 3.5g (3.65 GHz) ou 6g (6.475 GHz)")
    p.add_argument("--clean", action="store_true",
                   help="apaga todos os .yaml existentes em input/ antes de gerar")
    return p.parse_args()


def main():
    args = parse_args()
    cfg = BAND_CONFIG[args.band]
    rng = random.Random(cfg["rng_seed"])

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    template_path = HERE / cfg["template"]
    data = yaml.load(template_path.read_text(encoding="utf-8"))

    # ---- arranjo / potencia da BS ----
    arr = data["imt"]["bs"]["antenna"]["array"]
    arr["n_rows"] = cfg["n_rows"]
    arr["n_columns"] = cfg["n_columns"]
    if cfg["conducted_power"] is not None:
        data["imt"]["bs"]["conducted_power"] = cfg["conducted_power"]

    # ---- pula o SINR interno da rede IMT ----
    # A interferencia no RA nao depende do SINR BS<->UE; pular esse bloco
    # reduz o tempo por snapshot em ~5x (medido: 9.4 s -> 1.8 s). So deixam de
    # ser gravados os CSVs internos da IMT (imt_dl_sinr, imt_dl_tput, ...).
    imt = data["imt"]
    if "imt_dl_intra_sinr_calculation_disabled" not in imt:
        pos = list(imt.keys()).index("interfered_with") + 1
        imt.insert(pos, "imt_dl_intra_sinr_calculation_disabled", True,
                   comment="SINR interno da IMT nao entra no resultado do RA")
    else:
        imt["imt_dl_intra_sinr_calculation_disabled"] = True

    # ---- centro do grid (lido do template) ----
    geom = data["single_space_station"]["geometry"]
    lat0_deg = float(geom.get("es_lat_deg", 0.0))
    lon0_deg = float(geom.get("es_long_deg", 0.0))
    meters_per_deg_lat = 111_132.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0_deg))
    if meters_per_deg_lon <= 0:
        meters_per_deg_lon = 1.0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    existing = sorted(OUT_DIR.glob("*.yaml"))
    if args.clean:
        for f in existing:
            f.unlink()
        print(f"--clean: {len(existing)} arquivo(s) removido(s) de {OUT_DIR}")
    elif existing:
        print(f"AVISO: input/ ja contem {len(existing)} .yaml; o runner executa todos. "
              f"Use --clean se quiser so este lote.", file=sys.stderr)

    n_array = cfg["n_rows"]
    prefix = cfg["prefix"]
    total_files = 0

    for bs_height in BS_HEIGHTS_M:
        for s_m in DISTANCES_M:
            # altura do aviao na rampa
            h_m = math.tan(math.radians(GLIDESLOPE_DEG)) * s_m

            # posicao local (m) -> graus
            x_m = X0_M + APPROACH_SIGN * s_m
            y_m = Y0_M
            lon_i = lon0_deg + x_m / meters_per_deg_lon
            lat_i = lat0_deg + y_m / meters_per_deg_lat

            for downtilt_deg in DOWNTILT_DEG_LIST:
                doc = deepcopy(data)

                doc["imt"]["bs"]["height"] = bs_height
                doc["imt"]["bs"]["antenna"]["array"]["downtilt"] = downtilt_deg

                g = doc["single_space_station"]["geometry"]
                fx = g["location"]["fixed"]
                g["altitude"] = float(f"{h_m:.2f}")
                fx["lat_deg"] = float(f"{lat_i:.6f}")
                fx["long_deg"] = float(f"{lon_i:.6f}")

                doc["general"]["seed"] = rng.randint(0, 1000)
                doc["general"]["output_dir"] = "campaigns/09_Guarulhos/output_dl/"
                doc["general"]["output_dir_prefix"] = (
                    f"{prefix}array_{n_array}_approach_{int(s_m)}m_h{bs_height}_dt{downtilt_deg}"
                )

                out = OUT_DIR / (
                    f"{prefix}input_air_approach_array_{n_array}_{int(s_m)}m"
                    f"_h{bs_height}_dt{downtilt_deg}.yaml"
                )
                with out.open("w", encoding="utf-8") as f:
                    yaml.dump(doc, f)
                total_files += 1

    print(f"OK! Banda {args.band} ({cfg['template']}): {total_files} arquivos gerados em {OUT_DIR}")


if __name__ == "__main__":
    main()
