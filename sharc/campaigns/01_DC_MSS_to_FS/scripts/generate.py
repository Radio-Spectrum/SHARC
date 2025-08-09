import os
from pathlib import Path
import random

# Obtém o diretório base do projeto SHARC automaticamente
base_dir = Path(__file__).resolve().parent

# Diretório de entrada e saída baseado no diretório do projeto
input_file = base_dir / "base_input.yaml"
output_dir = base_dir.parent / "input"
output_dir.mkdir(parents=True, exist_ok=True)

# Caminho até 'campaigns'
campaigns_path = Path(*base_dir.parts[base_dir.parts.index('campaigns'):]).parent
# Carregar arquivo de referência como texto
with open(input_file, "r") as f:
    reference_text = f.readlines()

modified_text = reference_text[:]
# Gerar arquivos para cada ângulo de azimute
for sistema in ["System_340km", "System_525km"]:
    R = "23775" if sistema == "System 340km" else "36712"
    margin_base = 25 if sistema == "System_340km" else 40
    modified_text[29 - 1] = f"      - n_planes: {'48' if sistema == "System_340km" else '28'}\n"
    modified_text[31 - 1] = f"        perigee_alt_km: {'340' if sistema == "System_340km" else '525'}\n"
    modified_text[32 - 1] = f"        apogee_alt_km: {'340' if sistema == "System_340km" else '525'}\n"
    modified_text[33 - 1] = f"        sats_per_plane: {'110' if sistema == "System_340km" else '120'}\n"
    modified_text[58 - 1] = f"    height: {'340000' if sistema == "System_340km" else '525000'}\n"
    modified_text[53 - 1] = f"      beam_radius: {R}\n"

    for halt_antena in [20, 40]:
        modified_text[124 - 1] = f"    height: {halt_antena}\n"
        modified_text[147 - 1] = f"    mean_clutter_height: {'low' if halt_antena == 20 else 'Mid'}\n"
        modified_text[148 - 1] = f"    below_rooftop: {'60' if halt_antena == 20 else '10'}\n"

        for azimuth in [90, 180]:
            modified_text[127 - 1] = f"      fixed: {azimuth}\n"

            for load_factor in [.2, .5]:
                modified_text[56 - 1] = f"    load_probability: {load_factor}\n"

                for margin in [margin_base, 2 * margin_base, 3 * margin_base]:
                    num = random.randint(0, 1000)
                    modified_text[2 - 1] = f"  seed: {num}\n"
                    modified_text[45 - 1] = f"          margin_from_border: {margin}\n"

                    # Alterar linha 7 e 8 sufixo do nome do arquivo
                    name_file = f"output_dc_mss_to_fs_{sistema}_altant_{halt_antena}m_azi_{azimuth}deg_lf_{load_factor}_margin_{margin}km"
                    modified_text[6 - 1] = f"  output_dir_prefix: {name_file}\n"


                    output_filename = f"{name_file}.yaml"
                    output_path = output_dir / output_filename

                    # Escrever o novo arquivo mantendo a estrutura original
                    with open(output_path, "w") as out_file:
                        out_file.writelines(modified_text)

print("Arquivos YAML gerados com sucesso!")