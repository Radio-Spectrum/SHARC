# Auto-generated SINGLE_EARTH_STATION (victim) tab
# Uses GRID consistently inside each container (no pack/grid mixing).
from sharc_gui.common.imports import *  # noqa
from tkinter import filedialog, messagebox
import json


SUPPORTED_ANTENNA_PATTERNS = [
    "OMNI",
    "HibleoX",
    "ITU-R F.699",
    "ITU-R S.465",
    "ITU-R S.580",
    "MODIFIED ITU-R S.465",
    "ITU-R S.1855",
    "ITU-R Reg. RR. Appendice 7 Annex 3",
    "ARRAY",
    "ITU-R-S.1528-Taylor",
    "ITU-R-S.1528-Section1.2",
    "ITU-R-S.1528-LEO",
    "MSS Adjacent",
    "ITU-R S.672",
    "ITU-R F.1245_fs",
    "RA_M2319",
]

AZ_EL_TYPES = ["UNIFORM_DIST", "FIXED", "POINTING_AT_IMT_CENTER"]
LOC_TYPES = ["FIXED", "CELL", "NETWORK", "UNIFORM_DIST"]
CHANNEL_MODELS = ["FSPL", "P452"]


class VictimEarthTabTabMixin:
    def _tab_victim_earth(self, root):
        app = self  # capture correct self for callbacks

        # Root layout: use pack only at the very top level (safe), and grid inside frames.
        topbar = ttk.Frame(root)
        topbar.pack(fill="x", pady=(0, 6))
        ttk.Label(
            topbar,
            text="SINGLE_EARTH_STATION – parâmetros de vítima (Earth Station)",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        # Right-side actions: Save / Load config
        actions = ttk.Frame(topbar)
        actions.pack(side="right")
        ttk.Button(actions, text="Salvar config", command=app._se_save_config).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Carregar config", command=app._se_load_config).pack(side="left")

        # -------------------------
        # BASIC PARAMETERS
        # -------------------------
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

        # -------------------------
        # GEOMETRY
        # -------------------------
        geom = ttk.LabelFrame(root, text="Geometria")
        geom.pack(fill="x", padx=2, pady=4)

        # Location
        loc_box = ttk.LabelFrame(geom, text="Posição (location)")
        loc_box.pack(fill="x", padx=2, pady=(6, 6))

        add_row_three(loc_box, 0, [
            ("location.type", ttk.Combobox(loc_box, textvariable=app.se_loc_type, values=LOC_TYPES, width=14, state="readonly")),
            ("", ttk.Label(loc_box, text="")),
            ("", ttk.Label(loc_box, text="")),
        ])

        # Option frames inside loc_box: use GRID (row=1) and grid_remove/grid for show/hide
        loc_fixed = ttk.Frame(loc_box)
        loc_cell = ttk.Frame(loc_box)
        loc_net = ttk.Frame(loc_box)
        loc_ud = ttk.Frame(loc_box)

        for f in (loc_fixed, loc_cell, loc_net, loc_ud):
            f.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 0))
            f.grid_remove()

        add_row_three(loc_fixed, 0, [
            ("x [m]", ttk.Entry(loc_fixed, textvariable=app.se_loc_fixed_x, width=12)),
            ("y [m]", ttk.Entry(loc_fixed, textvariable=app.se_loc_fixed_y, width=12)),
            ("", ttk.Label(loc_fixed, text="")),
        ])
        add_row_three(loc_cell, 0, [
            ("cell.min_dist_to_bs [m]", ttk.Entry(loc_cell, textvariable=app.se_loc_cell_min_dist_to_bs, width=14)),
            ("", ttk.Label(loc_cell, text="")),
            ("", ttk.Label(loc_cell, text="")),
        ])
        add_row_three(loc_net, 0, [
            ("network.min_dist_to_bs [m]", ttk.Entry(loc_net, textvariable=app.se_loc_network_min_dist_to_bs, width=14)),
            ("", ttk.Label(loc_net, text="")),
            ("", ttk.Label(loc_net, text="")),
        ])
        add_row_three(loc_ud, 0, [
            ("min_dist_to_center [m]", ttk.Entry(loc_ud, textvariable=app.se_loc_ud_min_dist_to_center, width=18)),
            ("max_dist_to_center [m]", ttk.Entry(loc_ud, textvariable=app.se_loc_ud_max_dist_to_center, width=18)),
            ("", ttk.Label(loc_ud, text="")),
        ])

        def _refresh_loc_ui(*_):
            t = (app.se_loc_type.get() or "").strip()
            for f in (loc_fixed, loc_cell, loc_net, loc_ud):
                f.grid_remove()
            if t == "FIXED":
                loc_fixed.grid()
            elif t == "CELL":
                loc_cell.grid()
            elif t == "NETWORK":
                loc_net.grid()
            elif t == "UNIFORM_DIST":
                loc_ud.grid()

        app.se_loc_type.trace_add("write", _refresh_loc_ui)
        _refresh_loc_ui()

        # Azimuth / Elevation
        ae_box = ttk.LabelFrame(geom, text="Direção da antena (azimuth / elevation)")
        ae_box.pack(fill="x", padx=2, pady=(0, 6))

        # Two columns: left=Azimuth, right=Elevation
        col_az = ttk.LabelFrame(ae_box, text="Azimuth")
        col_el = ttk.LabelFrame(ae_box, text="Elevation")
        col_az.grid(row=0, column=0, sticky="nsew", padx=(2, 6), pady=2)
        col_el.grid(row=0, column=1, sticky="nsew", padx=(6, 2), pady=2)
        ae_box.columnconfigure(0, weight=1)
        ae_box.columnconfigure(1, weight=1)

        # --- Azimuth controls
        ttk.Label(col_az, text="type").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        cb_az = ttk.Combobox(col_az, textvariable=app.se_az_type, values=AZ_EL_TYPES, width=22, state="readonly")
        cb_az.grid(row=0, column=1, sticky="w", padx=4, pady=(4, 2))

        az_fixed = ttk.Frame(col_az)
        az_ud = ttk.Frame(col_az)
        az_fixed.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        az_ud.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        az_fixed.grid_remove()
        az_ud.grid_remove()

        ttk.Label(az_fixed, text="fixed [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(az_fixed, textvariable=app.se_az_fixed, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(az_ud, text="min [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(az_ud, textvariable=app.se_az_ud_min, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(az_ud, text="max [deg]").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(az_ud, textvariable=app.se_az_ud_max, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        az_hint = ttk.Label(col_az, text="(POINTING_AT_IMT_CENTER: automático)", foreground="#555")
        az_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 6))
        az_hint.grid_remove()

        def _refresh_az_ui(*_):
            t = (app.se_az_type.get() or "").strip()
            az_fixed.grid_remove()
            az_ud.grid_remove()
            az_hint.grid_remove()
            if t == "UNIFORM_DIST":
                az_ud.grid()
            elif t == "FIXED":
                az_fixed.grid()
            elif t == "POINTING_AT_IMT_CENTER":
                az_hint.grid()

        app.se_az_type.trace_add("write", _refresh_az_ui)
        _refresh_az_ui()

        # --- Elevation controls
        ttk.Label(col_el, text="type").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))
        cb_el = ttk.Combobox(col_el, textvariable=app.se_el_type, values=AZ_EL_TYPES, width=22, state="readonly")
        cb_el.grid(row=0, column=1, sticky="w", padx=4, pady=(4, 2))

        el_fixed = ttk.Frame(col_el)
        el_ud = ttk.Frame(col_el)
        el_fixed.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        el_ud.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))
        el_fixed.grid_remove()
        el_ud.grid_remove()

        ttk.Label(el_fixed, text="fixed [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(el_fixed, textvariable=app.se_el_fixed, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(el_ud, text="min [deg]").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(el_ud, textvariable=app.se_el_ud_min, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(el_ud, text="max [deg]").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(el_ud, textvariable=app.se_el_ud_max, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        el_hint = ttk.Label(col_el, text="(POINTING_AT_IMT_CENTER: n/a p/ elevação)", foreground="#555")
        el_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 6))
        el_hint.grid_remove()

        def _refresh_el_ui(*_):
            t = (app.se_el_type.get() or "").strip()
            el_fixed.grid_remove()
            el_ud.grid_remove()
            el_hint.grid_remove()
            if t == "UNIFORM_DIST":
                el_ud.grid()
            elif t == "FIXED":
                el_fixed.grid()
            elif t == "POINTING_AT_IMT_CENTER":
                el_hint.grid()

        app.se_el_type.trace_add("write", _refresh_el_ui)
        _refresh_el_ui()


        # -------------------------
        # ANTENNA
        # -------------------------
        ant = ttk.LabelFrame(root, text="Antena (pattern + parâmetros)")
        ant.pack(fill="x", padx=2, pady=4)

        add_row_three(ant, 0, [
            ("antenna.pattern", ttk.Combobox(ant, textvariable=app.se_ant_pattern, values=SUPPORTED_ANTENNA_PATTERNS, width=28, state="readonly")),
            ("antenna.gain [dBi]", ttk.Entry(ant, textvariable=app.se_ant_gain, width=12)),
            ("", ttk.Label(ant, text="")),
        ])

        ant_diam = ttk.Frame(ant)      # diameter
        ant_env = ttk.Frame(ant)       # envelope_gain
        ant_s672 = ttk.Frame(ant)      # s672
        ant_f1245 = ttk.Frame(ant)     # f1245
        ant_hint = ttk.Frame(ant)      # fallback

        for f in (ant_diam, ant_env, ant_s672, ant_f1245, ant_hint):
            f.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 0))
            f.grid_remove()

        ttk.Label(ant_hint, text="Selecione um pattern para ver os parâmetros específicos.").grid(row=0, column=0, sticky="w")

        add_row_three(ant_diam, 0, [
            ("diameter [m]", ttk.Entry(ant_diam, textvariable=app.se_ant_diameter, width=12)),
            ("", ttk.Label(ant_diam, text="(freq e gain vêm do sistema)")),
            ("", ttk.Label(ant_diam, text="")),
        ])
        add_row_three(ant_env, 0, [
            ("envelope_gain [dB]", ttk.Entry(ant_env, textvariable=app.se_ant_envelope_gain, width=12)),
            ("", ttk.Label(ant_env, text="")),
            ("", ttk.Label(ant_env, text="")),
        ])
        add_row_three(ant_s672, 0, [
            ("antenna_3_dB [deg]", ttk.Entry(ant_s672, textvariable=app.se_ant_3db, width=12)),
            ("antenna_l_s [dB] (opt.)", ttk.Entry(ant_s672, textvariable=app.se_ant_l_s, width=12)),
            ("", ttk.Label(ant_s672, text="")),
        ])
        add_row_three(ant_f1245, 0, [
            ("gain (F1245) [dB]", ttk.Entry(ant_f1245, textvariable=app.se_ant_f1245_gain, width=12)),
            ("diameter [m]", ttk.Entry(ant_f1245, textvariable=app.se_ant_f1245_diameter, width=12)),
            ("frequency [MHz]", ttk.Entry(ant_f1245, textvariable=app.se_ant_f1245_frequency, width=12)),
        ])

        def _refresh_ant_ui(*_):
            pat = (app.se_ant_pattern.get() or "").strip()
            for f in (ant_diam, ant_env, ant_s672, ant_f1245, ant_hint):
                f.grid_remove()

            diameter_patterns = {
                "ITU-R F.699",
                "ITU-R S.465",
                "ITU-R S.580",
                "ITU-R S.1855",
                "ITU-R Reg. RR. Appendice 7 Annex 3",
            }

            if not pat:
                ant_hint.grid()
            elif pat in diameter_patterns:
                ant_diam.grid()
            elif pat == "MODIFIED ITU-R S.465":
                ant_env.grid()
            elif pat == "ITU-R S.672":
                ant_s672.grid()
            elif pat == "ITU-R F.1245_fs":
                ant_f1245.grid()
            else:
                ant_hint.grid()
                ttk.Label(
                    ant_hint,
                    text="(Por enquanto) Este pattern não tem campos específicos na GUI.",
                    foreground="#555",
                    justify="left",
                ).grid(row=1, column=0, sticky="w")

        app.se_ant_pattern.trace_add("write", _refresh_ant_ui)
        _refresh_ant_ui()

        # -------------------------
        # CHANNEL MODEL
        # -------------------------
        ch = ttk.LabelFrame(root, text="Channel model")
        ch.pack(fill="x", padx=2, pady=4)

        add_row_three(ch, 0, [
            ("channel_model", ttk.Combobox(ch, textvariable=app.se_channel_model, values=CHANNEL_MODELS, width=10, state="readonly")),
            ("", ttk.Label(ch, text="")),
            ("", ttk.Label(ch, text="")),
        ])


        p452_box = ttk.LabelFrame(ch, text="P452 parameters")
        p452_box.grid(row=1, column=0, columnspan=6, sticky="ew", padx=2, pady=(6, 2))
        p452_box.grid_remove()

        # ---- linha 0
        add_row_three(p452_box, 0, [
            ("atmospheric_pressure [hPa]", ttk.Entry(p452_box, textvariable=app.p452_atmospheric_pressure, width=12)),
            ("air_temperature [K]", ttk.Entry(p452_box, textvariable=app.p452_air_temperature, width=12)),
            ("p_452 [%]", ttk.Entry(p452_box, textvariable=app.p452_percentage_p, width=12)),
        ])

        # ---- linha 1
        add_row_three(p452_box, 1, [
            ("N0", ttk.Entry(p452_box, textvariable=app.p452_N0, width=12)),
            ("delta_N", ttk.Entry(p452_box, textvariable=app.p452_delta_N, width=12)),
            ("polarization", ttk.Entry(p452_box, textvariable=app.p452_polarization, width=12)),
        ])

        # ---- linha 2
        add_row_three(p452_box, 2, [
            ("Dct [km]", ttk.Entry(p452_box, textvariable=app.p452_Dct, width=12)),
            ("Dcr [km]", ttk.Entry(p452_box, textvariable=app.p452_Dcr, width=12)),
            ("", ttk.Label(p452_box, text="")),
        ])

        # ---- linha 3 (Hre travado + clutter_loss)
        hre_entry = ttk.Entry(
            p452_box,
            textvariable=app.p452_Hre,
            width=12,
            state="readonly",
        )
        # ---- linha 3 (Hre travado + clutter_loss)
        hte_entry = ttk.Entry(
            p452_box,
            textvariable=app.p452_Hte,
            width=12,
            state="readonly",
        )
        add_row_three(p452_box, 3, [
            ("Hte [m]", hte_entry),
            ("Hre [m]", hre_entry),
            ("clutter_loss", ttk.Checkbutton(p452_box, variable=app.p452_clutter_loss)),
        ])

        # ---- linha 4 (apenas se clutter_loss=True)
        clutter_row = ttk.Frame(p452_box)
        clutter_row.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(2, 0))
        clutter_row.grid_remove()

        # cria uma coluna vazia que expande
        clutter_row.columnconfigure(0, weight=1)

        # coloca o label à direita
        ttk.Label(clutter_row, text="clutter_type").grid(
            row=0, column=1, sticky="e", padx=4, pady=2
        )

        ttk.Combobox(
            clutter_row,
            textvariable=app.p452_clutter_type,
            values=["one_end", "both_ends"],
            width=12,
            state="readonly",
        ).grid(row=0, column=2, sticky="w", padx=4, pady=2)

        # ---- linha 5
        add_row_three(p452_box, 5, [
            ("tx_lat [deg]", ttk.Entry(p452_box, textvariable=app.p452_tx_lat, width=12)),
            ("rx_lat [deg]", ttk.Entry(p452_box, textvariable=app.p452_rx_lat, width=12)),
            ("is_terrain", ttk.Checkbutton(p452_box, variable=app.p452_is_terrain)),
        ])

        # Hre sempre segue height da estação
        def _sync_hre_with_height(*_):
            app.p452_Hre.set(app.se_height.get())
            if app.var_imt_link.get() == "DOWNLINK":
                app.p452_Hte.set(app.bs_height.get())
            else:
                app.p452_Hte.set(app.ue_height.get())

        app.se_height.trace_add("write", _sync_hre_with_height)
        _sync_hre_with_height()

        # Mostrar / esconder o bloco P452 conforme channel_model
        def _refresh_ch_ui(*_):
            if (app.se_channel_model.get() or "").strip() == "P452":
                p452_box.grid()          # mostra o grupo inteiro
            else:
                p452_box.grid_remove()   # esconde
            _refresh_clutter_ui()        # garante coerência da linha clutter_type

        # Mostrar / esconder clutter_type SOMENTE quando:
        # (1) channel_model == P452 e (2) clutter_loss == True
        def _refresh_clutter_ui(*_):
            is_p452 = (app.se_channel_model.get() or "").strip() == "P452"
            if is_p452 and bool(app.p452_clutter_loss.get()):
                clutter_row.grid()
            else:
                clutter_row.grid_remove()

        app.se_channel_model.trace_add("write", _refresh_ch_ui)
        app.p452_clutter_loss.trace_add("write", _refresh_clutter_ui)

        _refresh_ch_ui()


        ttk.Frame(root, height=10).pack(fill="x")


    # =========================================================
    # SINGLE_EARTH_STATION – Save / Load configuration
    # =========================================================

    def _se_collect_config(self):
        """Collect SINGLE_EARTH_STATION UI variables into a dict."""
        def g(v, default=None):
            try:
                return v.get()
            except Exception:
                return default

        cfg = {
            "frequency": g(self.se_frequency),
            "bandwidth": g(self.se_bandwidth),
            "noise_temperature": g(self.se_noise_temperature),
            "adjacent_ch_reception": g(self.se_adjacent_ch_reception),
            "adjacent_ch_selectivity": g(self.se_adjacent_ch_selectivity),
            "adjacent_ch_emissions": g(self.se_adjacent_ch_emissions),
            "adjacent_ch_leak_ratio": g(self.se_adjacent_ch_leak_ratio),
            "spectral_mask": g(self.se_spectral_mask),
            "spurious_emissions": g(self.se_spurious_emissions),
            "tx_power_density": g(self.se_tx_power_density),
            "height": g(self.se_height),

            "geometry": {
                "location": {
                    "type": g(self.se_loc_type),
                    "fixed": {
                        "x": g(self.se_loc_fixed_x),
                        "y": g(self.se_loc_fixed_y),
                    },
                    "cell": {
                        "min_dist_to_bs": g(self.se_loc_cell_min_dist_to_bs),
                    },
                    "network": {
                        "min_dist_to_bs": g(self.se_loc_network_min_dist_to_bs),
                    },
                    "uniform_dist": {
                        "min_dist_to_center": g(self.se_loc_ud_min_dist_to_center),
                        "max_dist_to_center": g(self.se_loc_ud_max_dist_to_center),
                    },
                },
                "azimuth": {
                    "type": g(self.se_az_type),
                    "fixed": g(self.se_az_fixed),
                    "uniform_dist": {
                        "min": g(self.se_az_ud_min),
                        "max": g(self.se_az_ud_max),
                    },
                },
                "elevation": {
                    "type": g(self.se_el_type),
                    "fixed": g(self.se_el_fixed),
                    "uniform_dist": {
                        "min": g(self.se_el_ud_min),
                        "max": g(self.se_el_ud_max),
                    },
                },
            },

            "antenna": {
                "pattern": g(self.se_ant_pattern),
                "gain": g(self.se_ant_gain),
                "diameter": g(self.se_ant_diameter),
                "envelope_gain": g(self.se_ant_envelope_gain),
            },

            "channel_model": g(self.se_channel_model),

            "p452": {
                "atmospheric_pressure": g(self.p452_atmospheric_pressure),
                "air_temperature": g(self.p452_air_temperature),
                "N0": g(self.p452_N0),
                "delta_N": g(self.p452_delta_N),
                "percentage_p": g(self.p452_percentage_p),
                "Dct": g(self.p452_Dct),
                "Dcr": g(self.p452_Dcr),
                "Hte": g(self.p452_Hte),
                "tx_lat": g(self.p452_tx_lat),
                "rx_lat": g(self.p452_rx_lat),
                "polarization": g(self.p452_polarization),
                "clutter_loss": bool(self.p452_clutter_loss.get()),
                "clutter_type": g(self.p452_clutter_type),
                "is_terrain": bool(self.p452_is_terrain.get()),
            },
        }
        return cfg


    def _se_apply_config(self, cfg: dict):
        """Apply config dict to SINGLE_EARTH_STATION UI."""
        def s(var, val):
            if val is None:
                return
            try:
                var.set(val)
            except Exception:
                pass

        s(self.se_frequency, cfg.get("frequency"))
        s(self.se_bandwidth, cfg.get("bandwidth"))
        s(self.se_noise_temperature, cfg.get("noise_temperature"))
        s(self.se_adjacent_ch_reception, cfg.get("adjacent_ch_reception"))
        s(self.se_adjacent_ch_selectivity, cfg.get("adjacent_ch_selectivity"))
        s(self.se_adjacent_ch_emissions, cfg.get("adjacent_ch_emissions"))
        s(self.se_adjacent_ch_leak_ratio, cfg.get("adjacent_ch_leak_ratio"))
        s(self.se_spectral_mask, cfg.get("spectral_mask"))
        s(self.se_spurious_emissions, cfg.get("spurious_emissions"))
        s(self.se_tx_power_density, cfg.get("tx_power_density"))
        s(self.se_height, cfg.get("height"))

        geom = cfg.get("geometry", {})
        loc = geom.get("location", {})
        s(self.se_loc_type, loc.get("type"))

        s(self.se_loc_fixed_x, loc.get("fixed", {}).get("x"))
        s(self.se_loc_fixed_y, loc.get("fixed", {}).get("y"))

        s(self.se_loc_cell_min_dist_to_bs, loc.get("cell", {}).get("min_dist_to_bs"))
        s(self.se_loc_network_min_dist_to_bs, loc.get("network", {}).get("min_dist_to_bs"))

        ud = loc.get("uniform_dist", {})
        s(self.se_loc_ud_min_dist_to_center, ud.get("min_dist_to_center"))
        s(self.se_loc_ud_max_dist_to_center, ud.get("max_dist_to_center"))

        az = geom.get("azimuth", {})
        s(self.se_az_type, az.get("type"))
        s(self.se_az_fixed, az.get("fixed"))
        s(self.se_az_ud_min, az.get("uniform_dist", {}).get("min"))
        s(self.se_az_ud_max, az.get("uniform_dist", {}).get("max"))

        el = geom.get("elevation", {})
        s(self.se_el_type, el.get("type"))
        s(self.se_el_fixed, el.get("fixed"))
        s(self.se_el_ud_min, el.get("uniform_dist", {}).get("min"))
        s(self.se_el_ud_max, el.get("uniform_dist", {}).get("max"))

        ant = cfg.get("antenna", {})
        s(self.se_ant_pattern, ant.get("pattern"))
        s(self.se_ant_gain, ant.get("gain"))
        s(self.se_ant_diameter, ant.get("diameter"))
        s(self.se_ant_envelope_gain, ant.get("envelope_gain"))

        s(self.se_channel_model, cfg.get("channel_model"))

        p = cfg.get("p452", {})
        s(self.p452_atmospheric_pressure, p.get("atmospheric_pressure"))
        s(self.p452_air_temperature, p.get("air_temperature"))
        s(self.p452_N0, p.get("N0"))
        s(self.p452_delta_N, p.get("delta_N"))
        s(self.p452_percentage_p, p.get("percentage_p"))
        s(self.p452_Dct, p.get("Dct"))
        s(self.p452_Dcr, p.get("Dcr"))
        s(self.p452_Hte, p.get("Hte"))
        s(self.p452_tx_lat, p.get("tx_lat"))
        s(self.p452_rx_lat, p.get("rx_lat"))
        s(self.p452_polarization, p.get("polarization"))

        self.p452_clutter_loss.set(bool(p.get("clutter_loss", False)))
        s(self.p452_clutter_type, p.get("clutter_type"))
        self.p452_is_terrain.set(bool(p.get("is_terrain", False)))

        # garante coerência da UI
        try:
            self.p452_Hre.set(self.se_height.get())
            if self.var_imt_link.get() == "Downlink":
                self.p452_Hte.set(self.bs_height.get())
            else:
                self.p452_Hte.set(self.ue_height.get())
        except Exception:
            pass

        # Atualização da UI:
        # - as traces (trace_add) já disparam quando vars mudam
        # - mas forçamos um "evento" pra garantir atualização imediata do layout
        try:
            self.update_idletasks()
        except Exception:
            pass

    def _refresh_loc_ui(*_):
        t = (app.se_loc_type.get() or "").strip()
        for f in (loc_fixed, loc_cell, loc_net, loc_ud):
            f.grid_remove()
        if t == "FIXED":
            loc_fixed.grid()
        elif t == "CELL":
            loc_cell.grid()
        elif t == "NETWORK":
            loc_net.grid()
        elif t == "UNIFORM_DIST":
            loc_ud.grid()


    def _se_save_config(self):
        from tkinter import filedialog, messagebox
        import json

        try:
            fpath = filedialog.asksaveasfilename(
                title="Salvar configuração SINGLE_EARTH_STATION",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
            )
            if not fpath:
                return
            cfg = self._se_collect_config()
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            messagebox.showinfo("Config", f"Configuração salva:\n{fpath}")
        except Exception as e:
            messagebox.showerror("Config", str(e))


    def _se_load_config(self):
        from tkinter import filedialog, messagebox
        import json

        try:
            fpath = filedialog.askopenfilename(
                title="Carregar configuração SINGLE_EARTH_STATION",
                filetypes=[("JSON", "*.json")],
            )
            if not fpath:
                return
            with open(fpath, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self._se_apply_config(cfg)
            messagebox.showinfo("Config", f"Configuração carregada:\n{fpath}")
        except Exception as e:
            messagebox.showerror("Config", str(e))
