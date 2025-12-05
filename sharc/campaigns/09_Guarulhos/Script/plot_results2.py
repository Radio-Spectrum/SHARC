"""
Post-processing IMT HIBS RAS 2600 MHz.

- Plots CCDF "originais" por arquivo (via PostProcessor)
- 1º Monte Carlo por arquivo (dl_interf_power_mc_sum_dBm)
- 2º Monte Carlo MISTO (3G + 6G) POR DISTÂNCIA (e N)

- Depois: % de casos que violam ITM e plot Altitude(ft) × % de violações
"""

import os
from pathlib import Path
import re
import numpy as np
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


from sharc.results import Results
from sharc.post_processor import PostProcessor

# =========================
# Configuração da Campanha
# =========================

MC_ATTR_IN    = "system_dl_interf_power_per_mhz"   # dBm/MHz
MC_ATTR_OUT   = "dl_interf_power_mc_sum_dBm"       # 1º MC
MC_N_SAMPLES  = 10000
MC_SEED       = 200
DB_PER_100MHZ = 15  # (20 - 5) dB

# 2º MC
MC_K_MIXED = {
    '':    int(30000 / (57 * 3)),
    '6G_': int(30000 / (57 * 3)),
}

MC2_3G_ATTR  = "dl_interf_power_mc2_3g_dBm"
MC2_6G_ATTR  = "dl_interf_power_mc2_6g_dBm"
MC2_MIX_ATTR = "dl_interf_power_mc2_mix_dBm"

# Grupos
n_array      = [4, 8, 16]
propag       = ['']   #, "6G_"
#distances_km = [1000, 2000, 10000, 15000, 25000, 35000, 40000]
#distances_km = [1000, 2000, 4000, 6000, 10000, 12000, 15000, 16000, 17000, 20000, 22000, 25000, 27000, 32000, 35000, 40000]
distances_km = [1000, 2000, 4000, 8000, 16000, 32000]
cutoff_percentage = 0.001
shift_scale       = 0.0
legenda_dens_potencia = "dBm"

# =======================
# PostProcessor básico
# =======================

post_processor = PostProcessor()
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO[MC_ATTR_IN]["x_label"] = legenda_dens_potencia

# =======================
# Construção de padrões
# =======================

combinations = [
    (b, a, s)
    for b in sorted(propag)
    for a in sorted(n_array)
    for s in sorted(distances_km)
]

PATTERN_TO_LEGEND = {}
valid_patterns    = []

for b, a, s in combinations:
    alt = np.round(s * np.tan(np.deg2rad(3)))
    s1 = s / 1000
    if b == "6G_":
        legend = f"6,5 GHz - N={a} x 8 - d={int(s1):02d} km - alt={int(alt):03d}m"
        pattern = f"{b}array_{a}_approach_{s}m"
    else:
        legend = f"3,65 GHz - N={a} x 8 - d={int(s1):02d} km - alt={int(alt):03d}m"
        pattern = f"{b}array_{a}_approach_{s}m"

    post_processor.add_plot_legend_pattern(
        dir_name_contains=pattern,
        legend=legend
    )

    PATTERN_TO_LEGEND[pattern] = legend
    valid_patterns.append(pattern)

# Regex para extrair parâmetros
_pat = re.compile(r'(6G_)?array_(\d+)_approach_(\d+)m')

def _sort_key(res):
    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))
    m = _pat.search(base)
    if not m:
        return (99, 99, 10**12)
    prop  = m.group(1) or ""
    N     = int(m.group(2))
    dist  = int(m.group(3))
    rank  = {"": 0, "6G_": 1}.get(prop, 9)
    return (rank, N, dist)

# ==================================
# Carregar resultados da campanha
# ==================================

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

def filter_fn(dir_path: str) -> bool:
    base = os.path.basename(dir_path)
    return any(base.startswith(pattern) for pattern in valid_patterns)

many_results = Results.load_many_from_dir(
    os.path.join(campaign_base_dir, "output_dl"),
    only_latest=True,
    only_samples=[
        "system_dl_interf_power_per_mhz",
    ],
    filter_fn=filter_fn,
)

many_results.sort(key=_sort_key)
post_processor.add_results(many_results)

for plot in post_processor.plots:
    plot.show()

# ==========================================================
# 1º Monte Carlo
# ==========================================================

def mc_sum_dBm_per_file(x_dBm, k, n_trials, seed=MC_SEED):
    x = np.asarray(x_dBm, float)
    x = x[np.isfinite(x)]
    if x.size == 0 or k <= 0 or n_trials <= 0:
        return np.array([])

    x_mW = 10 ** (x / 10)
    rng  = np.random.default_rng(seed)
    draws = rng.choice(x_mW, size=(n_trials, k), replace=True)
    sums  = draws.sum(axis=1)
    return 10 * np.log10(sums)

MC_K_original = int(round(30000 / (57 * 3)))

for res in many_results:
    x = getattr(res, MC_ATTR_IN, None)
    if x is None:
        continue
    out = mc_sum_dBm_per_file(x, MC_K_original, MC_N_SAMPLES)
    setattr(res, MC_ATTR_OUT, out)

# =============================================================
# Função CCDF
# =============================================================

def ccdf(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.array([]), np.array([])
    xs = np.sort(x)
    n  = xs.size
    y  = 1.0 - (np.arange(1, n + 1) / (n + 1))
    return xs, y

# =============================================================
# 1) Plot CCDF – 3G sólido, 6G tracejado
# =============================================================

plt.figure()

for res in many_results:
    x = getattr(res, MC_ATTR_OUT, None)
    if x is None:
        continue

    x = np.asarray(x, float)
    if x.size == 0:
        continue

    xs, ys = ccdf(x)
    xs = xs + DB_PER_100MHZ

    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))

    label = next(
        (p["legend"]
         for p in post_processor.plot_legend_patterns
         if p["dir_name_contains"] in base),
        base
    )

    linestyle = "--" if "N=8" in label else "-"
    if '1 km' in label:
        color_line = 'blue'
    elif '2 km' in label:
        color_line = 'red'
    elif '4 km' in label:
        color_line = 'green'
    elif '8 km' in label:
        color_line = 'cyan'
    elif '16 km' in label:
        color_line = 'moccasin'
    elif '32 km' in label:
        color_line = 'yellow'


    plt.plot(xs, ys, label=label, linestyle=linestyle, color=color_line)
# Limites ITM piores (mais restritivos)
itm_worst_limits_dBmMHz = {
    "Cat 1": -58,
    "Cat 2&3": -93,
}

# Converter para dBm/100MHz (soma 20 dB)
itm_worst_limits_dBm100MHz = {
    cat: val + 20 for cat, val in itm_worst_limits_dBmMHz.items()
}

for cat, lim in itm_worst_limits_dBm100MHz.items():
    plt.axvline(lim, color="red", linestyle=":", linewidth=2)
    plt.text(
        lim, 1e-3,  # posição do texto no gráfico
        f"{cat}: {lim:.1f} dBm/100MHz",
        rotation=90,
        color="red",
        verticalalignment="bottom",
        fontsize=12
    )

plt.yscale("log")
plt.xlabel("Power (dBm/100 MHz)")
plt.ylabel("CCDF")
plt.ylim(1e-3,1)
plt.grid(True, which="both", ls="--", alpha=0.4)
plt.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
plt.tight_layout()
plt.show()

# =============================================================
# 2) % de violações ITM — 3 gráficos (um por categoria)
#     e várias curvas (uma por cenário/label) em cada gráfico
# =============================================================
# =============================================================
# 2) % de violações ITM — 3 gráficos (um por categoria)
#     e curvas 3G N=8, 6G N=8 (distâncias viram os pontos da curva)
# =============================================================

ITM_LIMITS = {
    1: { "alt_ft": np.array([10,200,1000,5000, 30000]),
         "psd_dBm_MHz": np.array([-39,-39,-46,-53, -53]) },

    2: { "alt_ft": np.array([10,200,1000,2000, 30000]),
         "psd_dBm_MHz": np.array([-76,-76,-86,-94, -94]) },

    3: { "alt_ft": np.array([10,100,1000, 2000, 30000]),
         "psd_dBm_MHz": np.array([-67,-67,-86, -94, -94]) },
}

def itm_limit_psd(category: int, alt_ft: float) -> float:
    data = ITM_LIMITS[category]
    alt  = data["alt_ft"]
    psd  = data["psd_dBm_MHz"]

    # abaixo da faixa → valor constante
    if alt_ft <= alt[0]:
        return float(psd[0])

    # acima da faixa → valor constante
    if alt_ft >= alt[-1]:
        return float(psd[-1])

    # dentro da faixa → encontrar os 2 pontos que cercam a altitude
    for i in range(len(alt) - 1):
        alt_low = alt[i]
        alt_high = alt[i + 1]

        if alt_low <= alt_ft <= alt_high:
            psd_low = psd[i]
            psd_high = psd[i + 1]

            # interpolação linear manual:
            # y = y0 + (y1 - y0) * (x - x0)/(x1 - x0)
            return float(
                psd_low +
                (psd_high - psd_low) * (alt_ft - alt_low) / (alt_high - alt_low)
            )

    # fallback (não deve acontecer)
    return float(psd[-1])

from collections import defaultdict

# viol_by_cat[cat][family_label] = lista de (alt_ft, pct_viol)
# onde family_label é algo como "3G - N=8" ou "6G - N=8"
viol_by_cat = {
    1: defaultdict(list),
    2: defaultdict(list),
    3: defaultdict(list),
}

for res in many_results:
    x = getattr(res, MC_ATTR_OUT, None)
    if x is None:
        continue
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        continue

    # base do diretório (para altitude e label)
    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))

    # distância -> altitude (3 graus)
    m = _pat.search(base)
    if not m:
        continue
    dist_m = float(m.group(3))
    alt_m  = dist_m * np.tan(np.deg2rad(3.0))
    alt_ft = alt_m * 3.28084

    # legenda completa (igual da CCDF)
    full_label = next(
        (p["legend"]
         for p in post_processor.plot_legend_patterns
         if p["dir_name_contains"] in base),
        base or "Resultado"
    )

    # "família" = tira a parte do d=xxxxm e alt=...
    # Ex.: "3G - N=8 d=01000m - alt=52.0" -> "3G - N=8"
    family_label = full_label.split(" d=")[0].strip()

    # calcula % de violação para cada categoria e guarda por família
    for cat in (1, 2, 3):
        limite = itm_limit_psd(cat, alt_ft)        # dBm/MHz
        pct_viol = 100.0 * np.mean(x > limite)     # %

        viol_by_cat[cat][family_label].append((alt_ft, pct_viol))

# -------------------------------------------------------------
# Plots: 3 figuras, uma para cada categoria ITM
#   – cada figura: curvas "3G - N=8", "6G - N=8", etc.
# -------------------------------------------------------------

for cat in (1, 2, 3):
    plt.figure(figsize=(9, 6))

    for family_label, pairs in viol_by_cat[cat].items():
        pairs = np.asarray(pairs, float)   # shape (n, 2) -> [alt_ft, pct]
        if pairs.size == 0:
            continue

        alts = pairs[:, 0]
        pcts = pairs[:, 1]

        # ordenar por altitude para a curva ficar organizada
        order = np.argsort(alts)
        alts = alts[order]
        pcts = pcts[order]

        # 6G tracejado, 3G linha cheia (opcional)
        linestyle = "--" if "6,5 G" in family_label else "-"

        plt.plot(np.array(distances_km) / 1000, pcts, linestyle=linestyle, marker="o", label=family_label)

    plt.xscale("log")
    ticks = [1, 5, 10, 20, 40]
    plt.xticks(ticks)            # set tick positions manually
    plt.gca().xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
    plt.grid(True, which="both", ls="--", alpha=0.4)
    plt.xlabel("Distance (km)")
    plt.ylabel("% de Violações")
    plt.title(f"Porcentagem de Casos que Violam o Limite ITM – Categoria {cat}")
    plt.legend()
    plt.tight_layout()
    plt.show()



# =============================================================
# 3) MONTE CARLO MISTO POR DISTÂNCIA (junta tudo num vetor)
#    – para cada distância:
#        * constrói um pool 3G e um pool 6G
#        * cada pool tem participação igual de cada N_array
#        * em cada trial: soma MC_K_MIXED[''] amostras 3G
#                          + MC_K_MIXED['6G_'] amostras 6G
# =============================================================

print("\n=== Monte Carlo misto por distância (3G+6G, pools balanceados em N_array) ===")

rng = np.random.default_rng(MC_SEED + 2025)

# -------------------------------------------------------------
# 3.1) Agrupar amostras por (distância, propagador, N_array)
#      groups[dist_m][prop_key][N] = vetor 1D com todas as amostras dBm
# -------------------------------------------------------------
groups = {}
for dist_m in distances_km:
    groups[dist_m] = {
        "3G": {N: [] for N in n_array},
        "6G": {N: [] for N in n_array},
    }

for res in many_results:
    x = getattr(res, MC_ATTR_IN, None)
    if x is None:
        continue
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        continue

    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))
    m = _pat.search(base)
    if not m:
        continue

    prop_tag = m.group(1) or ""        # "" ou "6G_"
    N_val    = int(m.group(2))
    dist_m   = int(m.group(3))

    if dist_m not in groups:
        continue
    if N_val not in groups[dist_m]["3G"]:  # garante que N está em n_array
        continue

    prop_key = "6G" if prop_tag == "6G_" else "3G"

    groups[dist_m][prop_key][N_val].append(x)

# -------------------------------------------------------------
# 3.2) Para cada distância, construir pools 3G e 6G:
#      pool_3G[dist], pool_6G[dist] (em mW)
#      – balanceando número de amostras por N_array
# -------------------------------------------------------------
pools_mW = {dist_m: {"3G": None, "6G": None} for dist_m in distances_km}

for dist_m in distances_km:
    for prop_key, mc_key in [("3G", ""), ("6G", "6G_")]:

        # junta todos os vetores por N, se existirem
        per_N = {}
        for N_val in n_array:
            vecs = groups[dist_m][prop_key].get(N_val, [])
            if not vecs:
                continue
            per_N[N_val] = np.concatenate(vecs)

        if not per_N:
            continue  # não há cenários desse tipo nessa distância

        # queremos equalizar o número de amostras para cada N
        # escolhemos um tamanho-alvo por N (pode ser grande, pois sorteamos com replace)
        target_per_N = MC_N_SAMPLES  # por exemplo, 10000 amostras de cada N

        pooled_list = []
        for N_val, vec_dBm in per_N.items():
            # sorteia target_per_N amostras (com reposição)
            chosen = rng.choice(vec_dBm, size=target_per_N, replace=True)
            pooled_list.append(chosen)

        pooled_dBm = np.concatenate(pooled_list)
        pooled_mW  = 10.0 ** (pooled_dBm / 10.0)
        pools_mW[dist_m][prop_key] = pooled_mW

# -------------------------------------------------------------
# 3.3) Monte Carlo por distância usando apenas os pools (vetores)
# -------------------------------------------------------------
ccdf_mixed_by_dist = {}

for dist_m in sorted(distances_km):
    pool_3g = pools_mW[dist_m]["3G"]
    pool_6g = pools_mW[dist_m]["6G"]

    if pool_3g is None and pool_6g is None:
        print(f"[AVISO] Nenhum pool para distância {dist_m} m.")
        continue

    samples_sum_mW = []

    for _ in range(MC_N_SAMPLES):
        total_mW = 0.0

        # 3G: pega MC_K_MIXED[''] amostras do pool 3G
        if pool_3g is not None and MC_K_MIXED[''] > 0:
            draws_3g = rng.choice(pool_3g, size=MC_K_MIXED[''], replace=True)
            total_mW += draws_3g.sum()

        # 6G: pega MC_K_MIXED['6G_'] amostras do pool 6G
        if pool_6g is not None and MC_K_MIXED['6G_'] > 0:
            draws_6g = rng.choice(pool_6g, size=MC_K_MIXED['6G_'], replace=True)
            total_mW += draws_6g.sum()

        if total_mW > 0:
            samples_sum_mW.append(total_mW)

    samples_sum_mW = np.asarray(samples_sum_mW, float)
    if samples_sum_mW.size == 0:
        print(f"[AVISO] Nenhuma amostra válida para distância {dist_m} m.")
        continue

    samples_dBm_100MHz = 10 * np.log10(samples_sum_mW) + DB_PER_100MHZ
    xs, ys = ccdf(samples_dBm_100MHz)
    ccdf_mixed_by_dist[dist_m] = (xs, ys)

# -------------------------------------------------------------
# 3.4) Plot: CCDF do Monte Carlo misto para cada distância
# -------------------------------------------------------------
plt.figure(figsize=(10, 6))

for dist_m, (xs, ys) in sorted(ccdf_mixed_by_dist.items()):
    label = f"d = {dist_m/1000:.1f} km"
    plt.plot(xs, ys, label=label)
for cat, lim in itm_worst_limits_dBm100MHz.items():
    plt.axvline(lim, color="red", linestyle=":", linewidth=2)
    plt.text(
        lim, 1e-3,  # posição do texto no gráfico
        f"{cat}: {lim:.1f} dBm/100MHz",
        rotation=90,
        color="red",
        verticalalignment="bottom",
        fontsize=12
    )
plt.yscale("log")
plt.ylim(1e-3,1)
plt.grid(True, which="both", ls="--", alpha=0.4)
plt.xlabel("Power (dBm/100 MHz)")
plt.ylabel("CCDF")
plt.title("CCDF por Distância com o agregado das BSs (3,65 GHz + 6,5 GHz)")
plt.legend()
plt.tight_layout()
plt.show()

# =============================================================
# 4) Gráfico de violação (MC misto) para TODAS as categorias ITM
#     – eixo x: altitude (ft)
#     – eixo y: % de amostras que violam o limite ITM
# =============================================================

print("\n=== Violação ITM usando Monte Carlo misto (pools 3G+6G) ===")

rng_viol = np.random.default_rng(MC_SEED + 4242)

viol_mixed_by_cat = {
    1: {"alt_ft": [], "pct": []},
    2: {"alt_ft": [], "pct": []},
    3: {"alt_ft": [], "pct": []},
}

for dist_m in sorted(distances_km):
    pool_3g = pools_mW.get(dist_m, {}).get("3G", None)
    pool_6g = pools_mW.get(dist_m, {}).get("6G", None)

    if pool_3g is None and pool_6g is None:
        print(f"[AVISO] Sem pools válidos para distância {dist_m} m.")
        continue

    # distância -> altitude
    alt_m  = dist_m * np.tan(np.deg2rad(3.0))
    alt_ft = alt_m * 3.28084

    # Monte Carlo misto para essa distância (em dBm/MHz)
    samples_dBm_MHz = []

    for _ in range(MC_N_SAMPLES):
        total_mW = 0.0

        # 3G
        if pool_3g is not None and MC_K_MIXED[''] > 0:
            draws_3g = rng_viol.choice(pool_3g, size=MC_K_MIXED[''], replace=True)
            total_mW += draws_3g.sum()

        # 6G
        if pool_6g is not None and MC_K_MIXED['6G_'] > 0:
            draws_6g = rng_viol.choice(pool_6g, size=MC_K_MIXED['6G_'], replace=True)
            total_mW += draws_6g.sum()

        if total_mW <= 0.0:
            continue

        # aqui ainda é dBm/MHz (sem offset de 100 MHz)
        p_dBm_MHz = 10.0 * np.log10(total_mW)
        samples_dBm_MHz.append(p_dBm_MHz)

    samples_dBm_MHz = np.asarray(samples_dBm_MHz, float)
    if samples_dBm_MHz.size == 0:
        print(f"[AVISO] Nenhuma amostra válida em dBm/MHz para dist {dist_m} m.")
        continue

    # Calcula % de violação por categoria para essa altitude
    for cat in (1, 2, 3):
        lim = itm_limit_psd(cat, alt_ft)  # limite em dBm/MHz
        pct_viol = 100.0 * np.mean(samples_dBm_MHz > lim)
        viol_mixed_by_cat[cat]["alt_ft"].append(alt_ft)
        viol_mixed_by_cat[cat]["pct"].append(pct_viol)

# -------------------------------------------------------------
# Plot: 3 curvas (uma por categoria) vs altitude
# -------------------------------------------------------------
plt.figure(figsize=(9, 6))

for cat, color, label_txt in [
    (1, "tab:red",   "Categoria 1"),
    (2, "tab:green", "Categoria 2"),
    (3, "tab:blue",  "Categoria 3"),
]:
    alts = np.asarray(viol_mixed_by_cat[cat]["alt_ft"], float)
    pcts = np.asarray(viol_mixed_by_cat[cat]["pct"], float)
    if alts.size == 0:
        continue

    order = np.argsort(alts)
    alts = alts[order]
    pcts = pcts[order]

    plt.plot(np.array(distances_km) / 1000, pcts, "-o", label=label_txt, color=color)

plt.xscale("log")
ticks = [1, 5, 10, 20, 40]
plt.xticks(ticks)            # set tick positions manually
plt.gca().xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
plt.grid(True, which="both", ls="--", alpha=0.4)
plt.xlabel("Distância (km)")
plt.ylabel("% de Violações")
plt.title("Probabilidade de Violação do Critério com o agregado das BSs (3,65 GHz + 6,5 GHz)")
plt.legend()
plt.tight_layout()
plt.show()


# =============================================================
# 5) Figura de Margens ITM (PSD x Altitude) para Cat 1, 2 e 3
#     – estilo similar à figura de referência
#     – eixo x: altitude em metros (escala log)
#     – eixo y: PSD limite (dBm/MHz)
# =============================================================

plt.figure(figsize=(9, 6))

for cat, color, label_txt in [
    (1, "tab:red",   "Categoria 1"),
    (2, "tab:green", "Categoria 2"),
    (3, "tab:blue",  "Categoria 3"),
]:
    alt_ft = np.asarray(ITM_LIMITS[cat]["alt_ft"], float)       # altitudes em ft
    psd    = np.asarray(ITM_LIMITS[cat]["psd_dBm_MHz"], float)  # limites em dBm/MHz

    # converter ft -> m
    alt_m = alt_ft / 3.28084

    # curva interpolada (segmentos de reta em escala log de x)
    plt.semilogx(alt_m, psd+20, '-', color=color, label=label_txt)

    # marcar os pontos originais (como os “Measured Tolerance Thresholds”)
    plt.semilogx(alt_m, psd+20, 'o', color=color, markersize=6)

plt.grid(True, which="both", ls="--", alpha=0.4)
plt.xlabel("Altitude (m)")
plt.ylabel("Potência para desensibilização (dBm/100MHz)")
plt.legend()
plt.tight_layout()
plt.show()