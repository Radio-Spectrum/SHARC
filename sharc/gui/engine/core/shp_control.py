from tkinter import filedialog
import tkinter as tk

def _browse_shapefile(self):
            fn = filedialog.askopenfilename(
                title="Escolher shapefile de países",
                filetypes=[("Shapefile", "*.shp"), ("Todos os arquivos", "*.*")]
            )
            if fn:
                self.path_shp.set(fn)


def _browse_raster(self):
    fn = filedialog.askopenfilename(
        title="Escolher raster de população (SEDAC/GeoTIFF)",
        filetypes=[("GeoTIFF", "*.tif;*.tiff"), ("Todos os arquivos", "*.*")]
    )
    if fn:
        self.path_raster.set(fn)


def _toggle_raster_by_encoding(root, *_):

    topo_raster_enc = tk.StringVar(value="Denspop")
    enc = (topo_raster_enc.get() or "").strip()
    if enc == "Uniforme":
        # desliga e limpa o raster
        root.path_raster.set("")
        root.ent_raster.configure(state="disabled")
        root.btn_raster.configure(state="disabled")
    else:
        # habilita para Denspop
        root.ent_raster.configure(state="normal")
        root.btn_raster.configure(state="normal")