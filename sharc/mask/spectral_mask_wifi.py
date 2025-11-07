import numpy as np
from sharc.mask.spectral_mask import SpectralMask
from sharc.support.enumerations import StationType

class SpectralMaskWifi(SpectralMask):
    """
    Ref: IEEE Std 802.11-2020, Sec. 17.3.9.3–4.
    """

    MASK_TABLE = {
        5: {
            "offsets": [2.75, 5, 7.5],
            "levels": [0, -20, -28, -40],  # relativo (dBr)
            "abs_floor": -47
        },
        10: {
            "offsets": [5.5, 10, 15],
            "levels": [0, -20, -28, -40],
            "abs_floor": -50
        },
        20: {
            "offsets": [11, 20, 30],
            "levels": [0, -20, -28, -40],
            "abs_floor": -53
        }
    }

    def __init__(self, freq_mhz: float, band_mhz: float, station_type: StationType, spurious_emissions: float = None):

        self.freq_mhz = freq_mhz
        self.band_mhz = band_mhz
        self.spurious_emissions = spurious_emissions

        delta_f_lim = self.get_frequency_limits(band_mhz)
        delta_f_lim_flipped = delta_f_lim[::-1]

        self.freq_lim = np.concatenate((
            (self.freq_mhz - self.band_mhz / 2) - delta_f_lim_flipped,
            (self.freq_mhz + self.band_mhz / 2) + delta_f_lim,
        ))

    def get_frequency_limits(self, bandwidth: float) -> np.array:
    
        if bandwidth in self.MASK_TABLE:
            return np.array([0] + self.MASK_TABLE[bandwidth]["offsets"])
        
        elif bandwidth in [40, 80, 160]:
            scale = bandwidth / 20
            base = self.MASK_TABLE[20]["offsets"]
            return np.array([0] + [o * scale for o in base])
        else:
            raise ValueError(f"Largura de banda {bandwidth} MHz não suportada")

    def get_emission_limits(self, bandwidth: float) -> np.array:
        """
        Retorna limites de emissão em dBm/MHz (relativos + spurious).
        """
        if bandwidth in self.MASK_TABLE:
            levels = self.MASK_TABLE[bandwidth]["levels"]
            abs_floor = self.MASK_TABLE[bandwidth]["abs_floor"]
        elif bandwidth in [40, 80, 160]:
            levels = self.MASK_TABLE[20]["levels"]  # mesmos dBr
            abs_floor = self.MASK_TABLE[20]["abs_floor"]
        else:
            raise ValueError(f"Largura de banda {bandwidth} MHz não suportada")

        # Se usuário passou um spurious manual, sobrescreve
        if self.spurious_emissions is not None:
            abs_floor = self.spurious_emissions

        return np.array(levels[:-1] + [max(levels[-1], abs_floor)])

    def set_mask(self, p_tx=0):
        """
        Define a máscara (mask_dbm) em dBm/MHz.
        """
        # Potência média por MHz
        self.p_tx = p_tx - 10 * np.log10(self.band_mhz)

        # Limites relativos convertidos para absolutos
        emission_limits = self.get_emission_limits(self.band_mhz) + self.p_tx

        # Monta a máscara simétrica
        emission_limits_flipped = emission_limits[::-1]
        self.mask_dbm = np.concatenate((
            emission_limits_flipped,
            np.array([self.p_tx]),
            emission_limits
        ))


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.table import Table
    # parãmetros de exemplo (adicione os seus)
    p_tx = 34.061799739838875
    freq = 7000           # centro em MHz (apenas para posicionamento absoluto)
    band = 80             # largura de banda em MHz
    spurious_emissions_dbm_mhz = -30

    msk = SpectralMaskWifi(freq, band, StationType.WIFI_APS, spurious_emissions_dbm_mhz)
    msk.set_mask(p_tx)

    # construir eixo de frequências centrado (usamos +/- 600 MHz como antes)
    freqs = np.linspace(-600, 600, num=2000) + freq

    # converter mask para dBr relativo (relativo à potência no centro p_tx)
    # sua mask_dbm está em dBm/MHz; p_tx (médio por MHz) foi calculado em set_mask
    # então dBr = mask_dbm - p_tx
    mask_dbm = msk.mask_dbm
    center_dBm = msk.p_tx  # p_tx já convertido para dBm/MHz dentro do objeto
    mask_dBr = mask_dbm - center_dBm

    # criar array de valores da máscara ao longo do eixo de frequências
    mask_val = np.ones_like(freqs) * mask_dBr[0]
    # apply thresholds from the rightmost limit to leftmost
    for k in range(len(msk.freq_lim) - 1, -1, -1):
        mask_val[np.where(freqs < msk.freq_lim[k])] = mask_dBr[k]

    # agora plot
    fig, ax = plt.subplots(figsize=(10,6))
    ax.plot(freqs - freq, mask_val, linewidth=2)      # plot em Δf (MHz) no eixo x
    ax.set_xlim([freqs[0]-freq, freqs[-1]-freq])
    ax.set_xlabel(r"$\Delta f$ (MHz) — deslocamento em relação ao centro")
    ax.set_ylabel("Nivel (dBr)")
    ax.set_ylim([-60, 5])
    ax.grid(True, linestyle='--', alpha=0.5)

    # desenhar linhas horizontais de referência 0, -20, -28, -40 dBr
    for lvl in [0, -20, -28, -40]:
        ax.axhline(lvl, linestyle=':', linewidth=1)
        ax.text((freqs[0]-freq)*0.98, lvl+0.5, f"{lvl} dBr", va='bottom')

    # marcar limites de frequência A B C D
    # msk.freq_lim contém os pontos absolutos; transformamos para delta em relação ao centro
    freq_lim_delta = (msk.freq_lim - freq)
    # escolher os pontos centrais como A,B,C,D: normalmente são os 4 internos (dependendo do mask)
    # vamos anotar todos os limites e rotular os 4 centrais como A,B,C,D (da esquerda para direita)
    # assumindo ordem: [left-most ..., center, ... right-most]
    # Encontrar índices próximos ao centro
    # Para simplicidade vamos achar os 4 mais próximos da borda do canal (internos)
    # Mas geralmente os A,B,C,D são os 4 limites mais próximos do centro (2 à esquerda, 2 à direita)
    # Pegamos o array e identificamos 4 limites internos: use a metade esquerda interna e a metade direita interna
    n = len(freq_lim_delta)
    # limites da metade esquerda (exclui extremos)
    left_internals = freq_lim_delta[:n//2]
    right_internals = freq_lim_delta[n//2:]
    # escolher 2 mais próximos ao centro de cada lado
    A = left_internals[-2]
    B = left_internals[-1]
    C = right_internals[0]
    D = right_internals[1]

    # desenhar linhas verticais e rótulos A B C D
    for x, label in zip([A, B, C, D], ['A','B','C','D']):
        ax.axvline(x, linestyle='--', linewidth=1.2)
        ax.text(x, -55, f"{label}\n{float(x):.0f} MHz", ha='center', va='bottom', bbox=dict(boxstyle="round,pad=0.2", alpha=0.2))

    # adicionar legenda / título
    ax.set_title(f"Spectral Mask (BW = {band} MHz) — centro {freq} MHz")

    # Adicionar uma "tabela" simples com os valores A/B/C/D para canais comuns (opcional)
    table_text = (
        "Channel Size |   A   |   B   |   C   |   D\n"
        "----------------------------------------\n"
        "20 MHz       | 9 MHz | 11 MHz| 20 MHz| 30 MHz\n"
        "40 MHz       |19 MHz | 21 MHz| 40 MHz| 60 MHz\n"
        "80 MHz       |39 MHz | 41 MHz| 80 MHz|120 MHz\n"
        "160 MHz      |79 MHz | 81 MHz|160 MHz|240 MHz\n"
    )
    # exibir no canto superior direito como anotação de texto
    ax.text(0.98, 0.98, table_text, transform=ax.transAxes, fontsize=9,
            va='top', ha='right', family='monospace', bbox=dict(boxstyle="round", alpha=0.15))

    plt.show()
