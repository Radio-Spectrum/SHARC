import glob
import os
from pathlib import Path

import plotly.graph_objects as go

from sharc.antenna.antenna_beamforming_imt import (AntennaBeamformingImt,
                                                   PlotAntennaPattern)
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.parameters.parameters import Parameters
from sharc.post_processor import PostProcessor
from sharc.results import Results

# Definição do diretório base da campanha FS
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())
dl_dir = os.path.join(campaign_base_dir, "output_dl")
ul_dir = os.path.join(campaign_base_dir, "output_ul")

post_processor = PostProcessor()

# Adiciona legendas para cada ângulo de azimute (DL e UL)
for azimuth in range(10, 181, 10):  # De 10 até 180 graus
    post_processor.add_plot_legend_pattern(
        dir_name_contains=f"output_fs_dl_{azimuth}deg",
        legend=f"FS System DL ({azimuth}°)"
    ).add_plot_legend_pattern(
        dir_name_contains=f"output_fs_ul_{azimuth}deg",
        legend=f"FS System UL ({azimuth}°)"
    )
# Atributos a serem plotados
attributes_to_plot = [
    "system_fs_antenna_gain",
    "fs_system_path_loss",
    "fs_system_antenna_gain",
    "system_dl_interf_power_per_mhz",
    "system_ul_interf_power_per_mhz",
]

# Filtro para selecionar quais resultados carregar
def filter_fn(result_dir: str) -> bool:
    return True  # Mantendo todos os arquivos

# Carregando resultados para DL e UL
dl_results = Results.load_many_from_dir(dl_dir, only_latest=True, only_samples=attributes_to_plot, filter_fn=filter_fn)
ul_results = Results.load_many_from_dir(ul_dir, only_latest=True, only_samples=attributes_to_plot, filter_fn=filter_fn)

all_results = [*dl_results, *ul_results]

post_processor.add_results(all_results)

# Gerar gráficos CDF e CCDF
post_processor.add_plots(post_processor.generate_ccdf_plots_from_results(all_results))
post_processor.add_plots(post_processor.generate_cdf_plots_from_results(all_results))

# Critério de proteção
plots_to_add_vline = [
    "system_ul_interf_power_per_mhz",
    "system_dl_interf_power_per_mhz"
]
interf_protection_criteria = -154 + 30  # Conversão para dBm

for prop_name in plots_to_add_vline:
    for plot_type in ["cdf", "ccdf"]:
        plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type=plot_type)
        if plt:
            plt.add_vline(interf_protection_criteria, line_dash="dash", name="1% criteria")

# Agregação de resultados (TDD) para UL e DL combinados
system_dl_interf_power_plot = post_processor.get_plot_by_results_attribute_name("system_dl_interf_power_per_mhz")
system_ul_interf_power_plot = post_processor.get_plot_by_results_attribute_name("system_ul_interf_power_per_mhz")

aggregated_plot = None
if system_ul_interf_power_plot and system_dl_interf_power_plot:
    aggregated_plot = go.Figure()

    for dl_r in dl_results:
        legend1 = post_processor.get_results_possible_legends(dl_r)[0]
        ul_r = None
        for maybe in ul_results:
            legend2 = post_processor.get_results_possible_legends(maybe)[0]
            if legend1 == legend2:
                ul_r = maybe
                break
        if ul_r is None:
            continue  # Se não houver correspondência, ignora

        aggregated_results = PostProcessor.aggregate_results(
            dl_samples=dl_r.system_dl_interf_power,
            ul_samples=ul_r.system_ul_interf_power,
            ul_tdd_factor=0.25,
            n_bs_sim=1,
            n_bs_actual=1
        )
        x, y = PostProcessor.cdf_from(aggregated_results)

        aggregated_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'{legend1["legend"]}')
        )

    aggregated_plot.add_vline(interf_protection_criteria, line_dash="dash", name="1% criteria")

# Salvando gráficos na pasta correta
PostProcessor.save_plots(
    os.path.join(campaign_base_dir, "output_fs", "figs"),
    post_processor.plots,
)

if aggregated_plot:
    aggregated_plot.show()

# Geração de estatísticas dos resultados
full_results = ""

for result in all_results:
    stats = PostProcessor.generate_statistics(result=result).write_to_results_dir()
    full_results += str(stats) + "\n"

with open(dl_dir + "/stats.txt", "w") as f:
    f.write(full_results)
