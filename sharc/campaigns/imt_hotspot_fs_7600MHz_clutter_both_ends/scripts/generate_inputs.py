import os
from pathlib import Path

# Obtém o diretório base do projeto SHARC automaticamente
base_dir = Path(__file__).resolve().parent.parent.parent  # Caminha 3 níveis acima para alcançar SHARC

# Diretório de entrada e saída baseado no diretório do projeto
input_file = base_dir / "imt_hotspot_fs_7600MHz_clutter_both_ends/scripts/parameters_reference.yaml"
output_dir = base_dir / "imt_hotspot_fs_7600MHz_clutter_both_ends/input"
output_dir.mkdir(parents=True, exist_ok=True)

# Carregar arquivo de referência como texto
with open(input_file, "r") as f:
    reference_text = f.readlines()

# Gerar arquivos para cada ângulo de azimute
for dista in [-2600, -6600, -11600, -16600, -21600]:
    for link_type in ["dl", "ul"]:
        modified_text = reference_text[:]
        
        # Alterar linha 8 para DL ou UL
        modified_text[7] = f"    imt_link: {'DOWNLINK' if link_type == 'dl' else 'UPLINK'}\n"

        # Alterar linhas 24 e 27 sufixo do nome do arquivo
        modified_text[23] = f"    output_dir: campaigns/imt_hotspot_fs_7600MHz_clutter_both_ends/output/\n"
        modified_text[26] = f"    output_dir_prefix: output_imt_hotspot_fs_7600MHz_clutter_both_ends_{link_type}_{dista}m\n"
        
        # Alterar linha 300 para a distância da estação correta
        modified_text[299] = f"    x: {dista}\n"
        
        # Criar nome do arquivo de saída
        output_filename = f"parameters_imt_hotspot_fs_{link_type}_{dista}m.yaml"
        output_path = output_dir / output_filename
        
        # Escrever o novo arquivo mantendo a estrutura original
        with open(output_path, "w") as out_file:
            out_file.writelines(modified_text)

print("Arquivos YAML gerados com sucesso!")