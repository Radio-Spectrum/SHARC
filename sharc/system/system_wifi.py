import math
import sys

import numpy as np
from sharc.antenna.antenna_omni import AntennaOmni
from sharc.parameters.wifi.parameters_hotspot import ParametersHotspot
from sharc.parameters.wifi.parameters_wifi_system import ParametersWifiSystem
from sharc.station_manager import StationManager
from sharc.support.enumerations import StationType
from sharc.topology.topology import Topology
from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.parameters.wifi.parameters_antenna_wifi import ParametersAntennaWifi
from sharc.mask.spectral_mask_wifi import SpectralMaskWifi
from sharc.support.sharc_utils import wrap2_180
from scipy.stats.sampling import DiscreteAliasUrn
import matplotlib.pyplot as plt
from itertools import product

class SystemWifi:
    """Implements a Wifi Network compose of APs and STAs."""
    def __init__(self, param: ParametersWifiSystem, param_ant_ap: ParametersAntennaWifi, random_number_gen: np.random.RandomState, topology: Topology):
        self.parameters = param
        self.parameters_antenna = param_ant_ap
        self.topology = topology
        self.topology.calculate_coordinates()
        self.num_aps = self.topology.num_base_stations
        self.num_sta = self.num_aps * self.parameters.sta.k * self.parameters.sta.k_m

        self.wrap_around_enabled = True

        '''self.ap_power_gain = 10 * math.log10(
            self.parameters.ap.antenna.n_rows *
            self.parameters.ap.antenna.n_columns,
        )
        self.sta_power_gain = 10 * math.log10(
            self.parameters.sta.antenna.n_rows *
            self.parameters.sta.antenna.n_columns,
        )'''
        self.ap_antenna_gain = list()
        self.sta_antenna_gain = list()
        self.path_loss = np.empty([self.num_aps, self.num_sta])
        self.coupling_loss = np.empty([self.num_aps, self.num_sta])

        self.ap_to_sta_phi = np.empty([self.num_aps, self.num_sta])
        self.ap_to_sta_theta = np.empty([self.num_aps, self.num_sta])
        self.ap_to_sta_beam_rbs = -1.0 * np.ones(self.num_sta, dtype=int)

        self.sta = np.empty(self.num_sta)
        self.ap = np.empty(self.num_aps)

        self.link = dict([(bs, list()) for bs in range(self.num_aps)])

        self.num_rb_per_bs = math.trunc(
            (1 - self.parameters.guard_band_ratio) *
            self.parameters.bandwidth / self.parameters.rb_bandwidth,
        )
        # calculates the number of RB per STA on a given AP
        self.num_rb_per_sta = math.trunc(
            self.num_rb_per_bs / self.parameters.sta.k,
        )

        if hasattr(self.parameters, "polarization_loss"):
            self.polarization_loss = self.parameters.polarization_loss
        else:
            self.polarization_loss = 3.0
            
        self.bandwidth = self.parameters.bandwidth
        self.noise_temperature = self.parameters.noise_temperature

        self.inr = np.empty([self.num_aps, self.num_sta])
        self.rx_interference = np.empty(0)

        self.wall_loss = self.parameters.wall_loss

        self.floor_probs = [0.2466, 0.2036, 0.1405, 0.1127, 0.0919, 0.0752, 0.0556, 0.0388, 0.0241, 0.0110]
        self.floor_height_m = 3.0 # Altura padrão por andar em metros

        self.ap = self.generate_aps(random_number_gen)
        self.sta = self.generate_stas(random_number_gen)

    
    def generate_aps(self, random_number_gen: np.random.RandomState) -> StationManager:
        param_ant = self.parameters_antenna
        num_aps = self.num_aps
        wifi_aps = StationManager(num_aps)
        wifi_aps.station_type = StationType.WIFI_APS

        wifi_aps.x = self.topology.x
        wifi_aps.y = self.topology.y
        wifi_aps.z = self.topology.z
        
        if self.parameters.topology.type == "INDOOR_BUILDING": 
            wifi_aps.floor = self.topology.floor
            wifi_aps.indoor = self.topology.indoor
            wifi_aps.building_id = self.topology.building_id

        wifi_aps.height = wifi_aps.z
        wifi_aps.elevation = -param_ant.downtilt * np.ones(num_aps)

        wifi_aps.azimuth =  wrap2_180(self.topology.azimuth)
        random_values = random_number_gen.rand(num_aps)
        wifi_aps.active = random_values < self.parameters.ap.load_probability
        wifi_aps.tx_power = self.parameters.ap.conducted_power * np.ones(num_aps)
        wifi_aps.rx_power = np.full((num_aps, self.parameters.sta.k), -500.0)
        wifi_aps.rx_interference = np.full(num_aps, -500.0)
        wifi_aps.ext_interference = np.full(num_aps, -500.0)
        wifi_aps.total_interference = np.full((num_aps, self.parameters.sta.k), -500.0)
        wifi_aps.snr = np.full((num_aps, self.parameters.sta.k), -500.0)
        wifi_aps.sinr = np.full((num_aps, self.parameters.sta.k), -500.0)
        wifi_aps.sinr_ext = np.full((num_aps, self.parameters.sta.k), -500.0)
        wifi_aps.inr = np.full((num_aps, self.parameters.sta.k), -500.0)

        for i in range(num_aps):
            wifi_aps.antenna[i] = AntennaOmni()
    
        wifi_aps.bandwidth = self.parameters.bandwidth * np.ones(num_aps)
        wifi_aps.center_freq = self.parameters.frequency * np.ones(num_aps)
        wifi_aps.noise_figure = self.parameters.ap.noise_figure * np.ones(num_aps)
        wifi_aps.thermal_noise = -500 * np.ones(num_aps)

        if self.parameters.spectral_mask == "WIFI-2020":
            wifi_aps.spectral_mask = SpectralMaskWifi(
                self.parameters.frequency,
                self.parameters.bandwidth,
                StationType.WIFI_APS,
                self.parameters.spurious_emissions,
            )

        if self.parameters.topology.type == 'HOTSPOT':
            wifi_aps.intersite_dist = self.parameters.topology.hotspot.intersite_distance
        

        return wifi_aps

    def generate_stas(self,random_number_gen: np.random.RandomState) -> StationManager:
        num_sta_per_ap = self.parameters.sta.k * self.parameters.sta.k_m
        wifi_sta = StationManager(self.num_sta)
        wifi_sta.station_type = StationType.WIFI_STA

        

        sta_height = self.parameters.sta.height * np.ones(self.num_sta)
        azimuth_range = self.parameters.sta.azimuth_range
        azimuth = (azimuth_range[1] - azimuth_range[0]) * \
            random_number_gen.random_sample(self.num_sta) + azimuth_range[0]
        
        wifi_sta.tx_power = self.parameters.sta.conducted_power * np.ones(self.num_sta)
        
        elevation_range = (-90, 90)
        elevation = (elevation_range[1] - elevation_range[0]) * \
            random_number_gen.random_sample(self.num_sta) + elevation_range[0]
        
        if self.parameters.topology.type == "INDOOR_BUILDING":
            wifi_sta.indoor = np.ones(self.num_sta, dtype=bool)
            # 2. Pede as coordenadas e andares para dentro dos prédios
            sta_x, sta_y, sta_z, wifi_sta.floor, wifi_sta.building_id = self.topology.generate_indoor_coordinates(self.num_sta, random_number_gen)
        
        else:
            sta_x = list()
            sta_y = list()
            sta_z = list()
            if self.parameters.sta.distribution_type.upper() == "ANGLE_AND_DISTANCE":
                # The Rayleigh and Normal distribution parameters (mean, scale and cutoff)
                # were agreed in TG 5/1 meeting (May 2017).

                if self.parameters.sta.distribution_distance.upper() == "SQRT(UNIFORM)":
                    # this is so that area distribution may be uniform in
                    # annulus/ring
                    r_min = self.parameters.minimum_separation_distance_ap_sta
                    r_max = self.topology.cell_radius
                    radius = np.sqrt(
                        random_number_gen.random_sample(
                            self.num_sta
                        ) * (r_max**2 - r_min**2) + r_min**2
                    )

                if self.parameters.sta.distribution_azimuth.upper() == "UNIFORM":
                    angle = (azimuth_range[1] - azimuth_range[0]) * \
                        random_number_gen.random_sample(self.num_sta) + azimuth_range[0]
            

                for ap in range(self.num_aps):
                    idx = [
                        i for i in range(
                            ap * num_sta_per_ap, ap * num_sta_per_ap + num_sta_per_ap,
                        )
                    ]

                    # theta is the horizontal angle of the UE wrt the serving BS
                    theta = self.topology.azimuth[ap] + angle[idx]
                    # calculate UE position in x-y coordinates
                    x = radius[idx] * np.cos(np.radians(theta))
                    y = radius[idx] * np.sin(np.radians(theta))
                    z = np.zeros_like(x)
                    x, y, z = self.topology.transform_ue_xyz(
                        ap, x, y, z
                    )
                    sta_x.extend(x)
                    sta_y.extend(y)
                    sta_z.extend(z)

                    # calculate UE azimuth wrt serving BS
                    wifi_sta.azimuth[idx] = (azimuth[idx] + theta + 180) % 360

                    # calculate elevation angle
                    # psi is the vertical angle of the UE wrt the serving BS
                    distance = np.sqrt(
                        (self.topology.x[ap] - x) ** 2 + (self.topology.y[ap] - y) ** 2,
                    )
                    psi = np.degrees(
                        np.arctan((self.parameters.ap.height - self.parameters.sta.height) / distance),
                    )
                    wifi_sta.elevation[idx] = elevation[idx] + psi

        wifi_sta.x = np.array(sta_x)
        wifi_sta.y = np.array(sta_y)
        wifi_sta.z = np.full(self.num_sta, self.parameters.sta.height)  
        wifi_sta.height = wifi_sta.z


        random_values = random_number_gen.rand(self.num_sta)
        wifi_sta.active = random_values < self.parameters.sta.load_probability        
        wifi_sta.rx_interference = np.full(self.num_sta, -500.0)
        wifi_sta.ext_interference = np.full(self.num_sta, -500.0)

        # TODO: this piece of code works only for uplink
        '''self.parameters_antenna.get_antenna_parameters()
        wifi_sta.antenna = AntennaFactory.create_n_antennas(
            self.parameters.sta.antenna,
            wifi_sta.azimuth,
            wifi_sta.elevation,
            self.num_sta,
        )'''

        wifi_sta.antenna = [AntennaOmni(0) for ap in range(self.num_sta)]
        wifi_sta.bandwidth = self.parameters.bandwidth * np.ones(self.num_sta)
        wifi_sta.center_freq = self.parameters.frequency * np.ones(self.num_sta)
        wifi_sta.noise_figure = self.parameters.sta.noise_figure * np.ones(self.num_sta)

        if self.parameters.spectral_mask == "WIFI-2020":
            wifi_sta.spectral_mask = SpectralMaskWifi(
                self.parameters.frequency,
                self.parameters.bandwidth,
                StationType.WIFI_STA,
                self.parameters.spurious_emissions,
            )
        wifi_sta.spectral_mask.set_mask()


        return wifi_sta

    def run_csma_ca_scheduling(self, random_gen):
        # 1. Pré-calcular as matrizes de distância (Vetorizado e rápido)
        # Retornam matrizes NumPy [origem x destino]
        d_ap_ap = self.ap.get_distance_to(self.ap)
        d_ap_sta = self.ap.get_distance_to(self.sta)
        d_sta_sta = self.sta.get_distance_to(self.sta)
        
        # Mapeamento para facilitar a busca dinâmica por tipo
        dist_map = {
            (StationType.WIFI_APS, StationType.WIFI_APS): d_ap_ap,
            (StationType.WIFI_APS, StationType.WIFI_STA): d_ap_sta,
            (StationType.WIFI_STA, StationType.WIFI_APS): d_ap_sta.T, # Transposta
            (StationType.WIFI_STA, StationType.WIFI_STA): d_sta_sta
        }

        # 2. Pegar os índices dos que 'querem' transmitir (Intent to transmit)
        ap_candidates = np.where(self.ap.active)[0]
        sta_candidates = np.where(self.sta.active)[0]
        '''n_aps_before = np.sum(self.ap.active)
        n_stas_before = np.sum(self.sta.active)
        
        print(f"\n[CSMA/CA] Tentativa de Transmissão (Load Probability):")
        print(f"   -> APs: {n_aps_before} / {self.num_aps}")
        print(f"   -> STAs: {n_stas_before} / {self.num_sta}")'''
        
        # Pool único de (Manager, Index)
        candidates = []
        candidates.extend([(self.ap, i) for i in ap_candidates])
        candidates.extend([(self.sta, i) for i in sta_candidates])
        
        # 3. Resetar o estado 'active' (agora ele representará 'vencedores do canal')
        self.ap.active[:] = False
        self.sta.active[:] = False

        # 4. Embaralhar para garantir justiça no sorteio (Simula Backoff)
        random_gen.shuffle(candidates)

        radius_km = self.parameters.max_dist_nodes_wifi

        # 5. Processo de Contenção (CSMA/CA)
        while candidates:
            mgr_tx, idx_tx = candidates.pop(0)
            mgr_tx.active[idx_tx] = True # Este nó ganhou o canal
            
            # Filtrar os vizinhos usando os índices nas matrizes pré-calculadas
            remaining = []
            for mgr_target, idx_target in candidates:
                # Busca a distância na matriz correta usando os índices
                dist = dist_map[(mgr_tx.station_type, mgr_target.station_type)][idx_tx, idx_target]
                
                if dist >= radius_km:
                    remaining.append((mgr_target, idx_target))
            
            candidates = remaining
        '''n_aps_after = np.sum(self.ap.active)
        n_stas_after = np.sum(self.sta.active)
        
        print(f"[CSMA/CA] Transmissão Efetiva (Pós-Contenção):")
        print(f"   -> APs: {n_aps_after} (Perda: {n_aps_before - n_aps_after})")
        print(f"   -> STAs: {n_stas_after} (Perda: {n_stas_before - n_stas_after})")
        print(f"   -> Total Transmitindo: {n_aps_after + n_stas_after}\n")'''
    
    def connect_wifi_sta_to_ap(self, parameters: ParametersWifiSystem):
        """
        Link the Wi-Fi STA's to the serving AP. It is assumed that each group of K
        user equipments are distributed and pointed to a certain access point
        """
        num_sta_per_ap = parameters.sta.k * parameters.sta.k_m
        ap_active = np.where(self.ap.active)[0]
        for ap in ap_active:
            sta_list = [
                i for i in range(
                    ap * num_sta_per_ap, ap * num_sta_per_ap + num_sta_per_ap,
                )
            ]
            self.link[ap] = sta_list

    def select_sta(self, random_number_gen: np.random.RandomState):
        """
        Select K STAs randomly from all the STAs linked to one AP as “chosen”
        STAs. These K “chosen” STAs will be scheduled during this snapshot.
        """
        # Calculate distances and angles between Access Points (APs) and Stations (STAs)
        if self.wrap_around_enabled:
            self.ap_to_sta_d_2D, self.ap_to_sta_d_3D, self.ap_to_sta_phi, self.ap_to_sta_theta = \
                self.ap.get_dist_angles_wrap_around(self.sta)
        else:
            self.ap_to_sta_d_2D = self.ap.get_distance_to(self.sta)
            self.ap_to_sta_d_3D = self.ap.get_3d_distance_to(self.sta)
            self.ap_to_sta_phi, self.ap_to_sta_theta = self.ap.get_pointing_vector_to(
                self.sta,
            )

        # Get all currently active Access Points
        ap_active = np.where(self.ap.active)[0]
        
        # Iterate over each active Access Point
        for ap in ap_active:
            # Select K STA's among the ones that are connected to this AP
            random_number_gen.shuffle(self.link[ap])
            K = self.parameters.sta.k
            del self.link[ap][K:]
            
            # Activate the selected STA's and create beams if the AP is active
            if self.ap.active[ap]:
                self.sta.active[self.link[ap]] = np.ones(K, dtype=bool)
                
                for sta in self.link[ap]:
                    # Add a beam from the AP's antenna to the STA
                    self.ap.antenna[ap].add_beam(
                        self.ap_to_sta_phi[ap, sta],
                        self.ap_to_sta_theta[ap, sta],
                    )
                    
                    # Add a corresponding beam from the STA's antenna back to the AP
                    self.sta.antenna[sta].add_beam(
                        self.ap_to_sta_phi[ap, sta] - 180,
                        180 - self.ap_to_sta_theta[ap, sta],
                    )
                    
                    # Set beam resource block group for the STA
                    self.ap_to_sta_beam_rbs[sta] = len(
                        self.ap.antenna[ap].beams_list,
                    ) - 1
    


if __name__ == "__main__":
    from sharc.parameters.wifi.parameters_indoor_building import ParametersIndoorBuilding
    from sharc.parameters.parameters import Parameters
    from sharc.topology.topology_indoor_building import TopologyIndoorBuilding
    from sharc.topology.topology_macrocell import TopologyMacrocell 
    import os
    import numpy as np
    import matplotlib.pyplot as plt

    # Lendo os parâmetros
    param_file = os.path.join(os.getcwd(), "sharc/input", "parameters.yaml")
    params = Parameters()
    params.set_file_name(param_file)
    params.read_params()

    wifi_ant_param = ParametersAntennaWifi() # Certifique-se de que esta classe está importada
    wifi_param = params.wifi
    t_param = ParametersIndoorBuilding()

    # 1. Instanciar e calcular a Topologia IMT (Macrocell) base primeiro
    imt_topology = TopologyMacrocell(intersite_distance=450, num_clusters=1)
    imt_topology.calculate_coordinates()

    # 2. Passar a Topologia IMT para a Topologia Indoor
    wifi_topology = TopologyIndoorBuilding(t_param, imt_topology)
    wifi_topology.calculate_coordinates()

    rnd = np.random.RandomState(1)
    wifi = SystemWifi(wifi_param, wifi_ant_param, rnd, wifi_topology)

    """
    Plota o cenário 3D mostrando os Prédios, a posição dos APs e das STAs.
    """
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # ==========================================================
    # 1. Desenhar o Volume dos Prédios (Paredes de "Vidro")
    # ==========================================================
    def draw_building_3d(ax, b):
        z_base = 0
        z_top = b.total_height
        x = [b.x_min, b.x_max, b.x_max, b.x_min, b.x_min]
        y = [b.y_min, b.y_min, b.y_max, b.y_max, b.y_min]
        
        # Paredes com transparência elevada (alpha=0.1)
        for i in range(4):
            ax.plot([x[i], x[i]], [y[i], y[i]], [z_base, z_top], color='gray', alpha=0.1)
        # Chão
        ax.plot(x, y, [z_base]*5, color='gray', alpha=0.1)
        # Teto mais escuro para demarcar o fim do prédio
        ax.plot(x, y, [z_top]*5, color='black', alpha=0.5, linewidth=1.5)
        
    for b in wifi_topology.buildings:
        draw_building_3d(ax, b)

    # ==========================================================
    # 2. Plotando os APs e as STAs
    # ==========================================================
    # APs (Roteadores - Triângulos Vermelhos Grandes)
    ax.scatter(wifi.ap.x, wifi.ap.y, wifi.ap.z, 
                c='red', marker='^', s=120, alpha=1.0, edgecolors='black', label='APs (Roteadores)')
    
    # STAs (Utilizadores - Círculos Azuis Menores)
    ax.scatter(wifi.sta.x, wifi.sta.y, wifi.sta.z, 
                c='blue', marker='o', s=40, alpha=0.8, edgecolors='black', label='STAs (Utilizadores)')
    
    # Configurando os rótulos e título
    ax.set_title("Distribuição Espacial 3D: Prédios, APs e STAs", fontsize=14)
    ax.set_xlabel("Eixo X (metros)")
    ax.set_ylabel("Eixo Y (metros)")
    ax.set_zlabel("Eixo Z / Altura (metros)")
    
    # ==========================================================
    # 3. Adicionando as linhas tracejadas das alturas dos andares
    # ==========================================================
    # Juntamos as coordenadas de todos os dispositivos para achar os limites do mapa
    all_x = np.concatenate((wifi.ap.x, wifi.sta.x))
    all_y = np.concatenate((wifi.ap.y, wifi.sta.y))
    all_z = np.concatenate((wifi.ap.z, wifi.sta.z))

    x_min = np.min(all_x) - 10 # Margem visual
    x_max = np.max(all_x) + 10
    y_min = np.min(all_y) - 10
    y_max = np.max(all_y) + 10
    
    # Extraímos todas as alturas únicas onde há algum equipamento (AP ou STA)
    alturas_andares = np.unique(all_z)
    
    for z in alturas_andares:
        ax.plot([x_min, x_max, x_max, x_min, x_min], 
                [y_min, y_min, y_max, y_max, y_min], 
                [z, z, z, z, z], 
                color='blue', linestyle=':', alpha=0.3, linewidth=1.0)

    # Ajusta o ângulo de visão para uma boa perspetiva isométrica
    ax.view_init(elev=25, azim=-45)
    
    plt.legend()
    plt.show()