import os
from pathlib import Path
from sharc.results import Results, SampleList
from sharc.post_processorJ import PostProcessor
import plotly.graph_objects as go
from sharc.parameters.parameters import Parameters

import re
import numpy as np
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt, PlotAntennaPattern

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())
dl_dir = os.path.join(campaign_base_dir, "output_dl")
ul_dir = os.path.join(campaign_base_dir, "output_ul")

post_processor = PostProcessor()

def legend_gen(dir_name):
    #print(dir_name)
    link = re.search("_(dl|ul)", dir_name)
    if link is not None:
        link = link.group(1)
    else:
        return "None"
    
    return f"{link.upper()} "

post_processor.add_plot_legend_generator(legend_gen)

attributes_to_plot = [
    "system_imt_antenna_gain",
    "imt_system_path_loss",
    "imt_system_antenna_gain",
    "imt_dl_tx_power",
    "imt_dl_tx_power_density",
    "imt_ul_inr",
    "imt_dl_inr",
    "system_dl_interf_power_per_mhz",
    "system_ul_interf_power_per_mhz",
    "system_inr"
]

dl_results = Results.load_many_from_dir(
    dl_dir, only_latest=True,
    only_samples=attributes_to_plot,
)

ul_results = Results.load_many_from_dir(
    ul_dir, only_latest=True,
    only_samples=attributes_to_plot,

)

all_results = [
    *dl_results,
    *ul_results,
]

for result in all_results:
    result.system_inr = SampleList(
        np.array(result.system_inr))

post_processor.add_results(all_results)

post_processor.add_plots(
    post_processor.generate_ccdf_plots_from_results(
        all_results,
        cutoff_percentage=0.001
    )
)
post_processor.add_plots(
    post_processor.generate_cdf_plots_from_results(
        all_results,
    )
)

plots_to_add_vline = [
    "system_inr",
    "imt_ul_inr",
    "imt_dl_inr",
]

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

system_inr_plot = post_processor.get_plot_by_results_attribute_name("system_inr")
aggregated_plot = None

if system_inr_plot:
    aggregated_plot = go.Figure()
    cutoff_percentage = 0.001
    next_tick = 1
    ticks_at = []

    while next_tick > cutoff_percentage:
        ticks_at.append(next_tick)
        next_tick /= 10

    ticks_at.append(cutoff_percentage)
    ticks_at.reverse()

    aggregated_plot.update_layout(
        title='CDF Plot for MSS Space Station received INR aggregated from Micro IMT in 7962.5 MHz',
        title_font_size=22,
        yaxis=dict(title="$\\text{P } (X < x)$", title_font_size=18, tickmode="array", tickvals=ticks_at, type="log", range=[np.log10(cutoff_percentage - cutoff_percentage/2), 0], tickfont=dict(size=18)),
        xaxis=dict(title="INR [dB]", title_font_size=18, tickmode="linear", dtick=5, tickfont=dict(size=18)),
        legend=dict(
            x=0.55, y=0.1,
            bgcolor="rgba(255, 255, 255, 0.5)",
            bordercolor="rgba(0, 0, 0, 0.5)",
            borderwidth=1,
            font=dict(size=15),
            xanchor="center",
            yanchor="auto",
        ),
        meta={"plot_type": "cdf"},
    )
    
    aggregated_ccdf_plot = go.Figure()
    aggregated_ccdf_plot.update_layout(
        title='CCDF Plot for MSS Space Station received INR aggregated from Micro IMT in 7962.5 MHz',
        title_font_size=22,
        yaxis=dict(title="$\\text{P } (X > x)$", title_font_size=18, tickmode="array", tickvals=ticks_at, type="log", range=[np.log10(cutoff_percentage - cutoff_percentage/2), 0], tickfont=dict(size=18)),
        xaxis=dict(title="INR [dB]", title_font_size=18, tickmode="linear", dtick=5, tickfont=dict(size=18)),
        legend=dict(
            x=0.55, y=0.1,
            bgcolor="rgba(255, 255, 255, 0.5)",
            bordercolor="rgba(0, 0, 0, 0.5)",
            borderwidth=1,
            font=dict(size=15),
            xanchor="center",
            yanchor="auto",
        ),
        meta={"plot_type": "cdf"},
    )

    # Como há apenas um resultado de cada tipo, você pode acessá-los diretamente
    dl_urb_r = dl_results[0]
    ul_urb_r = ul_results[0]  # Pega o único resultado de UL urbano

    n_bs_sim = 19 * 3 * 3 * 7

    # NOTE: From Table 13 Annex 4.15 for micro cells
    ra_urban = np.array([.05, .1])  # ra1, ra2 urbano micro
    rb = np.array([.01, .03])  # rb1, rb2
    
    area = 8515767 # área do Brasil exata
    # area = 8510000 # área do Brasil utilizada como input

    # Deployment density for IMT BS (BS/km²)
    # NOTE: From Table 13 Annex 4.15 for micro cells
    ds_urb = 30

    for i in range(2):
        # Cálculo do número real de estações base macro
        # N_BS_ART ,  A * Ds*Ra*Rb
        
        # Ra1Rb1 (i=0)
        # Ra2Rb2 (i=1)
        
        n_bs_actual_urban = int(area * ds_urb * ra_urban[i] * rb[i])  #
        # n_bs_actual_suburban = int(area * ds_sub * ra_suburban[i] * rb[i])  #
      
        # print(f"Ra{i+1}Rb{i+1} : N_bs_urban = {n_bs_actual_urban} - N_bs_suburban = {n_bs_actual_suburban}")
        print(f"Ra{i+1}Rb{i+1} : N_bs_urban = {n_bs_actual_urban}")
        # Lista para armazenar os resultados
        aggregated_results_list = []

        aggregated_results = PostProcessor.aggregate_results(
            dl_samples=dl_urb_r.system_inr,
            ul_samples=ul_urb_r.system_inr,
            ul_tdd_factor=0.25,
            n_bs_sim=n_bs_sim,
            n_bs_actual=n_bs_actual_urban,
            n_drops=10000
        )

	    #Agregado total	
        x, y = PostProcessor.cdf_from(aggregated_results)

        aggregated_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'Ra{i+1}Rb{i+1}',),
        )
        #Limite dos eixos 
        # range_x = [min(range_x[0],min(x)),max(range_x[1],max(x))] 

        x, y = PostProcessor.ccdf_from(aggregated_results)
        aggregated_ccdf_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'Ra{i+1}Rb{i+1}',),
        )
        #Limite dos eixos 
        # range_x_ccdf = [min(range_x_ccdf[0],min(x)),max(range_x_ccdf[1],max(x))] 

    # Adicionando a linha vertical com uma legenda
    # aggregated_plot.add_trace(
    #     go.Scatter(
    #         x=[interf_protection_criteria, interf_protection_criteria],
    #         y=[0, 1],  # Ajuste os valores de y conforme necessário
    #         mode='lines',
    #         line=dict(dash='dash', color='gray'),  # Estilo da linha
    #         name='Protection criterion [-6 dB]',  # Nome que aparecerá na legenda
    #         showlegend=True  # Garante que apareça na legenda
    #     )
    # )

    # Adicionando a anotação (linha vertical)
    # aggregated_plot.add_vline(
    #     x=interf_protection_criteria,
    #     line_dash="dash",
    #     line_color="gray",
    #     opacity=0.75  #  ajuste a opacidade
    # )

    # # Repetindo o mesmo para o gráfico CCDF
    # aggregated_ccdf_plot.add_trace(
    #     go.Scatter(
    #         x=[interf_protection_criteria, interf_protection_criteria],
    #         y=[0, 1],  # Ajuste os valores de y conforme necessário
    #         mode='lines',
    #         line=dict(dash='dash', color='black'),  # Estilo da linha
    #         name='Protection criterion [-6 dB]',  # Nome que aparecerá na legenda
    #         showlegend=True  # Garante que apareça na legenda
    #     )
    # )

    # Adicionando a anotação (linha vertical)
    # aggregated_ccdf_plot.add_vline(
    #     x=interf_protection_criteria,
    #     line_dash="dash",
    #     line_color="gray",
    #     opacity=0.75  # Ajuste a opacidade
    # )
    #Linha horizontal no limite inferior

    # aggregated_plot.add_hline(
    #     cutoff_percentage, line_dash="dash",
    #     name="limite inferior"
    # )
    # aggregated_ccdf_plot.add_hline(
    #     cutoff_percentage, line_dash="dash",
    #     name="limite inferior"
    # )       

    #Adicionando limites para o eixo x que faça sentido)
    # aggregated_plot.update_layout(xaxis=dict(range = [range_x_ccdf[0]-1, max(range_x_ccdf[1],interf_protection_criteria)+4]))
    # aggregated_ccdf_plot.update_layout(xaxis=dict(range = [range_x_ccdf[0]-1, max(range_x_ccdf[1],interf_protection_criteria)+4]))

    aggregated_plot = add_protection_criteria(aggregated_plot, interf_protection_criteria)
    aggregated_ccdf_plot = add_protection_criteria(aggregated_ccdf_plot, interf_protection_criteria)
    # aggregated_plot = adjust_range_x(aggregated_plot)
    # aggregated_ccdf_plot = adjust_range_x(aggregated_ccdf_plot)

plots = [*post_processor.plots, aggregated_plot, aggregated_ccdf_plot]

# PostProcessor.save_plots(
#     os.path.join(campaign_base_dir, "output", "figs"),
#     plots,
#     width = 1200,
#     height= 800
# )

plot_antenna_imt = PlotAntennaPattern("")

for plot in plots:
    plot.show()

"""
# Filtra e exibe apenas os gráficos Individuais coforme a escolha 
graf = "MHz from IMT DL"
for plot in post_processor.plots:
    title = plot.layout.title.text  # Obtém o título do gráfico
    if graf in title:  # Verifica se "graf" está no título
        plot.show()  # Exibe o gráfico no navegador
"""
        
# Plot BS TX radiation patterns
# f = plot_antenna_imt.plot_element_pattern(antenna_bs, "BS", "ELEMENT")
# # f.savefig(figs_dir + "BS_element.pdf", bbox_inches='tight')
# f = plot_antenna_imt.plot_element_pattern(antenna_bs, "TX", "ARRAY")
# # f.savefig(figs_dir + "BS_array.pdf", bbox_inches='tight')

# # Plot UE TX radiation patterns
# plot_antenna_imt.plot_element_pattern(antenna_ue, "UE", "ELEMENT")
# plot_antenna_imt.plot_element_pattern(antenna_ue, "UE", "ARRAY")

# Plot every plot:
# for plot in plots:
#     plot.show()

# full_results = ""

# for result in all_results:
#     # This generates the mean, median, variance, etc
#     stats = PostProcessor.generate_statistics(
#         result=result
#     ).write_to_results_dir()

#     full_results += str(stats) + "\n"
#     # # do whatever you want here:
#     # if "fspl_45deg" in stats.results_output_dir:
#     #     get some stat and do something

# with open(dl_dir + "/stats.txt", "w") as f:
#     f.write(full_results)