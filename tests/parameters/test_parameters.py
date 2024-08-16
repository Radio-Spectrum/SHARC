import unittest
from sharc.parameters.parameters import Parameters


class ParametersTest(unittest.TestCase):
    """Run Parameter class tests."""

    def setUp(self):
        self.parameters = Parameters()
        self.parameters.set_file_name("./parameters/parameters_for_testing.ini")
        self.parameters.read_params()

    def test_parameters_imt(self):
        """Unit test for ParametersIMT"""

        self.assertEqual(self.parameters.imt.topology, "INDOOR")
        self.assertEqual(self.parameters.imt.wrap_around, False)
        self.assertEqual(self.parameters.imt.num_clusters, 1)
        self.assertEqual(self.parameters.imt.intersite_distance, 399)
        self.assertEqual(self.parameters.imt.minimum_separation_distance_bs_ue, 1.3)
        self.assertEqual(self.parameters.imt.interfered_with, False)
        self.assertEqual(self.parameters.imt.frequency, 24360)
        self.assertEqual(self.parameters.imt.bandwidth, 200.5)
        self.assertEqual(self.parameters.imt.rb_bandwidth, 0.181)
        self.assertEqual(self.parameters.imt.spectral_mask, "3GPP E-UTRA")
        self.assertEqual(self.parameters.imt.spurious_emissions, -13.1)
        self.assertEqual(self.parameters.imt.guard_band_ratio, 0.14)
        self.assertEqual(self.parameters.imt.bs_load_probability, 0.2)
        self.assertEqual(self.parameters.imt.bs_conducted_power, 11.1)
        self.assertEqual(self.parameters.imt.bs_height, 6.1)
        self.assertEqual(self.parameters.imt.bs_noise_figure, 10.1)
        self.assertEqual(self.parameters.imt.bs_noise_temperature, 290.1)
        self.assertEqual(self.parameters.imt.bs_ohmic_loss, 3.1)
        self.assertEqual(self.parameters.imt.ul_attenuation_factor, 0.4)
        self.assertEqual(self.parameters.imt.ul_sinr_min, -10.0)
        self.assertEqual(self.parameters.imt.ul_sinr_max, 22.0)
        self.assertEqual(self.parameters.imt.ue_k, 3)
        self.assertEqual(self.parameters.imt.ue_k_m, 1)
        self.assertEqual(self.parameters.imt.ue_indoor_percent, 5.0)
        self.assertEqual(self.parameters.imt.ue_distribution_type, "ANGLE_AND_DISTANCE")
        self.assertEqual(self.parameters.imt.ue_distribution_distance, "UNIFORM")
        self.assertEqual(self.parameters.imt.ue_tx_power_control, True)
        self.assertEqual(self.parameters.imt.ue_p_o_pusch, -95.0)
        self.assertEqual(self.parameters.imt.ue_alpha, 1.0)
        self.assertEqual(self.parameters.imt.ue_p_cmax, 22.0)
        self.assertEqual(self.parameters.imt.ue_power_dynamic_range, 63.0)
        self.assertEqual(self.parameters.imt.ue_height, 1.5)
        self.assertEqual(self.parameters.imt.ue_noise_figure, 10.0)
        self.assertEqual(self.parameters.imt.ue_ohmic_loss, 3.0)
        self.assertEqual(self.parameters.imt.ue_body_loss, 4.0)
        self.assertEqual(self.parameters.imt.dl_attenuation_factor, 0.6)
        self.assertEqual(self.parameters.imt.dl_sinr_min, -10.0)
        self.assertEqual(self.parameters.imt.dl_sinr_max, 30.0)
        self.assertEqual(self.parameters.imt.channel_model, "FSPL")
        self.assertEqual(self.parameters.imt.los_adjustment_factor, 18.0)
        self.assertEqual(self.parameters.imt.shadowing, False)

    def test_parameters_imt_antenna(self):
        """Test ParametersImtAntenna parameters"""
        self.assertEqual(
            self.parameters.antenna_imt.adjacent_antenna_model, "BEAMFORMING"
        )
        self.assertEqual(self.parameters.antenna_imt.bs_normalization, False)
        self.assertEqual(self.parameters.antenna_imt.ue_normalization, False)
        self.assertEqual(
            self.parameters.antenna_imt.bs_normalization_file,
            "antenna/beamforming_normalization/bs_norm.npz",
        )
        self.assertEqual(
            self.parameters.antenna_imt.ue_normalization_file,
            "antenna/beamforming_normalization/ue_norm.npz",
        )
        self.assertEqual(self.parameters.antenna_imt.bs_element_pattern, "F1336")
        self.assertEqual(self.parameters.antenna_imt.ue_element_pattern, "F1336")
        self.assertEqual(self.parameters.antenna_imt.bs_minimum_array_gain, -200)
        self.assertEqual(self.parameters.antenna_imt.ue_minimum_array_gain, -200)
        self.assertEqual(self.parameters.antenna_imt.bs_downtilt, 6)
        self.assertEqual(self.parameters.antenna_imt.bs_element_max_g, 5)
        self.assertEqual(self.parameters.antenna_imt.ue_element_max_g, 5)
        self.assertEqual(self.parameters.antenna_imt.bs_element_phi_3db, 65)
        self.assertEqual(self.parameters.antenna_imt.ue_element_phi_3db, 90)
        self.assertEqual(self.parameters.antenna_imt.bs_element_theta_3db, 65)
        self.assertEqual(self.parameters.antenna_imt.ue_element_theta_3db, 90)
        self.assertEqual(self.parameters.antenna_imt.bs_n_rows, 8)
        self.assertEqual(self.parameters.antenna_imt.ue_n_rows, 4)
        self.assertEqual(self.parameters.antenna_imt.bs_n_columns, 8)
        self.assertEqual(self.parameters.antenna_imt.ue_n_columns, 4)
        self.assertEqual(self.parameters.antenna_imt.bs_element_horiz_spacing, 0.5)
        self.assertEqual(self.parameters.antenna_imt.ue_element_horiz_spacing, 0.5)
        self.assertEqual(self.parameters.antenna_imt.bs_element_vert_spacing, 0.5)
        self.assertEqual(self.parameters.antenna_imt.ue_element_vert_spacing, 0.5)
        self.assertEqual(self.parameters.antenna_imt.bs_element_am, 30)
        self.assertEqual(self.parameters.antenna_imt.ue_element_am, 25)
        self.assertEqual(self.parameters.antenna_imt.bs_element_sla_v, 30)
        self.assertEqual(self.parameters.antenna_imt.ue_element_sla_v, 25)
        self.assertEqual(self.parameters.antenna_imt.bs_multiplication_factor, 12)
        self.assertEqual(self.parameters.antenna_imt.ue_multiplication_factor, 12)

    def test_parameters_hotspot(self):
        """Test ParametersHotspot"""
        self.assertEqual(self.parameters.hotspot.num_hotspots_per_cell, 1)
        self.assertEqual(self.parameters.hotspot.max_dist_hotspot_ue, 99.9)
        self.assertEqual(self.parameters.hotspot.min_dist_bs_hotspot, 1.2)

    def test_parameters_indoor(self):
        """Test ParametersIndoor"""
        self.assertEqual(self.parameters.indoor.basic_path_loss, "FSPL")
        self.assertEqual(self.parameters.indoor.n_rows, 3)
        self.assertEqual(self.parameters.indoor.n_colums, 2)
        self.assertEqual(self.parameters.indoor.num_imt_buildings, 2)
        self.assertEqual(self.parameters.indoor.street_width, 30.1)
        self.assertEqual(self.parameters.indoor.intersite_distance, 40.1)
        self.assertEqual(self.parameters.indoor.num_cells, 3)
        self.assertEqual(self.parameters.indoor.num_floors, 1)
        self.assertEqual(self.parameters.indoor.ue_indoor_percent, 0.95)
        self.assertEqual(self.parameters.indoor.building_class, "THERMALLY_EFFICIENT")

    def test_parameters_fss_ss(self):
        """Test ParametersFssSs"""
        self.assertEqual(self.parameters.fss_ss.frequency, 43000.0)
        self.assertEqual(self.parameters.fss_ss.bandwidth, 200.0)
        self.assertEqual(self.parameters.fss_ss.tx_power_density, -5.0)
        self.assertEqual(self.parameters.fss_ss.altitude, 35780000.0)
        self.assertEqual(self.parameters.fss_ss.lat_deg, 0.0)
        self.assertEqual(self.parameters.fss_ss.elevation, 270.0)
        self.assertEqual(self.parameters.fss_ss.azimuth, 0.0)
        self.assertEqual(self.parameters.fss_ss.noise_temperature, 950.0)
        self.assertEqual(self.parameters.fss_ss.adjacent_ch_selectivity, 0.0)
        self.assertEqual(self.parameters.fss_ss.antenna_gain, 46.6)
        self.assertEqual(self.parameters.fss_ss.antenna_pattern, "FSS_SS")
        self.assertEqual(self.parameters.fss_ss.imt_altitude, 0.0)
        self.assertEqual(self.parameters.fss_ss.imt_lat_deg, 0.0)
        self.assertEqual(self.parameters.fss_ss.imt_long_diff_deg, 0.0)
        self.assertEqual(self.parameters.fss_ss.season, "SUMMER")
        self.assertEqual(self.parameters.fss_ss.channel_model, "P619")
        self.assertEqual(self.parameters.fss_ss.antenna_l_s, -20.0)
        self.assertEqual(self.parameters.fss_ss.antenna_3_dB, 0.65)

    def test_parameters_fss_es(self):
        """Test ParametersFssEs"""
        self.assertEqual(self.parameters.fss_es.location, "UNIFORM_DIST")
        self.assertEqual(self.parameters.fss_es.x, 10000)
        self.assertEqual(self.parameters.fss_es.y, 0)
        self.assertEqual(self.parameters.fss_es.min_dist_to_bs, 10)
        self.assertEqual(self.parameters.fss_es.max_dist_to_bs, 600)
        self.assertEqual(self.parameters.fss_es.height, 6)
        self.assertEqual(self.parameters.fss_es.elevation_min, 48)
        self.assertEqual(self.parameters.fss_es.elevation_max, 80)
        self.assertEqual(self.parameters.fss_es.azimuth, "RANDOM")
        self.assertEqual(self.parameters.fss_es.frequency, 43000)
        self.assertEqual(self.parameters.fss_es.bandwidth, 6)
        self.assertEqual(self.parameters.fss_es.adjacent_ch_selectivity, 0)
        self.assertEqual(self.parameters.fss_es.tx_power_density, -68.3)
        self.assertEqual(self.parameters.fss_es.noise_temperature, 950)
        self.assertEqual(self.parameters.fss_es.antenna_gain, 32)
        self.assertEqual(self.parameters.fss_es.antenna_pattern, "Modified ITU-R S.465")
        self.assertEqual(self.parameters.fss_es.antenna_envelope_gain, 0)
        self.assertEqual(self.parameters.fss_es.diameter, 1.8)
        self.assertEqual(self.parameters.fss_es.channel_model, "P452")
        self.assertEqual(self.parameters.fss_es.atmospheric_pressure, 935)
        self.assertEqual(self.parameters.fss_es.air_temperature, 300)
        self.assertEqual(self.parameters.fss_es.N0, 352.58)
        self.assertEqual(self.parameters.fss_es.delta_N, 43.127)
        self.assertEqual(self.parameters.fss_es.percentage_p, 0.2)
        self.assertEqual(self.parameters.fss_es.Dct, 70)
        self.assertEqual(self.parameters.fss_es.Dcr, 70)
        self.assertEqual(self.parameters.fss_es.Hte, 20)
        self.assertEqual(self.parameters.fss_es.Hre, 3)
        self.assertEqual(self.parameters.fss_es.tx_lat, -23.55028)
        self.assertEqual(self.parameters.fss_es.rx_lat, -23.17889)
        self.assertEqual(self.parameters.fss_es.polarization, "horizontal")
        self.assertEqual(self.parameters.fss_es.clutter_loss, True)
        self.assertEqual(self.parameters.fss_es.es_position, "ROOFTOP")
        self.assertEqual(self.parameters.fss_es.shadow_enabled, True)
        self.assertEqual(self.parameters.fss_es.building_loss_enabled, True)
        self.assertEqual(self.parameters.fss_es.same_building_enabled, False)
        self.assertEqual(self.parameters.fss_es.diffraction_enabled, False)
        self.assertEqual(
            self.parameters.fss_es.bs_building_entry_loss_type, "P2109_FIXED"
        )
        self.assertEqual(self.parameters.fss_es.bs_building_entry_loss_prob, 0.75)
        self.assertEqual(self.parameters.fss_es.bs_building_entry_loss_value, 35.0)

    def test_parameters_fs(self):
        """Test ParametersFs"""
        self.assertEqual(self.parameters.fs.x, 1000.0)
        self.assertEqual(self.parameters.fs.y, 0.0)
        self.assertEqual(self.parameters.fs.height, 15.0)
        self.assertEqual(self.parameters.fs.elevation, -10.0)
        self.assertEqual(self.parameters.fs.azimuth, 180.0)
        self.assertEqual(self.parameters.fs.frequency, 27250.0)
        self.assertEqual(self.parameters.fs.bandwidth, 112.0)
        self.assertEqual(self.parameters.fs.noise_temperature, 290.0)
        self.assertEqual(self.parameters.fs.adjacent_ch_selectivity, 20.0)
        self.assertEqual(self.parameters.fs.tx_power_density, -68.3)
        self.assertEqual(self.parameters.fs.antenna_gain, 36.9)
        self.assertEqual(self.parameters.fs.antenna_pattern, "OMNI")
        self.assertEqual(self.parameters.fs.diameter, 0.3)
        self.assertEqual(self.parameters.fs.channel_model, "TerrestrialSimple")

    def test_parameters_haps(self):
        """Test ParametersHaps"""
        self.assertEqual(self.parameters.haps.frequency, 27251.1)
        self.assertEqual(self.parameters.haps.bandwidth, 200.0)
        self.assertEqual(self.parameters.haps.antenna_gain, 28.1)
        self.assertEqual(self.parameters.haps.eirp_density, 4.4)
        self.assertEqual(
            self.parameters.haps.tx_power_density,
            self.parameters.haps.eirp_density - self.parameters.haps.antenna_gain - 60,
        )
        self.assertEqual(self.parameters.haps.altitude, 20001.1)
        self.assertEqual(self.parameters.haps.lat_deg, 0.1)
        self.assertEqual(self.parameters.haps.elevation, 270.0)
        self.assertEqual(self.parameters.haps.azimuth, 0)
        self.assertEqual(self.parameters.haps.antenna_pattern, "OMNI")
        self.assertEqual(self.parameters.haps.imt_altitude, 0.0)
        self.assertEqual(self.parameters.haps.imt_lat_deg, 0.0)
        self.assertEqual(self.parameters.haps.imt_long_diff_deg, 0.0)
        self.assertEqual(self.parameters.haps.season, "SUMMER")
        self.assertEqual(self.parameters.haps.acs, 30.0)
        self.assertEqual(self.parameters.haps.channel_model, "P619")
        self.assertEqual(self.parameters.haps.antenna_l_n, -25)

    def test_paramters_rns(self):
        """Test ParametersRns"""
        self.assertEqual(self.parameters.rns.x, 660.1)
        self.assertEqual(self.parameters.rns.y, -370.1)
        self.assertEqual(self.parameters.rns.altitude, 150.1)
        self.assertEqual(self.parameters.rns.frequency, 32000.1)
        self.assertEqual(self.parameters.rns.bandwidth, 60.1)
        self.assertEqual(self.parameters.rns.noise_temperature, 1154.1)
        self.assertEqual(self.parameters.rns.tx_power_density, -70.79)
        self.assertEqual(self.parameters.rns.antenna_gain, 30.1)
        self.assertEqual(self.parameters.rns.antenna_pattern, "ITU-R M.1466")
        self.assertEqual(self.parameters.rns.channel_model, "P619")
        self.assertEqual(self.parameters.rns.season, "SUMMER")
        self.assertEqual(self.parameters.rns.imt_altitude, 0.0)
        self.assertEqual(self.parameters.rns.imt_lat_deg, 0.0)
        self.assertEqual(self.parameters.rns.acs, 30.1)

    def test_parametes_ras(self):
        """Test ParametersRas"""
        self.assertEqual(self.parameters.ras.x, 81000.1)
        self.assertEqual(self.parameters.ras.y, 0.1)
        self.assertEqual(self.parameters.ras.height, 15.1)
        self.assertEqual(self.parameters.ras.elevation, 45.1)
        self.assertEqual(self.parameters.ras.azimuth, -90.1)
        self.assertEqual(self.parameters.ras.frequency, 43000.1)
        self.assertEqual(self.parameters.ras.bandwidth, 1000.1)
        self.assertEqual(self.parameters.ras.antenna_noise_temperature, 25.1)
        self.assertEqual(self.parameters.ras.receiver_noise_temperature, 65.1)
        self.assertEqual(self.parameters.ras.adjacent_ch_selectivity, 20.1)
        self.assertEqual(self.parameters.ras.antenna_efficiency, 0.9)
        self.assertEqual(self.parameters.ras.antenna_pattern, "ITU-R SA.509")
        self.assertEqual(self.parameters.ras.antenna_gain, 0.5)
        self.assertEqual(self.parameters.ras.diameter, 15.1)
        self.assertEqual(self.parameters.ras.channel_model, "P452")
        self.assertEqual(self.parameters.ras.atmospheric_pressure, 935.2)
        self.assertEqual(self.parameters.ras.air_temperature, 300.1)
        self.assertEqual(self.parameters.ras.N0, 352.58)
        self.assertEqual(self.parameters.ras.delta_N, 43.127)
        self.assertEqual(self.parameters.ras.percentage_p, 0.2)
        self.assertEqual(self.parameters.ras.Dct, 70.1)
        self.assertEqual(self.parameters.ras.Dcr, 70.1)
        self.assertEqual(self.parameters.ras.Hte, 20.1)
        self.assertEqual(self.parameters.ras.Hre, 3.1)
        self.assertEqual(self.parameters.ras.tx_lat, -23.55028)
        self.assertEqual(self.parameters.ras.rx_lat, -23.17889)
        self.assertEqual(self.parameters.ras.polarization, "horizontal")
        self.assertEqual(self.parameters.ras.clutter_loss, True)

    def test_paramters_eess_passive(self):
        """Test ParametersEessPassive"""
        self.assertEqual(self.parameters.eess_passive.frequency, 23900.1)
        self.assertEqual(self.parameters.eess_passive.bandwidth, 200.1)
        self.assertEqual(self.parameters.eess_passive.nadir_angle, 46.6)
        self.assertEqual(self.parameters.eess_passive.altitude, 828000.1)
        self.assertEqual(self.parameters.eess_passive.antenna_pattern, "ITU-R RS.1813")
        self.assertEqual(self.parameters.eess_passive.antenna_efficiency, 0.6)
        self.assertEqual(self.parameters.eess_passive.antenna_diameter, 2.2)
        self.assertEqual(self.parameters.eess_passive.antenna_gain, 52.1)
        self.assertEqual(self.parameters.eess_passive.channel_model, "FSPL")
        self.assertEqual(self.parameters.eess_passive.imt_altitude, 20.1)
        self.assertEqual(self.parameters.eess_passive.imt_lat_deg, -22.9)
        self.assertEqual(self.parameters.eess_passive.season, "WINTER")


if __name__ == "__main__":
    unittest.main()
