import numpy as np

def calculate_gain_multiple_transceivers(antenna, phi_vec, theta_vec):
    """
    Calcula o ganho total para uma antena com múltiplos transceptores.

    Parâmetros:
    ----------
    antenna : AntennaMultipleTransceiver
        Instância da antena com múltiplos feixes.
    phi_vec : np.array
        Ângulos phi (azimutes) dos usuários-alvo.
    theta_vec : np.array
        Ângulos theta (elevações) dos usuários-alvo.

    Retorna:
    -------
    np.array:
        Ganho total da antena combinando todos os feixes.
    """
    num_beams = len(antenna.transceiver_radiation_pattern)  # Corrigindo para obter o número correto de feixes

    # Calcula ângulo fora do eixo para cada feixe
    off_axis_angles = get_off_axis_angle(
        antenna.theta, antenna.phi, theta_vec, phi_vec
    )

    # Inicializando array de ganhos individuais
    individual_gains = np.zeros((num_beams, *phi_vec.shape))

    for i in range(num_beams):
        individual_gains[i] = antenna.transceiver_radiation_pattern[i].calculate_gain(
            off_axis_angle_vec=off_axis_angles[i], theta_vec=theta_vec
        )

    # Convertendo dB para soma de potências, depois voltando para dB
    total_gain = 10 * np.log10(np.sum(10**(individual_gains / 10), axis=0))
    return total_gain

def get_off_axis_angle(antenna_theta, antenna_phi, obj_theta, obj_phi):
    """
    Calcula o ângulo fora do eixo entre a antena e um objeto alvo.

    Retorna:
    -------
    np.array:
        Ângulos fora do eixo em graus.
    """
    relative_phi = antenna_phi[:, np.newaxis] - obj_phi
    antenna_theta = antenna_theta[:, np.newaxis]

    rel_cos = (np.cos(np.radians(antenna_theta)) * np.cos(np.radians(obj_theta)) +
               np.sin(np.radians(antenna_theta)) * np.sin(np.radians(obj_theta)) *
               np.cos(np.radians(relative_phi)))

    rel = np.arccos(np.clip(rel_cos, -1.0, 1.0))  # Evita erros numéricos
    return np.degrees(rel)
