import os
import subprocess

# Diretório base onde os scripts estão localizados
base_dir = "/home/araujo/Documentos/Git/Projetos/Anatel/SHARC/sharc/campaigns"

# Lista dos scripts que você deseja executar (caminhos relativos ao base_dir)
scripts = [
    "imt_mss_hub_type_6_7300_DL_MICRO/scripts/plot_results_ccdf_log.py",
    "imt_mss_hub_type_6_7300_DL_MICRO/scripts/results_to_presentation.py",
    "imt_mss_hub_type_6_7300_DL/scripts/plot_results_ccdf_log.py",
    "imt_mss_hub_type_6_7300_DL/scripts/results_to_presentation.py",
    "imt_mss_hub_type_6_7300_UL_MICRO/scripts/plot_results_ccdf_log.py",
    "imt_mss_hub_type_6_7300_UL_MICRO/scripts/results_to_presentation.py",
    "imt_mss_hub_type_6_7300_UL/scripts/plot_results_ccdf_log.py",
    "imt_mss_hub_type_6_7300_UL/scripts/results_to_presentation.py"
]

# Executa cada script
for script in scripts:
    script_path = os.path.join(base_dir, script)  # Constrói o caminho absoluto
    if os.path.isfile(script_path):  # Verifica se o arquivo existe
        try:
            print(f"Executando: {script_path}")
            subprocess.run(["python3", script_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Erro ao executar {script_path}: {e}")
    else:
        print(f"Arquivo não encontrado: {script_path}")

print("Todos os scripts foram executados.")