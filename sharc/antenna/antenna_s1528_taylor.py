import numpy as np 
from scipy.special import jn, jn_zeros 

def ganho_antena_satelite_s1528_taylor(λ, Gmax, SLR, Lr, Lt, θ, φ, l=4):
    """
    Calcula o ganho de uma antena em um sistema de satélites não-GEO,
    conforme a Recomendação ITU-R S.1528, no FSS (Serviço Fixo por Satélite) 
    abaixo de 30 GHz, levando em consideração o efeito dos lóbulos laterais 
    no diagrama da antena.

    Referência:
    Taylor, T. “Design of Circular Aperture for Narrow Beamwidth and Low Sidelobes.” 
    IRE Trans. on Antennas and Propagation, Vol. 5, No. 1, January 1960, pp. 17-22.

    Parâmetros de entrada:
    λ (float): Comprimento de onda da menor frequência da banda de interesse (em metros).
    Gmax (float): Ganho máximo do diagrama da antena (em dB).
    SLR (int): Razão de lóbulos laterais do diagrama da antena (em dB).
    Lr, Lt (float): Tamanhos radial e transversal da área de radiação efetiva da antena do satélite (em metros).
    l (int): Número de lóbulos secundários considerados no diagrama (coincidem com as raízes da função de Bessel).
    θ (float ou np.ndarray): Ângulo entre a direção do centro da Terra (ponto subsatélite) e o ponto de teste (em graus).
    φ (float ou np.ndarray): Ângulo entre o plano meridiano do satélite (plano xz) e o plano definido pela direção do centro da Terra e o ponto de teste (em graus).

    Saída:
    G (float ou np.ndarray): Ganho na direção do ponto considerado (em dB).
    """
    
    # Converte os ângulos de graus para radianos e toma o valor absoluto
    φ = np.abs(np.radians(φ))
    θ = np.abs(np.radians(θ))

    # Verificação básica dos parâmetros de entrada
    if λ <= 0:
        raise ValueError("O comprimento de onda λ deve ser positivo.")
    if not (isinstance(l, int) and l > 0):
        raise ValueError("O parâmetro l deve ser um inteiro positivo.")

    # Cálculos intermediários
    A = (1/np.pi) * np.arccosh(10**(SLR/20))
    raizes_J1 = jn_zeros(1, l) / np.pi  # l raízes da função de Bessel J1(πx)
    σ = raizes_J1[-1] / np.sqrt(A**2 + (l-1/2)**2)
    u = (np.pi/λ) * np.sqrt((Lr*np.sin(θ)*np.cos(φ))**2 + (Lt*np.sin(θ)*np.sin(φ))**2)

    # Calculando v para o ganho
    μ = jn_zeros(1, l-1) / np.pi
    v = np.ones(u.shape + (l-1,))
    
    for i, ui in enumerate(μ):
        v[..., i] = (1 - u**2 / (np.pi**2 * σ**2 * (A**2 + (i+1 - 0.5)**2))) / (1 - (u/(np.pi*ui))**2)

    # Evitar divisões por zero
    with np.errstate(divide='ignore', invalid='ignore'):
        G = Gmax + 20 * np.log10(np.abs((2 * jn(1, u) / u) * np.prod(v, axis=-1)))

    # Substitui valores indefinidos por -inf (ou outro valor desejado)
    G = np.nan_to_num(G, nan=-np.inf)

    return G
