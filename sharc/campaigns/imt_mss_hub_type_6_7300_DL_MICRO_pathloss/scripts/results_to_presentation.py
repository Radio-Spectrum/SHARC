import os
import re
from pathlib import Path

import numpy as np

from sharc.post_processor import PostProcessor
from sharc.results import Results

# --- USER CONFIGURATION ---
mode = "DL"  # "DL" para Downlink, "UL" para Uplink
output_filename = "CDF_plots"  # Nome base dos arquivos de saída (sem extensão)
SAVE_FIG = True  # True para salvar os gráficos, False para exibi-los no navegador
OUTPUT_DIR = "/home/araujo/Documentos/Git/Projetos/Anatel/Graficos/MICRO_DL"  # Pasta onde os gráficos serão salvos

# Widescreen resolution (16:9 format)
image_width = 1600
image_height = 900

# Lista dos campos que serão plotados
FIELDS_TO_PLOT = {"imt_system_path_loss", "imt_system_antenna_gain", "system_imt_antenna_gain"}

# Parâmetros para o regex
Ro = 1600
y_values = [Ro - 600, Ro - 300, Ro, Ro + 300, Ro + 600, Ro + 900, Ro + 1200, Ro + 1500] # Exemplo: ajuste conforme necessário
load_probabilities = [20, 50]

# Compilamos a expressão regular para encontrar "y_<valor>_load_probability_<valor>"
pattern = re.compile(r"y_(\d+)_load_probability_(\d+)")

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

# --- Carrega os resultados ---
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())
many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)

# Filtra os resultados usando regex
filtered_results = []
for result in many_results:
    full_path = result.output_directory  # caminho completo
    match = pattern.search(full_path)
    if match:
        y_val_str, load_prob_str = match.groups()  # capturamos as duas partes
        y_val_int = int(y_val_str)
        load_prob_int = int(load_prob_str)
        # Verifica se os valores extraídos estão nas listas definidas
        if y_val_int in y_values and load_prob_int in load_probabilities:
            filtered_results.append(result)

# Adiciona os resultados filtrados ao post_processor
post_processor.add_results(filtered_results)

# Gera os gráficos CDF para todos os resultados filtrados
cdf_plots = list(post_processor.generate_cdf_plots_from_results(filtered_results))

# Filtra somente os gráficos dos campos desejados
selected_plots = []
for plot in cdf_plots:
    attr = plot.layout.meta.get("related_results_attribute", "")
    if attr in FIELDS_TO_PLOT:
        # Atualiza o título para incluir o modo (DL ou UL)
        plot.update_layout(title=f'{plot.layout.title.text} - {mode}')
        selected_plots.append(plot)

# Cria o diretório de saída, se necessário
if SAVE_FIG:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

# Função para salvar o gráfico
def save_plot(plot, filename):
    """Salva o gráfico como PNG com o nome de arquivo fornecido."""
    plot.write_image(filename, width=image_width, height=image_height, scale=2)
    print(f"Gráfico salvo como: {filename}")

def main():
    if SAVE_FIG:
        # Salva cada gráfico na pasta OUTPUT_DIR, com o nome baseado no campo e no modo
        for plot in selected_plots:
            attr = plot.layout.meta.get("related_results_attribute", "plot")
            file_path = os.path.join(OUTPUT_DIR, f"{output_filename}_{mode}_{attr}.png")
            save_plot(plot, file_path)
    else:
        print("SAVE_FIG está definido como False. Exibindo os gráficos no navegador.")
        for plot in selected_plots:
            plot.show()

if __name__ == "__main__":
    main()