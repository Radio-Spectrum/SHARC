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
    
    # t = re.search("_((sub){0,1}urban)", dir_name)
    # if t is not None:
    #     t = t.group(1)
    # else:
    #     return "None"
    
    return f"{link.upper()}"

post_processor.add_plot_legend_generator(legend_gen)

# Atributos a serem plotados
attributes_to_plot = [
    "imt_ul_inr",
    "imt_dl_inr",
    # "system_dl_interf_power_per_mhz",
    # "system_ul_interf_power_per_mhz",
    "system_inr"
    # "imt_system_path_loss",
    # "system_imt_antenna_gain",
    # "imt_system_antenna_gain"
]

# Função para filtrar resultados com base no tipo de ambiente (urbano/suburbano)
# def filter_fn(result_dir: str, is_suburban: bool) -> bool:
#     sub = "_suburban" if is_suburban else "_urban"
#     return "MSS" in result_dir and sub in result_dir

# Carrega os resultados para diferentes cenários
# dl_urban_results = Results.load_many_from_dir(
#     dl_dir, only_latest=True,
#     only_samples=attributes_to_plot,
#     filter_fn=lambda x: filter_fn(x, False)
# )

dl_results = Results.load_many_from_dir(
    dl_dir, only_latest=True,
    only_samples=attributes_to_plot
)

# ul_urban_results = Results.load_many_from_dir(
#     ul_dir, only_latest=True,
#     only_samples=attributes_to_plot,
#     filter_fn=lambda x: filter_fn(x, False)
# )

ul_results = Results.load_many_from_dir(
    ul_dir, only_latest=True,
    only_samples=attributes_to_plot
)

print('Carregou resultados')

# Combina todos os resultados em uma única lista
all_results = [
    *dl_results,
    *ul_results
]

# Converte os valores de INR para SampleList
for result in all_results:
    result.system_inr = SampleList(np.array(result.system_inr))

# Adiciona os resultados ao pós-processador
post_processor.add_results(all_results)

ccdf = post_processor.generate_ccdf_plots_from_results(
        all_results,
        cutoff_percentage=0.00001
    )
cdf = post_processor.generate_cdf_plots_from_results(
        all_results,
    )
# Gera e adiciona gráficos CCDF e CDF ao pós-processador
post_processor.add_plots(
    post_processor.generate_ccdf_plots_from_results(
        all_results,
        cutoff_percentage=0.00001
    )
)

post_processor.add_plots(
    post_processor.generate_cdf_plots_from_results(
        all_results,
    )
)
print("Adicionou plots")

# Lista de atributos para adicionar linhas de critério de proteção
plots_to_add_vline = [
    "system_inr",
    "imt_ul_inr",
    "imt_dl_inr",
]

# Critérios de proteção: linha horizontal, linha vertical, estilo tracejado
interf_protection_criteria = {
    "Protection criterion [-1.3 dB, 0.005%]": [0.00005, -1.3, "dash"],
    "Protection criterion [-10.5 dB, 20%]": [0.2, -10.5, "dot"]
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
                annotation_text=f"{legend_crite}",
                annotation_position="top left"
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
        fig.update_layout(xaxis=dict(range=[min_x_auto - 1, max_x_auto + 4]))

    return fig

# Adiciona critérios de proteção aos gráficos selecionados
for prop_name in plots_to_add_vline:
    for plot_type in ["cdf", "ccdf"]:
        plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type=plot_type)
        if plt:
            plt = add_protection_criteria(plt, interf_protection_criteria)
            # plt = adjust_range_x(plt)
print("Realizou ajustes e adiconou critério de proteção")

# Gera gráficos agregados para INR
system_inr_plot = post_processor.get_plot_by_results_attribute_name("system_inr")
aggregated_plot = None
print("Gera agregados")
if system_inr_plot:
    aggregated_plot = go.Figure()
    cutoff_percentage = 0.00001
    next_tick = 1
    ticks_at = []
    while next_tick > cutoff_percentage:
        ticks_at.append(next_tick)
        next_tick /= 10
    ticks_at.append(cutoff_percentage)
    ticks_at.reverse()

    aggregated_plot.update_layout(
        title='CDF Plot for FSS Earth to Space INR aggregated from Micro IMT in 7962.5 MHz',
        title_font_size=22,
        yaxis=dict(title="$\\text{P } (X < x)$", title_font_size=18, tickmode="array", tickvals=ticks_at, type="log", range=[np.log10(cutoff_percentage - cutoff_percentage/2), 0], tickfont=dict(size=18)),
        xaxis=dict(title="INR [dB]", title_font_size=18, tickmode="linear", dtick=5, tickfont=dict(size=18)),
        legend=dict(
            x=0.75, y=0,
            bgcolor="rgba(255, 255, 255, 0.5)",
            bordercolor="rgba(0, 0, 0, 0.5)",
            borderwidth=1,
            font=dict(size=18),
            xanchor="center",
            yanchor="auto",
        ),
        meta={"plot_type": "cdf"},
    )

    aggregated_ccdf_plot = go.Figure()
    aggregated_ccdf_plot.update_layout(
        title='CCDF Plot for FSS Earth to Space INR aggregated from Micro IMT in 7962.5 MHz',
        title_font_size=22,
        yaxis=dict(title="$\\text{P } (X > x)$", title_font_size=18, tickmode="array", tickvals=ticks_at, type="log", range=[np.log10(cutoff_percentage - cutoff_percentage/2), 0], tickfont=dict(size=18)),
        xaxis=dict(title="INR [dB]", title_font_size=18, tickmode="linear", dtick=5, tickfont=dict(size=18)),
        legend=dict(
            x=0.75, y=0,
            bgcolor="rgba(255, 255, 255, 0.5)",
            bordercolor="rgba(0, 0, 0, 0.5)",
            borderwidth=1,
            font=dict(size=18),
            xanchor="center",
            yanchor="auto",
        ),
        meta={"plot_type": "cdf"},
    )

    # Acessa os resultados diretamente
    # dl_urb_r = dl_urban_results[0]
    # ul_urb_r = ul_urban_results[0]
    ul_r = ul_results[0]
    dl_r = dl_results[0]

    if None in [dl_r, ul_r]:
        raise Exception("Cannot aggregate results")

    n_bs_sim = 19 * 3 * 3 * 7
    rb = np.array([.01, .03])
    # ra_urban = np.array([.1, 0.45])
    # ra_suburban = np.array([0.05, 0.2])
    ra = np.array([0.05, 0.1])
    area = 8515767  # Área do Brasil em km²
    # ds_urb = 10
    # ds_sub = 2.4
    ds_bs = 30

    for i in range(2):
        n_bs_actual = int(area * ds_bs * ra[i] * rb[i])
        print(f"Ra{i+1}Rb{i+1} : N_bs = {n_bs_actual}")

        aggregated_results = PostProcessor.aggregate_results(
            dl_samples=dl_r.system_inr,
            ul_samples=ul_r.system_inr,
            ul_tdd_factor=0.25,
            n_bs_sim=n_bs_sim,
            n_bs_actual=n_bs_actual
        )

        # aggregated_results_sub = PostProcessor.aggregate_results(
        #     dl_samples=dl_sub_r.system_inr,
        #     ul_samples=ul_sub_r.system_inr,
        #     ul_tdd_factor=0.25,
        #     n_bs_sim=n_bs_sim,
        #     n_bs_actual=n_bs_actual_suburban
        # )

        # min_length = min(len(aggregated_results_sub), len(aggregated_results_urb))
        # aggregated_results = 10**(aggregated_results_sub[:min_length]/10) + 10**(aggregated_results_urb[:min_length]/10)
        # aggregated_results = 10 * np.log10(aggregated_results)

        x, y = PostProcessor.cdf_from(aggregated_results)
        aggregated_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'Ra{i+1}Rb{i+1}'),
        )

        x, y = PostProcessor.ccdf_from(aggregated_results)
        aggregated_ccdf_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'Ra{i+1}Rb{i+1}'),
        )

        # Criando os dois intervalos
        valores1 = np.arange(0.01, 0.11, 0.01)  # De 0.01 a 0.1 com passo de 0.01
        valores2 = np.arange(0.1, 1.1, 0.1)    # De 0.1 a 1 com passo de 0.1
        valores3 = np.arange(0.001, 0.011, 0.001)    # De 0.001 a 1 com passo de 0.1
        valores4 = np.arange(0.0001, 0.0011, 0.0001)    # De 0.1 a 1 com passo de 0.1
        valores5 = np.arange(0.00001, 0.00011, 0.00001)    # De 0.1 a 1 com passo de 0.1

        # Adicionando linhas tracejadas apenas no eixo Y
        y_values = np.concatenate((valores1, valores2, valores3))

        for y in y_values:
            aggregated_ccdf_plot.add_shape(
                type="line",
                x0=0, x1=1,  # Cobre toda a largura do gráfico
                y0=y, y1=y,  # Define a altura fixa
                xref="paper",  # Faz com que x0 e x1 sejam relativos ao tamanho do gráfico (0 a 1)
                line=dict(dash="dash", color="lightblue", width=1.5)  # Azul claro e um pouco mais espessa
            )

    aggregated_plot = add_protection_criteria(aggregated_plot, interf_protection_criteria)
    aggregated_ccdf_plot = add_protection_criteria(aggregated_ccdf_plot, interf_protection_criteria)
    # aggregated_plot = adjust_range_x(aggregated_plot)
    # aggregated_ccdf_plot = adjust_range_x(aggregated_ccdf_plot)
print("Concluiu agregados")
# Salva os gráficos em diferentes resoluções
# PostProcessor.save_plots(
#     os.path.join(campaign_base_dir, "output", "1200x1200"),
#     [*post_processor.plots, aggregated_plot, aggregated_ccdf_plot],
#     width=1200, height=1200,
# )

# PostProcessor.save_plots(
#     os.path.join(campaign_base_dir, "output", "1200x800"),
#     [*post_processor.plots, aggregated_plot, aggregated_ccdf_plot],
#     width=1200, height=800,
# )

# Exibe o gráfico CCDF agregado
for plot in post_processor.plots:
    plot.show()
aggregated_plot.show()
aggregated_ccdf_plot.show()
