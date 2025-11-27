import os
import sys
import pandas as pd
import yaml
from collections import defaultdict

# Diretório raiz onde estão as pastas output_dl e output_ul
campaign_base_dir = os.path.dirname(__file__) # Diretorio que esta arquivo esta 

#Para os multiplos cenarios
cenarios = ["paraguay","suriname"]

#Deixando minusculo para facilar a comparação 

cenarios = [cen.lower() for cen in cenarios]
#print(cenarios)

# Diretórios de entrada
dl_dir = os.path.join(campaign_base_dir, "output_dl")


# Nome do diretório de saída principal
output_combined_name = "output_combined"
output_combined_dir = os.path.join(campaign_base_dir, output_combined_name)
os.makedirs(output_combined_dir, exist_ok=True)

# Diretórios de saída para UL e DL
output_dl_dir = os.path.join(output_combined_dir, "output_dl")

os.makedirs(output_dl_dir, exist_ok=True)

# Função para carregar e limpar YAML
def carregar_yaml_limpo(caminho):
    with open(caminho, 'r') as f:
        yaml_dict = yaml.load(f, Loader=yaml.FullLoader)  # <--- trocado de safe_load para load

    campos_para_ignorar = ["num_snapshots", "output_dir", "output_dir_prefix", 'seed']
    for campo in campos_para_ignorar:
        if campo in yaml_dict.get("general", {}):
            del yaml_dict["general"][campo]

    return yaml_dict

def validar_diretorios(base_dir, tipo_link):
    print(f"\nValidando diretórios para: {tipo_link.upper()}")
    subpastas = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    diretorios_validos = {}
    seeds_usadas_por_categoria = {}

    for dirpath in subpastas:
        dir_lower = dirpath.lower()
        for cenario in cenarios:
            for tipo in ["urban", "suburban"]:
                diretorios_validos.setdefault(f"{tipo}_{cenario}", [])
                seeds_usadas_por_categoria.setdefault(f"{tipo}_{cenario}", set())

            is_urban = "urban"
            is_suburban = "suburban" in dir_lower and cenario in dir_lower

            #print("dire",dir_lower,"--------Cenario",cenario)

            if is_urban:
                categoria = f"urban_{cenario}"
            elif is_suburban:
                categoria = f"suburban_{cenario}"
            else:
                continue

            #print("Não Pulou")
            # Procurar YAML
            yaml_path = None
            for file in os.listdir(dirpath):
                if file.lower().endswith(".yaml"):
                    yaml_path = os.path.join(dirpath, file)
                    break
            if not yaml_path:
                print(f"Aviso: Nenhum YAML encontrado em {dirpath}")
                continue

            with open(yaml_path, 'r') as f:
                yaml_original = yaml.load(f, Loader=yaml.FullLoader)  # <--- trocado de safe_load para load

            seed = yaml_original.get("general", {}).get("seed")
            if seed is None:
                print(f"Erro: YAML {yaml_path} sem seed.")
                continue

            # Verificação agora é por categoria
            if seed in seeds_usadas_por_categoria[categoria]:
                print(f"Erro: seed duplicada '{seed}' encontrada no YAML {yaml_path}")
                sys.exit()

            seeds_usadas_por_categoria[categoria].add(seed)
            yaml_limpo = carregar_yaml_limpo(yaml_path)

            #print("Dir val", diretorios_validos)

            if len(diretorios_validos[categoria]) == 0:
                diretorios_validos[categoria].append((dirpath, yaml_limpo))
            else:
                yaml_ref = diretorios_validos[categoria][0][1]
                if yaml_limpo == yaml_ref:
                    diretorios_validos[categoria].append((dirpath, yaml_limpo))
                else:
                    print(f"Incompatibilidade no YAML de {dirpath} (categoria: {categoria})")

    return diretorios_validos


# Função principal de combinação
def combinar_e_salvar(tipo_link, base_dir, output_base_dir, num_snap=None):
    valid_dirs = validar_diretorios(base_dir, tipo_link)
    for cenario in cenarios:
        for categoria in [f"urban_{cenario}", f"suburban_{cenario}"]:
            if not valid_dirs[categoria]:
                continue  # Pula se não houver diretórios dessa categoria

            arquivos_por_nome = defaultdict(list)

            for dirpath, _ in valid_dirs[categoria]:
                for file in os.listdir(dirpath):
                    if file.lower().endswith(".csv"):
                        arquivos_por_nome[file].append(os.path.join(dirpath, file))

            for filename, paths in arquivos_por_nome.items():
                dfs = []
                for path in paths:
                    try:
                        df = pd.read_csv(path)
                        dfs.append(df)
                    except Exception as e:
                        print(f"Erro ao ler {path}: {e}")

                if dfs:
                    combined_df = pd.concat(dfs, ignore_index=True)

                    # ===== Verificação e truncamento de snapshots =====
                    if "system_inr" in filename:
                        total_snapshots = len(combined_df)

                        if num_snap is not None:
                            if num_snap > total_snapshots:
                                print(f"Erro: O número de snapshots desejado ({num_snap}) "
                                    f"é maior que o total disponível ({total_snapshots}) para {filename}")
                                sys.exit(1)
                            else:
                                combined_df = combined_df.iloc[:num_snap]

                        snapshot_totals.setdefault(tipo_link+" "+categoria, []).append(len(combined_df))

                    elif "interf_power_per_mhz" in filename.lower() and num_snap is not None:
                        combined_df = combined_df.iloc[:num_snap]

                    # ===== Criação do caminho de saída =====
                    nome_subpasta = f"{output_combined_name}_{tipo_link}_{categoria}"

                    subpasta_path = os.path.join(output_base_dir, nome_subpasta)
                    os.makedirs(subpasta_path, exist_ok=True)
                    output_path = os.path.join(subpasta_path, filename)

                    combined_df.to_csv(output_path, index=False)
                    print(f"Arquivo combinado salvo em: {output_path}")

def copiar_yaml_para_saida():
    """Copia TODOS os YAMLs encontrados para os diretórios de saída, mantendo a estrutura original."""
    # Para cada tipo de link (DL)
    for tipo_link, base_dir in [("dl", dl_dir)]:
        # Diretório de saída correspondente
        output_dir = output_dl_dir if tipo_link == "dl" else "erro"
        
        # Percorre todos os diretórios recursivamente
        for root, _, files in os.walk(base_dir):
                for file in files:
                    for cenario in cenarios:
                        if file.lower().endswith('.yaml'):
                            yaml_path = os.path.join(root, file)
                            
                            # Determina a categoria (urban/suburban/default)
                            rel_path = os.path.relpath(root, base_dir)
                            dir_lower = rel_path.lower()
                            
                            #print("diretorio : ",dir_lower,"--- Cenario : ",cenario)
                            is_urban = "urban" in dir_lower and "suburban" not in dir_lower and cenario in dir_lower
                            is_suburban = "suburban" in dir_lower and cenario in dir_lower
                            
                            # Define a subpasta de saída baseada na categoria
                            if is_urban:
                                categoria = f"urban_{cenario}"
                                output_subdir = os.path.join(output_dir, f"output_combined_{tipo_link}_{categoria}")
                            elif is_suburban:
                                categoria = f"suburban_{cenario}"
                                output_subdir = os.path.join(output_dir, f"output_combined_{tipo_link}_{categoria}")

                            else:
                                continue
                            
                            #print("\n\nNão Pulou\n\n")
                            os.makedirs(output_subdir, exist_ok=True)
                            
                            # Copia o YAML mantendo a estrutura de pastas relativa
                            dest_path = os.path.join(output_subdir, file)
                            
                            try:
                                with open(yaml_path, 'r') as src_file, open(dest_path, 'w') as dest_file:
                                    dest_file.write(src_file.read())
                                print(f"YAML copiado para: {dest_path}")
                            except Exception as e:
                                print(f"Erro ao copiar YAML para {dest_path}: {e}")


# Armazenamento global dos totais de snapshots para arquivos system_inr
copiar_yaml_para_saida() 
snapshot_totals = {}
# Executa para DL e UL
combinar_e_salvar("dl", dl_dir, output_dl_dir, num_snap=None)
print("\nAnálise final dos snapshots para arquivos :")

for tipo_link, valores in snapshot_totals.items():
    if not valores:
        print(f" - Nenhum arquivo 'system_inr' encontrado para {tipo_link.upper()}")
        continue

    if all(v == valores[0] for v in valores):
        print(f" - Todos os arquivos '{tipo_link.upper()}' têm {valores[0]} snapshots.")
    else:
        print(f" - Inconsistência nos snapshots de '{tipo_link.upper()}'.")
        print(f"   Valores encontrados: {valores}")
        print(f"   Menor valor: {min(valores)}")


print("\nProcesso concluído com sucesso.")
