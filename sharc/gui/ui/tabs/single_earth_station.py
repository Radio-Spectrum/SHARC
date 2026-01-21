# single_earth_tab.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from utils import add_row_three

SUPPORTED_ANTENNA_PATTERNS = [
    "OMNI", "HibleoX", "ITU-R F.699", "ITU-R S.465", "ITU-R S.580",
    "MODIFIED ITU-R S.465", "ITU-R S.1855", "ITU-R Reg. RR. Appendice 7 Annex 3",
    "ARRAY", "ITU-R-S.1528-Taylor", "ITU-R-S.1528-Section1.2",
    "ITU-R-S.1528-LEO", "MSS Adjacent", "ITU-R S.672",
    "ITU-R F.1245_fs", "RA_M2319",
]

AZ_EL_TYPES = ["UNIFORM_DIST", "FIXED", "POINTING_AT_IMT_CENTER"]
LOC_TYPES = ["FIXED", "CELL", "NETWORK", "UNIFORM_DIST"]
CHANNEL_MODELS = ["FSPL", "P452"]

class SingleEarthStationTab:
    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame
        
        # Constrói a UI imediatamente
        self._build_ui()

    def _build_ui(self):
        # Frame principal (pai)
        main_container = self.frame
        app = self.app 

        # --- TOP BAR (Fixa, não rola) ---
        topbar = ttk.Frame(main_container)
        topbar.pack(fill="x", pady=(0, 6), side="top")

        actions = ttk.Frame(topbar)
        actions.pack(side="right")
        ttk.Button(actions, text="Salvar config", command=self._se_save_config).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Carregar config", command=self._se_load_config).pack(side="left")

        # --- ÁREA DE SCROLL ---
        # 1. Cria o Canvas e a Scrollbar
        canvas_frame = ttk.Frame(main_container)
        canvas_frame.pack(fill="both", expand=True, side="top")

        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        
        # 2. Cria o Frame interno que conterá os widgets (scrollable_frame)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # O 'root' agora passa a ser esse frame interno
        root = self.scrollable_frame

        # 3. Configura a janela dentro do canvas
        # window_id é guardado para redimensionar a largura corretamente
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # 4. Lógica de atualização do Scrollregion
        def configure_scroll_region(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def configure_window_width(event):
            # Ajusta a largura do frame interno para igualar a do canvas (evita que fique estreito)
            self.canvas.itemconfig(self.canvas_window, width=event.width)

        self.scrollable_frame.bind("<Configure>", configure_scroll_region)
        self.canvas.bind("<Configure>", configure_window_width)

        # 5. Configurações finais de pack do canvas
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # 6. Bind do Mouse Wheel (Scroll do mouse)
        self._bind_mouse_scroll(self.canvas)
        self._bind_mouse_scroll(self.scrollable_frame)

        # --- A PARTIR DAQUI, O CÓDIGO É O MESMO, MAS USANDO 'root' (que é o scrollable_frame) ---

        # --- BASIC PARAMETERS ---
        frm0 = ttk.LabelFrame(root, text="Parâmetros básicos")
        frm0.pack(fill="x", padx=2, pady=4)

        add_row_three(frm0, 0, [
            ("frequency [MHz]", ttk.Entry(frm0, textvariable=app.se_frequency, width=12)),
            ("bandwidth [MHz]", ttk.Entry(frm0, textvariable=app.se_bandwidth, width=12)),
            ("noise_temperature [K]", ttk.Entry(frm0, textvariable=app.se_noise_temperature, width=12)),
        ])
        add_row_three(frm0, 1, [
            ("adjacent_ch_reception", ttk.Combobox(frm0, textvariable=app.se_adjacent_ch_reception, values=["ACS", "OFF"], width=12, state="readonly")),
            ("adjacent_ch_selectivity [dB]", ttk.Entry(frm0, textvariable=app.se_adjacent_ch_selectivity, width=12)),
            ("adjacent_ch_emissions", ttk.Combobox(frm0, textvariable=app.se_adjacent_ch_emissions, values=["ACLR", "SPECTRAL_MASK", "OFF"], width=14, state="readonly")),
        ])
        add_row_three(frm0, 2, [
            ("adjacent_ch_leak_ratio [dB]", ttk.Entry(frm0, textvariable=app.se_adjacent_ch_leak_ratio, width=12)),
            ("spectral_mask", ttk.Entry(frm0, textvariable=app.se_spectral_mask, width=18)),
            ("spurious_emissions [dBm/MHz]", ttk.Entry(frm0, textvariable=app.se_spurious_emissions, width=14)),
        ])
        add_row_three(frm0, 3, [
            ("tx_power_density [dBW/Hz]", ttk.Entry(frm0, textvariable=app.se_tx_power_density, width=14)),
            ("height [m]", ttk.Entry(frm0, textvariable=app.se_height, width=12)),
            ("polarization_loss [dB] (opt.)", ttk.Entry(frm0, textvariable=app.se_polarization_loss, width=12)),
        ])

        # --- GEOMETRY ---
        geom = ttk.LabelFrame(root, text="Geometria")
        geom.pack(fill="x", padx=2, pady=4)

        # Location
        loc_box = ttk.LabelFrame(geom, text="Posição (location)")
        loc_box.pack(fill="x", padx=2, pady=(6, 6))

        add_row_three(loc_box, 0, [
            ("location.type", ttk.Combobox(loc_box, textvariable=app.se_loc_type, values=LOC_TYPES, width=14, state="readonly")),
            ("", ttk.Label(loc_box, text="")), ("", ttk.Label(loc_box, text="")),
        ])

        self.loc_fixed = ttk.Frame(loc_box)
        self.loc_cell = ttk.Frame(loc_box)
        self.loc_net = ttk.Frame(loc_box)
        self.loc_ud = ttk.Frame(loc_box)

        for f in (self.loc_fixed, self.loc_cell, self.loc_net, self.loc_ud):
            f.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 0))
            f.grid_remove()

        add_row_three(self.loc_fixed, 0, [
            ("x [m]", ttk.Entry(self.loc_fixed, textvariable=app.se_loc_fixed_x, width=12)),
            ("y [m]", ttk.Entry(self.loc_fixed, textvariable=app.se_loc_fixed_y, width=12)), ("", ttk.Label(self.loc_fixed, text="")),
        ])
        add_row_three(self.loc_cell, 0, [
            ("cell.min_dist_to_bs [m]", ttk.Entry(self.loc_cell, textvariable=app.se_loc_cell_min_dist_to_bs, width=14)),
            ("", ttk.Label(self.loc_cell, text="")), ("", ttk.Label(self.loc_cell, text="")),
        ])
        add_row_three(self.loc_net, 0, [
            ("network.min_dist_to_bs [m]", ttk.Entry(self.loc_net, textvariable=app.se_loc_network_min_dist_to_bs, width=14)),
            ("", ttk.Label(self.loc_net, text="")), ("", ttk.Label(self.loc_net, text="")),
        ])
        add_row_three(self.loc_ud, 0, [
            ("min_dist_to_center [m]", ttk.Entry(self.loc_ud, textvariable=app.se_loc_ud_min_dist_to_center, width=18)),
            ("max_dist_to_center [m]", ttk.Entry(self.loc_ud, textvariable=app.se_loc_ud_max_dist_to_center, width=18)), ("", ttk.Label(self.loc_ud, text="")),
        ])

        app.se_loc_type.trace_add("write", self._refresh_loc_ui)
        self._refresh_loc_ui()

        # Azimuth / Elevation
        ae_box = ttk.LabelFrame(geom, text="Direção da antena (azimuth / elevation)")
        ae_box.pack(fill="x", padx=2, pady=(0, 6))

        col_az = ttk.LabelFrame(ae_box, text="Azimuth")
        col_el = ttk.LabelFrame(ae_box, text="Elevation")
        col_az.grid(row=0, column=0, sticky="nsew", padx=(2, 6), pady=2)
        col_el.grid(row=0, column=1, sticky="nsew", padx=(6, 2), pady=2)
        ae_box.columnconfigure(0, weight=1)
        ae_box.columnconfigure(1, weight=1)

        # Azimuth
        ttk.Label(col_az, text="type").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        cb_az = ttk.Combobox(col_az, textvariable=app.se_az_type, values=AZ_EL_TYPES, width=22, state="readonly")
        cb_az.grid(row=0, column=1, sticky="w", padx=4, pady=(4, 2))

        self.az_fixed = ttk.Frame(col_az)
        self.az_ud = ttk.Frame(col_az)
        self.az_fixed.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        self.az_ud.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        
        ttk.Label(self.az_fixed, text="fixed [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(self.az_fixed, textvariable=app.se_az_fixed, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(self.az_ud, text="min [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(self.az_ud, textvariable=app.se_az_ud_min, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(self.az_ud, text="max [deg]").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(self.az_ud, textvariable=app.se_az_ud_max, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        self.az_hint = ttk.Label(col_az, text="(POINTING_AT_IMT_CENTER: automático)", foreground="#555")
        self.az_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 6))

        app.se_az_type.trace_add("write", self._refresh_az_ui)
        self._refresh_az_ui()

        # Elevation
        ttk.Label(col_el, text="type").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        cb_el = ttk.Combobox(col_el, textvariable=app.se_el_type, values=AZ_EL_TYPES, width=22, state="readonly")
        cb_el.grid(row=0, column=1, sticky="w", padx=4, pady=(4, 2))

        self.el_fixed = ttk.Frame(col_el)
        self.el_ud = ttk.Frame(col_el)
        self.el_fixed.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        self.el_ud.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        
        ttk.Label(self.el_fixed, text="fixed [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(self.el_fixed, textvariable=app.se_el_fixed, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(self.el_ud, text="min [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(self.el_ud, textvariable=app.se_el_ud_min, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(self.el_ud, text="max [deg]").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(self.el_ud, textvariable=app.se_el_ud_max, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        self.el_hint = ttk.Label(col_el, text="(POINTING_AT_IMT_CENTER: n/a p/ elevação)", foreground="#555")
        self.el_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 6))

        app.se_el_type.trace_add("write", self._refresh_el_ui)
        self._refresh_el_ui()

        # --- ANTENNA ---
        ant = ttk.LabelFrame(root, text="Antena (pattern + parâmetros)")
        ant.pack(fill="x", padx=2, pady=4)

        add_row_three(ant, 0, [
            ("antenna.pattern", ttk.Combobox(ant, textvariable=app.se_ant_pattern, values=SUPPORTED_ANTENNA_PATTERNS, width=28, state="readonly")),
            ("antenna.gain [dBi]", ttk.Entry(ant, textvariable=app.se_ant_gain, width=12)), ("", ttk.Label(ant, text="")),
        ])

        self.ant_diam = ttk.Frame(ant); self.ant_env = ttk.Frame(ant); self.ant_s672 = ttk.Frame(ant)
        self.ant_f1245 = ttk.Frame(ant); self.ant_hint = ttk.Frame(ant)

        for f in (self.ant_diam, self.ant_env, self.ant_s672, self.ant_f1245, self.ant_hint):
            f.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 0))
            f.grid_remove()

        ttk.Label(self.ant_hint, text="Selecione um pattern para ver os parâmetros específicos.").grid(row=0, column=0, sticky="w")
        
        # Conteúdo dos frames de antena
        add_row_three(self.ant_diam, 0, [("diameter [m]", ttk.Entry(self.ant_diam, textvariable=app.se_ant_diameter, width=12)), ("", ttk.Label(self.ant_diam, text="(freq e gain vêm do sistema)")), ("", ttk.Label(self.ant_diam, text=""))])
        add_row_three(self.ant_env, 0, [("envelope_gain [dB]", ttk.Entry(self.ant_env, textvariable=app.se_ant_envelope_gain, width=12)), ("", ttk.Label(self.ant_env, text="")), ("", ttk.Label(self.ant_env, text=""))])
        add_row_three(self.ant_s672, 0, [("antenna_3_dB [deg]", ttk.Entry(self.ant_s672, textvariable=app.se_ant_3db, width=12)), ("antenna_l_s [dB] (opt.)", ttk.Entry(self.ant_s672, textvariable=app.se_ant_l_s, width=12)), ("", ttk.Label(self.ant_s672, text=""))])
        add_row_three(self.ant_f1245, 0, [("gain (F1245) [dB]", ttk.Entry(self.ant_f1245, textvariable=app.se_ant_f1245_gain, width=12)), ("diameter [m]", ttk.Entry(self.ant_f1245, textvariable=app.se_ant_f1245_diameter, width=12)), ("frequency [MHz]", ttk.Entry(self.ant_f1245, textvariable=app.se_ant_f1245_frequency, width=12))])

        app.se_ant_pattern.trace_add("write", self._refresh_ant_ui)
        self._refresh_ant_ui()

        # --- CHANNEL MODEL ---
        ch = ttk.LabelFrame(root, text="Channel model")
        ch.pack(fill="x", padx=2, pady=4)
        add_row_three(ch, 0, [
            ("channel_model", ttk.Combobox(ch, textvariable=app.se_channel_model, values=CHANNEL_MODELS, width=10, state="readonly")), ("", ttk.Label(ch, text="")), ("", ttk.Label(ch, text="")),
        ])

        self.p452_box = ttk.LabelFrame(ch, text="P452 parameters")
        self.p452_box.grid(row=1, column=0, columnspan=6, sticky="ew", padx=2, pady=(6, 2))
        
        add_row_three(self.p452_box, 0, [("atmospheric_pressure [hPa]", ttk.Entry(self.p452_box, textvariable=app.p452_atmospheric_pressure, width=12)), ("air_temperature [K]", ttk.Entry(self.p452_box, textvariable=app.p452_air_temperature, width=12)), ("p_452 [%]", ttk.Entry(self.p452_box, textvariable=app.p452_percentage_p, width=12))])
        add_row_three(self.p452_box, 1, [("N0", ttk.Entry(self.p452_box, textvariable=app.p452_N0, width=12)), ("delta_N", ttk.Entry(self.p452_box, textvariable=app.p452_delta_N, width=12)), ("polarization", ttk.Entry(self.p452_box, textvariable=app.p452_polarization, width=12))])
        add_row_three(self.p452_box, 2, [("Dct [km]", ttk.Entry(self.p452_box, textvariable=app.p452_Dct, width=12)), ("Dcr [km]", ttk.Entry(self.p452_box, textvariable=app.p452_Dcr, width=12)), ("", ttk.Label(self.p452_box, text=""))])
        add_row_three(self.p452_box, 3, [("Hte [m]", ttk.Entry(self.p452_box, textvariable=app.p452_Hte, width=12, state="readonly")), ("Hre [m]", ttk.Entry(self.p452_box, textvariable=app.p452_Hre, width=12, state="readonly")), ("clutter_loss", ttk.Checkbutton(self.p452_box, variable=app.p452_clutter_loss))])

        self.clutter_row = ttk.Frame(self.p452_box)
        self.clutter_row.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(2, 0))
        self.clutter_row.columnconfigure(0, weight=1)
        ttk.Label(self.clutter_row, text="clutter_type").grid(row=0, column=1, sticky="e", padx=4, pady=2)
        ttk.Combobox(self.clutter_row, textvariable=app.p452_clutter_type, values=["one_end", "both_ends"], width=12, state="readonly").grid(row=0, column=2, sticky="w", padx=4, pady=2)

        add_row_three(self.p452_box, 5, [("tx_lat [deg]", ttk.Entry(self.p452_box, textvariable=app.p452_tx_lat, width=12)), ("rx_lat [deg]", ttk.Entry(self.p452_box, textvariable=app.p452_rx_lat, width=12)), ("is_terrain", ttk.Checkbutton(self.p452_box, variable=app.p452_is_terrain))])

        # Sincronia de alturas e visibilidade
        def _sync_hre_with_height(*_):
            app.p452_Hre.set(app.se_height.get())
            if hasattr(app, 'bs_height') and hasattr(app, 'ue_height') and hasattr(app, 'var_imt_link'):
                if app.var_imt_link.get() == "DOWNLINK":
                    app.p452_Hte.set(app.bs_height.get())
                else:
                    app.p452_Hte.set(app.ue_height.get())

        app.se_height.trace_add("write", _sync_hre_with_height)
        _sync_hre_with_height()

        app.se_channel_model.trace_add("write", self._refresh_ch_ui)
        app.p452_clutter_loss.trace_add("write", self._refresh_clutter_ui)
        self._refresh_ch_ui()

        # Espaço extra no final do scroll
        ttk.Frame(root, height=30).pack(fill="x")

    def _bind_mouse_scroll(self, widget):
        """Binda o scroll do mouse ao widget (suporta Windows, Linux, MacOS)."""
        def _on_mousewheel(event):
            # Windows e MacOS
            if event.delta:
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _on_linux_scroll_up(event):
            self.canvas.yview_scroll(-1, "units")
            
        def _on_linux_scroll_down(event):
            self.canvas.yview_scroll(1, "units")

        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_linux_scroll_up)
        widget.bind("<Button-5>", _on_linux_scroll_down)

    # --- UI Logic Methods (converted to instance methods) ---
    def _refresh_loc_ui(self, *args):
        t = (self.app.se_loc_type.get() or "").strip()
        for f in (self.loc_fixed, self.loc_cell, self.loc_net, self.loc_ud): f.grid_remove()
        if t == "FIXED": self.loc_fixed.grid()
        elif t == "CELL": self.loc_cell.grid()
        elif t == "NETWORK": self.loc_net.grid()
        elif t == "UNIFORM_DIST": self.loc_ud.grid()

    def _refresh_az_ui(self, *args):
        t = (self.app.se_az_type.get() or "").strip()
        self.az_fixed.grid_remove(); self.az_ud.grid_remove(); self.az_hint.grid_remove()
        if t == "UNIFORM_DIST": self.az_ud.grid()
        elif t == "FIXED": self.az_fixed.grid()
        elif t == "POINTING_AT_IMT_CENTER": self.az_hint.grid()

    def _refresh_el_ui(self, *args):
        t = (self.app.se_el_type.get() or "").strip()
        self.el_fixed.grid_remove(); self.el_ud.grid_remove(); self.el_hint.grid_remove()
        if t == "UNIFORM_DIST": self.el_ud.grid()
        elif t == "FIXED": self.el_fixed.grid()
        elif t == "POINTING_AT_IMT_CENTER": self.el_hint.grid()

    def _refresh_ant_ui(self, *args):
        pat = (self.app.se_ant_pattern.get() or "").strip()
        for f in (self.ant_diam, self.ant_env, self.ant_s672, self.ant_f1245, self.ant_hint): f.grid_remove()
        diameter_patterns = {"ITU-R F.699", "ITU-R S.465", "ITU-R S.580", "ITU-R S.1855", "ITU-R Reg. RR. Appendice 7 Annex 3"}
        if not pat: self.ant_hint.grid()
        elif pat in diameter_patterns: self.ant_diam.grid()
        elif pat == "MODIFIED ITU-R S.465": self.ant_env.grid()
        elif pat == "ITU-R S.672": self.ant_s672.grid()
        elif pat == "ITU-R F.1245_fs": self.ant_f1245.grid()
        else: self.ant_hint.grid()

    def _refresh_ch_ui(self, *args):
        if (self.app.se_channel_model.get() or "").strip() == "P452":
            self.p452_box.grid()
        else:
            self.p452_box.grid_remove()
        self._refresh_clutter_ui()

    def _refresh_clutter_ui(self, *args):
        is_p452 = (self.app.se_channel_model.get() or "").strip() == "P452"
        if is_p452 and bool(self.app.p452_clutter_loss.get()):
            self.clutter_row.grid()
        else:
            self.clutter_row.grid_remove()

    # --- SAVE / LOAD (Methods mapped to use self.app) ---
    def _se_collect_config(self):
        """Collect SINGLE_EARTH_STATION UI variables into a dict."""
        def g(v): return v.get()
        app = self.app
        cfg = {
            "frequency": g(app.se_frequency), "bandwidth": g(app.se_bandwidth), "noise_temperature": g(app.se_noise_temperature),
            "adjacent_ch_reception": g(app.se_adjacent_ch_reception), "adjacent_ch_selectivity": g(app.se_adjacent_ch_selectivity),
            "adjacent_ch_emissions": g(app.se_adjacent_ch_emissions), "adjacent_ch_leak_ratio": g(app.se_adjacent_ch_leak_ratio),
            "spectral_mask": g(app.se_spectral_mask), "spurious_emissions": g(app.se_spurious_emissions),
            "tx_power_density": g(app.se_tx_power_density), "height": g(app.se_height),
            "geometry": {
                "location": {
                    "type": g(app.se_loc_type),
                    "fixed": {"x": g(app.se_loc_fixed_x), "y": g(app.se_loc_fixed_y)},
                    "cell": {"min_dist_to_bs": g(app.se_loc_cell_min_dist_to_bs)},
                    "network": {"min_dist_to_bs": g(app.se_loc_network_min_dist_to_bs)},
                    "uniform_dist": {"min_dist_to_center": g(app.se_loc_ud_min_dist_to_center), "max_dist_to_center": g(app.se_loc_ud_max_dist_to_center)},
                },
                "azimuth": {
                    "type": g(app.se_az_type), "fixed": g(app.se_az_fixed),
                    "uniform_dist": {"min": g(app.se_az_ud_min), "max": g(app.se_az_ud_max)},
                },
                "elevation": {
                    "type": g(app.se_el_type), "fixed": g(app.se_el_fixed),
                    "uniform_dist": {"min": g(app.se_el_ud_min), "max": g(app.se_el_ud_max)},
                },
            },
            "antenna": {
                "pattern": g(app.se_ant_pattern), "gain": g(app.se_ant_gain),
                "diameter": g(app.se_ant_diameter), "envelope_gain": g(app.se_ant_envelope_gain),
            },
            "channel_model": g(app.se_channel_model),
            "p452": {
                "atmospheric_pressure": g(app.p452_atmospheric_pressure), "air_temperature": g(app.p452_air_temperature),
                "N0": g(app.p452_N0), "delta_N": g(app.p452_delta_N), "percentage_p": g(app.p452_percentage_p),
                "Dct": g(app.p452_Dct), "Dcr": g(app.p452_Dcr), "Hte": g(app.p452_Hte),
                "tx_lat": g(app.p452_tx_lat), "rx_lat": g(app.p452_rx_lat), "polarization": g(app.p452_polarization),
                "clutter_loss": bool(app.p452_clutter_loss.get()), "clutter_type": g(app.p452_clutter_type),
                "is_terrain": bool(app.p452_is_terrain.get()),
            },
        }
        return cfg

    def _se_apply_config(self, cfg: dict):
        """Apply config dict to SINGLE_EARTH_STATION UI."""
        def s(var, val):
            if val is not None: var.set(val)
        
        app = self.app
        # --- (A lógica de parsing do seu código, mapeando para self.app) ---
        s(app.se_frequency, cfg.get("frequency")); s(app.se_bandwidth, cfg.get("bandwidth")); s(app.se_noise_temperature, cfg.get("noise_temperature"))
        s(app.se_adjacent_ch_reception, cfg.get("adjacent_ch_reception")); s(app.se_adjacent_ch_selectivity, cfg.get("adjacent_ch_selectivity"))
        s(app.se_adjacent_ch_emissions, cfg.get("adjacent_ch_emissions")); s(app.se_adjacent_ch_leak_ratio, cfg.get("adjacent_ch_leak_ratio"))
        s(app.se_spectral_mask, cfg.get("spectral_mask")); s(app.se_spurious_emissions, cfg.get("spurious_emissions"))
        s(app.se_tx_power_density, cfg.get("tx_power_density")); s(app.se_height, cfg.get("height"))

        geom = cfg.get("geometry", {}); loc = geom.get("location", {})
        s(app.se_loc_type, loc.get("type"))
        s(app.se_loc_fixed_x, loc.get("fixed", {}).get("x")); s(app.se_loc_fixed_y, loc.get("fixed", {}).get("y"))
        s(app.se_loc_cell_min_dist_to_bs, loc.get("cell", {}).get("min_dist_to_bs"))
        s(app.se_loc_network_min_dist_to_bs, loc.get("network", {}).get("min_dist_to_bs"))
        ud = loc.get("uniform_dist", {})
        s(app.se_loc_ud_min_dist_to_center, ud.get("min_dist_to_center")); s(app.se_loc_ud_max_dist_to_center, ud.get("max_dist_to_center"))

        az = geom.get("azimuth", {}); s(app.se_az_type, az.get("type")); s(app.se_az_fixed, az.get("fixed"))
        s(app.se_az_ud_min, az.get("uniform_dist", {}).get("min")); s(app.se_az_ud_max, az.get("uniform_dist", {}).get("max"))
        
        el = geom.get("elevation", {}); s(app.se_el_type, el.get("type")); s(app.se_el_fixed, el.get("fixed"))
        s(app.se_el_ud_min, el.get("uniform_dist", {}).get("min")); s(app.se_el_ud_max, el.get("uniform_dist", {}).get("max"))

        ant = cfg.get("antenna", {}); s(app.se_ant_pattern, ant.get("pattern")); s(app.se_ant_gain, ant.get("gain"))
        s(app.se_ant_diameter, ant.get("diameter")); s(app.se_ant_envelope_gain, ant.get("envelope_gain"))
        
        s(app.se_channel_model, cfg.get("channel_model"))
        p = cfg.get("p452", {})
        s(app.p452_atmospheric_pressure, p.get("atmospheric_pressure")); s(app.p452_air_temperature, p.get("air_temperature"))
        s(app.p452_N0, p.get("N0")); s(app.p452_delta_N, p.get("delta_N")); s(app.p452_percentage_p, p.get("percentage_p"))
        s(app.p452_Dct, p.get("Dct")); s(app.p452_Dcr, p.get("Dcr")); s(app.p452_Hte, p.get("Hte"))
        s(app.p452_tx_lat, p.get("tx_lat")); s(app.p452_rx_lat, p.get("rx_lat")); s(app.p452_polarization, p.get("polarization"))
        app.p452_clutter_loss.set(bool(p.get("clutter_loss", False)))
        s(app.p452_clutter_type, p.get("clutter_type"))
        app.p452_is_terrain.set(bool(p.get("is_terrain", False)))

        # Força refresh visual chamando os métodos da instância
        self._refresh_loc_ui()
        self._refresh_az_ui()
        self._refresh_el_ui()
        self._refresh_ant_ui()
        self._refresh_ch_ui()

    def _se_save_config(self):
        try:
            fpath = filedialog.asksaveasfilename(title="Salvar config Earth Station", defaultextension=".json", filetypes=[("JSON", "*.json")])
            if fpath:
                with open(fpath, "w", encoding="utf-8") as f: json.dump(self._se_collect_config(), f, indent=2)
                messagebox.showinfo("Config", f"Salvo em:\n{fpath}")
        except Exception as e: messagebox.showerror("Erro", str(e))

    def _se_load_config(self):
        try:
            fpath = filedialog.askopenfilename(title="Carregar config Earth Station", filetypes=[("JSON", "*.json")])
            if fpath:
                with open(fpath, "r", encoding="utf-8") as f: self._se_apply_config(json.load(f))
                messagebox.showinfo("Config", "Configuração carregada com sucesso.")
        except Exception as e: messagebox.showerror("Erro", str(e))