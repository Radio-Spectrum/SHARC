import os
import random
import yaml
from pathlib import Path
from copy import deepcopy

# Parâmetros principais
num_copias = 30   # número de cópias por variação
num_snapshots_padrao = 500

below_rooftop = {"urban":65}
distancias = {"urban": 400, "suburban": 800}
ambientes = ["urban"]
links = ["DOWNLINK"]

# Caminho do diretório atual
script_dir = Path(__file__).parent


# Lista todos os arquivos de referência refer_*.yaml
arquivos_ref = [f for f in script_dir.glob("*.yaml")]

# Gera uma única seed para todas as cópias desta combinação ambiente/link
seeds = random.sample(range(100,200), num_copias)

for arquivo_ref in arquivos_ref:

    with open(arquivo_ref, 'r') as f:
        dados_ref = yaml.load(f, Loader=yaml.FullLoader)  # <--- trocado de safe_load para load


    # Extrai nome base (remove "refer_" e extensão)
    nome_base = nome_base = arquivo_ref.stem  # mantém o nome completo do arquivo, sem extensão

    for seed in seeds:
    # Loop pelas combinações de ambiente e link
        for ambiente in ambientes:
            for link in links:
                novo_dados = deepcopy(dados_ref)

                # Atualiza os campos no novo YAML (usando a mesma seed para todas as cópias)
                novo_dados['general']['seed'] = seed
                novo_dados['general']['num_snapshots'] = num_snapshots_padrao
                novo_dados['general']['imt_link'] = link
                novo_dados['imt']['topology']['hotspot']['max_dist_hotspot_ue'] = distancias[ambiente]

                #Modificação para os valores de clutter 

                below = below_rooftop[ambiente]

                # output_dir
                sufixo_link = "dl" if link == "DOWNLINK" else "ul"
                output_dir_original = dados_ref['general']['output_dir']


                partes_output = output_dir_original.rstrip("/").split("/")
                if partes_output[-1].startswith("output_"):
                    partes_output[-1] = f"output_{sufixo_link}"
                else:
                    partes_output.append(f"output_{sufixo_link}")

                novo_output_dir = "/".join(partes_output) + "/"
                
                novo_dados['general']['output_dir'] = novo_output_dir

                # output_dir_prefix
                partes_prefix = dados_ref['general']['output_dir_prefix'].split("_")
                prefix_customizado = "_".join(partes_prefix + [ambiente, sufixo_link])
                # Adiciona o número da cópia ao prefixo para diferenciar os arquivos
                novo_dados['general']['output_dir_prefix'] = prefix_customizado + f"_{seed}"
                
                # Nome do novo arquivo
                nome_novo_arquivo = f"{nome_base}_{ambiente}_{sufixo_link}_{seed}.yaml"

                # Caminho da pasta 'input' no nível acima
                input_dir = script_dir.parent / 'input'
                input_dir.mkdir(exist_ok=True)

                caminho_novo = input_dir / nome_novo_arquivo
                with open(caminho_novo, 'w') as f_out:
                    yaml.dump(novo_dados, f_out, default_flow_style=False, sort_keys=False)


print(f"Os arquivos foram gerados com sucesso.")
