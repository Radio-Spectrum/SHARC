"""2o Monte Carlo da campanha 09_Guarulhos -> JSON compacto de quantis por configuracao e densidade."""
import os, re, json, math, glob, time
import numpy as np

OUT_DL = r"C:\Achiles\SHARC\sharc\campaigns\09_Guarulhos\output_dl"
OUT_JSON = os.path.join(os.path.dirname(__file__), "results.json")

N_BS_SNAP = 398          # hotspots por snapshot (7 clusters x 19 sites x 3 setores x 1)
AREA_KM2 = 2827.0        # 133 hexagonos com ISD 4954.6 m
RHO_SNAP = N_BS_SNAP / AREA_KM2
DENSITIES = [1.0, 2.5, 5.0, 10.0]           # BS/km2
K_OF = {rho: int(round(rho * AREA_KM2 / N_BS_SNAP)) for rho in DENSITIES}
N_TRIALS = 20000
SEED = 20260913
GLIDESLOPE_DEG = 3.0
# grade de excedencia (P[X > Q] = e)
E_GRID = np.concatenate([np.logspace(-4, -1, 61), np.linspace(0.1, 1.0, 46)[1:-1], [0.9999]])
E_GRID = np.unique(np.round(E_GRID, 6))

pat_main = re.compile(r"^(?P<b>6G_)?array_8_approach_(?P<d>\d+)m_h(?P<h>\d+)_dt(?P<t>\d+)_")
pat_sens = re.compile(r"^(?P<b>6G_)?sens_(?P<case>[a-z]+[0-9x]*)_approach_(?P<d>\d+)m_h(?P<h>\d+)_dt(?P<t>\d+)_")
pat_lvl = re.compile(r"^(?P<b>6G_)?sens_level(?P<alt>\d+)m_h(?P<h>\d+)_dt(?P<t>\d+)_")

def load_samples(folder):
    f = os.path.join(folder, "system_dl_interf_power_per_mhz.csv")
    x = np.loadtxt(f, skiprows=1)
    return x[np.isfinite(x)]

def quantiles(x_dbm_agg):
    return np.round(np.percentile(x_dbm_agg, 100.0 * (1.0 - E_GRID)), 2).tolist()

def second_mc(x_dbm, k, rng):
    x_mw = 10.0 ** (x_dbm / 10.0)
    draws = rng.choice(x_mw, size=(N_TRIALS, k), replace=True)
    return 10.0 * np.log10(draws.sum(axis=1))

def parse(name):
    m = pat_main.match(name)
    if m:
        d = int(m["d"]); return dict(group="main", case="ref", dist_m=d, alt_m=round(math.tan(math.radians(GLIDESLOPE_DEG))*d, 2), h=int(m["h"]), dt=int(m["t"]), band="6.475" if m["b"] else "3.65")
    m = pat_lvl.match(name)
    if m:
        return dict(group="level", case="level", dist_m=None, alt_m=float(m["alt"]), h=int(m["h"]), dt=int(m["t"]), band="6.475" if m["b"] else "3.65")
    m = pat_sens.match(name)
    if m:
        case = m["case"]; grp = re.match(r"[a-z]+", case).group(0)
        d = int(m["d"]); return dict(group=grp, case=case, dist_m=d, alt_m=round(math.tan(math.radians(GLIDESLOPE_DEG))*d, 2), h=int(m["h"]), dt=int(m["t"]), band="6.475" if m["b"] else "3.65")
    return None

t0 = time.time()
rng = np.random.default_rng(SEED)
records = []
raw = {}   # id -> samples (para o cenario misto)
folders = sorted(glob.glob(os.path.join(OUT_DL, "*")))
for fo in folders:
    name = os.path.basename(fo)
    meta = parse(name)
    if meta is None:
        print("ignorado:", name); continue
    x = load_samples(fo)
    rid = name.split("_2026-")[0]
    meta["id"] = rid; meta["n_snap"] = int(x.size)
    q = {"snap": quantiles(x)}
    for rho in DENSITIES:
        q[str(rho)] = quantiles(second_mc(x, K_OF[rho], rng))
    meta["q"] = q
    records.append(meta)
    raw[rid] = x

# cenario misto: soma das duas bandas na mesma configuracao (main sweep e sensibilidades pareadas)
by_key = {}
for r in records:
    key = (r["group"], r["case"], r["dist_m"], r["alt_m"], r["h"], r["dt"])
    by_key.setdefault(key, {})[r["band"]] = r
n_mix = 0
for key, bands in by_key.items():
    if "3.65" in bands and "6.475" in bands:
        a = raw[bands["3.65"]["id"]]; b = raw[bands["6.475"]["id"]]
        q = {}
        for rho in DENSITIES:
            k = K_OF[rho]
            sa = 10.0 ** (a / 10.0); sb = 10.0 ** (b / 10.0)
            # filtro do RA e aplicado por banda no JS; aqui guardamos as duas somas separadas
            agg_a = rng.choice(sa, size=(N_TRIALS, k), replace=True).sum(axis=1)
            agg_b = rng.choice(sb, size=(N_TRIALS, k), replace=True).sum(axis=1)
            q[str(rho)] = {"a": quantiles(10*np.log10(agg_a)), "b": quantiles(10*np.log10(agg_b)),
                           # soma com filtro do RA ja aplicado (-4.85 dB e -13.4 dB) e sem filtro
                           "mix_f": quantiles(10*np.log10(agg_a*10**(-0.485) + agg_b*10**(-1.34))),
                           "mix_nf": quantiles(10*np.log10(agg_a + agg_b))}
        g, case, d, alt, h, dt = key
        records.append(dict(group=g, case=case, dist_m=d, alt_m=alt, h=h, dt=dt, band="mix", id=f"mix_{bands['3.65']['id']}", n_snap=None, q=q))
        n_mix += 1

meta = dict(n_bs_snapshot=N_BS_SNAP, area_km2=AREA_KM2, rho_snapshot=round(RHO_SNAP, 4), densities=DENSITIES, k_of={str(k): v for k, v in K_OF.items()},
            n_trials=N_TRIALS, seed=SEED, e_grid=E_GRID.tolist(), glideslope_deg=GLIDESLOPE_DEG,
            ra_filter_db={"3.65": -4.85, "6.475": -13.4},
            itm={"UC1": {"alt_ft": [200, 1000, 5000, 7500], "psd": [-39, -46, -54, -54]},
                 "UC2": {"alt_ft": [200, 1000, 2000], "psd": [-76, -86, -94]},
                 "UC3": {"alt_ft": [200, 1000, 2000], "psd": [-68, -86, -94]}},
            n_records=len(records), n_mix=n_mix)
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump({"meta": meta, "records": records}, f, separators=(",", ":"))
print(f"{len(records)} registros ({n_mix} mistos) em {time.time()-t0:.0f} s -> {OUT_JSON} ({os.path.getsize(OUT_JSON)/1e6:.1f} MB)")
from collections import Counter
print(Counter((r['band'], r['group']) for r in records))
