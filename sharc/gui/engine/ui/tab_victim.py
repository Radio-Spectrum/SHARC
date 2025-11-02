import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

# (Imports from other project files would go here)
# from ..core.utils import add_row_three

def _tab_victim(self, root):
    topbar = ttk.Frame(root);
topbar.pack(fill="x", pady=(0,6))
    ttk.Button(topbar, text="Salvar config Single Space Station (.json)", command=self._save_victim_config).pack(side="left")
    ttk.Button(topbar, text="Carregar config Single Space Station (.json)", command=self._load_victim_config).pack(side="left", padx=(6,0))

    # ==== Básicos ====
    frm0 = ttk.LabelFrame(root, text="Parâmetros básicos")
    frm0.pack(fill="x", padx=2, pady=4)
    add_row_three(frm0, 0, [
        ("frequency [MHz]", ttk.Entry(frm0, textvariable=self.v_freq, width=10)),
     
   ("bandwidth [MHz]", ttk.Entry(frm0, textvariable=self.v_bw, width=10)),
        ("tx_power_density [dBW/Hz]", ttk.Entry(frm0, textvariable=self.v_txpsd, width=12)),
    ])
    add_row_three(frm0, 1, [
        ("polarization_loss [dB]", ttk.Entry(frm0, textvariable=self.v_pol_loss, width=10)),
        ("noise_temperature [K]", ttk.Entry(frm0, textvariable=self.v_tnoise, width=10)),
        ("channel_model", ttk.Combobox(frm0, textvariable=self.v_ch_model, values=["P619","FSPL"], state="readonly", width=12)),
    ])

      add_row_three(frm0, 2, [
        ("season", ttk.Combobox(
            frm0, textvariable=self.v_season,
            values=["SUMMER", "WINTER"], state="readonly", width=10
        )),
        ("Terra Esférica?", ttk.Checkbutton(
            frm0, 
variable=self.ss_is_global_cs  # <- só passa o widget, sem .grid()
        )),
        ("", ttk.Label(frm0, text="")),
    ])

    # ==== P619 ====
    frm1 = ttk.LabelFrame(root, text="P619 parameters")
    frm1.pack(fill="x", padx=2, pady=4)
    add_row_three(frm1, 0, [
        ("mean_clutter_height", ttk.Combobox(frm1, 
textvariable=self.v_p619_clutter,
                                             values=["Low","Mid","High"], state="readonly", width=10)),
        ("below_rooftop [%]", ttk.Entry(frm1, textvariable=self.v_p619_below_rooftop, width=10)),
        ("", ttk.Label(frm1, text="")),
    ])

    # ==== Geometria 
(subdividida) ====
    wrap = ttk.LabelFrame(root, text="Geometria – Classes")
    wrap.pack(fill="x", padx=2, pady=4)

    # Spacecraft (FIXED)
    frm_sc = ttk.LabelFrame(wrap, text="Spacecraft – Location (FIXED/GEO)")
    frm_sc.pack(fill="x", padx=2, pady=(6,6))
    add_row_three(frm_sc, 0, [
        ("altitude [m] (sat)", ttk.Entry(frm_sc, textvariable=self.v_alt, width=12)),
        ("location.fixed.lat_deg", ttk.Entry(frm_sc, textvariable=self.v_fix_lat, 
width=12)),
        ("location.fixed.long_deg", ttk.Entry(frm_sc, textvariable=self.v_fix_lon, width=12)),
    ])

    # Earth Station
    frm_es = ttk.LabelFrame(wrap, text="Earth Station – Reference point on Earth")
    frm_es.pack(fill="x", padx=2, pady=(0,6))
    add_row_three(frm_es, 0, [
        ("es_altitude [m]", ttk.Entry(frm_es, textvariable=self.v_es_alt, width=12)),
        ("es_lat_deg", ttk.Entry(frm_es, 
textvariable=self.v_es_lat, width=12)),
        ("es_long_deg", ttk.Entry(frm_es, textvariable=self.v_es_lon, width=12)),
    ])

    # Pointing (export only)
    frm_pt = ttk.LabelFrame(wrap, text="Pointing (export only)")
    frm_pt.pack(fill="x", padx=2, pady=(0,6))
    add_row_three(frm_pt, 0, [
        ("azimuth.type", ttk.Combobox(frm_pt, textvariable=self.v_az_type, values=["POINTING_AT_IMT","FIXED"], state="readonly", width=18)),
        ("elevation.type", ttk.Combobox(frm_pt, textvariable=self.v_el_type, 
values=["POINTING_AT_IMT","FIXED"], state="readonly", width=18)),
        ("", ttk.Label(frm_pt, text="")),
    ])

    # Antenna
    frm3 = ttk.LabelFrame(root, text="Antenna")
    frm3.pack(fill="x", padx=2, pady=4)
    add_row_three(frm3, 0, [
        ("pattern", ttk.Combobox(frm3, textvariable=self.v_ant_pattern,
                  
               values=["ITU-R S.672","ITU-R M.2101","3GPP TR 38.901","Custom"], state="readonly", width=18)),
        ("gain [dBi]", ttk.Entry(frm3, textvariable=self.v_ant_gain, width=10)),
        ("", ttk.Label(frm3, text="")),
    ])
    self.frm_s672 = ttk.Frame(frm3)
    self.frm_s672.grid(row=1, column=0, columnspan=6, sticky="we", pady=(4,0))
    add_row_three(self.frm_s672, 0, [
     
   ("itu_r_s_672.antenna_3_dB", ttk.Entry(self.frm_s672, textvariable=self.v_s672_3db, width=8)),
        ("itu_r_s_672.antenna_l_s [dB]", ttk.Entry(self.frm_s672, textvariable=self.v_s672_ls, width=8)),
        ("", ttk.Label(self.frm_s672, text="")),
    ])
    self.frm_other_ant = ttk.Frame(frm3)
    ttk.Label(self.frm_other_ant, text="Parâmetros para este padrão ainda não implementados.").grid(row=0, column=0, sticky="w")

    def _toggle_antenna(*_):
        if self.v_ant_pattern.get() == "ITU-R S.672":

            self.frm_other_ant.grid_remove()
            self.frm_s672.grid()
        else:
            self.frm_s672.grid_remove()
            self.frm_other_ant.grid(row=1, column=0, columnspan=6, sticky="w", pady=(4,0))
    self.v_ant_pattern.trace_add("write", _toggle_antenna)
    _toggle_antenna()

def _save_victim_config(self):
    data = {
        "v_freq": self.v_freq.get(), "v_bw": self.v_bw.get(), "v_txpsd": self.v_txpsd.get(),
        "v_pol_loss": self.v_pol_loss.get(), "v_tnoise": self.v_tnoise.get(),
        "v_ch_model": self.v_ch_model.get(), "v_season": self.v_season.get(),
        "v_p619_clutter": self.v_p619_clutter.get(), "v_p619_below_rooftop": self.v_p619_below_rooftop.get(),
       
 "v_alt": self.v_alt.get(), "v_fix_lat": self.v_fix_lat.get(), "v_fix_lon": self.v_fix_lon.get(),
        "v_es_alt": self.v_es_alt.get(), "v_es_lat": self.v_es_lat.get(), "v_es_lon": self.v_es_lon.get(),
        "v_az_type": self.v_az_type.get(), "v_el_type": self.v_el_type.get(),
        "v_ant_pattern": self.v_ant_pattern.get(), "v_ant_gain": self.v_ant_gain.get(),
        "v_s672_3db": self.v_s672_3db.get(), "v_s672_ls": self.v_s672_ls.get(),
    }
    path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], initialfile="single_space_station_config.json")
    if not path: return

       with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
    messagebox.showinfo("Single Space Station", f"Configuração salva em:\n{path}")

def _load_victim_config(self):
    path = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
    if not path: return
    with open(path, "r", encoding="utf-8") as f: vals = json.load(f)
    def S(name, var):
        if name in vals:
 
           try: var.set(vals[name])
            except: pass
    S("v_freq", self.v_freq);
S("v_bw", self.v_bw); S("v_txpsd", self.v_txpsd)
    S("v_pol_loss", self.v_pol_loss);
S("v_tnoise", self.v_tnoise)
    S("v_ch_model", self.v_ch_model);
S("v_season", self.v_season)
    S("v_p619_clutter", self.v_p619_clutter);
S("v_p619_below_rooftop", self.v_p619_below_rooftop)
    S("v_alt", self.v_alt); S("v_fix_lat", self.v_fix_lat);
S("v_fix_lon", self.v_fix_lon)
    S("v_es_alt", self.v_es_alt); S("v_es_lat", self.v_es_lat);
S("v_es_lon", self.v_es_lon)
    S("v_az_type", self.v_az_type);
S("v_el_type", self.v_el_type)
    S("v_ant_pattern", self.v_ant_pattern);
S("v_ant_gain", self.v_ant_gain)
    S("v_s672_3db", self.v_s672_3db);
S("v_s672_ls", self.v_s672_ls)
    messagebox.showinfo("Single Space Station", "Configuração carregada.")