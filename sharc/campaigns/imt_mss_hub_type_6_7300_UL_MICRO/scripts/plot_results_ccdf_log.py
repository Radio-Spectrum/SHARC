import os
from pathlib import Path

import numpy as np

from sharc.post_processor import PostProcessor
from sharc.results import Results

# --- USER CONFIGURATION ---
apply_shift = True  # Define True para aplicar shift, False para desabilitar
mode = "UL"  # "DL" para Downlink, "UL" para Uplink
output_filename = "CCDF_plot_MICRO"  # Nome base do arquivo de saída (sem extensão)
SAVE_FIG = True  # Defina como True para salvar a figura, ou False para exibir no navegador
OUTPUT_DIR = "/home/araujo/Documentos/Git/Projetos/Anatel/Graficos/MICRO_UL"  # Pasta onde os gráficos serão salvos

# Widescreen resolution (16:9 format)
image_width = 1600
image_height = 900

# Define o valor de shift baseado no modo
shift_value = -10 * np.log10(0.75) if mode == "DL" else -10 * np.log10(0.25)

# Lista de valores para 'y' (distância) e 'load_probability'
Ro = 1600
y_values = [Ro - 600, Ro - 300, Ro, Ro + 300, Ro + 600, Ro + 900, Ro + 1200, Ro + 1500]
load_probabilities = [20, 50]

post_processor = PostProcessor()

# Função para adicionar legendas dinamicamente
def add_plot_legends(y_values, load_probabilities):
    for y in y_values:
        for load_probability in load_probabilities:
            y_circ = y - Ro
            dir_pattern = f"y_{y}_load_probability_{load_probability}"
            legend = f"Dist(m)={y_circ}, Load={load_probability}%"
            post_processor.add_plot_legend_pattern(
                dir_name_contains=dir_pattern,
                legend=legend
            )

# Adiciona legendas dinamicamente
add_plot_legends(y_values, load_probabilities)

# Diretório base para os resultados
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

# Carrega os resultados
many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)

# Filtra os resultados para incluir somente aqueles que correspondam ao padrão desejado
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

# Gera os plots CDF somente para os resultados filtrados
cdf_plots = list(post_processor.generate_cdf_plots_from_results(filtered_results))  # Converte para lista

# Gera os plots CCDF (1 - CDF) com escala logarítmica no eixo Y
ccdf_plots = []
for plot in cdf_plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        ccdf_plot = plot  # Utiliza a mesma estrutura do plot
        for trace in ccdf_plot.data:
            trace.y = 1 - trace.y  # CCDF = 1 - CDF
            # Aplica shift se estiver habilitado
            if apply_shift:
                trace.x = trace.x + shift_value

        ccdf_plot.update_layout(
            title="CCDF Plot for [SYS] System INR",
            xaxis_title="INR (dB)",
            yaxis_title="CCDF",
            yaxis=dict(
                type="log",  # Define o eixo Y em escala logarítmica
                range=[-4, 0],  # Força os limites do eixo Y de 10^-4 a 10^0
                tickmode="array",  # Define o modo de ticks como array
                tickvals=[1, 0.1, 0.01, 0.001, 0.0001],  # Define os valores dos ticks (apenas potências de 10)
                ticktext=["$10^0$", "$10^{-1}$", "$10^{-2}$", "$10^{-3}$", "$10^{-4}$"],  # Rótulos dos ticks
                showgrid=True,  # Habilita as linhas de grade principais
                gridwidth=1,  # Largura das linhas de grade principais
                gridcolor="lightgray",  # Cor das linhas de grade principais
                minor=dict(  # Configuração para as linhas de grade menores
                    showgrid=False,  # Desativa as linhas de grade menores
                )
            )
        )

        # Adiciona linhas horizontais tracejadas para os valores intermediários
        intermediate_values = np.concatenate([
            np.linspace(1, 0.1, 10),  # Valores entre 1 e 0.1
            np.linspace(0.1, 0.01, 10),  # Valores entre 0.1 e 0.01
            np.linspace(0.01, 0.001, 10),  # Valores entre 0.01 e 0.001
            np.linspace(0.001, 0.0001, 10)  # Valores entre 0.001 e 0.0001
        ])

        for y_val in intermediate_values:
            ccdf_plot.add_hline(
                y=y_val,
                line_dash="dash",  # Linha tracejada
                line_color="black",  # Cor da linha
                line_width=1,  # Espessura da linha
                opacity=0.8  # Transparência
            )

        # Adiciona linha vertical em -6 dB na CCDF 
        ccdf_plot.add_vline(
            x=-6,
            line_dash="dash",
            line_color="red",
            annotation_text="-6 dB",
            annotation_position="top right"
        )
        
        ccdf_plot.add_vline(
            x=-10.5,
            line_dash="dash",
            line_color="darkblue",
            annotation_text="-10.5 dB",
            annotation_position="top left"
        )
        
        ccdf_plot.add_hline(
            y=0.2,
            line_dash="dash",
            line_color="blue",
            annotation_text="20%",
            annotation_position="left"
        )
        
        ccdf_plots.append(ccdf_plot)

# Adiciona os plots CCDF ao post_processor
post_processor.add_plots(ccdf_plots)

# Função para salvar o plot
def save_plot(plot, filename):
    """Salva o plot como PNG com o nome de arquivo fornecido."""
    plot.write_image(filename, width=image_width, height=image_height, scale=2)
    print(f"Plot salvo como: {filename}")

# Função principal para tratar o salvamento ou exibição do plot
def main():
    # Cria o diretório de saída, se não existir
    if SAVE_FIG:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    final_filename = f"{output_filename}_{mode}_bck.png" if apply_shift else f"{output_filename}_{mode}.png"
    file_path = os.path.join(OUTPUT_DIR, final_filename)
    
    if SAVE_FIG:
        for plot in ccdf_plots:
            save_plot(plot, file_path)
    else:
        print("SAVE_FIG está definido como False. Exibindo os plots no navegador.")
        for plot in ccdf_plots:
            plot.show()

# Executa a função principal
if __name__ == "__main__":
    main()