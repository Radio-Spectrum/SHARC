import numpy as np
import matplotlib.pyplot as plt
import matplotlib.axes
import math

from shapely.geometry import Polygon
from scipy.stats.sampling import DiscreteAliasUrn
from sharc.parameters.wifi.parameters_indoor_building import ParametersIndoorBuilding
from sharc.topology.topology import Topology 

class Building:
    """Representa um único edifício no cenário (Polígono XY com altura Z)."""
    def __init__(self, build_id: int, x_center: float, y_center: float, 
                 width: float, length: float, floors: int, floor_height: float = 3.0):
        self.build_id = build_id
        self.x_center = x_center
        self.y_center = y_center
        self.width = width
        self.length = length
        self.floors = floors
        self.floor_height = floor_height
        self.total_height = floors * floor_height
        
        self.x_min = x_center - (width / 2)
        self.x_max = x_center + (width / 2)
        self.y_min = y_center - (length / 2)
        self.y_max = y_center + (length / 2)
        
        # Objeto Polygon para deteção de colisão (Overlap)
        self.polygon = Polygon([
            (self.x_min, self.y_min), 
            (self.x_max, self.y_min), 
            (self.x_max, self.y_max), 
            (self.x_min, self.y_max)
        ])

class TopologyIndoorBuilding(Topology):
    
    MAX_NUM_LOOPS = 1000 # Limite de tentativas para evitar loops infinitos

    def __init__(self, param: ParametersIndoorBuilding, imt_topology: Topology):
        self.intersite_distance = param.intersite_distance
        self.cell_radius = self.intersite_distance / np.sqrt(3)
        super().__init__(param.intersite_distance, self.cell_radius)
        
        self.parameters = param
        self.buildings_per_cell = self.parameters.buildings_per_cell # Quantidade de prédios por Macrocell
        self.buildings = []
        self.imt_topology = imt_topology
        self.num_aps = self.parameters.num_aps

    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        """Calcula a posição dos edifícios e dos Access Points (APs) Wi-Fi."""
        if not self.static_base_stations:
            self.static_base_stations = True
            self.buildings = []
            
            min_dist_bs = self.parameters.min_dist_bs # Distância mínima da antena do IMT
            max_radius = self.imt_topology.intersite_distance / 2
            
            for bs_idx in range(self.imt_topology.num_base_stations):
                bs_x = self.imt_topology.x[bs_idx]
                bs_y = self.imt_topology.y[bs_idx]
                
                created_buildings = 0
                loop_count = 0
                
                # Gera prédios evitando sobreposição (Overlap)
                while created_buildings < self.buildings_per_cell and loop_count < self.MAX_NUM_LOOPS:
                    loop_count += 1
                    
                    width = random_number_gen.uniform(20.0, 40.0)
                    length = random_number_gen.uniform(20.0, 40.0)
                    floors = random_number_gen.randint(2, 11) # Até 10 andares
                    
                    safe_radius = max_radius - max(width, length)
                    if safe_radius < min_dist_bs:
                        safe_radius = min_dist_bs + 1.0
                    
                    angle = random_number_gen.uniform(0, 2 * np.pi)
                    distance = np.sqrt(random_number_gen.uniform(0, 1)) * (safe_radius - min_dist_bs) + min_dist_bs
                    
                    x_center = bs_x + (distance * math.cos(angle))
                    y_center = bs_y + (distance * math.sin(angle))
                    
                    temp_b = Building(len(self.buildings), x_center, y_center, width, length, floors)
                    
                    overlap = False
                    for existing_b in self.buildings:
                        if temp_b.polygon.intersects(existing_b.polygon.buffer(1.0)):
                            overlap = True
                            break
                    
                    if not overlap:
                        self.buildings.append(temp_b)
                        created_buildings += 1

            # Gera as coordenadas nativas dos APs dentro dos prédios criados
            self.x, self.y, self.z, self.floor = self.generate_indoor_coordinates(self.num_aps, random_number_gen)
            
            self.indoor = np.ones(self.num_aps, dtype=bool)
            self.azimuth = np.zeros(self.num_aps) 
            self.num_base_stations = self.num_aps

    def generate_indoor_coordinates(self, num_nodes: int, rng_state: np.random.RandomState):
        """Devolve coordenadas seguras dentro dos prédios, evitando sobreposição física."""
        out_x = np.zeros(num_nodes)
        out_y = np.zeros(num_nodes)
        out_z = np.zeros(num_nodes)
        out_floors = np.zeros(num_nodes, dtype=int)
        
        itu_probs = np.array([0.2466, 0.2036, 0.1405, 0.1127, 0.0919, 
                              0.0752, 0.0556, 0.0388, 0.0241, 0.0110])
        
        # Parâmetros de Colisão
        min_dist = self.parameters.min_dist_nodes_indoor # Distância mínima aceitável entre dois nós (em metros)
        MAX_RETRIES = 100 # Limite de tentativas para não causar um "loop infinito"
                              
        for i in range(num_nodes):
            placed = False
            retries = 0
            
            while not placed and retries < MAX_RETRIES:
                retries += 1
                
                # 1. Sorteia o Prédio e as Coordenadas
                b = rng_state.choice(self.buildings)
                temp_x = rng_state.uniform(b.x_min, b.x_max)
                temp_y = rng_state.uniform(b.y_min, b.y_max)
                
                # 2. Sorteia o Andar
                floors_available = min(b.floors, len(itu_probs))
                building_pmf = itu_probs[:floors_available] / np.sum(itu_probs[:floors_available])
                
                rng_floor = DiscreteAliasUrn(building_pmf, random_state=rng_state)
                temp_floor = rng_floor.rvs(size=1)[0]
                temp_z = (temp_floor * b.floor_height) + 1.5
                
                # 3. VERIFICAÇÃO DE SOBREPOSIÇÃO 3D
                if i == 0:
                    overlap = False # O primeiro nó nunca colide
                else:
                    # Calcula a distância 3D entre a posição temporária e TODOS os nós já posicionados
                    # O NumPy faz isto numa fração de milissegundo de forma vetorizada
                    dx = out_x[:i] - temp_x
                    dy = out_y[:i] - temp_y
                    dz = out_z[:i] - temp_z
                    distances = np.sqrt(dx**2 + dy**2 + dz**2)
                    
                    # Se alguma das distâncias for menor que 2 metros, há colisão!
                    if np.any(distances < min_dist):
                        overlap = True
                    else:
                        overlap = False
                
                # 4. Se o espaço estiver livre, guardamos os dados e avançamos para o próximo nó
                if not overlap:
                    out_x[i] = temp_x
                    out_y[i] = temp_y
                    out_z[i] = temp_z
                    out_floors[i] = temp_floor
                    placed = True
            
            # Se tentou 100 vezes e falhou (ex: prédio pequeno demais para tanta gente),
            # aceitamos a última posição gerada e mostramos um aviso no terminal.
            if not placed:
                out_x[i] = temp_x
                out_y[i] = temp_y
                out_z[i] = temp_z
                out_floors[i] = temp_floor
                print(f"[Aviso] O nó {i} foi forçado na posição após {MAX_RETRIES} tentativas. O prédio pode estar sobrelotado.")
                
        return out_x, out_y, out_z, out_floors
            
    def plot(self, ax: matplotlib.axes.Axes):
        """Plota a vista superior (2D) do cenário HetNet."""
        self.imt_topology.plot(ax) 
            
        for b in self.buildings:
            rect = plt.Rectangle((b.x_min, b.y_min), b.width, b.length, 
                                 edgecolor='black', facecolor='gray', alpha=0.7, zorder=2)
            ax.add_patch(rect)
            ax.text(b.x_center, b.y_center, f'ID:{b.build_id}\n{b.floors}F', 
                    ha='center', va='center', fontsize=7, color='white', zorder=3)

        if hasattr(self, 'x') and self.x is not None and len(self.x) > 0:
            ax.scatter(self.x, self.y, c='blue', marker='o', s=50, 
                       edgecolors='black', label='Wi-Fi APs (Indoor)', zorder=4)

        ax.set_title("Cenário Urban Micro - Células IMT, Edifícios e APs")
        ax.set_xlabel("Eixo X Global (metros)")
        ax.set_ylabel("Eixo Y Global (metros)")
        ax.autoscale_view()
        plt.legend(loc='upper right', bbox_to_anchor=(1.15, 1)) 
        plt.grid(True, linestyle=':', alpha=0.5)

    def plot_3d_scenario(self):
        """Plota o cenário em 3D, desenhando o volume dos prédios e os nós."""
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        def draw_building_3d(ax, b):
            z_base = 0
            z_top = b.total_height
            x = [b.x_min, b.x_max, b.x_max, b.x_min, b.x_min]
            y = [b.y_min, b.y_min, b.y_max, b.y_max, b.y_min]
            for i in range(4):
                ax.plot([x[i], x[i]], [y[i], y[i]], [z_base, z_top], color='gray', alpha=0.3)
            ax.plot(x, y, [z_base]*5, color='gray', alpha=0.3)
            ax.plot(x, y, [z_top]*5, color='black', alpha=0.8, linewidth=1.5)
            
        for b in self.buildings:
            draw_building_3d(ax, b)

        for bs_idx in range(self.imt_topology.num_base_stations):
            bs_x = self.imt_topology.x[bs_idx]
            bs_y = self.imt_topology.y[bs_idx]
            bs_height = self.imt_topology.z[bs_idx] if hasattr(self.imt_topology, 'z') else 25.0
            ax.scatter(bs_x, bs_y, bs_height, c='red', marker='^', s=100, label='IMT BS' if bs_idx == 0 else "")
            ax.plot([bs_x, bs_x], [bs_y, bs_y], [0, bs_height], color='red', linestyle='-', linewidth=2)

        if hasattr(self, 'x') and self.x is not None and len(self.x) > 0:
            ax.scatter(self.x, self.y, self.z, c='blue', marker='o', s=50, 
                       edgecolors='black', label='Wi-Fi APs (Indoor)')

        ax.set_title("Cenário Urban Micro 3D - Edifícios, IMT e APs")
        ax.set_xlabel("Eixo X (metros)")
        ax.set_ylabel("Eixo Y (metros)")
        ax.set_zlabel("Eixo Z (Altura)")
        ax.view_init(elev=30, azim=-45)
        plt.legend()
        plt.show()