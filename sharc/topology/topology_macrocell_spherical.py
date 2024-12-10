from sharc.topology.topology_macrocell import TopologyMacrocell
import numpy as np
import matplotlib.pyplot as plt
import math


class TopologyMacrocellSpherical(TopologyMacrocell):
    def __init__(
        self,
        intersite_distance: float,
        num_clusters: int,
        central_latitude: float,
        central_longitude: float,
        earth_radius: float = 6371000,
    ):
        super().__init__(intersite_distance, num_clusters)
        self.central_latitude = np.radians(central_latitude)
        self.central_longitude = np.radians(central_longitude)
        self.earth_radius = earth_radius

    def _cartesian_to_sphere(self, x, y):
        # Ajustando a escala para ter aproximadamente 6km pico a pico
        # scale = 0.0000001  # Reduzido por um fator de 10
        scale = scale = 1 / self.earth_radius
        x_scaled = x * scale
        y_scaled = y * scale

        lat = self.central_latitude + y_scaled
        lon = self.central_longitude + x_scaled / np.cos(self.central_latitude)

        x = self.earth_radius * np.cos(lat) * np.cos(lon)
        y = self.earth_radius * np.cos(lat) * np.sin(lon)
        z = self.earth_radius * np.sin(lat)

        return np.array([x, y, z])

    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        """
        Calcula as coordenadas seguindo a mesma lógica do TopologyMacrocell,
        mas adicionando a projeção para coordenadas esféricas.
        """
        # Primeiro executa o cálculo original do TopologyMacrocell
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

    def _generate_hex_vertices_planar(self, center_x, center_y):
        """Gera os vértices do hexágono no plano, igual ao TopologyMacrocell"""
        vertices = []
        r = self.intersite_distance / 3
        for angle in range(0, 360, 60):
            rad = np.radians(angle)
            x = center_x + r * np.cos(rad)
            y = center_y + r * np.sin(rad)
            vertices.append([x, y])
        return vertices

    def plot_3d(self, ax=None):
        if ax is None:
            fig = plt.figure(figsize=(12, 12))
            ax = fig.add_subplot(111, projection="3d")

        # Plot do globo
        u = np.linspace(0, 2 * np.pi, 100)
        v = np.linspace(0, np.pi, 100)
        x = self.earth_radius * np.outer(np.cos(u), np.sin(v))
        y = self.earth_radius * np.outer(np.sin(u), np.sin(v))
        z = self.earth_radius * np.outer(np.ones(np.size(u)), np.cos(v))
        ax.plot_surface(x, y, z, color="lightblue", alpha=0.3)

        # Cria os hexágonos para todos os pontos
        r = self.intersite_distance / 3
        for x, y, az in zip(self.planar_x, self.planar_y, self.planar_azimuth):
            # Começa do ponto da estação base
            se = [[x, y]]
            angle = int(az - 60)  # Começa 60 graus antes do azimute

            # Adiciona os 6 vértices do hexágono
            for a in range(6):
                next_x = se[-1][0] + r * math.cos(math.radians(angle))
                next_y = se[-1][1] + r * math.sin(math.radians(angle))
                se.append([next_x, next_y])
                angle += 60

            # Projeta os pontos para coordenadas esféricas
            vertices = [self._cartesian_to_sphere(vx, vy) for vx, vy in se]
            vertices = np.array(vertices)
            vertices = np.vstack([vertices, vertices[0]])  # Fecha o polígono

            ax.plot(
                vertices[:, 0],
                vertices[:, 1],
                vertices[:, 2],
                color="black",
                alpha=0.8,
                linewidth=1,
            )

        # Plot das estações base
        ax.scatter(
            self.x_sphere,
            self.y_sphere,
            self.z_sphere,
            color="black",
            s=50,
            label="Base Stations",
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

        ax.set_title("Macrocell Topology on Globe")
        ax.legend()

        return ax

    def export_to_kml(self, filename="macrocell_topology.kml"):
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


if __name__ == "__main__":
    intersite_distance = 500
    num_clusters = 7
    central_latitude = -15.7801  # Brasília
    central_longitude = -47.9292  # Brasília

    topology = TopologyMacrocellSpherical(
        intersite_distance=intersite_distance,
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
