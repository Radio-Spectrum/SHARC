"""
Post-processing IMT HIBS RAS 2600 MHz.

- Plots CCDF "originais" por arquivo (via PostProcessor)
- 1º Monte Carlo por arquivo (dl_interf_power_mc_sum_dBm) – opcional
- 2º Monte Carlo MISTO (3G + 6G) POR DISTÂNCIA (e N),
  usando MC_K_MIXED amostras de cada propagador,
  gerando três vetores por par:
    * dl_interf_power_mc2_3g_dBm   (3G-only)
    * dl_interf_power_mc2_6g_dBm   (6G-only)
    * dl_interf_power_mc2_mix_dBm  (3G+6G misto)

As CCDFs finais de 3G, 6G e MISTO são todas baseadas neste 2º Monte Carlo.
"""

import os
from pathlib import Path
import re
import numpy as np
import plotly.graph_objects as go

from sharc.results import Results
from sharc.post_processor import PostProcessor

# =========================
# Configuração da Campanha
# =========================

MC_ATTR_IN    = "system_dl_interf_power_per_mhz"   # dBm/MHz (saída do SHARC)
MC_ATTR_OUT   = "dl_interf_power_mc_sum_dBm"       # 1º MC (por arquivo) – opcional
MC_N_SAMPLES  = 10000
MC_SEED       = 12345
DB_PER_100MHZ = 20 - 6  # dBm/MHz -> dBm/100MHz (+6 dB filtro)

# 2º Monte Carlo MISTURADO (OPÇÃO A, por par 3G/6G, POR DISTÂNCIA)
MC_K_MIXED = {
    '':    int(6000 / (57 * 3)),   # nº de amostras da distribuição 3G
    '6G_': int(6000 / (57 * 3)),   # nº de amostras da distribuição 6G
}

MC2_3G_ATTR  = "dl_interf_power_mc2_3g_dBm"
MC2_6G_ATTR  = "dl_interf_power_mc2_6g_dBm"
MC2_MIX_ATTR = "dl_interf_power_mc2_mix_dBm"

# Grupos
n_array      = [4, 8, 16]
propag       = ['', "6G_"]
distances_km = [1000, 2000, 15000, 20000, 30000]

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
valid_patterns = []

for b, a, s in combinations:
    alt = np.round(s * np.tan(np.deg2rad(3)))
    pattern = f"{b}array_{a}_approach_{s}m"
    if b == "6G_":
        legend = f"6G - N={a} d={s:05d}m - alt={alt}"
    else:
        legend = f"3G - N={a} d={s:05d}m - alt={alt}"

    post_processor.add_plot_legend_pattern(
        dir_name_contains=pattern,
        legend=legend
    )
    PATTERN_TO_LEGEND[pattern] = legend
    valid_patterns.append(pattern)

# Regex: extrai propag, N, distância
_pat = re.compile(r'(6G_)?array_(\d+)_approach_(\d+)m')

def _sort_key(res):
    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))
    m = _pat.search(base)
    if not m:
        return (99, 99, 10**12)
    prop = m.group(1) or ""
    N    = int(m.group(2))
    dist = int(m.group(3))
    prop_rank = {"": 0, "6G_": 1}.get(prop, 9)
    return (prop_rank, N, dist)

# ==================================
# Carregar resultados da campanha
# ==================================
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

def filter_fn(dir_path: str) -> bool:
    base = os.path.basename(dir_path)
    return any(pattern in base for pattern in valid_patterns)

many_results = Results.load_many_from_dir(
    os.path.join(campaign_base_dir, "output_dl"),
    only_latest=True,
    only_samples=[
        "imt_system_antenna_gain",
        "imt_bs_antenna_gain",
        "system_imt_antenna_gain",
        "imt_system_path_loss",
        "system_dl_interf_power_per_mhz",
    ],
    filter_fn=filter_fn,
)
many_results.sort(key=_sort_key)

post_processor.add_results(many_results)

# ==========================================================
# 1º Monte Carlo simples (por arquivo) – opcional
# ==========================================================
def mc_sum_dBm_per_file(x_dBm, k, n_trials, seed=MC_SEED):
    x = np.asarray(x_dBm, float)
    x = x[np.isfinite(x)]
    if x.size == 0 or k <= 0 or n_trials <= 0:
        return np.array([])

    x_mW = 10 ** (x / 10)
    rng = np.random.default_rng(seed)
    draws = rng.choice(x_mW, size=(n_trials, k), replace=True)
    sums = draws.sum(axis=1)
    return 10 * np.log10(sums)

MC_K_original = int(round(6000 / (57 * 3)))

for res in many_results:
    x = getattr(res, MC_ATTR_IN, None)
    if x is None:
        continue
    out = mc_sum_dBm_per_file(x, MC_K_original, MC_N_SAMPLES)
    setattr(res, MC_ATTR_OUT, out)

post_processor.RESULT_FIELDNAME_TO_PLOT_INFO[MC_ATTR_OUT] = dict(
    x_label=legenda_dens_potencia
)

# ===================================================================================
# 2º MONTE-CARLO (3G-only, 6G-only e MISTO) POR DISTÂNCIA (e N)
# ===================================================================================
def collect_attr_for_res_list(res_list, attr_name):
    vals = []
    for r in res_list:
        v = getattr(r, attr_name, None)
        if v is not None:
            arr = np.asarray(v, float)
            arr = arr[np.isfinite(arr)]
            if arr.size:
                vals.append(arr)
    if not vals:
        return np.array([])
    return np.concatenate(vals)

def mc_single_distribution(x_dBm, k, n_trials, seed=MC_SEED):
    """
    Monte-Carlo para uma única distribuição (3G-only ou 6G-only).
    Retorna dBm/100MHz (já com DB_PER_100MHZ somado).
    """
    x = np.asarray(x_dBm, float)
    x = x[np.isfinite(x)]
    if x.size == 0 or k <= 0 or n_trials <= 0:
        return np.array([])

    x_mW = 10 ** (x / 10)
    rng = np.random.default_rng(seed)
    draws = rng.choice(x_mW, size=(n_trials, k), replace=True)
    sums = draws.sum(axis=1)
    out_dBm = 10 * np.log10(sums) + DB_PER_100MHZ
    return out_dBm

def mc_mixed_two_distributions(x3_dBm, x6_dBm, k_dict, n_trials, seed=MC_SEED):
    """
    Monte-Carlo misto para um par (3G, 6G):
    - x3_dBm: amostras 3G (dBm/MHz)
    - x6_dBm: amostras 6G (dBm/MHz)
    Retorna vetor em dBm/100MHz (já com DB_PER_100MHZ somado).
    """
    x3 = np.asarray(x3_dBm, float)
    x3 = x3[np.isfinite(x3)]
    x6 = np.asarray(x6_dBm, float)
    x6 = x6[np.isfinite(x6)]

    if x3.size == 0 or x6.size == 0:
        return np.array([])

    x3_mW = 10 ** (x3 / 10)
    x6_mW = 10 ** (x6 / 10)

    k3 = int(k_dict[''])
    k6 = int(k_dict['6G_'])

    if k3 <= 0 or k6 <= 0 or n_trials <= 0:
        return np.array([])

    rng = np.random.default_rng(seed)
    draws3 = rng.choice(x3_mW, size=(n_trials, k3), replace=True)
    draws6 = rng.choice(x6_mW, size=(n_trials, k6), replace=True)

    sums_mW = draws3.sum(axis=1) + draws6.sum(axis=1)
    out_dBm = 10 * np.log10(sums_mW) + DB_PER_100MHZ
    return out_dBm

# Mapa (N, dist) -> {'': [res_3G...], '6G_': [res_6G...]}
pairs_map = {}

for res in many_results:
    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))
    m = _pat.search(base)
    if not m:
        continue
    prop = m.group(1) or ""
    N    = int(m.group(2))
    dist = int(m.group(3))

    key = (N, dist)
    d = pairs_map.setdefault(key, {'': [], '6G_': []})
    d[prop].append(res)

# Para cada par com 3G + 6G, calcula MC2 (3G-only, 6G-only, MISTO)
for (N, dist), d in pairs_map.items():
    res_list_3g = d['']
    res_list_6g = d['6G_']

    if not res_list_3g or not res_list_6g:
        continue

    x3 = collect_attr_for_res_list(res_list_3g, MC_ATTR_IN)
    x6 = collect_attr_for_res_list(res_list_6g, MC_ATTR_IN)

    mc2_3g  = mc_single_distribution(x3, MC_K_MIXED[''],    MC_N_SAMPLES, seed=MC_SEED)
    mc2_6g  = mc_single_distribution(x6, MC_K_MIXED['6G_'], MC_N_SAMPLES, seed=MC_SEED)
    mc2_mix = mc_mixed_two_distributions(x3, x6, MC_K_MIXED, MC_N_SAMPLES, seed=MC_SEED)

    if mc2_3g.size == 0 or mc2_6g.size == 0 or mc2_mix.size == 0:
        continue

    # Guarda MC2_3G e MC2_MIX no primeiro Results 3G do par
    res3 = res_list_3g[0]
    setattr(res3, MC2_3G_ATTR,  mc2_3g)
    setattr(res3, MC2_MIX_ATTR, mc2_mix)

    # Guarda MC2_6G no primeiro Results 6G do par
    res6 = res_list_6g[0]
    setattr(res6, MC2_6G_ATTR,  mc2_6g)

# =============================================================
# CCDF auxiliar
# =============================================================
def ccdf(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.array([]), np.array([])
    xs = np.sort(x)
    n = xs.size
    y = 1.0 - (np.arange(1, n + 1) / (n + 1.0))
    return xs, y

# Legenda a partir do diretório (mantendo a legenda original)
def legend_for_result(res):
    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))
    for pattern, legend in PATTERN_TO_LEGEND.items():
        if pattern in base:
            return legend
    return base or "Resultado"

# =============================================================
# 1) Plots originais (per-MHz e 1º MC) via PostProcessor
# =============================================================
plots_orig = post_processor.generate_ccdf_plots_from_results(
    many_results,
    cutoff_percentage=cutoff_percentage,
    shift_scale=shift_scale,
    legenda_dens_potencia=legenda_dens_potencia
)
post_processor.add_plots(plots_orig)

# =============================================================
# 2) Plot manual – 3G-only (2º MC) por distância
# =============================================================
results_3g_mc2 = [
    r for r in many_results
    if getattr(r, MC2_3G_ATTR, None) is not None
]

fig_3g = go.Figure()

for res in results_3g_mc2:
    vals = getattr(res, MC2_3G_ATTR, None)
    if vals is None:
        continue
    xs, ys = ccdf(vals)
    if xs.size == 0:
        continue
    label = legend_for_result(res)
    fig_3g.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", name=label
    ))

fig_3g.update_layout(
    title="CCDF – 2º Monte Carlo (3G-only) por distância",
    xaxis_title="Potência (dBm/100MHz)",
    yaxis_title="CCDF",
    yaxis_type="log",
    template="plotly_white",
)
fig_3g.add_vline(x=-36, line_dash="dash", line_color="black")
fig_3g.add_vline(x=-74, line_dash="dash", line_color="black")

# =============================================================
# 3) Plot manual – 6G-only (2º MC) por distância
# =============================================================
results_6g_mc2 = [
    r for r in many_results
    if getattr(r, MC2_6G_ATTR, None) is not None
]

fig_6g = go.Figure()

for res in results_6g_mc2:
    vals = getattr(res, MC2_6G_ATTR, None)
    if vals is None:
        continue
    xs, ys = ccdf(vals)
    if xs.size == 0:
        continue
    label = legend_for_result(res)
    fig_6g.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", name=label
    ))

fig_6g.update_layout(
    title="CCDF – 2º Monte Carlo (6G-only) por distância",
    xaxis_title="Potência (dBm/100MHz)",
    yaxis_title="CCDF",
    yaxis_type="log",
    template="plotly_white",
)
fig_6g.add_vline(x=-36, line_dash="dash", line_color="black")
fig_6g.add_vline(x=-74, line_dash="dash", line_color="black")

# =============================================================
# 4) Plot manual – MISTO (2º MC) por distância
# =============================================================
results_mix_mc2 = [
    r for r in many_results
    if getattr(r, MC2_MIX_ATTR, None) is not None
]

fig_mix = go.Figure()

for res in results_mix_mc2:
    vals = getattr(res, MC2_MIX_ATTR, None)
    if vals is None:
        continue
    xs, ys = ccdf(vals)
    if xs.size == 0:
        continue
    label = legend_for_result(res)
    fig_mix.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", name=label
    ))

fig_mix.update_layout(
    title="CCDF – 2º Monte Carlo MISTO (3G+6G) por distância",
    xaxis_title="Potência (dBm/100MHz)",
    yaxis_title="CCDF",
    yaxis_type="log",
    template="plotly_white",
)
fig_mix.add_vline(x=-36, line_dash="dash", line_color="black")
fig_mix.add_vline(x=-74, line_dash="dash", line_color="black")

# =============================================================
# 5) Mostrar tudo
# =============================================================
for p in post_processor.plots:
    p.show()

fig_3g.show()
fig_6g.show()
fig_mix.show()

print("\n[OK] Script executed successfully – 2º MC (3G, 6G e Misto) por distância.")
