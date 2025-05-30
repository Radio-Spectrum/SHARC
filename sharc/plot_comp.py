import os
from pathlib import Path
from sharc.results import Results, SampleList
from sharc.post_processor import PostProcessor
import plotly.graph_objects as go
from sharc.parameters.parameters import Parameters
import glob
import numpy as np
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt, PlotAntennaPattern

# Define o diretório base da campanha
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())
dl_dir = os.path.join(campaign_base_dir, "output_dl")
ul_dir = os.path.join(campaign_base_dir, "output_ul")

base_dir_stationD = str((Path(__file__) / ".." / ".." / "..").resolve())
dl_dir_stationD = os.path.join(base_dir_stationD, "imt_micro_fss_ss_stationD/output_dl")
ul_dir_stationD = os.path.join(base_dir_stationD, "imt_micro_fss_ss_stationD/output_ul")


# Inicializa o pós-processador
post_processor = PostProcessor()

# Função para gerar legendas com base no nome do diretório
import re

def legend_gen(dir_name):
    link = re.search("_(dl|ul)", dir_name)
    if link is not None:
        link = link.group(1)
    else:
        return "None"
    
    station = re.search("_(stationD|stationJ)", dir_name)
    if station is not None:
        station = station.group(1)
        if station == "stationD":
            station = "Station D"
        elif station == "stationJ":
            station = "Station J"
    else:
        return "None"
    return f"{link.upper()} - {station}"

post_processor.add_plot_legend_generator(legend_gen)

# Atributos a serem plotados
attributes_to_plot = [
    "system_inr"
]

# Carrega os resultados para diferentes cenários
dl_satJ = Results.load_many_from_dir(
    dl_dir, only_latest=True,
    only_samples=attributes_to_plot
)

ul_satJ = Results.load_many_from_dir(
    ul_dir, only_latest=True,
    only_samples=attributes_to_plot
)

dl_satD = Results.load_many_from_dir(
    dl_dir_stationD, only_latest=True,
    only_samples=attributes_to_plot
)

ul_satD = Results.load_many_from_dir(
    ul_dir_stationD, only_latest=True,
    only_samples=attributes_to_plot
)

# Combina todos os resultados em uma única lista
all_results = [
    *dl_satJ,
    *ul_satJ,
    *dl_satD,
    *ul_satD,
]

# Adiciona os resultados ao pós-processador
post_processor.add_results(all_results)

# Gera e adiciona gráficos CCDF e CDF ao pós-processador
post_processor.add_plots(
    post_processor.generate_ccdf_plots_from_results(
        all_results,
        cutoff_percentage=0.0001
    )
)

post_processor.add_plots(
    post_processor.generate_cdf_plots_from_results(
        all_results
    )
)

# Lista de atributos para adicionar linhas de critério de proteção
plots_to_add_vline = [
    "system_inr"
]

# Critérios de proteção: linha horizontal, linha vertical, estilo tracejado
interf_protection_criteria = {
    "Protection criterion [-6 dB, 0.03%]": [0.0003, -6, "dash", "gray"],
    "Protection criterion [-7 dB, 0.1%]": [0.001, -7, "dot", "gray"],
    "Protection criterion [-10.5 dB, 20%]": [0.2, -10.5, "dashdot", "gray"]
}

def add_protection_criteria(fig: go.Figure, interf_protection_criteria: dict) -> go.Figure:
    """
    Adiciona linhas de critério de proteção ao gráfico.
    
    Parâmetros:
    - fig: go.Figure -> Gráfico Plotly onde as linhas serão adicionadas.
    - interf_protection_criteria: dict -> Dicionário com critérios de proteção.
    """
    for legend_crite, val_crite in interf_protection_criteria.items():
        # Adiciona a linha vertical
        fig.add_trace(
            go.Scatter(
                x=[val_crite[1], val_crite[1]],
                y=[0, 1],
                mode='lines',
                line=dict(dash=val_crite[2], color=val_crite[3]),
                name=legend_crite,
                showlegend=True
            )
        )

        # Adiciona a linha horizontal, se aplicável
        if val_crite[0] is not None:
            fig.add_hline(
                y=val_crite[0],
                line_dash=val_crite[2],
                line_color=val_crite[3],
            )

    return fig

def adjust_range_x(fig: go.Figure) -> go.Figure:
    """
    Ajusta automaticamente o eixo X do gráfico para melhor visualização.
    
    Parâmetros:
    - fig: go.Figure -> Gráfico Plotly a ser ajustado.
    """
    lim = fig.full_figure_for_development(warn=False)
    min_x_auto = lim.layout.xaxis.range[0] if lim.layout.xaxis.range else None
    max_x_auto = lim.layout.xaxis.range[1] if lim.layout.xaxis.range else None

    if min_x_auto is not None and max_x_auto is not None:
        fig.update_layout(xaxis=dict(range=[min_x_auto - 1, max_x_auto+1]))

    return fig

# Adiciona critérios de proteção aos gráficos selecionados
for prop_name in plots_to_add_vline:
    for plot_type in ["cdf", "ccdf"]:
        plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type=plot_type)
        if plt:
            plt = add_protection_criteria(plt, interf_protection_criteria)
            plt = adjust_range_x(plt)

# Gera gráficos agregados para interferencia
system_dl_inr_plot = post_processor.get_plot_by_results_attribute_name("system_inr")
system_ul_inr_plot = post_processor.get_plot_by_results_attribute_name("system_inr")

aggregated_plot = go.Figure()
aggregated_ccdf_plot = go.Figure()

if system_ul_inr_plot and system_dl_inr_plot:
    cutoff_percentage = 0.0001
    next_tick = 1
    ticks_major = []
    ticks_minor = []

    current_tick = next_tick
    while current_tick > cutoff_percentage:
        ticks_major.append(current_tick)
        # Generate minor ticks for the current major interval:
        # They range from 10% to 90% of the current major value (step 10%)
        minor_ticks_for_interval = [current_tick * i for i in np.arange(1, .1, -0.1)]
        ticks_minor.extend(minor_ticks_for_interval)
                
        # Divide the current major tick by 10 for the next iteration
        current_tick /= 10  

    ticks_major.append(cutoff_percentage)
    ticks_major.reverse()
    ticks_minor.append(cutoff_percentage)
    ticks_minor.reverse()
            # Create tick labels so that only major ticks are labeled
    all_ticks = np.sort(np.unique(np.concatenate((ticks_major, ticks_minor))))
    ticktext = [str(tick) if tick in ticks_major else "" for tick in all_ticks]

    # Create tick labels so that only major ticks are labeled
    all_ticks = np.sort(np.unique(np.concatenate((ticks_major, ticks_minor))))
    ticktext = [f'10<sup><span style="font-size: 1.2em;">{int(np.floor(np.log10(tick)))}</span></sup>' if tick in ticks_major else "" for tick in all_ticks]


    aggregated_plot.update_layout(
                        title=f'Aggregated CDF Plot for system Station J receveid interference from Micro IMT at 8150 MHz',
                        xaxis_title="Interference Power [dBm/MHz]",
                        yaxis_title="$\\text{P } (X > x)$",
                        yaxis=dict(tickmode="array", tickvals=[0, 0.25, 0.5, 0.75, 1]),
                        xaxis=dict(tickmode="linear", dtick=5),
                        legend_title="Labels",
                        meta={"plot_type": "cdf"},
                    )
    
    aggregated_ccdf_plot.update_layout(
                        # title=f'Aggregated CCDF Plot for system Station J receveid interference from Micro IMT at 8150 MHz',
                        xaxis_title="INR [dB]",
                        yaxis_title="$\\text{P } I > X$",
                        yaxis=dict(tickmode="array", tickvals=all_ticks, type="log",
                                   range=[np.log10(cutoff_percentage), 0],
                                   ticktext=ticktext,
                                   gridcolor="lightgray",
                                   gridwidth=.5,
                                   griddash="dot"
                                   ),
                        xaxis=dict(tickmode="linear",
                                   dtick=5,
                                   gridcolor="lightgray",
                                   gridwidth=.5,
                                   griddash="dot"
                                   ),
                        # legend_title="Labels",
                        meta={"plot_type": "ccdf"},
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        font=dict(
                            family="Arial, sans-serif",
                            size=16,         # Base font size for all text
                            color="black"    # Text color
                        ),
                        shapes=[
                            dict(
                                type="rect",
                                xref="paper",
                                yref="paper",
                                x0=0,
                                y0=cutoff_percentage,
                                x1=1,
                                y1=1,
                                line=dict(
                                    color="black",
                                    width=1
                                ),
                                fillcolor="rgba(0,0,0,0)"  # transparent fill
                            )
                        ],
                        legend=dict(
                            x=0.9,          # x position (95% from the left)
                            y=0.8,          # y position (95% from the bottom)
                            xanchor='right', # anchor the legend's right side at x=0.95
                            yanchor='top',   # anchor the legend's top at y=0.95
                            bgcolor='rgba(255,255,255,0.5)',  # Optional: semi-transparent white background
                            bordercolor='black',              # Optional: border color for better separation
                            borderwidth=1                     # Optional: border width in pixels
                        )
                    )
    

   # Acessa os resultados diretamente
    dl_satJ_r = dl_satJ[0]
    ul_satJ_r = ul_satJ[0]

    dl_satD_r = dl_satD[0]
    ul_satD_r = ul_satD[0]

    if None in [dl_satJ_r, ul_satJ_r, dl_satD_r, ul_satD_r]:
        raise Exception("Cannot aggregate results")

    n_bs_sim = 19 * 3 * 3 * 7
    area = 8515767  # Área do Brasil em km²

    # NOTE: From Table 13 Annex 4.15 for micro cells
    ra_urban = np.array([.05, .1])  # ra1, ra2 urbano micro
    rb = np.array([.01, .05]) if area < 3500000 else np.array([.01, .03])

    legenda = "Ra2Rb1"
    
    # Deployment density for IMT BS (BS/km²)
    # NOTE: From Table 13 Annex 4.15 for micro cells
    ds_urb = 30

    aggregated_results_satJ_ra1rb1 = PostProcessor.aggregate_results(
        dl_samples=dl_satJ_r.system_inr,
        ul_samples=ul_satJ_r.system_inr,
        ul_tdd_factor=0.25,
        n_bs_sim=n_bs_sim,
        n_bs_actual=166500,
        n_drops=100000
    )

    aggregated_results_satJ_ra2rb1 = PostProcessor.aggregate_results(
        dl_samples=dl_satJ_r.system_inr,
        ul_samples=ul_satJ_r.system_inr,
        ul_tdd_factor=0.25,
        n_bs_sim=n_bs_sim,
        n_bs_actual=303310,
        n_drops=100000
    )

    aggregated_results_satD_ra1rb1 = PostProcessor.aggregate_results(
        dl_samples=dl_satD_r.system_inr,
        ul_samples=ul_satD_r.system_inr,
        ul_tdd_factor=0.25,
        n_bs_sim=n_bs_sim,
        n_bs_actual=166500,
        n_drops=10000
    )

    aggregated_results_satD_ra2rb1 = PostProcessor.aggregate_results(
        dl_samples=dl_satD_r.system_inr,
        ul_samples=ul_satD_r.system_inr,
        ul_tdd_factor=0.25,
        n_bs_sim=n_bs_sim,
        n_bs_actual=303310,
        n_drops=10000
    )

    x, y = PostProcessor.ccdf_from(aggregated_results_satD_ra1rb1)
    aggregated_ccdf_plot.add_trace(
        go.Scatter(x=x, y=y, mode='lines', line=dict(dash="dash", color="blue"), name="Ra1Rb1 - station D"),
    )

    x, y = PostProcessor.ccdf_from(aggregated_results_satD_ra2rb1)
    aggregated_ccdf_plot.add_trace(
        go.Scatter(x=x, y=y, mode='lines', line=dict(dash="solid", color="blue"), name="Ra2Rb1 - station D"),
    )

    x, y = PostProcessor.ccdf_from(aggregated_results_satJ_ra1rb1)
    aggregated_ccdf_plot.add_trace(
        go.Scatter(x=x, y=y, mode='lines', line=dict(dash="dash", color="red"), name="Ra1Rb1 - station J"),
    )

    x, y = PostProcessor.ccdf_from(aggregated_results_satJ_ra2rb1)
    aggregated_ccdf_plot.add_trace(
        go.Scatter(x=x, y=y, mode='lines', line=dict(dash="solid", color="red"), name="Ra2Rb1 - station J"),
    )

aggregated_ccdf_plot = add_protection_criteria(aggregated_ccdf_plot, interf_protection_criteria)
aggregated_ccdf_plot = adjust_range_x(aggregated_ccdf_plot)

# plots = [*post_processor.plots, aggregated_plot, aggregated_ccdf_plot]
# plots = [*post_processor.plots, aggregated_ccdf_plot]
# plots = [*post_processor.plots]
plots = [aggregated_ccdf_plot]

PostProcessor.save_plots(
    os.path.join(campaign_base_dir, "output"),
    plots,
    width=1200, height=800,
)

# for plot in plots:
#     plot.show()