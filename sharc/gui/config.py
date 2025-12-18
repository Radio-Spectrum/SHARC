import os
from pathlib import Path

# ============================================================================
# CONSTANTES FÍSICAS E GEODÉSICAS
# ============================================================================
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563

# ============================================================================
# CONFIGURAÇÕES PADRÃO DA APLICAÇÃO
# ============================================================================
# Estas configurações são carregadas na inicialização do App.
# Você pode alterar aqui para evitar redigitar sempre.

DEFAULTS = {
    # --- Simulação ---
    "seed": 157,
    "num_snapshots": 10000,
    "output_dir": str(Path.cwd() / "sharc/campaigns"),

    # --- SSH / Conexão Remota ---
    "ssh_host": "164.41.75.34",
    "ssh_user": "achiles.mota",
    "ssh_port": 2222,
    "remote_base_dir": "/home/achiles.mota/SHARC",

    # --- Túnel SSH (Bastion) ---
    "tunnel_bastion_host": "164.41.75.34",
    "tunnel_bastion_user": "anatel",
    "tunnel_bastion_port": 13508,
    "tunnel_internal_ip": "192.168.0.204",
    "tunnel_internal_port": 22,
    "tunnel_local_port": 2222,

    # Caminho padrão da chave (ajuste conforme seu sistema)
    "tunnel_key_path": r"C:/Users/PC-CASA/OneDrive/Achiles/Pessoal/1 - UNB/3 - Pós-Graduação/3 - Pesquisas/Atuais/10 - Anatel 2/23 - Servidor/key"
}

# ============================================================================
# METADADOS DE PLOTAGEM (Resultados)
# ============================================================================
# Mapeia o nome do campo (no CSV) para Título e Label do eixo X.

RESULT_FIELDNAME_TO_PLOT_INFO = {
    "imt_ul_tx_power_density": {
        "x_label": "Transmit power density [dBm/Hz]",
        "title": "[IMT] UE transmit power density"
    },
    "imt_ul_tx_power": {
        "x_label": "Transmit power [dBm]",
        "title": "[IMT] UE transmit power"
    },
    "imt_ul_sinr_ext": {
        "x_label": "SINR [dB]",
        "title": "[IMT] UL SINR with external interference"
    },
    "imt_ul_snr": {
        "title": "[IMT] UL SNR",
        "x_label": "SNR [dB]"
    },
    "imt_ul_inr": {
        "title": "[IMT] UL interference-to-noise ratio",
        "x_label": "$I/N$ [dB]"
    },
    "imt_ul_sinr": {
        "x_label": "SINR [dB]",
        "title": "[IMT] UL SINR"
    },
    "imt_system_build_entry_loss": {
        "x_label": "Building entry loss [dB]",
        "title": "[SYS] IMT to system building entry loss"
    },
    "imt_ul_tput_ext": {
        "title": "[IMT] UL throughput with external interference",
        "x_label": "Throughput [bits/s/Hz]"
    },
    "imt_ul_tput": {
        "title": "[IMT] UL throughput",
        "x_label": "Throughput [bits/s/Hz]"
    },
    "imt_path_loss": {
        "title": "[IMT] path loss",
        "x_label": "Path loss [dB]"
    },
    "imt_coupling_loss": {
        "title": "[IMT] coupling loss",
        "x_label": "Coupling loss [dB]"
    },
    "imt_bs_antenna_gain": {
        "x_label": "Antenna gain [dBi]",
        "title": "[IMT] BS antenna gain towards the UE"
    },
    "imt_ue_antenna_gain": {
        "x_label": "Antenna gain [dBi]",
        "title": "[IMT] UE antenna gain towards the BS"
    },
    "system_imt_antenna_gain": {
        "x_label": "Antenna gain [dBi]",
        "title": "[SYS] system antenna gain towards IMT stations"
    },
    "imt_system_antenna_gain": {
        "x_label": "Antenna gain [dBi]",
        "title": "[IMT] IMT station antenna gain towards system"
    },
    "imt_system_path_loss": {
        "x_label": "Path Loss [dB]",
        "title": "[SYS] IMT to system path loss"
    },
    "sys_to_imt_coupling_loss": {
        "x_label": "Coupling Loss [dB]",
        "title": "[SYS] IMT to system coupling loss"
    },
    "system_dl_interf_power": {
        "x_label": "Interference Power [dB]",
        "title": "[SYS] system interference power from IMT DL"
    },
    "imt_system_diffraction_loss": {
        "x_label": "Building entry loss [dB]",
        "title": "[SYS] IMT to system diffraction loss"
    },
    "imt_dl_sinr_ext": {
        "x_label": "SINR [dB]",
        "title": "[IMT] DL SINR with external interference"
    },
    "imt_dl_sinr": {
        "x_label": "SINR [dB]",
        "title": "[IMT] DL SINR"
    },
    "imt_dl_snr": {
        "title": "[IMT] DL SNR",
        "x_label": "SNR [dB]"
    },
    "imt_dl_inr": {
        "title": "[IMT] DL interference-to-noise ratio",
        "x_label": "$I/N$ [dB]"
    },
    "imt_dl_tput_ext": {
        "title": "[IMT] DL throughput with external interference",
        "x_label": "Throughput [bits/s/Hz]"
    },
    "imt_dl_tput": {
        "title": "[IMT] DL throughput",
        "x_label": "Throughput [bits/s/Hz]"
    },
    "system_ul_interf_power": {
        "title": "[SYS] system interference power from IMT UL",
        "x_label": "Interference Power [dBm/BMHz]"
    },
    "system_ul_interf_power_per_mhz": {
        "title": "[SYS] system interference PSD from IMT UL",
        "x_label": "Interference Power [dBm/MHz]"
    },
    "system_dl_interf_power_per_mhz": {
        "title": "[SYS] system interference PSD from IMT DL",
        "x_label": "Interference Power [dBm/MHz]"
    },
    "system_inr": {
        "title": "[SYS] system INR",
        "x_label": "INR [dB]"
    },
    "system_pfd": {
        "title": "[SYS] system PFD",
        "x_label": "PFD [dBm/m^2]"
    },
    "imt_dl_tx_power": {
        "x_label": "Transmit power [dBm]",
        "title": "[IMT] DL transmit power"
    },
    "imt_dl_pfd_external": {
        "title": "[IMT] DL external Power Flux Density (PFD)",
        "x_label": "PFD [dBW/m²/MHz]"
    },
    "imt_dl_pfd_external_aggregated": {
        "title": "[IMT] Aggregated DL external Power Flux Density (PFD)",
        "x_label": "PFD [dBW/m²/MHz]"
    },
}
