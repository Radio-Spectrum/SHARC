"""
Post-processing IMT HIBS RAS 2600 MHz:
- Lê resultados SHARC (3G e 6G) para várias distâncias.
- Faz 2º Monte Carlo:
    * 3G-only (por distância)
    * 6G-only (por distância)
    * Misto 3G+6G (por distância)
- Plota:
    1) CCDF comparando 3G-only, 6G-only e Misto (agregado).
    2) Probabilidade de violação do ITM (UC1, UC2, UC3) vs distância,
       para 3G-only, 6G-only e Misto.
"""

import os
import re
import math
from pathlib import Path
from typing import Dict, Tuple, List

import numpy as np
import plotly.graph_objects as go

from sharc.results import Results

# ================================================================
# Configuração geral da campanha
# ================================================================

# Diretório base da campanha (assumindo estrutura padrão do SHARC)
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

# Prefixos de propagação (3G e 6G) nos nomes dos diretórios
propag_list = ['', "6G_"]        # '' => 3G, '6G_' => 6G

# Arrays (linhas) considerados
n_array_list = [4, 8, 16]

# Distâncias (em metros) – devem bater com o que você usou na geração dos YAMLs.
# Aqui vou assumir que você está usando algo como:
distances_m = [1000, 2000, 6000, 10000, 15000, 20000, 25000, 30000]

# Apenas como conveniência, as mesmas distâncias em km para eixo x
distances_km = [d / 1000.0 for d in distances_m]

# Glideslope do seu cenário (em graus) para converter distância -> altitude
GLIDESLOPE_DEG = 3.0

# 2º Monte Carlo: parâmetros básicos
MC_ATTR_IN = "system_dl_interf_power_per_mhz"   # dBm/MHz
# Esses vetores depois são convertidos para dBm/100MHz com margem via DB_PER_100MHZ
MC_N_SAMPLES = 10_000
MC_SEED = 12345

# Número de amostras por trial para MC "single" (3G-only e 6G-only)
# Você pode ajustar esses valores se quiser outra proporção.
MC_K_SINGLE = {
    '':     int(6000 / (57 * 3)),    # nº de amostras por somatório para 3G
    '6G_':  int(6000 / (57 * 3))     # nº de amostras por somatório para 6G
}

# Monte-Carlo MISTO (3G + 6G), por trial:
# (pode mudar os inteiros para outra proporção, se quiser)
MC_K_MIXED = {
    '':     int(6000 / (57 * 3)),    # nº de amostras da dist. 3G
    '6G_':  int(6000 / (57 * 3))     # nº de amostras da dist. 6G
}

# Conversão dBm/MHz -> dBm/100MHz e margem de 6 dB:
# +20 dB (100 MHz) - 6 dB (margem) = +14 dB
DB_PER_100MHZ = 20.0 - 6.0

# ================================================================
# Máscara de tolerância (ITM) 3750 MHz – valores extraídos dos gráficos
# (altitude em pés, PSD em dBm/MHz)
# ================================================================

# Uso Categoria 1
UC1_ALT_FT = np.array([200.0, 1000.0, 5000.0, 7500.0])
UC1_PSD_DBM_MHZ = np.array([-39.0, -46.0, -54.0, -54.0])

# Uso Categoria 2
UC2_ALT_FT = np.array([200.0, 1000.0, 2000.0])
UC2_PSD_DBM_MHZ = np.array([-76.0, -86.0, -94.0])

# Uso Categoria 3
UC3_ALT_FT = np.array([200.0, 1000.0, 2000.0])
UC3_PSD_DBM_MHZ = np.array([-68.0, -86.0, -94.0])


def itm_psd_ft(alt_ft: float,
               alt_grid_ft: np.ndarray,
               psd_grid_dbm_mhz: np.ndarray) -> float:
    """
    Interpola linearmente o ITM (PSD em dBm/MHz) em função da altitude (ft),
    com clamp na borda (usa o valor da extremidade).
    """
    return float(np.interp(alt_ft,
                           alt_grid_ft,
                           psd_grid_dbm_mhz,
                           left=psd_grid_dbm_mhz[0],
                           right=psd_grid_dbm_mhz[-1]))


def itm_total_dbm_100mhz_with_margin(alt_m: float,
                                     usage_category: int) -> float:
    """
    Retorna o limiar de proteção em dBm/100MHz já com margem de 6 dB:
        threshold_100MHz(margem) = PSD_ITM + 20 dB - 6 dB
    """
    ft = alt_m * 3.28084
    if usage_category == 1:
        psd = itm_psd_ft(ft, UC1_ALT_FT, UC1_PSD_DBM_MHZ)
    elif usage_category == 2:
        psd = itm_psd_ft(ft, UC2_ALT_FT, UC2_PSD_DBM_MHZ)
    elif usage_category == 3:
        psd = itm_psd_ft(ft, UC3_ALT_FT, UC3_PSD_DBM_MHZ)
    else:
        raise ValueError("usage_category deve ser 1, 2 ou 3")
    return psd + DB_PER_100MHZ


# ================================================================
# Funções auxiliares de Monte Carlo
# ================================================================

rng = np.random.default_rng(MC_SEED)


def _mc_sum_dBm(x_dBm: np.ndarray,
                k: int,
                n_trials: int) -> np.ndarray:
    """
    2º Monte Carlo simples:
    - x_dBm: vetor de amostras em dBm/MHz (uma realização da simulação SHARC).
    - k: nº de amostras sorteadas por trial (com reposição).
    - n_trials: nº de trials.
    Retorna um vetor (n_trials,) com o somatório em dBm/MHz.
    """
    x = np.asarray(x_dBm, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0 or k <= 0 or n_trials <= 0:
        return np.array([], dtype=float)

    x_mW = 10.0 ** (x / 10.0)
    draws = rng.choice(x_mW, size=(n_trials, k), replace=True)
    sums_mW = draws.sum(axis=1)
    return 10.0 * np.log10(sums_mW)


def _mc_sum_dBm_mixed(x3_dBm: np.ndarray,
                      x6_dBm: np.ndarray,
                      k_mix: Dict[str, int],
                      n_trials: int) -> np.ndarray:
    """
    2º Monte Carlo MISTO (3G + 6G):
    - x3_dBm: vetor da distribuição 3G (dBm/MHz).
    - x6_dBm: vetor da distribuição 6G (dBm/MHz).
    - k_mix: dict com nº de amostras por trial, por tipo:
        { '': k_3G, '6G_': k_6G }
    - n_trials: nº de trials.
    Retorna vetor (n_trials,) do somatório combinado em dBm/MHz.
    """
    k3 = int(k_mix.get('', 0))
    k6 = int(k_mix.get('6G_', 0))
    if n_trials <= 0 or (k3 + k6) <= 0:
        return np.array([], dtype=float)

    x3 = np.asarray(x3_dBm, dtype=float)
    x3 = x3[np.isfinite(x3)]
    x6 = np.asarray(x6_dBm, dtype=float)
    x6 = x6[np.isfinite(x6)]

    if x3.size == 0 and x6.size == 0:
        return np.array([], dtype=float)

    x3_mW = 10.0 ** (x3 / 10.0) if x3.size > 0 else None
    x6_mW = 10.0 ** (x6 / 10.0) if x6.size > 0 else None

    sums_mW = np.zeros(n_trials, dtype=float)

    if k3 > 0 and x3_mW is not None:
        draws3 = rng.choice(x3_mW, size=(n_trials, k3), replace=True)
        sums_mW += draws3.sum(axis=1)

    if k6 > 0 and x6_mW is not None:
        draws6 = rng.choice(x6_mW, size=(n_trials, k6), replace=True)
        sums_mW += draws6.sum(axis=1)

    # se por acaso ainda tiver zero (casos degenerados)
    sums_mW[sums_mW <= 0] = np.nan
    return 10.0 * np.log10(sums_mW)


def _ccdf(series_dBm: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Retorna (x_sorted, CCDF) para o vetor de amostras em dBm.
    CCDF(p) = P(X > x).
    """
    y = np.asarray(series_dBm, dtype=float)
    y = y[np.isfinite(y)]
    if y.size == 0:
        return np.array([]), np.array([])
    x_sorted = np.sort(y)
    n = x_sorted.size
    ccdf = 1.0 - (np.arange(1, n + 1) / (n + 1.0))
    return x_sorted, ccdf


# ================================================================
# Carregar resultados do SHARC
# ================================================================

# Regex para extrair propag, N e distância do nome do diretório
# Ex: "array_8_approach_15000m" ou "6G_array_8_approach_15000m"
_pat = re.compile(r'(6G_)?array_(\d+)_approach_(\d+)m')

def _sort_key_dirname(dirname: str):
    """
    Ordena por (propag, N, dist).
    propag_rank: '' (3G) = 0, '6G_' (6G) = 1.
    """
    base = os.path.basename(dirname.rstrip(os.sep))
    m = _pat.search(base)
    if not m:
        return (99, 99, 10**12)
    propag = m.group(1) or ""
    nrows = int(m.group(2))
    dist = int(m.group(3))
    propag_rank = {"": 0, "6G_": 1}.get(propag, 9)
    return (propag_rank, nrows, dist)

def _filter_fn(dir_path: str) -> bool:
    """
    Mantém apenas diretórios que casam com o padrão de nomes esperado.
    """
    base = os.path.basename(dir_path.rstrip(os.sep))
    return _pat.search(base) is not None

# Carrega todos os resultados (última versão) dos diretórios filtrados
many_results: List[Results] = Results.load_many_from_dir(
    os.path.join(campaign_base_dir, "output_dl"),
    only_latest=True,
    only_samples=[
        "imt_system_antenna_gain",
        "imt_bs_antenna_gain",
        "system_imt_antenna_gain",
        "imt_system_path_loss",
        MC_ATTR_IN,
    ],
    filter_fn=_filter_fn,
)

# Ordena resultados para ficar previsível
many_results.sort(key=lambda r: _sort_key_dirname(r.output_directory))

# Extraímos meta-informação (propag, N, dist) de cada Results
meta: List[Tuple[Results, str, int, int]] = []  # (res, propag, n_array, dist_m)
for res in many_results:
    base = os.path.basename(res.output_directory.rstrip(os.sep))
    m = _pat.search(base)
    if not m:
        continue
    propag = m.group(1) or ""
    nrows = int(m.group(2))
    dist_m = int(m.group(3))
    meta.append((res, propag, nrows, dist_m))

if not meta:
    raise RuntimeError("Nenhum diretório de resultados casou com o padrão esperado.")

# ================================================================
# 2º Monte Carlo por distância (3G-only, 6G-only, Misto)
# ================================================================

# Armazenar resultados do 2º MC:
#   mc_single[(propag, n_array, dist_m)] -> vetor dBm/MHz
#   mc_mixed[(n_array, dist_m)]         -> vetor dBm/MHz (3G+6G)
mc_single: Dict[Tuple[str, int, int], np.ndarray] = {}
mc_mixed: Dict[Tuple[int, int], np.ndarray] = {}

# Primeiro: 2º MC "single" (3G-only e 6G-only)
for res, propag, nrows, dist_m in meta:
    x_dBm = getattr(res, MC_ATTR_IN, None)
    if x_dBm is None:
        continue

    k_single = MC_K_SINGLE.get(propag, 0)
    sums_single = _mc_sum_dBm(x_dBm, k=k_single, n_trials=MC_N_SAMPLES)
    mc_single[(propag, nrows, dist_m)] = sums_single

# Depois: MC misto por par (3G & 6G com mesmo nrows e dist_m)
# Agrupa por (nrows, dist_m)
groups: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}
for (propag, nrows, dist_m), vec in mc_single.items():
    groups.setdefault((nrows, dist_m), {})[propag] = vec

for (nrows, dist_m), dists in groups.items():
    x3 = dists.get('', None)
    x6 = dists.get('6G_', None)
    if x3 is None or x6 is None:
        # se não tiver os dois, não dá pra fazer MC misto
        continue
    sums_mixed = _mc_sum_dBm_mixed(x3, x6, k_mix=MC_K_MIXED,
                                   n_trials=MC_N_SAMPLES)
    mc_mixed[(nrows, dist_m)] = sums_mixed

# ================================================================
# Fig. 1 – CCDF comparando 3G-only, 6G-only e Misto (agregados)
# ================================================================

# Concatenamos todos os resultados de n_array=8 (por ex.) – você pode mudar aqui
TARGET_N_ARRAY = 8

all_3g = []
all_6g = []
all_mix = []

for (propag, nrows, dist_m), vec in mc_single.items():
    if nrows != TARGET_N_ARRAY:
        continue
    if propag == '':
        all_3g.append(vec)
    elif propag == '6G_':
        all_6g.append(vec)

for (nrows, dist_m), vec in mc_mixed.items():
    if nrows != TARGET_N_ARRAY:
        continue
    all_mix.append(vec)

if all_3g:
    all_3g = np.concatenate(all_3g)
else:
    all_3g = np.array([], dtype=float)

if all_6g:
    all_6g = np.concatenate(all_6g)
else:
    all_6g = np.array([], dtype=float)

if all_mix:
    all_mix = np.concatenate(all_mix)
else:
    all_mix = np.array([], dtype=float)

# Converte para dBm/100MHz já com margem
all_3g_100 = all_3g + DB_PER_100MHZ
all_6g_100 = all_6g + DB_PER_100MHZ
all_mix_100 = all_mix + DB_PER_100MHZ

x3, ccdf3 = _ccdf(all_3g_100)
x6, ccdf6 = _ccdf(all_6g_100)
xm, ccdm = _ccdf(all_mix_100)

fig_ccdf = go.Figure()
if x3.size:
    fig_ccdf.add_trace(go.Scatter(
        x=x3, y=ccdf3, mode="lines",
        name="3G-only"
    ))
if x6.size:
    fig_ccdf.add_trace(go.Scatter(
        x=x6, y=ccdf6, mode="lines",
        name="6G-only"
    ))
if xm.size:
    fig_ccdf.add_trace(go.Scatter(
        x=xm, y=ccdm, mode="lines",
        name="Mixed MC"
    ))

# Linhas de referência (ex.: -68 e -36 dBm/100MHz, se quiser)
fig_ccdf.add_vline(x=-68, line_dash="dash",
                   annotation_text="-68 dBm/100MHz", annotation_position="top")
fig_ccdf.add_vline(x=-36, line_dash="dash",
                   annotation_text="-36 dBm/100MHz", annotation_position="top")

fig_ccdf.update_layout(
    title="Comparação CCDF: 3G vs 6G vs Misto",
    xaxis_title="Potência (dBm/100MHz, com margem)",
    yaxis_title="CCDF",
    yaxis_type="log",
    template="plotly_white",
    legend_title="Distribuição"
)

fig_ccdf.show()

# ================================================================
# Fig. 2 – Probabilidade de violação vs distância (UC1, UC2, UC3)
# ================================================================

# Função auxiliar: dado vetor (dBm/100MHz+ margem) e limiar em dBm/100MHz,
# retorna P(X > limiar) em porcentagem.
def violation_probability(series_dBm_100: np.ndarray,
                          threshold_dBm_100: float) -> float:
    s = np.asarray(series_dBm_100, dtype=float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return 0.0
    return 100.0 * float(np.mean(s > threshold_dBm_100))


# Para cada distância (e n_array alvo), calculamos prob. de violação
# para 3 categorias (1,2,3) e 3 distribuições (3G, 6G, Misto).
# Vamos usar apenas n_array = TARGET_N_ARRAY.
dist_sorted = sorted(distances_m)  # ordem crescente

# Dicionários:
#   prob_ucX_3g[dist_m], prob_ucX_6g[dist_m], prob_ucX_mix[dist_m]
prob_uc1_3g, prob_uc1_6g, prob_uc1_mix = {}, {}, {}
prob_uc2_3g, prob_uc2_6g, prob_uc2_mix = {}, {}, {}
prob_uc3_3g, prob_uc3_6g, prob_uc3_mix = {}, {}, {}

# Pré-calcula altitude para cada distância
altitude_m_by_dist = {
    d: math.tan(math.radians(GLIDESLOPE_DEG)) * d
    for d in dist_sorted
}

for dist_m in dist_sorted:
    alt_m = altitude_m_by_dist[dist_m]

    # thresholds (dBm/100MHz com margem)
    th_uc1 = itm_total_dbm_100mhz_with_margin(alt_m, usage_category=1)
    th_uc2 = itm_total_dbm_100mhz_with_margin(alt_m, usage_category=2)
    th_uc3 = itm_total_dbm_100mhz_with_margin(alt_m, usage_category=3)

    # 3G-only e 6G-only (se existirem)
    vec_3g = mc_single.get(('', TARGET_N_ARRAY, dist_m), None)
    vec_6g = mc_single.get(('6G_', TARGET_N_ARRAY, dist_m), None)
    vec_mix = mc_mixed.get((TARGET_N_ARRAY, dist_m), None)

    if vec_3g is not None:
        vec_3g_100 = vec_3g + DB_PER_100MHZ
        prob_uc1_3g[dist_m] = violation_probability(vec_3g_100, th_uc1)
        prob_uc2_3g[dist_m] = violation_probability(vec_3g_100, th_uc2)
        prob_uc3_3g[dist_m] = violation_probability(vec_3g_100, th_uc3)
    else:
        prob_uc1_3g[dist_m] = 0.0
        prob_uc2_3g[dist_m] = 0.0
        prob_uc3_3g[dist_m] = 0.0

    if vec_6g is not None:
        vec_6g_100 = vec_6g + DB_PER_100MHZ
        prob_uc1_6g[dist_m] = violation_probability(vec_6g_100, th_uc1)
        prob_uc2_6g[dist_m] = violation_probability(vec_6g_100, th_uc2)
        prob_uc3_6g[dist_m] = violation_probability(vec_6g_100, th_uc3)
    else:
        prob_uc1_6g[dist_m] = 0.0
        prob_uc2_6g[dist_m] = 0.0
        prob_uc3_6g[dist_m] = 0.0

    if vec_mix is not None:
        vec_mix_100 = vec_mix + DB_PER_100MHZ
        prob_uc1_mix[dist_m] = violation_probability(vec_mix_100, th_uc1)
        prob_uc2_mix[dist_m] = violation_probability(vec_mix_100, th_uc2)
        prob_uc3_mix[dist_m] = violation_probability(vec_mix_100, th_uc3)
    else:
        prob_uc1_mix[dist_m] = 0.0
        prob_uc2_mix[dist_m] = 0.0
        prob_uc3_mix[dist_m] = 0.0

# Transforma em listas na ordem de dist_sorted
x_km = [d / 1000.0 for d in dist_sorted]

def dict_to_list(dct: Dict[int, float], keys: List[int]) -> List[float]:
    return [dct.get(k, 0.0) for k in keys]

uc1_3g = dict_to_list(prob_uc1_3g, dist_sorted)
uc1_6g = dict_to_list(prob_uc1_6g, dist_sorted)
uc1_mix = dict_to_list(prob_uc1_mix, dist_sorted)

uc2_3g = dict_to_list(prob_uc2_3g, dist_sorted)
uc2_6g = dict_to_list(prob_uc2_6g, dist_sorted)
uc2_mix = dict_to_list(prob_uc2_mix, dist_sorted)

uc3_3g = dict_to_list(prob_uc3_3g, dist_sorted)
uc3_6g = dict_to_list(prob_uc3_6g, dist_sorted)
uc3_mix = dict_to_list(prob_uc3_mix, dist_sorted)

# Figura com 3 subplots (UC1, UC2, UC3)
from plotly.subplots import make_subplots

fig_violation = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.07,
    subplot_titles=(
        "Uso Categoria 1 (UC1)",
        "Uso Categoria 2 (UC2)",
        "Uso Categoria 3 (UC3)",
    ),
)

def add_three_curves(row, uc3g, uc6g, ucmix):
    fig_violation.add_trace(
        go.Scatter(x=x_km, y=uc3g, mode="lines+markers", name="3G-only"),
        row=row, col=1
    )
    fig_violation.add_trace(
        go.Scatter(x=x_km, y=uc6g, mode="lines+markers", name="6G-only"),
        row=row, col=1
    )
    fig_violation.add_trace(
        go.Scatter(x=x_km, y=ucmix, mode="lines+markers", name="Mixed MC"),
        row=row, col=1
    )

add_three_curves(1, uc1_3g, uc1_6g, uc1_mix)
add_three_curves(2, uc2_3g, uc2_6g, uc2_mix)
add_three_curves(3, uc3_3g, uc3_6g, uc3_mix)

fig_violation.update_xaxes(title_text="Distância horizontal ao centro da pista (km)", row=3, col=1)
fig_violation.update_yaxes(title_text="% de violações (P[X > ITM])", row=1, col=1)
fig_violation.update_yaxes(title_text="% de violações", row=2, col=1)
fig_violation.update_yaxes(title_text="% de violações", row=3, col=1)

fig_violation.update_layout(
    title=f"Probabilidade de violação do ITM vs distância (N={TARGET_N_ARRAY})",
    template="plotly_white",
    legend_title="Distribuição",
    height=900,
)

fig_violation.show()
