"""
Script for post-processing and plotting IMT HIBS RAS 2600 MHz simulation results.
Keeps original loading/filtering logic and adds a second Monte Carlo aggregation
over system_dl_interf_power_per_mhz with CCDF plotting.

Tested with SHARC PostProcessor that does NOT support attr_name in
generate_ccdf_plots_from_results.
"""

import os
from pathlib import Path
import numpy as np
import plotly.graph_objects as go

from sharc.results import Results
from sharc.post_processor import PostProcessor


# =========================
# Configuração da Campanha
# =========================

# ======================================================================
# === SEGUNDO MONTE CARLO (adicionado após a leitura dos arquivos) ====
# ======================================================================

# Parâmetros do 2º Monte Carlo
MC_ATTR_IN    = "system_dl_interf_power_per_mhz"   # dBm (por MHz)
MC_ATTR_OUT   = "dl_interf_power_mc_sum_dBm"       # novo vetor agregado (dBm/100MHz)
MC_K          = 35          # nº de amostras aleatórias por somatório
MC_N_SAMPLES  = 10000       # nº de trials do 2º Monte Carlo
MC_SEED       = 12345
DB_PER_100MHZ = 20.0 - 6    # converter de dBm/MHz -> dBm/100MHz (+6 dB de filtro)

## Definition of plot variable (what to plot)
n_array = [4, 8]
propag = ['', "FS_"]            # '' e 'FS_' (duas opções de prefixo)
N = 15                          # número de pontos/distâncias
max_dist_km = 30000             # distância máxima ao centro da pista (km)
aux = (np.linspace(0, max_dist_km, N))
distances_km = [int(val) for val in aux]
distances_km = [2142, 6428, 15000, 23571]  # exemplo: subconjunto de distâncias

## Graphics adjustments
cutoff_percentage = 0.001
shift_scale = 0                 # Segment Factor + Filtro (originais)
legenda_INR_potencia = "INR [dB]"
legenda_dens_potencia = "dBm"

# Change default legend to the shifted
post_processor = PostProcessor()
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_inr']['x_label'] = legenda_dens_potencia
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_dl_interf_power_per_mhz']['x_label'] = legenda_dens_potencia

# Build sorted combinations (mantido)
combinations = [
    (b, a, s)
    for b in sorted(propag)
    for a in sorted(n_array)
    for s in sorted(distances_km)
]

# Mapa auxiliar para reproduzir as mesmas legendas em qualquer plot
PATTERN_TO_LEGEND = {}
valid_patterns = []

# Add them in sorted order (mantido)
for b, a, s in combinations:
    alt = np.round(s * np.tan(np.deg2rad(3)))
    pattern = f"{b}array_{a}_approach_{s}m"
    if b == 'FS_':
        legend = f"FS - N={a} d ={format(int(s), '05d')}m - alt = {alt}"
    else:
        legend = f"P528 - N={a} d ={format(int(s), '05d')}m - alt = {alt}"
    post_processor.add_plot_legend_pattern(
        dir_name_contains=pattern,
        legend=legend
    )
    valid_patterns.append(pattern)
    PATTERN_TO_LEGEND[pattern] = legend

import os, re

_pat = re.compile(r'(FS_)?array_(\d+)_approach_(\d+)m')

def _sort_key(res):
    # use output_directory/dir_path to extract (propag, N, distance)
    base = os.path.basename(getattr(res, "output_directory", "") or
                            getattr(res, "dir_path", ""))
    m = _pat.search(base)
    if not m:
        return (99, 99, 10**12)           # push unknowns to the end
    propag = m.group(1) or ""             # '' or 'FS_'
    N      = int(m.group(2))
    dist   = int(m.group(3))
    propag_rank = {"": 0, "FS_": 1}.get(propag, 9)
    return (propag_rank, N, dist)         # sort by propag, then N, then distance

# Define filter function (mantido)
filter_fn = lambda dir_path: any(
    pattern in os.path.basename(dir_path) for pattern in valid_patterns
)

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())





# === (MANTIDO) Carrega TODOS os resultados dos diretórios filtrados ===
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


# ---------------- Helpers p/ legenda idêntica ----------------
def _legend_for_result(res) -> str:
    """
    Retorna a legenda (texto) para um objeto Results, reutilizando os mesmos
    patterns usados nos plots originais. Usa o basename do diretório para casar.
    """
    base = ""
    for attr in ("dir_path", "base_dir", "directory", "path"):
        if hasattr(res, attr) and getattr(res, attr):
            base = os.path.basename(str(getattr(res, attr)))
            break

    if base:
        for pattern, legend in PATTERN_TO_LEGEND.items():
            if pattern in base:
                return legend

    # Fallbacks
    return getattr(res, "name", None) or getattr(res, "label", None) or (base or "Resultado")


# ---------------- 2º Monte Carlo: soma em mW e volta a dBm -------------
# Blindagem de tipos (evita TypeError no rng.choice se vierem como float)
MC_K = int(np.round(MC_K))
MC_N_SAMPLES = int(np.round(MC_N_SAMPLES))

rng = np.random.default_rng(MC_SEED)

def legend_from_output_dir(output_dir: str,
                           pattern_to_legend: dict[str, str],
                           valid_patterns: list[str]) -> tuple[str | None, str | None]:
    base = os.path.basename(output_dir.rstrip(os.sep))
    # find all patterns contained in the basename (handles timestamp suffixes)
    matches = [p for p in valid_patterns if p in base]
    if not matches:
        return None, None
    # prefer the longest match (most specific)
    pattern = max(matches, key=len)
    return pattern, pattern_to_legend.get(pattern)

def _mc_sum_dBm(x_dBm: np.ndarray, k: int, n_trials: int) -> np.ndarray:
    """
    Escolhe k amostras aleatórias (com reposição) de x_dBm (por MHz),
    soma em mW e retorna o somatório em dBm.
    """
    # Garante inteiros (podem vir como float)
    k = int(np.round(k))
    n_trials = int(np.round(n_trials))

    x = np.asarray(x_dBm, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0 or k <= 0 or n_trials <= 0:
        return np.array([])

    # Converte para escala linear (mW), soma e volta para dBm
    x_mW = 10.0 ** (x / 10.0)
    draws = rng.choice(x_mW, size=(n_trials, k), replace=True)  # (n_trials, k)
    sums_mW = draws.sum(axis=1)
    return 10.0 * np.log10(sums_mW)

# Para cada Results, cria o vetor agregado e salva como novo atributo
for res in getattr(post_processor, "results", []):
    x_dBm = getattr(res, MC_ATTR_IN, None)
    if x_dBm is None:
        continue
    sums_dBm = _mc_sum_dBm(x_dBm, k=MC_K, n_trials=MC_N_SAMPLES)
    setattr(res, MC_ATTR_OUT, sums_dBm)

# Registra metadados de plot para o novo atributo (para a pipeline CCDF do SHARC)
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO[MC_ATTR_OUT] = dict(
    x_label=legenda_dens_potencia
)

# ======================================================================
# === (MANTIDO) Plots “originais” (per-MHz) no post_processor ==========
# ======================================================================
plots_orig = post_processor.generate_ccdf_plots_from_results(
    many_results,
    cutoff_percentage=cutoff_percentage,
    shift_scale=shift_scale,  # mantendo como no seu script atual
    legenda_dens_potencia=legenda_dens_potencia
)
post_processor.add_plots(plots_orig)

# ======================================================================
# === (NOVO) Plots do agregado (2º MC) EM UM PROCESSOR SEPARADO ========
# ======================================================================

# Cria um segundo PostProcessor só para o agregado
mc_post_processor = PostProcessor()
mc_post_processor.RESULT_FIELDNAME_TO_PLOT_INFO[MC_ATTR_OUT] = dict(
    x_label=legenda_dens_potencia
)

# Replica os mesmos patterns de legenda
for pattern, legend in PATTERN_TO_LEGEND.items():
    mc_post_processor.add_plot_legend_pattern(
        dir_name_contains=pattern,
        legend=legend
    )

# Reaproveita os mesmos Results (já com o atributo MC salvo)
mc_post_processor.add_results(many_results)

# Gera CCDFs (aplicando o offset para dBm/100MHz) e filtra apenas o atributo agregado
plots_all_mc = mc_post_processor.generate_ccdf_plots_from_results(
    many_results,
    cutoff_percentage=cutoff_percentage,
    shift_scale=DB_PER_100MHZ,       # converter dBm/MHz -> dBm/100MHz (+ filtro)
    legenda_dens_potencia=legenda_dens_potencia
)

plots_mc = []
for p in plots_all_mc:
    attr = getattr(p, "results_attribute_name", None) \
        or getattr(p, "attribute_name", None) \
        or getattr(p, "attr_name", None)
    if attr == MC_ATTR_OUT:
        plots_mc.append(p)

mc_post_processor.add_plots(plots_mc)

# Linhas de referência APENAS no gráfico agregado
plt_mc = mc_post_processor.get_plot_by_results_attribute_name(MC_ATTR_OUT, plot_type='ccdf')
if plt_mc:
    # -36 dB/100MHz [Cat 1]
    plt_mc.add_trace(
        go.Scatter(
            x=[-36, -36],
            y=[cutoff_percentage, 1],
            mode="lines",
            line=dict(dash="dash", color="black"),
            name=" -36 dB/100MHz [Cat 1]",
            hoverinfo="skip",
            showlegend=True
        )
    )
    # -74 dB/100MHz [Cat 2&3]
    plt_mc.add_trace(
        go.Scatter(
            x=[-74, -74],
            y=[cutoff_percentage, 1],
            mode="lines",
            line=dict(dash="dash", color="black"),
            name=" -74 dB/100MHz [Cat 2&3]",
            hoverinfo="skip",
            showlegend=True
        )
    )
    # --------- Deixa tracejado quando a legenda indicar N=8 ----------
    if hasattr(plt_mc, "figure") and plt_mc.figure:
        fig_obj = plt_mc.figure
        for tr in fig_obj.data:
            name = getattr(tr, "name", "") or ""
            if "N=8" in name:
                tr.update(line=dict(dash="dash"))

# ======================================================================
# === Renderização separada (com fallback manual) ======================
# ======================================================================

# 1) Mostra originais (per-MHz)
for plot in post_processor.plots:
    plot.show()

# 2) Mostra agregados (2º MC) separadamente
if mc_post_processor.plots:
    for plot in mc_post_processor.plots:
        plot.show()
else:
    # ---------- Fallback manual: constrói a figura na unha ----------
    def _ccdf(series_dBm):
        y = np.asarray(series_dBm, dtype=float)
        y = y[np.isfinite(y)]
        if y.size == 0:
            return np.array([]), np.array([])
        x_sorted = np.sort(y)
        n = x_sorted.size
        ccdf = 1.0 - (np.arange(1, n + 1) / (n + 1.0))
        return x_sorted, ccdf

    fig_mc = go.Figure()
    any_trace = False
    idx = 0
    for res in many_results:
        vals = getattr(res, MC_ATTR_OUT, None)
        if vals is None:
            continue
        x, y = _ccdf(vals)
        x = x + DB_PER_100MHZ  # converter para dBm/100MHz (+ filtro)
        if x.size:
            pattern, label = legend_from_output_dir(res.output_directory, PATTERN_TO_LEGEND, valid_patterns)
            is_n8 = ("N=8" in label)
            fig_mc.add_trace(go.Scatter(
                x=x, y=y,
                mode="lines",
                name=label,
                line=dict(dash="dash") if is_n8 else None
            ))
            any_trace = True
        idx = idx+1

    if any_trace:
        # linhas de referência
        fig_mc.add_vline(x=-36, line_dash="dash", annotation_text="-36 dB/100MHz", annotation_position="top")
        fig_mc.add_vline(x=-74, line_dash="dash", annotation_text="-74 dB/100MHz", annotation_position="top")
        fig_mc.update_layout(
            title=f"CCDF (Agregado 2º MC) de {MC_ATTR_IN} (somado em mW, exibido em dBm/100MHz)",
            xaxis_title="Potência (dBm/100MHz)",
            yaxis_title="CCDF",
            yaxis_type="log",
            template="plotly_white",
            legend_title="Resultados (i)"
        )
        fig_mc.show()
    else:
        print("[WARN] Nenhum traço agregado para plotar no fallback manual.")









