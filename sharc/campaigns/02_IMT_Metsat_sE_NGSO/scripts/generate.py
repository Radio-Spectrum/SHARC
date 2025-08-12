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
for sistema in ["Sat_E&G", "Sat_C&S"]:
    modified_text[136 - 1] = f"    Hre: {'7' if sistema == "Sat_Q" else '7'}\n"
    modified_text[100 - 1] = f"    gain: {'57.2' if sistema == "Sat_Q" else '44.9'}\n"
    modified_text[102 - 1] = f"      diameter: {'12' if sistema == "Sat_Q" else '5'}\n"
    modified_text[104 - 1] = f"  bandwidth: {'60' if sistema == "Sat_Q" else '30'}\n"
    modified_text[106 - 1] = f"  frequency: {'7780' if sistema == "Sat_Q" else '7812'}\n"
    modified_text[47 - 1] = f"  frequency: {'7780' if sistema == "Sat_Q" else '7812'}\n"
    modified_text[116 - 1] = f"      fixed: {'5' if sistema == "Sat_Q" else '5'}\n"
    modified_text[121 - 1] = f"    height: {'7' if sistema == "Sat_Q" else '7'}\n"
    modified_text[103 - 1] = f"    pattern: {'ITU-R S.465' if sistema == "Sat_Q" else 'ITU-R S.465'}\n"
    modified_text[101 - 1] = f"{'    itu_r_s_465:' if sistema == "Sat_Q" else '    itu_r_s_465:'}\n"

    for imt_cell in ["macro", "micro"]:
        modified_text[17 - 1] = f"{'        vertical_beamsteering_range: !!python/tuple [90., 100.]' if imt_cell == "macro" else '        vertical_beamsteering_range: !!python/tuple [90., 120.]'}\n"
        modified_text[38 - 1] = f"    height: {'18' if imt_cell == "macro" else '6'}\n"
        modified_text[29 - 1] = f"        n_columns: {'16' if imt_cell == "macro" else '8'}\n"
        modified_text[35 - 1] = f"          is_enabled: {'true' if imt_cell == "macro" else 'false'}\n"
        modified_text[26 - 1] = f"        element_vert_spacing: {'2.1' if imt_cell == "macro" else '0.7'}\n"
        modified_text[37 - 1] = f"    conducted_power: {'22' if imt_cell == "macro" else '16'}\n"
        modified_text[137 - 1] = f"    Hte: {'18' if imt_cell == "macro" else '6'}\n"
        modified_text[56 - 1] = f"{'    macrocell:' if imt_cell == "macro" else '    hotspot:'}\n"
        modified_text[63 - 1] = f"    type: {'MACROCELL' if imt_cell == "macro" else 'HOTSPOT'}\n"
        modified_text[60 - 1] = f"{' ' if imt_cell == "macro" else '      num_hotspots_per_cell: 3'}\n"
        modified_text[61 - 1] = f"{' ' if imt_cell == "macro" else '      max_dist_hotspot_ue: 70'}\n"
        modified_text[62 - 1] = f"{' ' if imt_cell == "macro" else '      min_dist_bs_hotspot: 0'}\n"
        modified_text[80 - 1] = f"    distribution_type: {'UNIFORM_IN_CELL' if imt_cell == "macro" else 'ANGLE_AND_DISTANCE'}\n"
        modified_text[81 - 1] = f"{' ' if imt_cell == "macro" else '    distribution_distance: RAYLEIGH'}\n"
        modified_text[82 - 1] = f"{' ' if imt_cell == "macro" else '    distribution_azimuth: NORMAL'}\n"
        modified_text[42 - 1] = f"  channel_model: {'UMa' if imt_cell == "macro" else 'UMi'}\n"
        modified_text[18 - 1] = f"        downtilt: {'6' if imt_cell == "macro" else '10'}\n"
        modified_text[50 - 1] = f"  minimum_separation_distance_bs_ue: {'35' if imt_cell == "macro" else '5'}\n"
        modified_text[90 - 1] = f"    p_o_pusch: {'-92.2' if imt_cell == "macro" else '-87.2'}\n"
  

        for p_percentage in [20, 'RANDOM', 'RANDOM_CENARIO']: ##[20, 'RANDOM', 'RANDOM_CENARIO']
            modified_text[143 - 1] = f"    percentage_p: {p_percentage}\n"

            for clutter_type in ['both_ends']: ##['one_end', 'both_ends']
                modified_text[147 - 1] = f"    clutter_type: {clutter_type}\n"

                for link_type in ['dl']: ## ['ul', 'dl']
                    modified_text[4 - 1] = f"  imt_link: {'DOWNLINK' if link_type == "dl" else 'UPLINK'}\n"

                    for distance in [5, 10]: # In km
                        modified_text[124 - 1] = f"        x: {int(distance) * 1000 + 1500}\n"
                        # Modify seed
                        num = random.randint(0, 1000)
                        modified_text[9 - 1] = f"  seed: {num}\n"

                        # Alterar linha 7 e 8 sufixo do nome do arquivo
                        name_file = f"Metsat_sE_{imt_cell}_{sistema}_link_{link_type}_p_{p_percentage}_cluter_{clutter_type}_dist_{distance}km"
                        modified_text[7 - 1] = f"  output_dir_prefix: {name_file}\n"


                        output_filename = f"{name_file}.yaml"
                        output_path = output_dir / output_filename

                        # Escrever o novo arquivo mantendo a estrutura original
                        with open(output_path, "w") as out_file:
                            out_file.writelines(modified_text)

print("Arquivos YAML gerados com sucesso!")