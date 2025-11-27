import os
import pandas as pd
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
    
    t = re.search("_((sub){0,1}urban)", dir_name)
    if t is not None:
        t = t.group(1)
    else:
        return "None"
    
    return f"{link.upper()} {t.capitalize()} "

post_processor.add_plot_legend_generator(legend_gen)

# Atributos a serem plotados
attributes_to_plot = [
    #"system_imt_antenna_gain",
    #"imt_system_path_loss",
    #"imt_system_antenna_gain",
    "system_dl_interf_power_per_mhz",
    "system_ul_interf_power_per_mhz",
]

# Função para filtrar resultados com base no tipo de ambiente (urbano/suburbano)
def filter_fn(result_dir: str, is_suburban: bool) -> bool:
    sub = "_suburban" if is_suburban else "_urban"
    return sub in result_dir

# Carrega os resultados para diferentes cenários
dl_urban_results = Results.load_many_from_dir(
    dl_dir, only_latest=False,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, False)
)

dl_suburban_results = Results.load_many_from_dir(
    dl_dir, only_latest=False,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, True)
)

ul_urban_results = Results.load_many_from_dir(
    ul_dir, only_latest=False,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, False)
)

ul_suburban_results = Results.load_many_from_dir(
    ul_dir, only_latest=False,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, True)
)

#print(dl_urban_results[1].system_dl_interf_power_per_mhz)

# Combina todos os resultados em uma única lista
all_results = [
    *dl_urban_results,
    *dl_suburban_results,
    *ul_urban_results,
    *ul_suburban_results
]

#print(all_results)

# transforming dBm / MHz to dB / kHz
# dBm -> dB means -30
# /MHz -> /kHz means -30
for result in all_results:
    result.system_dl_interf_power_per_mhz = SampleList(
        np.array(result.system_dl_interf_power_per_mhz) - 30 - 30
    )
    result.system_ul_interf_power_per_mhz = SampleList(
        np.array(result.system_ul_interf_power_per_mhz) - 30 - 30
    )

# Adiciona os resultados ao pós-processador
post_processor.add_results(all_results)

# Gera e adiciona gráficos CCDF e CDF ao pós-processador
post_processor.add_plots(
    post_processor.generate_ccdf_plots_from_results(
        all_results,
        cutoff_percentage=0.001
    )
)

post_processor.add_plots(
    post_processor.generate_cdf_plots_from_results(
        all_results
    )
)

# Lista de atributos para adicionar linhas de critério de proteção
plots_to_add_vline = [
    "system_ul_interf_power_per_mhz",
    "system_dl_interf_power_per_mhz"
]

# Critérios de proteção: linha horizontal, linha vertical, estilo tracejado
interf_protection_criteria = {
    "Protection criterion [-161 dBW/kHz, 0.1%]": [0.001, -161, "dash"]
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
                line=dict(dash=val_crite[2], color="black"),
                name=legend_crite,
                showlegend=True
            )
        )

        # Adiciona a linha horizontal, se aplicável
        if val_crite[0] is not None:
            fig.add_hline(
                y=val_crite[0],
                line_dash=val_crite[2],
                line_color="black",
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
        fig.update_layout(xaxis=dict(range=[min_x_auto-5, max_x_auto+5]))

    return fig

#Salva um Sample List( nesse caso o agregado) como .csv , usando o nome e caminhos escolhido
def save_samplelist_as_csv(data, name: str, path: str):
    os.makedirs(path, exist_ok=True)
    df = pd.DataFrame({"samples": data})
    df.to_csv(os.path.join(path, name + ".csv"), index=False)

# Adiciona critérios de proteção aos gráficos selecionados
for prop_name in plots_to_add_vline:
    for plot_type in ["cdf", "ccdf"]:
        plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type=plot_type)
        if plt:
            plt = add_protection_criteria(plt, interf_protection_criteria)
            plt = adjust_range_x(plt)

# Gera gráficos agregados para interferencia
system_dl_interf_power_plot = post_processor.get_plot_by_results_attribute_name("system_dl_interf_power_per_mhz")
system_ul_interf_power_plot = post_processor.get_plot_by_results_attribute_name("system_ul_interf_power_per_mhz")
#print(system_dl_interf_power_plot,system_ul_interf_power_plot)

if system_ul_interf_power_plot and system_dl_interf_power_plot:
    cutoff_percentage = 0.001
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
    ticktext = [str(tick) if tick in ticks_major else "" for tick in all_ticks]

    aggregated_plot = go.Figure()
    aggregated_plot.update_layout(
        title=f'CDF Aggregated Plot for EESS Space Station receveid interference from Macro IMT in 7 216 MHz',
        xaxis_title="Interference [dBW/kHz]",
        yaxis_title="CDF",
        yaxis=dict(tickmode="array", tickvals=[0, 0.25, 0.5, 0.75, 1]),
        xaxis=dict(tickmode="linear", dtick=5),
        legend_title="Labels",
        meta={"related_results_attribute": "Aggregated", "plot_type": "cdf"},
    )

    aggregated_ccdf_plot = go.Figure()
    aggregated_ccdf_plot.update_layout(
                title=f'CCDF Aggregated Plot for EESS Space Station receveid interference from Macro IMT in 7 216 MHz',
                xaxis_title="Interference [dBW/kHz]",
                yaxis_title="$\\text{P } I > X$",
                yaxis=dict(tickmode="array", tickvals=all_ticks, type="log",
                        range=[np.log10(cutoff_percentage-cutoff_percentage/4), 0],
                        ticktext=ticktext,
                        gridcolor="lightgray",
                        gridwidth=.5,
                        griddash="dot",
                        ),
                xaxis=dict(tickmode="linear",
                        dtick=5,
                        gridcolor="lightgray",
                        gridwidth=.5,
                        griddash="dot"
                        ),
                legend_title="Labels",
                meta={"related_results_attribute": "Aggregated", "plot_type": "ccdf"},
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
                    x=0.82,          # x position (95% from the left)
                    y=0.95,          # y position (95% from the bottom)
                    xanchor='right', # anchor the legend's right side at x=0.95
                    yanchor='top',   # anchor the legend's top at y=0.95
                    bgcolor='rgba(255,255,255,0.5)',  # Optional: semi-transparent white background
                    bordercolor='black',              # Optional: border color for better separation
                    borderwidth=1                     # Optional: border width in pixels
                )
            )

    #Aumentando os tamanhos das fontes 

    aggregated_ccdf_plot.update_layout(
        legend=dict(
            font=dict(
                size=22,  # Tamanho da fonte da legenda
                family="Arial, sans-serif"
            ),
        )
    )

    aggregated_ccdf_plot.update_layout(
        xaxis=dict(
            tickfont=dict(size=22),  # Tamanho dos ticks do eixo x
        ),
        yaxis=dict(
            tickfont=dict(size=22),  # Tamanho dos ticks do eixo y
        )
    )
    #Aumentando os tamanhos das fontes 

    aggregated_ccdf_plot.update_layout(
        legend=dict(
            font=dict(
                size=22,  # Tamanho da fonte da legenda
                family="Arial, sans-serif"
            ),
        )
    )

    aggregated_ccdf_plot.update_layout(
        xaxis_title_font=dict(
            size=24, # Tamanho do label do eixo x
            family="Arial, sans-serif"
        ),
        yaxis_title_font=dict(
            size=24, # Tamanho do label do eixo y
            family="Arial, sans-serif"
        )
    )
    

   # Acessa os resultados diretamente
    dl_urb_r = dl_urban_results[0]
    ul_urb_r = ul_urban_results[0]
    ul_sub_r = ul_suburban_results[0]
    dl_sub_r = dl_suburban_results[0]

    if None in [dl_sub_r, ul_sub_r, ul_urb_r]:
        raise Exception("Cannot aggregate results")


    # Parece que o calculo mudou depois rever o calculo ( por equanto uso o valor de BS's caçculadas externamente)
    n_bs_sim = 19 * 3 * 3 * 7 #1179 

    #Numero de BS calculadas com seus respectivos metodos (Ra1Rb1 e Ra2Rb1)
    n_bs = {"Ra1Rb1":{"n_bs_actual_urban":121000,"n_bs_actual_suburban":13320},
            "Ra2Rb1":{"n_bs_actual_urban":454970,"n_bs_actual_suburban":48530}}

    for legenda_nbs in n_bs.keys():

        n_bs_actual_urban = n_bs[legenda_nbs]["n_bs_actual_urban"]
        n_bs_actual_suburban = n_bs[legenda_nbs]["n_bs_actual_suburban"]

        print(f"{legenda_nbs} : N_bs_urban = {n_bs_actual_urban} - N_bs_suburban = {n_bs_actual_suburban}")

        aggregated_results_urb = PostProcessor.aggregate_results(
            dl_samples=dl_urb_r.system_dl_interf_power_per_mhz,
            ul_samples=ul_urb_r.system_ul_interf_power_per_mhz,
            ul_tdd_factor=0.25,
            n_bs_sim=n_bs_sim,
            n_bs_actual=n_bs_actual_urban
        )

        aggregated_results_sub = PostProcessor.aggregate_results(
            dl_samples=dl_sub_r.system_dl_interf_power_per_mhz,
            ul_samples=ul_sub_r.system_ul_interf_power_per_mhz,
            ul_tdd_factor=0.25,
            n_bs_sim=n_bs_sim,
            n_bs_actual=n_bs_actual_suburban
        )


        min_length = min(len(aggregated_results_sub), len(aggregated_results_urb))
        aggregated_results = 10**(aggregated_results_sub[:min_length]/10) + 10**(aggregated_results_urb[:min_length]/10)
        aggregated_results = 10 * np.log10(aggregated_results)

        save_samplelist_as_csv(aggregated_results, f"aggregated_system_interf_power_per_mhz_macro_EESS_{legenda_nbs}", os.path.join(campaign_base_dir, "output"))
        save_samplelist_as_csv(aggregated_results_urb, f"aggregated_system_interf_power_per_mhz_macro_urban_EESS_{legenda_nbs}", os.path.join(campaign_base_dir, "output"))
        save_samplelist_as_csv(aggregated_results_sub, f"aggregated_system_interf_power_per_mhz_macro_suburban_EESS_{legenda_nbs}", os.path.join(campaign_base_dir, "output"))
        
        x, y = PostProcessor.cdf_from(aggregated_results,n_bins=200)
        aggregated_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=legenda_nbs),
        )

        x, y = PostProcessor.ccdf_from(aggregated_results,n_bins=200)
        aggregated_ccdf_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=legenda_nbs),
        )

    aggregated_plot = add_protection_criteria(aggregated_plot, interf_protection_criteria)
    aggregated_ccdf_plot = add_protection_criteria(aggregated_ccdf_plot, interf_protection_criteria)
    aggregated_plot = adjust_range_x(aggregated_plot)
    aggregated_ccdf_plot = adjust_range_x(aggregated_ccdf_plot)
    # Não quero cdf's tirei o aggregated_plot "

# Salva os gráficos 
PostProcessor.save_plots(
    os.path.join(campaign_base_dir, "output", "1200x1200"),
    [*post_processor.plots, aggregated_ccdf_plot],
    width=1200, height=1200,
)
PostProcessor.save_plots(
    os.path.join(campaign_base_dir, "output", "1200x800"),
    [*post_processor.plots, aggregated_ccdf_plot],
    width=1200, height=800,
)

# Exibe o gráfico CCDF agregado
aggregated_ccdf_plot.show()