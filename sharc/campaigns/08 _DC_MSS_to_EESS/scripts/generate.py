import numpy as np
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
    R = "25803" if sistema == "System 340km" else "39844"
    margin_base = 25 if sistema == "System_340km" else 40
    modified_text[29 - 1] = f"      - n_planes: {'48' if sistema == "System_340km" else '28'}\n"
    modified_text[31 - 1] = f"        perigee_alt_km: {'340' if sistema == "System_340km" else '525'}\n"
    modified_text[32 - 1] = f"        apogee_alt_km: {'340' if sistema == "System_340km" else '525'}\n"
    modified_text[33 - 1] = f"        sats_per_plane: {'110' if sistema == "System_340km" else '120'}\n"
    modified_text[58 - 1] = f"    height: {'340000' if sistema == "System_340km" else '525000'}\n"
    modified_text[53 - 1] = f"      beam_radius: {R}\n"

    for system_EESS in ["System_B", "System_D"]:
        modified_text[116 - 1] = f"  frequency: {'2202' if system_EESS == "System_B" else '2203'}\n"
        modified_text[117 - 1] = f"  bandwidth: {'4' if system_EESS == "System_B" else '6'}\n"
        modified_text[119 - 1] = f"  noise_temperature: {'190' if system_EESS == "System_B" else '120'}\n"
        modified_text[142 - 1] = f"    gain: {'45.8' if system_EESS == "System_B" else '39'}\n"
        modified_text[144 - 1] = f"      gain: {'45.8' if system_EESS == "System_B" else '39'}\n"
        f = 2202 if system_EESS == "System_B" else 2203
        G = 45.8 if system_EESS == "System_B" else 39
        G = 10**(G / 10)
        lam = 2.998e8 / (f * 1e6)
        n = .9
        diam = float(np.round(lam * np.sqrt(G / n) / np.pi, decimals=2))

        for type_adj in ["spurious", "adjacent"]:
            modified_text[14 - 1] = f"  frequency: {'2187.5' if type_adj == "spurious" else '2197.5'}\n"

            for load_factor in [.2, .5]:
                modified_text[56 - 1] = f"    load_probability: {load_factor}\n"

                num = random.randint(0, 1000)
                modified_text[2 - 1] = f"  seed: {num}\n"

                # Alterar linha 7 e 8 sufixo do nome do arquivo
                name_file = f"output_dc_mss_to_eess_{sistema}_altant_{system_EESS}m_azi_{type_adj}deg_lf_{load_factor}"
                modified_text[6 - 1] = f"  output_dir_prefix: {name_file}\n"


                output_filename = f"{name_file}.yaml"
                output_path = output_dir / output_filename

                # Escrever o novo arquivo mantendo a estrutura original
                with open(output_path, "w") as out_file:
                    out_file.writelines(modified_text)

print("Arquivos YAML gerados com sucesso!")