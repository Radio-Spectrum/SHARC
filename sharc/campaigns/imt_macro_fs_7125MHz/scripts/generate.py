import os
from pathlib import Path

# Obtém o diretório base do projeto SHARC automaticamente
base_dir = Path(__file__).resolve().parent.parent.parent  # Caminha 3 níveis acima para alcançar SHARC

# Diretório de entrada e saída baseado no diretório do projeto
input_file = base_dir / "imt_macro_fs_7125MHz/scripts/parameters_imt_macro_fs_reference.yaml"
output_dir = base_dir / "imt_macro_fs_7125MHz/input"
output_dir.mkdir(parents=True, exist_ok=True)

# Carregar arquivo de referência como texto
with open(input_file, "r") as f:
    reference_text = f.readlines()

# Gerar arquivos para cada ângulo de azimute
for coordinates in range(1500, 2501, 100):
    for link_type in ["dl", "ul"]:
        modified_text = reference_text[:]
        
        # Alterar linha 7 para DL ou UL
        modified_text[6] = f"    imt_link: {'DOWNLINK' if link_type == 'dl' else 'UPLINK'}\n"

        # Alterar linha 26 sufixo do nome do arquivo
        modified_text[25] = f"    output_dir_prefix  : output_imt_macro_fs_7125MHz_{link_type}_{coordinates}deg\n"
        
        # Alterar linha 324 para o ângulo de azimute correto
        modified_text[291] = f"    x: {coordinates}\n"
        
        # Criar nome do arquivo de saída
        output_filename = f"parameters_imt_macro_fs_{link_type}_{coordinates}m.yaml"
        output_path = output_dir / output_filename
        
        # Escrever o novo arquivo mantendo a estrutura original
        with open(output_path, "w") as out_file:
            out_file.writelines(modified_text)

print("Arquivos YAML gerados com sucesso!")
