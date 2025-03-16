import os
from pathlib import Path

# Obtém o diretório base do projeto SHARC automaticamente
base_dir = Path(__file__).resolve().parent.parent.parent  # Caminha 3 níveis acima para alcançar SHARC

# Diretório de entrada e saída baseado no diretório do projeto
input_file = base_dir / "FS_var_dist_clutter_both_ends_statitics/scripts/FS_1.yaml"
output_dir = base_dir / "FS_var_dist_clutter_both_ends_statitics/input"
output_dir.mkdir(parents=True, exist_ok=True)

# Carregar arquivo de referência como texto
with open(input_file, "r") as f:
    reference_text = f.readlines()

# Gerar arquivos para cada ângulo de azimute
for dista in [-2600, -6600, -11600, -16600, -21600]:
    for link_type in ["dl", "ul"]:
        modified_text = reference_text[:]
        
        # Alterar linha 7 para DL ou UL
        modified_text[6] = f"    imt_link: {'DOWNLINK' if link_type == 'dl' else 'UPLINK'}\n"

        # Alterar linha 27 sufixo do nome do arquivo
        modified_text[23] = f"    output_dir: campaigns/FS_var_dist_clutter_both_ends_statitics/output"
        modified_text[26] = f"    output_dir_prefix: output_imt_macro_FS_var_dist_clutter_both_ends_statitics_{link_type}_{dista}m\n"
        
        # Alterar linha 324 para o ângulo de azimute correto
        modified_text[334] = f"    x: {dista}\n"
        
        # Criar nome do arquivo de saída
        output_filename = f"parameters_imt_macro_fs_{link_type}_{dista}m.yaml"
        output_path = output_dir / output_filename
        
        # Escrever o novo arquivo mantendo a estrutura original
        with open(output_path, "w") as out_file:
            out_file.writelines(modified_text)

print("Arquivos YAML gerados com sucesso!")