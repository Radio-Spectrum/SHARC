import numpy as np

def s1528_taylor_angles(lat_ss, lon_ss, alt_ss, lat_es, lon_es, alt_es):
    """
    Calcula os 4 ângulos de interesse para o diagrama de radiação da antena
    de Taylor da Recomendação ITU-R S.1528, item 1.4: El, Az, θ e φ, 
    considerando o vetor com sentido estação espacial --> ponto na Terra.

    Parâmetros:
    - lat_ss: Latitude geocêntrica do satélite (rad)
    - lon_ss: Longitude do satélite (rad)
    - alt_ss: altitude do satélite (m)
    - lat_es: Latitude geocêntrica da estação (rad) 
    - lon_es: Longitude da estação (rad) 
    - alt_es: altitude da estação (m) 

    Retorna:
    - Az: Ângulo de azimute (graus) 
    - El: Ângulo de elevação (graus)
    - θ: Ângulo entre o eixo y (Nadir) e o vetor a (estação espacial --> ponto na Terra) (graus)
    - φ: Ângulo entre o plano definido pelos vetores y e a e o plano xy (graus)
    - dist: Distância entre a estação e o satélite (m)
    """

    # Raio médio da Terra, em m
    Re = 6378.145e3

    # Coordenadas ECEF do satélite
    sx = (Re + alt_ss) * np.cos(lat_ss) * np.cos(lon_ss)
    sy = (Re + alt_ss) * np.cos(lat_ss) * np.sin(lon_ss)
    sz = (Re + alt_ss) * np.sin(lat_ss)
    s = np.array([sx, sy, sz])

    # Coordenadas ECEF da estação
    px = (Re + alt_es) * np.cos(lat_es) * np.cos(lon_es)
    py = (Re + alt_es) * np.cos(lat_es) * np.sin(lon_es)
    pz = (Re + alt_es) * np.sin(lat_es)
    p = np.array([px, py, pz])

    # Vetor de apontamento, na base B (Terra)
    a_ecef = p - s   # da estação espacial para a estação terrena

    # Distância entre o satélite e a estação
    dist = np.linalg.norm(a_ecef)

    # Matriz de rotação
    m = np.array([-np.sin(lon_ss), np.cos(lon_ss), 0])
    n = np.array([-np.cos(lat_ss)*np.cos(lon_ss), -
                 np.sin(lon_ss)*np.cos(lat_ss), -np.sin(lat_ss)])
    o = np.array([-np.sin(lat_ss)*np.cos(lon_ss), -
                 np.sin(lat_ss)*np.sin(lon_ss), np.cos(lat_ss)])
    M = np.column_stack((m, n, o))

    # Aplicar a rotação para obter o vetor em ENU, na base B' (estação)``
    a_enu = np.dot(M.T, a_ecef)

    # Vetor unitário de apontamento, na base B' (estação)
    a = a_enu/dist

    # Componentes do vetor unitário de apontamento a, na base B' (estação)
    ax, ay, az = a[0], a[1], a[2]

    # Cálculo dos ângulos
    Az = (np.arctan2(ax, ay) + 2*np.pi) % (2*np.pi)  # entre 0 e 2π
    El = np.arcsin(az)  # entre -π/2 e π/2
    θ = np.arccos(ay)  # entre 0 e π
    φ = (np.arctan2(az, ax) + 2*np.pi) % (2*np.pi)  # entre 0 e 2π

    return np.degrees(Az), np.degrees(El), np.degrees(θ), np.degrees(φ), dist