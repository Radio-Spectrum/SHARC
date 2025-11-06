import os
from core.geodesy import lla_to_ecef

try:
    import shapefile as pyshp 
    HAS_PYSHP = True
except Exception:
    HAS_PYSHP = False

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