import os
import re
from pathlib import Path

import pandas as pd

# Diretório base para os resultados da simulação
campaign_base_dir = Path(__file__).resolve().parent.parent / "output"
latex_dir = campaign_base_dir / "latex"

# Cria a pasta 'latex' se ela não existir
latex_dir.mkdir(exist_ok=True)

# Prefixo para os diretórios de saída da simulação
prefix = "output_imt_mss_hub_type_6_DL_7300"

# Regex para extrair os valores de distância (y) e load probability
pattern = re.compile(rf"{prefix}_y_(\d+)_load_probability_(\d+)")

# Dicionário para armazenar os dados das simulações
data_dict = {}

# Itera por todas as subpastas em 'output'
for subdir in campaign_base_dir.iterdir():
    if subdir.is_dir():
        match = pattern.search(subdir.name)
        if match:
            y_value, load_probability = match.groups()

            # Caminho esperado para o arquivo de dados
            original_file = subdir / "system_inr.csv"

            # Verifica se o arquivo existe antes de processar
            if original_file.exists():
                # Lê o CSV assumindo que contém uma única coluna de valores INR
                df = pd.read_csv(original_file, names=["INR [dB]"])
                
                # Remove as linhas que contêm a palavra "sample" (caso exista)
                df = df[~df["INR [dB]"].astype(str).str.contains("sample", case=False, na=False)]
                
                # Nome da coluna para identificar a simulação
                column_name = f"Dist_{y_value}m_Load_{load_probability}"

                # Adiciona os dados ao dicionário
                data_dict[column_name] = df["INR [dB]"]

                print(f"Processado: {original_file}")
            else:
                print(f"Arquivo não encontrado: {original_file}")

# Cria um DataFrame final combinando todos os dados
if data_dict:
    combined_df = pd.DataFrame(dict(sorted(data_dict.items())))

    # Salva o CSV combinado
    output_csv_path = latex_dir / "combined_system_inr.csv"
    combined_df.to_csv(output_csv_path, index=False)

    print(f"Arquivo combinado salvo em: {output_csv_path}")
else:
    print("Nenhum arquivo CSV encontrado para combinar.")
