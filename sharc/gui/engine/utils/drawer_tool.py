import os
from core.geodesy import lla_to_ecef
from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
from sharc.antenna.antenna_s672 import AntennaS672

try:
    import shapefile as pyshp 
    HAS_PYSHP = True
except Exception:
    HAS_PYSHP = False

def _make_s672_antenna(root):
    """
    Constrói uma AntennaS672 a partir dos controles da UI (ganho de pico, L_s e 3 dB).
    """
    param = ParametersAntennaS672()
    # seus vars (ajuste os nomes se forem diferentes):
    # ganho de pico [dBi]
    param.antenna_gain = float(root.v_ant_gain.get())
    # largura de feixe 3 dB (atenção: o objeto original usa 'antenna_3_dB' ou 'antenna_3_dB_bw';
    # mapeie para 'antenna_3_dB' se necessário)
    param.antenna_3_dB = float(root.v_s672_3db.get())
    param.antenna_3_dB_bw = float(root.v_s672_3db.get())
    # L_s (-20, -25, -30 dB)
    param.antenna_l_s = float(root.v_s672_ls.get())
    return AntennaS672(param)

def _draw_country_borders(root):
    """Draw country borders from a shapefile onto the globe."""
    if not root.show_borders.get() or not HAS_PYSHP:
        return
    shp_path = root.path_shp.get()
    if not os.path.isfile(shp_path):
        return
    try:
        r = pyshp.Reader(shp_path)
        for sr in r.shapeRecords():
            shp = sr.shape
            pts = shp.points
            if not pts:
                continue
            parts = list(shp.parts) + [len(pts)]
            for i in range(len(parts) - 1):
                sub = pts[parts[i]:parts[i+1]]
                if len(sub) < 2:
                    continue
                lons = [p[0] for p in sub]
                lats = [p[1] for p in sub]
                x, y, z = lla_to_ecef(lats, lons, 0.0)
                root.ax3d.plot(x, y, z, lw=0.35, color="k", alpha=0.55, zorder=5, antialiased=True)
    except Exception:
        pass