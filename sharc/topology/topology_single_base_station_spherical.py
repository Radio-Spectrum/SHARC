from sharc.topology.topology_single_base_station import TopologySingleBaseStation
import numpy as np
import matplotlib.pyplot as plt
from sharc.station_manager import StationManager


class TopologySingleBaseStationSpherical(TopologySingleBaseStation):
    def __init__(
        self,
        cell_radius: float,
        num_clusters: int,
        central_latitude: float,
        central_longitude: float,
        earth_radius: float = 6371000,
    ):
        super().__init__(cell_radius, num_clusters)
        self.central_latitude = np.radians(central_latitude)
        self.central_longitude = np.radians(central_longitude)
        self.earth_radius = earth_radius

    def _cartesian_to_sphere(self, x, y):
        """
        Converte coordenadas cartesianas para coordenadas esféricas,
        mantendo a escala apropriada para a visualização.
        """
        # Ajusta a escala em relação ao raio da célula
        scale_factor = 1 / self.earth_radius # esse é o certo
        #scale_factor = self.cell_radius / (2 * self.earth_radius) * 10

        x_scaled = x * scale_factor
        y_scaled = y * scale_factor

        # Calcula as coordenadas na superfície da esfera
        lat = self.central_latitude + y_scaled
        lon = self.central_longitude + x_scaled / np.cos(self.central_latitude)

        # Converte para coordenadas cartesianas 3D
        x = self.earth_radius * np.cos(lat) * np.cos(lon)
        y = self.earth_radius * np.cos(lat) * np.sin(lon)
        z = self.earth_radius * np.sin(lat)

        return np.array([x, y, z])

    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        """
        Calcula as coordenadas seguindo a mesma lógica do TopologySingleBaseStation,
        mas adicionando a projeção para coordenadas esféricas.
        """
        # Primeiro executa o cálculo original do TopologySingleBaseStation
        super().calculate_coordinates(random_number_gen)

        # Armazena todas as coordenadas cartesianas
        self.planar_x = self.x
        self.planar_y = self.y
        self.planar_azimuth = self.azimuth

        # Projeta todos os pontos para coordenadas esféricas
        points = np.array(
            [self._cartesian_to_sphere(x, y) for x, y in zip(self.x, self.y)]
        )

        # Armazena as coordenadas esféricas
        self.x_sphere = points[:, 0]
        self.y_sphere = points[:, 1]
        self.z_sphere = points[:, 2]

    def plot_3d(self, ax=None):
        if ax is None:
            fig = plt.figure(figsize=(12, 12))
            ax = fig.add_subplot(111, projection="3d")

        # Plota o globo
        u = np.linspace(0, 2 * np.pi, 100)
        v = np.linspace(0, np.pi, 100)
        x = self.earth_radius * np.outer(np.cos(u), np.sin(v))
        y = self.earth_radius * np.outer(np.sin(u), np.sin(v))
        z = self.earth_radius * np.outer(np.ones(np.size(u)), np.cos(v))
        ax.plot_surface(x, y, z, color="lightblue", alpha=0.3)

        # Plota as áreas de cobertura
        for x, y, az in zip(self.planar_x, self.planar_y, self.planar_azimuth):
            # Gera pontos para o arco de cobertura com maior resolução
            angles = np.linspace(az - 60, az + 60, 100)  # 100 pontos no arco
            coverage_points = []

            # Gera pontos em formato de setor circular
            for angle in angles:
                # Gera 10 pontos ao longo do raio para cada ângulo
                for r in np.linspace(0, self.cell_radius, 10):
                    rad = np.radians(angle)
                    px = x + r * np.cos(rad)
                    py = y + r * np.sin(rad)
                    coverage_points.append([px, py])

            # Projeta os pontos para coordenadas esféricas
            coverage_sphere = [
                self._cartesian_to_sphere(px, py) for px, py in coverage_points
            ]
            coverage_sphere = np.array(coverage_sphere)

            # Redimensiona os pontos de cobertura para plot_surface
            X = coverage_sphere[:, 0].reshape((100, 10))
            Y = coverage_sphere[:, 1].reshape((100, 10))
            Z = coverage_sphere[:, 2].reshape((100, 10))

            # Desenha o setor de cobertura como uma superfície suave
            ax.plot_surface(X, Y, Z, color="green", alpha=0.3)

        # Plota as estações base
        ax.scatter(
            self.x_sphere,
            self.y_sphere,
            self.z_sphere,
            color="black",
            s=50,
            label="Estações Base",
        )

        # Configurações do plot
        ax.set_box_aspect([1, 1, 1])
        limit = self.earth_radius * 1.2
        ax.set_xlim([-limit, limit])
        ax.set_ylim([-limit, limit])
        ax.set_zlim([-limit, limit])

        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")

        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False

        ax.set_title("Topologia de Estação Base Única no Globo")
        ax.legend()

        return ax

    def export_to_kml(self, filename="single_base_station_topology.kml"):
        kml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
        kml_header += '<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n'

        kml_header += """
        <Style id="baseStation">
            <IconStyle>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/target.png</href>
                </Icon>
            </IconStyle>
        </Style>
        """

        kml_footer = "</Document>\n</kml>"

        with open(filename, "w") as f:
            f.write(kml_header)

            for x, y, z in zip(self.x_sphere, self.y_sphere, self.z_sphere):
                r = np.sqrt(x**2 + y**2 + z**2)
                lat = np.arcsin(z / r)
                lon = np.arctan2(y, x)

                lat_deg = np.degrees(lat)
                lon_deg = np.degrees(lon)

                f.write(
                    f"""
                <Placemark>
                    <styleUrl>#baseStation</styleUrl>
                    <Point>
                        <coordinates>{lon_deg},{lat_deg},0</coordinates>
                    </Point>
                </Placemark>
                """
                )

            f.write(kml_footer)

    def plot_ues_3d(self, ue_list: StationManager, ax):
        """
        Adiciona os UEs ao plot 3D existente.

        Parameters
        ----------
        ue_list : StationManager
            Lista de UEs a serem plotados
        ax : matplotlib.axes.Axes
            Eixo onde plotar os UEs
        """
        # Extrai as coordenadas dos UEs
        ax.scatter(
            ue_list.x,
            ue_list.y,
            ue_list.height,
            color="blue",
            s=30,
            label="UEs",
            alpha=0.6,
        )


if __name__ == "__main__":
    cell_radius = 1000  # 1km de raio
    num_clusters = 2
    central_latitude = -15.7801  # Brasília
    central_longitude = -47.9292  # Brasília

    topology = TopologySingleBaseStationSpherical(
        cell_radius=cell_radius,
        num_clusters=num_clusters,
        central_latitude=central_latitude,
        central_longitude=central_longitude,
    )

    topology.calculate_coordinates()

    # Plot 3D
    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_subplot(111, projection="3d")
    topology.plot_3d(ax)
    plt.show()

    # Exportar KML
    topology.export_to_kml()
    print(
        "Arquivo KML gerado! Você pode abri-lo no Google Earth ou importar no My Maps do Google Maps"
    )
