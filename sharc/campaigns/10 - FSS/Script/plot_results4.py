"""
Post-processamento FSS 6 GHz - analise de convergencia (array_8, bw_54).

Para cada longitude do single_space_station, roda o SEGUNDO Monte Carlo
(agregando urbano + suburbano) tres vezes, usando apenas as PRIMEIRAS
2500, 5000 e 10000 amostras de cada CSV. Gera uma figura por longitude com as
tres CCDFs de INR sobrepostas, para checar a convergencia estatistica.

INR agregado por trial (em linear):
    INR_total = sum_{i=1}^{N_URBAN}   INR_urb_i   + sum_{j=1}^{N_SUBURBAN} INR_sub_j
Como o INR ja vem dividido pelo ruido (comum a todos), somar INR em escala
linear equivale a somar as potencias de interferencia e dividir pelo ruido.
"""

import csv
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import plotly.graph_objects as go
import matplotlib
matplotlib.use("Agg")  # salva PNG sem abrir janela
import matplotlib.pyplot as plt  # noqa: E402


# ================================================================
# Configuracao
# ================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
CAMPAIGN_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = CAMPAIGN_DIR / "output_dl"
PLOTS_DIR = CAMPAIGN_DIR / "plots"

# Usamos o system_inr.csv (INR ja calculado, em dB).
INR_FILE = "system_inr.csv"

# Filtro fixo desta analise.
TARGET_ARRAY = 8
TARGET_BW = 54

# Casos: numero de PRIMEIRAS amostras usadas de cada CSV (checagem de convergencia).
SAMPLE_COUNTS = [1000, 2500, 5000, 10000]

# Abrir as CCDFs por longitude no navegador (sao 11). Os HTMLs sao salvos
# de qualquer forma; os 3 graficos de margem sao sempre exibidos.
SHOW_CCDF = False

# Segundo Monte Carlo.
MC_TRIALS = 50000
MC_SEED = 12345

# Composicao urbano/suburbano do 2o MC (mesma do plot_results4 original).
# N e o numero de amostras somadas por trial em cada ambiente (densidade).
N_total = 147000
pop_urb = 180
pup_remain = 35
N_URBAN = round(N_total / 500 * pop_urb / (pop_urb + pup_remain))
N_SUBURBAN = round(N_total / 500 * pup_remain / (pop_urb + pup_remain))

# Criterios de protecao: limiar de INR e a probabilidade de excedencia
# (percentil) em que o criterio e avaliado.
PROTECTION_CRITERIA = [
    {"label": "-10.5 dB", "threshold_db": -10.5, "exceedance_probability": 0.2},
    {"label": "-7 dB", "threshold_db": -7.0, "exceedance_probability": 0.001},
    {"label": "-6 dB", "threshold_db": -6.0, "exceedance_probability": 0.0003},
]

# Nome do diretorio: 6G_urban_array_8_sss_bw_54_sss_lon_m109.5_...
RESULT_DIR_RE = re.compile(
    r"^6G_(?P<env>urban|suburban)(?P<uniform>_uniform)?_array_"
    r"(?P<array>\d+)_sss_bw_(?P<bw>\d+)"
    r"(?:_sss_lon_(?P<lon>[mp]\d+(?:\.\d+)?))?_"
)


# ================================================================
# Leitura dos resultados
# ================================================================

def read_samples_db(csv_path: Path, max_n: int | None = None) -> np.ndarray:
    """Le a coluna 'samples' (INR em dB), opcionalmente so as primeiras max_n."""
    values: List[float] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "samples" not in (reader.fieldnames or []):
            raise ValueError(f"Arquivo sem coluna 'samples': {csv_path}")
        for row in reader:
            try:
                values.append(float(row["samples"]))
            except (TypeError, ValueError):
                continue
            if max_n is not None and len(values) >= max_n:
                break

    samples = np.asarray(values, dtype=float)
    samples = samples[np.isfinite(samples)]
    if samples.size == 0:
        raise ValueError(f"Nenhuma amostra valida em {csv_path}")
    return samples


def longitude_from_label(label: str | None) -> float:
    if label is None:
        return float("nan")
    sign = -1 if label.startswith("m") else 1
    return sign * float(label[1:])


def find_latest_dirs(
    target_array: int = TARGET_ARRAY,
    target_bw: int = TARGET_BW,
) -> Dict[Tuple[str, float], Path]:
    """
    Retorna a pasta mais recente para cada (env, sss_longitude),
    filtrando por target_array/target_bw e ignorando variantes uniform.
    """
    latest: Dict[Tuple[str, float], Path] = {}

    for path in OUTPUT_DIR.iterdir():
        if not path.is_dir():
            continue
        match = RESULT_DIR_RE.match(path.name)
        if not match or match.group("uniform"):
            continue
        if int(match.group("array")) != target_array:
            continue
        if int(match.group("bw")) != target_bw:
            continue
        if not (path / INR_FILE).exists():
            continue

        key = (match.group("env"), longitude_from_label(match.group("lon")))
        previous = latest.get(key)
        if previous is None or path.stat().st_mtime > previous.stat().st_mtime:
            latest[key] = path

    return latest


# ================================================================
# Segundo Monte Carlo (agregado urbano + suburbano, em INR linear)
# ================================================================

def monte_carlo_aggregate_inr(
    urban_inr_db: np.ndarray,
    suburban_inr_db: np.ndarray,
    n_urban: int,
    n_suburban: int,
    n_trials: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if n_trials <= 0 or (n_urban <= 0 and n_suburban <= 0):
        return np.array([], dtype=float)

    total_lin = np.zeros(n_trials, dtype=float)

    if n_urban > 0 and urban_inr_db.size > 0:
        urban_lin = 10.0 ** (urban_inr_db / 10.0)
        draws = rng.choice(urban_lin, size=(n_trials, n_urban), replace=True)
        total_lin += draws.sum(axis=1)

    if n_suburban > 0 and suburban_inr_db.size > 0:
        suburban_lin = 10.0 ** (suburban_inr_db / 10.0)
        draws = rng.choice(suburban_lin, size=(n_trials, n_suburban), replace=True)
        total_lin += draws.sum(axis=1)

    total_lin[total_lin <= 0.0] = np.nan
    return 10.0 * np.log10(total_lin)


def ccdf(samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    clean = np.asarray(samples, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    x_sorted = np.sort(clean)
    y_ccdf = 1.0 - (np.arange(1, x_sorted.size + 1) / (x_sorted.size + 1.0))
    return x_sorted, y_ccdf


def inr_at_exceedance(samples: np.ndarray, exceedance_probability: float) -> float:
    """INR [dB] excedido com probabilidade exceedance_probability."""
    clean = np.asarray(samples, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size == 0:
        return float("nan")
    return float(np.percentile(clean, 100.0 * (1.0 - exceedance_probability)))


# ================================================================
# Plot
# ================================================================

def plot_ccdf_for_longitude(
    sss_longitude: float,
    curves: List[Tuple[int, np.ndarray, np.ndarray]],
) -> go.Figure:
    fig = go.Figure()

    for n_samples, x, y in curves:
        if x.size == 0:
            continue
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=f"{n_samples} amostras",
            )
        )

    for criterion in PROTECTION_CRITERIA:
        fig.add_vline(
            x=criterion["threshold_db"],
            line_dash="dash",
            line_color="black",
            annotation_text=criterion["label"],
            annotation_position="top",
        )

    fig.update_layout(
        title=(
            f"CCDF INR - 2o Monte Carlo (urbano + suburbano) | "
            f"array {TARGET_ARRAY}, BW {TARGET_BW} MHz, SSS lon {sss_longitude:g}°"
            f"<br><sup>N_urb={N_URBAN}, N_sub={N_SUBURBAN}, trials={MC_TRIALS} | "
            f"convergencia vs n. de amostras do CSV</sup>"
        ),
        xaxis_title="INR [dB]",
        yaxis_title="CCDF",
        yaxis_type="log",
        yaxis_range=[-4, 0],
        template="plotly_white",
        legend_title="Amostras (primeiras K)",
    )
    return fig


def plot_margin_by_longitude(
    mc_inr: Dict[Tuple[float, int], np.ndarray],
    longitudes: List[float],
    criterion: dict,
) -> go.Figure:
    """
    Margem de seguranca x longitude para UM criterio, com uma curva por
    contagem de amostra (2.5k / 5k / 10k):

        margem [dB] = limiar - INR(percentil de excedencia)
    """
    fig = go.Figure()
    p = criterion["exceedance_probability"]
    percentile = 100.0 * (1.0 - p)

    for n_samples in SAMPLE_COUNTS:
        lons_ok: List[float] = []
        margins: List[float] = []
        for sss_longitude in longitudes:
            inr = mc_inr.get((sss_longitude, n_samples))
            if inr is None:
                continue
            value = inr_at_exceedance(inr, p)
            if not np.isfinite(value):
                continue
            lons_ok.append(sss_longitude)
            margins.append(criterion["threshold_db"] - value)

        if not lons_ok:
            continue
        order = np.argsort(lons_ok)
        fig.add_trace(
            go.Scatter(
                x=np.asarray(lons_ok)[order],
                y=np.asarray(margins)[order],
                mode="lines+markers",
                name=f"{n_samples} amostras",
                marker=dict(symbol="square-open", size=8),
            )
        )

    fig.add_hline(y=0.0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=(
            f"Margem de seguranca | criterio {criterion['threshold_db']:g} dB "
            f"(P<sub>{percentile:g}</sub>) | array {TARGET_ARRAY}, BW {TARGET_BW} MHz"
        ),
        xaxis_title="Longitude SSS (°)",
        yaxis_title="Margem de segurança (dB)",
        template="plotly_white",
        legend_title="Amostras (primeiras K)",
    )
    return fig


def plot_ccdf_all_longitudes(
    data: Dict[Tuple[float, int], np.ndarray],
    longitudes: List[float],
    title: str,
    show_criteria: bool = True,
) -> go.Figure:
    """
    Uma unica figura com as CCDFs de INR de TODAS as longitudes:
        cor   -> longitude
        traco -> contagem de amostra (2.5k / 5k / 10k ...)
    Legenda dupla (cores = longitude; tracos = sample count) para nao
    poluir com uma entrada por curva. `data` mapeia (longitude, n_samples)
    -> vetor de INR [dB] (pode ser o agregado do 2o MC ou as amostras reais).
    """
    import plotly.colors as pcolors

    fig = go.Figure()
    n_lon = len(longitudes)
    color_vals = [i / max(n_lon - 1, 1) for i in range(n_lon)]
    palette = pcolors.sample_colorscale("Turbo", color_vals)
    color_for = {lon: palette[i] for i, lon in enumerate(longitudes)}

    dash_styles = ["solid", "dash", "dot", "dashdot", "longdash"]
    dash_for = {k: dash_styles[i % len(dash_styles)]
                for i, k in enumerate(SAMPLE_COUNTS)}

    # Curvas (sem legenda individual)
    for sss_longitude in longitudes:
        for n_samples in SAMPLE_COUNTS:
            inr = data.get((sss_longitude, n_samples))
            if inr is None:
                continue
            x, y = ccdf(inr)
            if x.size == 0:
                continue
            fig.add_trace(
                go.Scatter(
                    x=x, y=y, mode="lines",
                    line=dict(color=color_for[sss_longitude],
                              dash=dash_for[n_samples], width=1.2),
                    showlegend=False,
                    legendgroup=f"lon{sss_longitude:g}",
                    hovertemplate=(
                        f"lon {sss_longitude:g}°, {n_samples} amostras<br>"
                        "INR %{x:.2f} dB<br>CCDF %{y:.3g}<extra></extra>"
                    ),
                )
            )

    # Legenda 1: longitude -> cor
    for sss_longitude in longitudes:
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None], mode="lines", showlegend=True,
                line=dict(color=color_for[sss_longitude], width=2),
                name=f"lon {sss_longitude:g}°",
                legendgroup=f"lon{sss_longitude:g}",
            )
        )
    # Legenda 2: sample count -> traco
    for n_samples in SAMPLE_COUNTS:
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None], mode="lines", showlegend=True,
                line=dict(color="black", dash=dash_for[n_samples], width=2),
                name=f"{n_samples} amostras",
                legendgroup=f"K{n_samples}",
            )
        )

    if show_criteria:
        for criterion in PROTECTION_CRITERIA:
            fig.add_vline(
                x=criterion["threshold_db"], line_dash="dash", line_color="gray",
                annotation_text=criterion["label"], annotation_position="top",
            )

    fig.update_layout(
        title=title,
        xaxis_title="INR [dB]",
        yaxis_title="CCDF",
        yaxis_type="log",
        yaxis_range=[-4, 0],
        template="plotly_white",
    )
    return fig


# ================================================================
# Comparacao gerado x referencia (pontos extraidos das imagens) - matplotlib
# ================================================================

# Pontos lidos (digitalizados) das imagens enviadas: margem [dB] por longitude
# e por criterio. Valores aproximados, estimados visualmente a partir do
# grafico; ajuste os numeros se quiser maior precisao.
# Chave = label do criterio (mesmo de PROTECTION_CRITERIA).
_REF_LONS = [-150, -136.5, -123, -109.5, -96, -82.5, -69, -55.5, -42, -28.5, -15]

REFERENCE_8x8 = {
    "-10.5 dB": dict(zip(_REF_LONS, [-15, -23, -21.5, -13, -11.5, -12, 2.5, 3, 2, 1.5, -9])),
    "-6 dB":    dict(zip(_REF_LONS, [-11, -19, -17, -9, -7.5, -7.5, 6.5, 7, 6, 5.5, -5])),
    "-7 dB":    dict(zip(_REF_LONS, [-12, -20, -18, -10, -8.5, -8.5, 6, 6, 5.5, 5, -6])),
}
REFERENCE_8x16 = {
    "-10.5 dB": dict(zip(_REF_LONS, [-15, -23, -21.5, -13, -11.5, -12, 2.5, 3, 2, 1.5, -9])),
    "-6 dB":    dict(zip(_REF_LONS, [-11, -19, -17, -9, -7.5, -7.5, 6.5, 7, 6, 5.5, -5])),
    "-7 dB":    dict(zip(_REF_LONS, [-12, -20, -18, -10, -8.5, -8.5, 6, 6, 5.5, 5, -6])),
}

# Ordem/cores das curvas (igual a imagem: P80 azul, P99.97 laranja, P99.9 verde).
_MARGIN_ORDER = ["-10.5 dB", "-6 dB", "-7 dB"]
_MARGIN_COLORS = {"-10.5 dB": "#1f77b4", "-6 dB": "#ff7f0e", "-7 dB": "#2ca02c"}


def compute_margin_by_longitude(
    target_array: int, target_bw: int,
) -> Dict[str, Dict[float, float]]:
    """
    margem[label][longitude] = limiar - INR(percentil), via 2o Monte Carlo
    (urbano + suburbano), usando TODAS as amostras disponiveis.
    """
    latest = find_latest_dirs(target_array, target_bw)
    longitudes = sorted({lon for (_env, lon) in latest})
    margins: Dict[str, Dict[float, float]] = {c["label"]: {} for c in PROTECTION_CRITERIA}

    for sss_longitude in longitudes:
        urban_dir = latest.get(("urban", sss_longitude))
        suburban_dir = latest.get(("suburban", sss_longitude))
        if urban_dir is None or suburban_dir is None:
            continue
        urban = read_samples_db(urban_dir / INR_FILE)
        suburban = read_samples_db(suburban_dir / INR_FILE)
        rng = np.random.default_rng(MC_SEED)
        inr = monte_carlo_aggregate_inr(
            urban, suburban, N_URBAN, N_SUBURBAN, MC_TRIALS, rng,
        )
        for criterion in PROTECTION_CRITERIA:
            value = inr_at_exceedance(inr, criterion["exceedance_probability"])
            margins[criterion["label"]][sss_longitude] = criterion["threshold_db"] - value

    return margins


def plot_margin_comparison_mpl(
    target_array: int, target_bw: int,
    reference: Dict[str, Dict[float, float]],
    title: str, out_path: Path,
) -> Path:
    """
    Grafico matplotlib no formato da imagem: margem x longitude.
      - linha CONTINUA + marcador quadrado = dados gerados (simulacao)
      - linha PONTILHADA = pontos extraidos da imagem (referencia)
    Uma cor por criterio (P80 azul, P99.97 laranja, P99.9 verde).
    """
    from matplotlib.lines import Line2D

    generated = compute_margin_by_longitude(target_array, target_bw)
    crit_by_label = {c["label"]: c for c in PROTECTION_CRITERIA}

    plt.rcParams.update({
        "font.family": "serif", "mathtext.fontset": "cm", "font.size": 11,
    })
    fig, ax = plt.subplots(figsize=(7.2, 4.4))

    for label in _MARGIN_ORDER:
        criterion = crit_by_label[label]
        color = _MARGIN_COLORS[label]
        pct = 100.0 * (1.0 - criterion["exceedance_probability"])
        leg = f"$P_{{{pct:g}}}$, Limiar: {criterion['threshold_db']:g} dB"

        gen = generated.get(label, {})
        if gen:
            gx = sorted(gen)
            ax.plot(gx, [gen[x] for x in gx], "-s", color=color,
                    markerfacecolor="none", markersize=6, label=leg)

        ref = reference.get(label, {})
        if ref:
            rx = sorted(ref)
            ax.plot(rx, [ref[x] for x in rx], ":s", color=color,
                    markerfacecolor="none", markersize=6)

    ax.set_title(title)
    ax.set_xlabel("Longitude SSS (°)")
    ax.set_ylabel("Margem de segurança (dB)")
    ax.grid(True, linestyle="--", alpha=0.4)

    leg1 = ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.add_artist(leg1)
    style_handles = [
        Line2D([0], [0], color="k", ls="-", marker="s", mfc="none", label="Base de dados"),
        Line2D([0], [0], color="k", ls=":", marker="s", mfc="none", label="DensPop"),
    ]
    ax.legend(handles=style_handles, loc="lower right", fontsize=9, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")          # PNG
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")  # PDF (vetorial)
    plt.close(fig)
    return out_path


# ================================================================
# Main
# ================================================================

def main() -> None:
    latest = find_latest_dirs()
    if not latest:
        raise RuntimeError(
            f"Nenhuma pasta array_{TARGET_ARRAY} / bw_{TARGET_BW} encontrada em {OUTPUT_DIR}"
        )

    longitudes = sorted({lon for (_env, lon) in latest})
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Comparacao margem x longitude: gerado (continuo) x imagem (pontilhado) ----
    def _save_and_open(path: Path):
        path = path.resolve()
        print(f"  -> {path}")
        if hasattr(os, "startfile"):
            try:
                os.startfile(str(path))  # abre o PNG no visualizador padrao (Windows)
            except Exception:
                pass

    print("Comparacoes (PNG) salvas em:")
    _save_and_open(plot_margin_comparison_mpl(
        8, 54, REFERENCE_8x8,
        "Largura de banda: 54 MHz, Arranjo: 8×8",
        PLOTS_DIR / "plot_results4_margin_cmp_8x8.png",
    ))
    try:
        _save_and_open(plot_margin_comparison_mpl(
            16, 54, REFERENCE_8x16,
            "Largura de banda: 54 MHz, Arranjo: 8×16",
            PLOTS_DIR / "plot_results4_margin_cmp_8x16.png",
        ))
    except Exception as exc:
        print(f"  (8x16 pulada: {exc})")

    print(
        f"array={TARGET_ARRAY}, bw={TARGET_BW} MHz | N_urb={N_URBAN}, "
        f"N_sub={N_SUBURBAN}, trials={MC_TRIALS}"
    )
    print(f"Casos (primeiras K amostras): {SAMPLE_COUNTS}")
    print(f"Longitudes encontradas: {longitudes}\n")

    outputs: List[Path] = []
    # INR agregado do 2o MC por (longitude, n_samples), reutilizado nos
    # graficos de margem.
    mc_inr: Dict[Tuple[float, int], np.ndarray] = {}
    # Amostras reais (sem 2o MC) por (longitude, n_samples), por ambiente.
    raw_urban: Dict[Tuple[float, int], np.ndarray] = {}
    raw_suburban: Dict[Tuple[float, int], np.ndarray] = {}

    for sss_longitude in longitudes:
        urban_dir = latest.get(("urban", sss_longitude))
        suburban_dir = latest.get(("suburban", sss_longitude))
        if urban_dir is None or suburban_dir is None:
            print(
                f"Pulando lon {sss_longitude:g}: faltou pasta "
                f"{'urbana' if urban_dir is None else 'suburbana'}."
            )
            continue

        curves: List[Tuple[int, np.ndarray, np.ndarray]] = []
        for n_samples in SAMPLE_COUNTS:
            urban_inr = read_samples_db(urban_dir / INR_FILE, max_n=n_samples)
            suburban_inr = read_samples_db(suburban_dir / INR_FILE, max_n=n_samples)
            raw_urban[(sss_longitude, n_samples)] = urban_inr
            raw_suburban[(sss_longitude, n_samples)] = suburban_inr

            # mesma semente por caso: isola o efeito do tamanho da amostra.
            rng = np.random.default_rng(MC_SEED)
            inr = monte_carlo_aggregate_inr(
                urban_inr, suburban_inr, N_URBAN, N_SUBURBAN, MC_TRIALS, rng,
            )
            mc_inr[(sss_longitude, n_samples)] = inr
            x, y = ccdf(inr)
            curves.append((n_samples, x, y))

            note = ""
            if urban_inr.size < n_samples or suburban_inr.size < n_samples:
                note = (
                    f"  [aviso: disponiveis urb={urban_inr.size}, "
                    f"sub={suburban_inr.size} < {n_samples}]"
                )
            p50 = float(np.nanpercentile(inr, 50)) if inr.size else float("nan")
            print(
                f"lon={sss_longitude:7g}, K={n_samples:5d}: "
                f"INR mediano={p50:7.3f} dB{note}"
            )

        fig = plot_ccdf_for_longitude(sss_longitude, curves)
        lon_tag = f"{sss_longitude:g}".replace("-", "m").replace(".", "p")
        out = PLOTS_DIR / (
            f"plot_results4_ccdf_array{TARGET_ARRAY}_bw{TARGET_BW}_lon_{lon_tag}.html"
        )
        fig.write_html(out)
        if SHOW_CCDF:
            fig.show()
        outputs.append(out)
        print("")

    # ---- 3 graficos de margem x longitude (um por criterio, 3 curvas cada) ----
    for criterion in PROTECTION_CRITERIA:
        margin_fig = plot_margin_by_longitude(mc_inr, longitudes, criterion)
        safe = (
            f"{criterion['threshold_db']:g}".replace("-", "m").replace(".", "p")
        )
        out = PLOTS_DIR / (
            f"plot_results4_margin_array{TARGET_ARRAY}_bw{TARGET_BW}_th_{safe}.html"
        )
        margin_fig.write_html(out)
        margin_fig.show()
        outputs.append(out)

    # ---- 1 figura: CCDFs do 2o MC, todas as longitudes (cor=lon, traco=K) ----
    fig_all = plot_ccdf_all_longitudes(
        mc_inr, longitudes,
        title=(
            f"CCDF INR - 2o MC, todas as longitudes | array {TARGET_ARRAY}, "
            f"BW {TARGET_BW} MHz<br><sup>cor = longitude, traço = nº de amostras | "
            f"N_urb={N_URBAN}, N_sub={N_SUBURBAN}, trials={MC_TRIALS}</sup>"
        ),
        show_criteria=True,
    )
    out = PLOTS_DIR / (
        f"plot_results4_ccdf_all_lon_array{TARGET_ARRAY}_bw{TARGET_BW}.html"
    )
    fig_all.write_html(out)
    fig_all.show()
    outputs.append(out)

    # ---- 2 figuras: CCDFs das AMOSTRAS REAIS (sem 2o MC), urbano e suburbano ----
    for env_name, env_data in (("urbano", raw_urban), ("suburbano", raw_suburban)):
        fig_raw = plot_ccdf_all_longitudes(
            env_data, longitudes,
            title=(
                f"CCDF INR - amostras reais ({env_name}), sem 2o MC | "
                f"array {TARGET_ARRAY}, BW {TARGET_BW} MHz"
                f"<br><sup>cor = longitude, traço = nº de amostras</sup>"
            ),
            show_criteria=False,
        )
        out = PLOTS_DIR / (
            f"plot_results4_ccdf_raw_{env_name}_array{TARGET_ARRAY}_bw{TARGET_BW}.html"
        )
        fig_raw.write_html(out)
        fig_raw.show()
        outputs.append(out)

    print("Plots salvos:")
    for out in outputs:
        print(f"  {out}")


if __name__ == "__main__":
    main()
