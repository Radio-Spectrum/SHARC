from tkinter import messagebox, filedialog
import json


def _save_victim_config(root):
    data = {
        "v_freq": root.v_freq.get(), "v_bw": root.v_bw.get(), "v_txpsd": root.v_txpsd.get(),
        "v_pol_loss": root.v_pol_loss.get(), "v_tnoise": root.v_tnoise.get(),
        "v_ch_model": root.v_ch_model.get(), "v_season": root.v_season.get(),
        "v_p619_clutter": root.v_p619_clutter.get(), "v_p619_below_rooftop": root.v_p619_below_rooftop.get(),
        "v_alt": root.v_alt.get(), "v_fix_lat": root.v_fix_lat.get(), "v_fix_lon": root.v_fix_lon.get(),
        "v_es_alt": root.v_es_alt.get(), "v_es_lat": root.v_es_lat.get(), "v_es_lon": root.v_es_lon.get(),
        "v_az_type": root.v_az_type.get(), "v_el_type": root.v_el_type.get(),
        "v_ant_pattern": root.v_ant_pattern.get(), "v_ant_gain": root.v_ant_gain.get(),
        "v_s672_3db": root.v_s672_3db.get(), "v_s672_ls": root.v_s672_ls.get(),
        }
    path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], initialfile="single_space_station_config.json")
    if not path: return
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
    messagebox.showinfo("Single Space Station", f"Configuração salva em:\n{path}")

def _load_victim_config(root):
    path = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
    if not path: return
    with open(path, "r", encoding="utf-8") as f: vals = json.load(f)
    def S(name, var):
        if name in vals:
            try: var.set(vals[name])
            except: pass
    S("v_freq", root.v_freq); S("v_bw", root.v_bw); S("v_txpsd", root.v_txpsd)
    S("v_pol_loss", root.v_pol_loss); S("v_tnoise", root.v_tnoise)
    S("v_ch_model", root.v_ch_model); S("v_season", root.v_season)
    S("v_p619_clutter", root.v_p619_clutter); S("v_p619_below_rooftop", root.v_p619_below_rooftop)
    S("v_alt", root.v_alt); S("v_fix_lat", root.v_fix_lat); S("v_fix_lon", root.v_fix_lon)
    S("v_es_alt", root.v_es_alt); S("v_es_lat", root.v_es_lat); S("v_es_lon", root.v_es_lon)
    S("v_az_type", root.v_az_type); S("v_el_type", root.v_el_type)
    S("v_ant_pattern", root.v_ant_pattern); S("v_ant_gain", root.v_ant_gain)
    S("v_s672_3db", root.v_s672_3db); S("v_s672_ls", root.v_s672_ls)
    messagebox.showinfo("Single Space Station", "Configuração carregada.")