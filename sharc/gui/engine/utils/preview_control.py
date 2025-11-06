from tkinter import messagebox, filedialog
import time

"""
Controls scroll in 3d preview
"""


def _zoom_preview_3d(root, factor):
        """Zoom no 3D: factor>1 dá zoom out; <1 dá zoom in."""
        try:
            # Preferível quando disponível (Matplotlib 3D antigo)
            if hasattr(root.ax3d, "dist"):
                root.ax3d.dist = max(1, float(root.ax3d.dist) * float(factor))
                root.canvas3d.draw_idle()
                return
        except Exception:
            pass


def _on_scroll_3d(root, event):
        def zoom_preview_3d(factor):
             _zoom_preview_3d(root, factor)

        """
        Zoom pelo scroll do mouse.
        - Windows/macOS: event.delta > 0 (zoom in), < 0 (zoom out)
        - Linux/X11: event.num == 4 (up -> in), 5 (down -> out)
        """
        # fator base (suave). maior => zoom mais “forte”
        base = 1.12
        direction = 0
        try:
            if hasattr(event, "num") and event.num in (4, 5):
                # Linux
                direction = -1 if event.num == 4 else 1
            else:
                # Windows/macOS
                direction = -1 if getattr(event, "delta", 0) > 0 else 1
        except Exception:
            direction = 1

        factor = (1.0 / base) if direction < 0 else base
        _zoom_preview_3d(factor)



def _save_image_3d(root):
    suggested = f"topology3d_{time.strftime('%Y%m%d_%H%M%S')}.png"
    path = filedialog.asksaveasfilename(
        title="Salvar imagem",
        defaultextension=".png",
        initialfile=suggested,
        filetypes=[("PNG", "*.png"), ("All files", "*.*")]
    )
    if not path:
        return
    root.fig3d.savefig(path, dpi=180, bbox_inches="tight")
    messagebox.showinfo("OK", f"Imagem salva em:\n{path}")