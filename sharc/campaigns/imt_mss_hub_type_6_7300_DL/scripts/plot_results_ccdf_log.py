import os
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from sharc.post_processor import PostProcessor
from sharc.results import Results

# Lista de valores para 'y' (distância) e 'load_probability'
Ro = 1600
y_values = [Ro - Ro, Ro - 400, Ro + 1500, Ro + 5000, Ro + 10000]
load_probabilities = [20, 50]

post_processor = PostProcessor()

# Função para adicionar legendas dinamicamente
def add_plot_legends(y_values, load_probabilities):
    for y in y_values:
        for load_probability in load_probabilities:
            y_circ = y - Ro
            dir_pattern = f"y_{y}_load_probability_{load_probability}"
            legend = f"INR(dB): Dist={y_circ}m, Load={load_probability}%"
            post_processor.add_plot_legend_pattern(
                dir_name_contains=dir_pattern,
                legend=legend
            )

# Adiciona as legendas dinamicamente
add_plot_legends(y_values, load_probabilities)

# Diretório base dos resultados
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

# Carrega os resultados
many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)

# Filtra os resultados de acordo com os padrões de diretório
filtered_results = []
for result in many_results:
    result_dir = os.path.basename(result.output_directory)
    for y in y_values:
        for load_probability in load_probabilities:
            dir_pattern = f"y_{y}_load_probability_{load_probability}"
            if dir_pattern in result_dir:
                filtered_results.append(result)
                break

# Adiciona os resultados filtrados ao post_processor
post_processor.add_results(filtered_results)

# Gera os gráficos de CDF dos resultados filtrados
cdf_plots = list(post_processor.generate_cdf_plots_from_results(filtered_results))

# Cria a CCDF (1 - CDF) com escala logarítmica no eixo X
ccdf_plots = []
for plot in cdf_plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        ccdf_plot = plot  # Copia a estrutura do gráfico
        for trace in ccdf_plot.data:
            trace.y = 1 - trace.y  # Converte para CCDF
            
            # 🔹 **Converte valores de dB para escala linear antes de aplicar log no eixo X**
            trace.x = 10 ** (trace.x / 10)

        ccdf_plot.update_layout(
            title="CCDF Plot for [SYS] System INR",
            yaxis_title="CCDF",
            xaxis_title="INR (dB)",
            xaxis_type="log",  # 🔹 **Escala logarítmica aplicada corretamente**
            xaxis=dict(
                tickmode="array",
                tickvals=[10**(-5),10**(-4),10**(-3),10**(-2), 10**(-1), 10**0, 10**1, 10**2, 10**3, 10**4],
                ticktext=["$10^{-5}$","$10^{-4}$","$10^{-3}$","$10^{-2}$", "$10^{-1}$", "$10^{0}$", "$10^{1}$", "$10^{2}$", "$10^{3}$", "$10^{4}$"]
            )
        )

        # 🔹 **Adiciona uma linha vertical em -6 dB (convertido para escala linear)**
        ccdf_plot.add_vline(
            x=10 ** (-6 / 10),  # Converte -6 dB para escala linear antes de traçar a linha
            line_dash="dash",
            line_color="red",
            annotation_text="-6 dB",
            annotation_position="top left"
        )

        ccdf_plots.append(ccdf_plot)

# Adiciona os gráficos de CCDF ao post_processor
post_processor.add_plots(ccdf_plots)

# 🔹 **Mantém a potência de backoff e aplica corretamente ao INR na escala linear**
for plot in ccdf_plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        for trace in plot.data:
            trace.x = trace.x * (10 ** (-10 * np.log10(0.75) / 10))  # Aplica o ajuste corretamente

# Mostra os gráficos CCDF ajustados
for plot in ccdf_plots:
    plot.show()

# Gera estatísticas para cada resultado filtrado
for result in filtered_results:
    stats = PostProcessor.generate_statistics(result=result).write_to_results_dir()
