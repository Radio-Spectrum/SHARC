import json
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox

class SESPersistence:
    """
    Handles saving and loading the Single Earth Station configuration in PySide6.
    """

    @staticmethod
    def collect_config(app):
        """Scrapes variables from the app instance into a clean dictionary."""
        def g(v): return v.get()

        return {
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
                "pattern": g(app.se_ant_pattern),
                "gain": g(app.se_ant_gain),
                "diameter": g(app.se_ant_diameter),
                "envelope_gain": g(app.se_ant_envelope_gain),
                "antenna_3db": g(app.se_ant_3db),
                "antenna_l_s": g(app.se_ant_l_s),
                "f1245_gain": g(app.se_ant_f1245_gain),
                "f1245_diameter": g(app.se_ant_f1245_diameter),
                "f1245_frequency": g(app.se_ant_f1245_frequency),
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

    @staticmethod
    def apply_config(app, cfg: dict):
        """Populates the app variables from a configuration dictionary."""
        def s(var, val):
            if val is not None:
                var.set(val)

        s(app.se_frequency, cfg.get("frequency"))
        s(app.se_bandwidth, cfg.get("bandwidth"))
        s(app.se_noise_temperature, cfg.get("noise_temperature"))
        s(app.se_adjacent_ch_reception, cfg.get("adjacent_ch_reception"))
        s(app.se_adjacent_ch_selectivity, cfg.get("adjacent_ch_selectivity"))
        s(app.se_adjacent_ch_emissions, cfg.get("adjacent_ch_emissions"))
        s(app.se_adjacent_ch_leak_ratio, cfg.get("adjacent_ch_leak_ratio"))
        s(app.se_spectral_mask, cfg.get("spectral_mask"))
        s(app.se_spurious_emissions, cfg.get("spurious_emissions"))
        s(app.se_tx_power_density, cfg.get("tx_power_density"))
        s(app.se_height, cfg.get("height"))

        geom = cfg.get("geometry", {})
        loc = geom.get("location", {})
        s(app.se_loc_type, loc.get("type"))
        s(app.se_loc_fixed_x, loc.get("fixed", {}).get("x"))
        s(app.se_loc_fixed_y, loc.get("fixed", {}).get("y"))
        s(app.se_loc_cell_min_dist_to_bs, loc.get("cell", {}).get("min_dist_to_bs"))
        s(app.se_loc_network_min_dist_to_bs, loc.get("network", {}).get("min_dist_to_bs"))
        ud = loc.get("uniform_dist", {})
        s(app.se_loc_ud_min_dist_to_center, ud.get("min_dist_to_center"))
        s(app.se_loc_ud_max_dist_to_center, ud.get("max_dist_to_center"))

        az = geom.get("azimuth", {})
        s(app.se_az_type, az.get("type"))
        s(app.se_az_fixed, az.get("fixed"))
        s(app.se_az_ud_min, az.get("uniform_dist", {}).get("min"))
        s(app.se_az_ud_max, az.get("uniform_dist", {}).get("max"))

        el = geom.get("elevation", {})
        s(app.se_el_type, el.get("type"))
        s(app.se_el_fixed, el.get("fixed"))
        s(app.se_el_ud_min, el.get("uniform_dist", {}).get("min"))
        s(app.se_el_ud_max, el.get("uniform_dist", {}).get("max"))

        ant = cfg.get("antenna", {})
        s(app.se_ant_pattern, ant.get("pattern"))
        s(app.se_ant_gain, ant.get("gain"))
        s(app.se_ant_diameter, ant.get("diameter"))
        s(app.se_ant_envelope_gain, ant.get("envelope_gain"))
        s(app.se_ant_3db, ant.get("antenna_3db"))
        s(app.se_ant_l_s, ant.get("antenna_l_s"))
        s(app.se_ant_f1245_gain, ant.get("f1245_gain"))
        s(app.se_ant_f1245_diameter, ant.get("f1245_diameter"))
        s(app.se_ant_f1245_frequency, ant.get("f1245_frequency"))

        s(app.se_channel_model, cfg.get("channel_model"))
        p = cfg.get("p452", {})
        s(app.p452_atmospheric_pressure, p.get("atmospheric_pressure"))
        s(app.p452_air_temperature, p.get("air_temperature"))
        s(app.p452_N0, p.get("N0"))
        s(app.p452_delta_N, p.get("delta_N"))
        s(app.p452_percentage_p, p.get("percentage_p"))
        s(app.p452_Dct, p.get("Dct"))
        s(app.p452_Dcr, p.get("Dcr"))
        s(app.p452_Hte, p.get("Hte"))
        s(app.p452_tx_lat, p.get("tx_lat"))
        s(app.p452_rx_lat, p.get("rx_lat"))
        s(app.p452_polarization, p.get("polarization"))
        app.p452_clutter_loss.set(bool(p.get("clutter_loss", False)))
        s(app.p452_clutter_type, p.get("clutter_type"))
        app.p452_is_terrain.set(bool(p.get("is_terrain", False)))

    @staticmethod
    def save_to_file(app, parent_widget=None):
        try:
            fpath, _ = QFileDialog.getSaveFileName(
                parent_widget, "Save Earth Station Config", "", "JSON (*.json)"
            )
            if fpath:
                config_data = SESPersistence.collect_config(app)
                final_data = {"config_type": "SES"}
                final_data.update(config_data)

                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(final_data, f, indent=2)

                QMessageBox.information(parent_widget, "Config", f"Saved to:\n{fpath}")
        except Exception as e:
            QMessageBox.critical(parent_widget, "Error", str(e))

    @staticmethod
    def load_from_file(app, refresh_callback=None, parent_widget=None):
        try:
            fpath, _ = QFileDialog.getOpenFileName(
                parent_widget, "Load Earth Station Config", "", "JSON (*.json)"
            )
            if fpath:
                with open(fpath, "r", encoding="utf-8") as f:
                    SESPersistence.apply_config(app, json.load(f))
                if refresh_callback:
                    refresh_callback()
                QMessageBox.information(parent_widget, "Config", "Configuration loaded successfully.")
        except Exception as e:
            QMessageBox.critical(parent_widget, "Error", str(e))