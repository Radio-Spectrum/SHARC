"""
Post-processamento FSS 6 GHz gerado por generate_inputs2.py.

Este script faz um segundo Monte Carlo agregando duas pastas por caso:
uma urbana e uma suburbana. Em cada trial ele sorteia N amostras urbanas
e N2 amostras suburbanas de system_dl_interf_power.csv, soma as potencias
linearmente e converte para INR:

    INR [dB] = I_total [dBm] - 10*log10(k*T*B*1000)

onde T vem do YAML da simulacao quando disponivel e B e a largura de banda
do single_space_station em Hz.
"""

import csv
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import plotly.graph_objects as go


# ================================================================
# Configuracao
# ================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
CAMPAIGN_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = CAMPAIGN_DIR / "output_dl"
PLOTS_DIR = CAMPAIGN_DIR / "plots"

INTERFERENCE_FILE = "system_dl_interf_power.csv"

# Numero de trials do segundo Monte Carlo.
MC_TRIALS = 50000
MC_SEED = 12345

# Numero de amostras sorteadas por trial em cada ambiente.
# Ajuste estes dois valores para mudar a composicao urbano/suburbano.
N_total = 147000
pop_urb = 180
pup_remain = 35
N_URBAN = round(N_total / 500 * pop_urb / (pop_urb + pup_remain))
N_SUBURBAN = round(N_total / 500 * pup_remain / (pop_urb + pup_remain))

# Usado se nao for possivel ler o YAML copiado para a pasta de saida.
DEFAULT_NOISE_TEMPERATURE_K = 800.0

# Correcao temporaria: aplica fator bandwidth/100 na potencia em mW.
# Desligue quando o gerador ja escrever system_dl_interf_power corrigido.
APPLY_BW_OVER_100_CORRECTION = True

BOLTZMANN_CONSTANT = 1.38064852e-23

RESULT_DIR_RE = re.compile(
    r"^6G_(?P<env>urban|suburban)_array_(?P<array>\d+)_sss_bw_(?P<bw>\d+)_"
)


# ================================================================
# Leitura dos resultados
# ================================================================

def read_samples_dbm(csv_path: Path) -> np.ndarray:
    """Le a coluna samples de um CSV do SHARC."""
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

    samples = np.asarray(values, dtype=float)
    samples = samples[np.isfinite(samples)]
    if samples.size == 0:
        raise ValueError(f"Nenhuma amostra valida em {csv_path}")
    return samples


def find_latest_result_dirs() -> Dict[Tuple[str, int, int], Path]:
    """
    Retorna a pasta mais recente para cada (env, array, bandwidth).

    O nome esperado e:
      6G_urban_array_8_sss_bw_36_...
      6G_suburban_array_8_sss_bw_36_...
    """
    latest: Dict[Tuple[str, int, int], Path] = {}

    for path in OUTPUT_DIR.iterdir():
        if not path.is_dir():
            continue
        match = RESULT_DIR_RE.match(path.name)
        if not match:
            continue
        csv_path = path / INTERFERENCE_FILE
        if not csv_path.exists():
            continue

        key = (
            match.group("env"),
            int(match.group("array")),
            int(match.group("bw")),
        )
        previous = latest.get(key)
        if previous is None or path.stat().st_mtime > previous.stat().st_mtime:
            latest[key] = path

    return latest


def read_noise_temperature_k(result_dir: Path) -> float:
    """
    Le noise_temperature do YAML da simulacao, sem depender de parser YAML.

    Como o campo usado nesta campanha aparece dentro de single_space_station,
    fazemos uma varredura simples e limitada a essa secao.
    """
    yaml_files = sorted(result_dir.glob("6G_input_*.yaml"))
    if not yaml_files:
        return DEFAULT_NOISE_TEMPERATURE_K

    in_single_space_station = False
    for line in yaml_files[0].read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "single_space_station:":
            in_single_space_station = True
            continue
        if in_single_space_station and line and not line.startswith(" "):
            break
        if in_single_space_station and stripped.startswith("noise_temperature:"):
            raw = stripped.split(":", 1)[1].split("#", 1)[0].strip()
            try:
                return float(raw)
            except ValueError:
                break

    return DEFAULT_NOISE_TEMPERATURE_K


# ================================================================
# Segundo Monte Carlo
# ================================================================

def thermal_noise_dbm(temperature_k: float, bandwidth_mhz: float) -> float:
    bandwidth_hz = bandwidth_mhz * 1e6
    noise_mw = BOLTZMANN_CONSTANT * temperature_k * bandwidth_hz * 1000.0
    return 10.0 * math.log10(noise_mw)


def monte_carlo_aggregate_inr(
    urban_dbm: np.ndarray,
    suburban_dbm: np.ndarray,
    n_urban: int,
    n_suburban: int,
    n_trials: int,
    noise_dbm: float,
    bandwidth_mhz: float,
    rng: np.random.Generator,
) -> np.ndarray:
    if n_trials <= 0:
        return np.array([], dtype=float)
    if n_urban <= 0 and n_suburban <= 0:
        return np.array([], dtype=float)

    total_mw = np.zeros(n_trials, dtype=float)
    correction_factor = bandwidth_mhz / 100.0

    if n_urban > 0:
        urban_mw = (10.0 ** (urban_dbm / 10.0)) * correction_factor
        draws = rng.choice(urban_mw, size=(n_trials, n_urban), replace=True)
        total_mw += draws.sum(axis=1)

    if n_suburban > 0:
        suburban_mw = (10.0 ** (suburban_dbm / 10.0)) * correction_factor
        draws = rng.choice(suburban_mw, size=(n_trials, n_suburban), replace=True)
        total_mw += draws.sum(axis=1)

    total_mw[total_mw <= 0.0] = np.nan
    interference_dbm = 10.0 * np.log10(total_mw)
    return interference_dbm - noise_dbm


def ccdf(samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    clean = np.asarray(samples, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    x_sorted = np.sort(clean)
    y_ccdf = 1.0 - (np.arange(1, x_sorted.size + 1) / (x_sorted.size + 1.0))
    return x_sorted, y_ccdf


# ================================================================
# Plot
# ================================================================

def plot_ccdf(results: Dict[Tuple[int, int], np.ndarray]) -> go.Figure:
    fig = go.Figure()

    for (n_array, bandwidth_mhz), inr in sorted(results.items()):
        x, y = ccdf(inr)
        if x.size == 0:
            continue
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=f"array {n_array}, BW {bandwidth_mhz} MHz",
            )
        )

    def add_limited_vline(x_value: float, y_bottom: float, label: str) -> None:
        fig.add_trace(
            go.Scatter(
                x=[x_value, x_value],
                y=[1.0, y_bottom],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=label,
                showlegend=False,
                hovertemplate=f"{label}<br>CCDF: %{{y:.4g}}<extra></extra>",
            )
        )
        fig.add_annotation(
            x=x_value,
            y=1.0,
            text=label,
            showarrow=False,
            yshift=10,
            textangle=-90,
        )

    add_limited_vline(-10.5, 0.2, "-10 dB")
    add_limited_vline(-7.0, 0.001, "-7 dB")
    add_limited_vline(-6.0, 0.0003, "-6 dB")

    fig.update_layout(
        title=(
            "CCDF INR - segundo Monte Carlo urbano + suburbano "
            f"(N={N_URBAN}, N2={N_SUBURBAN})"
        ),
        xaxis_title="INR [dB]",
        yaxis_title="CCDF",
        yaxis_type="log",
        yaxis_range=[-4, 0],
        template="plotly_white",
        legend_title="Caso",
    )
    return fig


def print_summary(results: Dict[Tuple[int, int], np.ndarray]) -> None:
    print("Resumo do segundo Monte Carlo:")
    print(f"  trials: {MC_TRIALS}")
    print(f"  N urbano: {N_URBAN}")
    print(f"  N2 suburbano: {N_SUBURBAN}")
    print("")

    for (n_array, bandwidth_mhz), inr in sorted(results.items()):
        clean = inr[np.isfinite(inr)]
        if clean.size == 0:
            continue
        p50, p95, p99 = np.percentile(clean, [50, 95, 99])
        print(
            f"array={n_array:2d}, bw={bandwidth_mhz:2d} MHz: "
            f"media={np.mean(clean):8.3f} dB, "
            f"p50={p50:8.3f} dB, p95={p95:8.3f} dB, p99={p99:8.3f} dB"
        )


def main() -> None:
    latest_dirs = find_latest_result_dirs()
    rng = np.random.default_rng(MC_SEED)

    available_cases = sorted(
        {
            (n_array, bandwidth_mhz)
            for env, n_array, bandwidth_mhz in latest_dirs
            if env in {"urban", "suburban"}
        }
    )

    mc_results: Dict[Tuple[int, int], np.ndarray] = {}

    for n_array, bandwidth_mhz in available_cases:
        urban_dir = latest_dirs.get(("urban", n_array, bandwidth_mhz))
        suburban_dir = latest_dirs.get(("suburban", n_array, bandwidth_mhz))
        if urban_dir is None or suburban_dir is None:
            print(
                f"Pulando array={n_array}, bw={bandwidth_mhz}: "
                "faltou pasta urbana ou suburbana."
            )
            continue

        urban_samples = read_samples_dbm(urban_dir / INTERFERENCE_FILE)
        suburban_samples = read_samples_dbm(suburban_dir / INTERFERENCE_FILE)
        temperature_k = read_noise_temperature_k(urban_dir)
        noise_dbm = thermal_noise_dbm(temperature_k, bandwidth_mhz)

        inr = monte_carlo_aggregate_inr(
            urban_dbm=urban_samples,
            suburban_dbm=suburban_samples,
            n_urban=N_URBAN,
            n_suburban=N_SUBURBAN,
            n_trials=MC_TRIALS,
            noise_dbm=noise_dbm,
            bandwidth_mhz=bandwidth_mhz,
            rng=rng,
        )
        mc_results[(n_array, bandwidth_mhz)] = inr

        print(
            f"OK array={n_array}, bw={bandwidth_mhz} MHz: "
            f"urban='{urban_dir.name}', suburban='{suburban_dir.name}', "
            f"T={temperature_k:g} K, N={noise_dbm:.3f} dBm"
        )

    if not mc_results:
        raise RuntimeError("Nenhum par urbano/suburbano encontrado para plotar.")

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig = plot_ccdf(mc_results)
    output_html = PLOTS_DIR / "plot_results4_inr_mc_urban_suburban.html"
    fig.write_html(output_html)
    fig.show()

    print("")
    print_summary(mc_results)
    print("")
    print(f"Plot salvo em: {output_html}")


if __name__ == "__main__":
    main()
