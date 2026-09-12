"""
Casos de sensibilidade da campanha 09_Guarulhos, em torno do caso de
referencia (BS a 20 m, downtilt 6 graus, arranjo 8x8), nas duas bandas.

Uso:
    python generate_inputs_sensitivity.py            # gera todos os casos, 3.65 e 6.475 GHz
    python generate_inputs_sensitivity.py --band 6g  # so uma banda
    python generate_inputs_sensitivity.py --cases arr roll   # so alguns grupos

Grupos (um fator varia por vez; o resto e o caso de referencia):
    arr    dimensao do arranjo da BS, potencia conduzida ajustada para EIRP constante
           3.65 GHz: 4x8 e 8x4 (34.95 dBm) | 6.475 GHz: 8x16 (30.9691 dBm)
    roll   rolagem da aeronave = faixa da elevacao do RA
           roll0: nadir fixo (-90) | roll10: -90..-80 | referencia ja e -90..-70
    level  voo nivelado sobre o centro da rede (x=y=0), altitudes em LEVEL_ALT_M
    load   probabilidade de carga da BS: 0.2 e 1.0 (referencia 0.5)
    k      feixes/UEs por BS: 1 e 8 (referencia 4)

Nomes (nao casam com a regex `array_(\\d+)_approach_` do plot_results4):
    input/<prefixo>input_sens_<caso>_<D>m_h20_dt6.yaml   (aproximacao)
    input/<prefixo>input_sens_level<alt>m_h20_dt6.yaml   (voo nivelado)
    output_dir_prefix = <prefixo>sens_<caso>_approach_<D>m_h20_dt6  ou  <prefixo>sens_level<alt>m_h20_dt6
"""

import argparse
import random
from copy import deepcopy

from generate_inputs import (
    BAND_CONFIG, DISTANCES_M, OUT_DIR,
    make_yaml, load_template, grid_center, place_aircraft, approach_xy_alt,
)

REF_BS_HEIGHT_M = 20
REF_DOWNTILT_DEG = 6

# dimensao do arranjo por banda: (nome, n_rows, n_columns, potencia conduzida dBm)
ARRAY_CASES = {
    "3.5g": [("arr4x8", 4, 8, 34.95), ("arr8x4", 8, 4, 34.95)],
    "6g": [("arr8x16", 8, 16, 30.9691)],
}
# rolagem: (nome, tipo, valores)
ROLL_CASES = [
    ("roll0", "FIXED", -90.0),
    ("roll10", "RANDOM_RANGE", (-90.0, -80.0)),
]
LEVEL_ALT_M = [100, 200, 300, 450, 600, 1000]
LOAD_CASES = [("load02", 0.2), ("load10", 1.0)]
K_CASES = [("k1", 1), ("k8", 8)]

ALL_GROUPS = ("arr", "roll", "level", "load", "k")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--band", choices=sorted(BAND_CONFIG), default=None,
                   help="so esta banda (padrao: as duas)")
    p.add_argument("--cases", nargs="+", choices=ALL_GROUPS, default=list(ALL_GROUPS),
                   help="grupos a gerar (padrao: todos)")
    return p.parse_args()


def set_roll(doc, kind, value):
    elev = doc["single_space_station"]["geometry"]["elevation"]
    for key in ("min", "max", "fixed"):
        if key in elev:
            del elev[key]
    elev["type"] = kind
    if kind == "FIXED":
        elev["fixed"] = float(value)
    else:
        elev["min"], elev["max"] = float(value[0]), float(value[1])


def reference_doc(data):
    doc = deepcopy(data)
    doc["imt"]["bs"]["height"] = REF_BS_HEIGHT_M
    doc["imt"]["bs"]["antenna"]["array"]["downtilt"] = REF_DOWNTILT_DEG
    return doc


def main():
    args = parse_args()
    bands = [args.band] if args.band else sorted(BAND_CONFIG)
    yaml = make_yaml()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0

    for band in bands:
        cfg = BAND_CONFIG[band]
        rng = random.Random(cfg["rng_seed"] + 1)   # distinto do sweep principal
        data = load_template(cfg, yaml)
        center = grid_center(data)
        prefix = cfg["prefix"]

        # (nome do caso, funcao que altera o doc, aproximacao? )
        variants = []
        if "arr" in args.cases:
            for name, n_rows, n_cols, power in ARRAY_CASES[band]:
                def f(doc, n_rows=n_rows, n_cols=n_cols, power=power):
                    arr = doc["imt"]["bs"]["antenna"]["array"]
                    arr["n_rows"], arr["n_columns"] = n_rows, n_cols
                    doc["imt"]["bs"]["conducted_power"] = power
                variants.append((name, f, True))
        if "roll" in args.cases:
            for name, kind, value in ROLL_CASES:
                variants.append((name, lambda doc, k=kind, v=value: set_roll(doc, k, v), True))
        if "load" in args.cases:
            for name, load in LOAD_CASES:
                variants.append((name, lambda doc, l=load: doc["imt"]["bs"].__setitem__("load_probability", l), True))
        if "k" in args.cases:
            for name, k in K_CASES:
                variants.append((name, lambda doc, k=k: doc["imt"]["ue"].__setitem__("k", k), True))
        if "level" in args.cases:
            for alt in LEVEL_ALT_M:
                variants.append((f"level{alt}m", None, False))

        for name, mutate, is_approach in variants:
            if is_approach:
                for s_m in DISTANCES_M:
                    doc = reference_doc(data)
                    mutate(doc)
                    x_m, y_m, h_m = approach_xy_alt(s_m)
                    place_aircraft(doc, x_m, y_m, h_m, center)
                    doc["general"]["seed"] = rng.randint(0, 1000)
                    doc["general"]["output_dir"] = "campaigns/09_Guarulhos/output_dl/"
                    doc["general"]["output_dir_prefix"] = (
                        f"{prefix}sens_{name}_approach_{int(s_m)}m_h{REF_BS_HEIGHT_M}_dt{REF_DOWNTILT_DEG}"
                    )
                    out = OUT_DIR / f"{prefix}input_sens_{name}_{int(s_m)}m_h{REF_BS_HEIGHT_M}_dt{REF_DOWNTILT_DEG}.yaml"
                    with out.open("w", encoding="utf-8") as fh:
                        yaml.dump(doc, fh)
                    total += 1
            else:
                alt = int(name[len("level"):-1])
                doc = reference_doc(data)
                place_aircraft(doc, 0.0, 0.0, float(alt), center)   # sobre o centro da rede
                doc["general"]["seed"] = rng.randint(0, 1000)
                doc["general"]["output_dir"] = "campaigns/09_Guarulhos/output_dl/"
                doc["general"]["output_dir_prefix"] = (
                    f"{prefix}sens_{name}_h{REF_BS_HEIGHT_M}_dt{REF_DOWNTILT_DEG}"
                )
                out = OUT_DIR / f"{prefix}input_sens_{name}_h{REF_BS_HEIGHT_M}_dt{REF_DOWNTILT_DEG}.yaml"
                with out.open("w", encoding="utf-8") as fh:
                    yaml.dump(doc, fh)
                total += 1

    print(f"OK! {total} arquivos de sensibilidade gerados em {OUT_DIR}")


if __name__ == "__main__":
    main()
