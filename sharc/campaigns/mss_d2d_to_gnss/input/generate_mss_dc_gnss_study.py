#!/usr/bin/env python3
"""
Script to generate the desired YAML configuration file.
"""

import os

# Elevation angles to generate
ANGLES = [80, 85, 90]

# Directory where this script resides
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_config(angle):
    """
    Create one YAML file for the specified elevation angle.
    """
    yaml_content = f"""
general:
    ###########################################################################
    # Number of simulation snapshots
    num_snapshots: 1000
    ###########################################################################
    # IMT link that will be simulated (DOWNLINK or UPLINK)
    imt_link: DOWNLINK
    ###########################################################################
    # The chosen system for sharing study
    system: SINGLE_EARTH_STATION
    ###########################################################################
    # Compatibility scenario (co-channel and/or adjacent channel interference)
    enable_cochannel: false
    enable_adjacent_channel: true
    ###########################################################################
    # Seed for random number generator
    seed: 681603
    ###########################################################################
    # if FALSE, then a new output directory is created
    overwrite_output: FALSE
    ###########################################################################
    # output destination folder - this is relative SHARC/sharc directory
    output_dir: campaigns/mss_d2d_to_gnss/output/
    ###########################################################################
    # output folder prefix
    output_dir_prefix: output_mss_d2d_to_gnss_elev_{angle}_deg
imt:
    ###########################################################################
    # Minimum 2D separation distance from BS to UE [m]
    minimum_separation_distance_bs_ue: 35
    ###########################################################################
    # Defines if IMT service is the interferer or interfered-with service
    #   TRUE: IMT suffers interference
    #   FALSE : IMT generates interference
    interfered_with: False
    ###########################################################################
    # IMT center frequency [MHz]
    # frequency: 2167.5  # B1/B4 - SPACE STATION - 2110-2 170
    # frequency: 1555.0 # adjacent channel interference
    frequency: 1515.5 # 
    # frequency: 1570.0 # adjacente channel almost co-channel
    ###########################################################################
    # IMT bandwidth [MHz]
    bandwidth: 5.0
    ###########################################################################
    # IMT resource block bandwidth [MHz]
    rb_bandwidth: 0.180
    # IMT resource block bandwidth [MHz]
    ###########################################################################
    adjacent_ch_reception: ACS
    ###########################################################################
    adjacent_ch_emissions: SPECTRAL_MASK
    adjacent_ch_leak_ratio: 50.0  # dB
    ###########################################################################
    # IMT spectrum emission mask. Options are:
    #   "IMT-2020" : for mmWave as described in ITU-R TG 5/1 Contribution 36
    #   "3GPP E-UTRA" : for E-UTRA bands > 1 GHz as described in
    #                   TS 36.104 v11.2.0 (BS) and TS 36.101 v11.2.0 (UE)
    spectral_mask: MSS
    ###########################################################################
    # level of spurious emissions [dBm/MHz]
    spurious_emissions: -13.0
    ###########################################################################
    # Amount of guard band wrt total bandwidth. Setting this parameter to 0.1
    # means that 10% of the total bandwidth will be used as guard band: 5% in
    # the lower
    guard_band_ratio: 0.1
    ###########################################################################
    # Network topology parameters.
    topology:
        ## Refernce latitude and longitude taken from INPE/Cachoeria Paulista
        ###########################################################################
        # The latitude position
        central_latitude: -22.681603
        ###########################################################################
        # The longitude position
        central_longitude: -45.002609
        ##########################
        central_altitude: 563  # meters
        ###########################################################################
        # Topology Type. Possible values are "MACROCELL", "HOTSPOT", "SINGLE_BS"
        # "INDOOR", "MSS_DC"
        type: MSS_DC
        ###########################################################################
        # Topology parameters for the MSS-DC network
        mss_dc:
            # MSS_DC cell radius in network topology [m]
            beam_radius: 39475.0
            # Number of sectors
            num_beams: 1
            beam_positioning:
                # type may be one of 
                # "ANGLE_FROM_SUBSATELLITE", "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
                # "SERVICE_GRID"
                # when "ANGLE_FROM_SUBSATELLITE", both phi and theta must be specified
                # when "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE", both phi and distance
                #  must be specified
                type: ANGLE_FROM_SUBSATELLITE
                # theta is the off axis angle from satellite nadir
                angle_from_subsatellite_theta:
                    # type may be one of
                    # "FIXED", "~U(MIN,MAX)", "~SQRT(U(0,1))*MAX"
                    type: FIXED
                    # used if TYPE == FIXED is specified
                    fixed: 0
                    # used if some distribution type is specified
                    # distribution:
                    #     min: 0.0
                    #     max: 66.1
                # phi completes polar coordinates
                # equivalent to "azimuth" from subsatellite in earth plane
                angle_from_subsatellite_phi:
                    # type may be one of
                    # "FIXED", "~U(MIN,MAX)", "~SQRT(U(0,1))*MAX"
                    type: FIXED
                    # used if TYPE == FIXED is specified
                    fixed: 0
                    # used if some distribution type is specified
                    # distribution:
                    #     min: 0.0
                    #     max: 66.1
                # distance from subsatellite. Substitutes theta
                # distance_from_subsatellite:
                #     # type may be one of
                #     # "FIXED", "~U(MIN,MAX)", "~SQRT(U(0,1))*MAX"
                #     type: FIXED
                #     # used if TYPE == FIXED is specified
                #     fixed: 0
                #     # used if some distribution type is specified
                #     distribution:
                #         min: 0.0
                #         max: 66.1
                # service_grid:
                #     # by default this already gets shapefile from natural earth
                #     country_shapes_filename: sharc/data/countries/ne_110m_admin_0_countries.shp
                #     # By default, these are the same as taken from `sat_is_active_if.lat_long_inside_country`
                #     country_names:
                #         - Brazil
                #         - Chile

                    # This margin defines where the grid is constructed
                    # margin from inside of border [km]
                    # By default, this is made to be the same as beam_radius
                    # if positive, makes border smaller by x km
                    # if negative, makes border bigger by x km
                    # grid_margin_from_border: 0.11

                    # This margin defines what satellites may serve the grid
                    # it should normally be a smaller value than the grid from border
                    # since a satellite not right above the grid may serve some point better
                    # margin from inside of border [km]
                    # By default, this is made to be the same as beam_radius
                    # if positive, makes border smaller by x km
                    # if negative, makes border bigger by x km
                    # eligible_sats_margin_from_border: -2.1
            sat_is_active_if:
                # for a satellite to be active, it needs to respect ALL conditions
                conditions:
                    # - LAT_LONG_INSIDE_COUNTRY
                    - MINIMUM_ELEVATION_FROM_ES
                    - MAXIMUM_ELEVATION_FROM_ES
                minimum_elevation_from_es: 5.0
                maximum_elevation_from_es: {angle}
                # lat_long_inside_country:
                #     # You may specify another shp file for country borders reference
                #     # country_shapes_filename: sharc/topology/countries/ne_110m_admin_0_countries.shp
                #     country_names:
                #         - Brazil
                #         - Ecuador
                #     # margin from inside of border [km]
                #     # if positive, makes border smaller by x km
                #     # if negative, makes border bigger by x km
                #     margin_from_border: 111.0
            ###########################################################################
            # Parameters for the orbits
            orbits:  # System 3 parameters
                # Number of planes
              - n_planes: 28
                # Inclination in degrees
                inclination_deg: 53.0
                # Perigee in km
                perigee_alt_km: 525.0
                # Apogee in km
                apogee_alt_km: 525.0
                # Number of satellites per plane
                sats_per_plane: 120
                # Longitude of the first ascending node in degrees
                long_asc_deg: 0.0
                # Phasing in degrees
                phasing_deg: 1.5
    ###########################################################################
    # Defines the antenna model to be used in compatibility studies between
    # IMT and other services in adjacent band
    # Possible values: SINGLE_ELEMENT, BEAMFORMING
    adjacent_antenna_model: SINGLE_ELEMENT
    # Base station parameters
    bs:
        ###########################################################################
        # The load probability (or activity factor) models the statistical
        # variation of the network load by defining the number of fully loaded
        # base stations that are simultaneously transmitting
        load_probability: 1.0
        ###########################################################################
        # Conducted power per antenna element [dBm/bandwidth]
        conducted_power: 41.4  # -55.6 [dB/Hz] + 10log(5*1e6)[Hz] + 30.0
        ###########################################################################
        # Base station height [m]
        height: 20.0
        ###########################################################################
        # Base station noise figure [dB]
        noise_figure: 5.0
        ###########################################################################
        # Base station array ohmic loss  [dB]
        ohmic_loss: 3.0
        # Base Station Antenna parameters:
        antenna:
            pattern: ARRAY
            # gain: 0  #  set to zero when using the adjacent MSS antenna model
            # itu_r_s_1528:
            #     antenna_pattern: ITU-R-S.1528-Taylor
            #     ### The following parameters are used for S.1528-Taylor antenna pattern
            #     # Maximum Antenna gain in dBi
            #     antenna_gain: 34.1
            #     # SLR is the side-lobe ratio of the pattern (dB), the difference in gain between the maximum
            #     # gain and the gain at the peak of the first side lobe.
            #     slr: 20.0
            #     # Number of secondary lobes considered in the diagram (coincide with the roots of the Bessel function)
            #     n_side_lobes: 2
            #     # Radial (l_r) and transverse (l_t) sizes of the effective radiating area of the satellite transmitt antenna (m)
            #     l_r: 1.6
            #     l_t: 1.6
            # mss_adjacent:
            #     frequency: 2167.5  # MHz
            #         # Base Station Antenna parameters:
            array:
                ###########################################################################
                # If normalization of M2101 should be applied for BS
                normalization: FALSE
                ###########################################################################
                # Base station horizontal beamsteering range. [deg]
                # The range considers the BS azimuth as 0deg
                horizontal_beamsteering_range: !!python/tuple [-60., 60.]
                ###########################################################################
                # Base station horizontal beamsteering range. [deg]
                # The range considers the horizon as 90deg, 0 as zenith
                vertical_beamsteering_range: !!python/tuple [90., 100.]
                ###########################################################################
                # File to be used in the BS beamforming normalization
                # Normalization files can be generated with the
                # antenna/beamforming_normalization/normalize_script.py script
                normalization_file: antenna/beamforming_normalization/bs_norm.npz
                ###########################################################################
                # File to be used in the UE beamforming normalization
                # Normalization files can be generated with the 
                # antenna/beamforming_normalization/normalize_script.py script
                ###########################################################################
                # Radiation pattern of each antenna element
                # Possible values: "M2101", "F1336", "FIXED"
                element_pattern: M2101
                ###########################################################################
                # Minimum array gain for the beamforming antenna [dBi]
                minimum_array_gain: -200
                ###########################################################################
                # mechanical downtilt [degrees]
                # NOTE: consider defining it to 90 degrees in case of indoor simulations
                downtilt: 0.0  # the topology MSS takes care of this
                ###########################################################################
                # BS/UE maximum transmit/receive element gain [dBi]
                # default: element_max_g = 5, for M.2101
                #                           = 15, for M.2292
                #                           = -3, for M.2292
                element_max_g: 6.4
                ###########################################################################
                # BS/UE horizontal 3dB beamwidth of single element [degrees]
                element_phi_3db: 90
                ###########################################################################
                # BS/UE vertical 3dB beamwidth of single element [degrees]
                # For F1336: if equal to 0, then beamwidth is calculated automaticaly
                element_theta_3db: 65
                ###########################################################################
                # BS/UE number of rows in antenna array
                n_rows: 1
                ###########################################################################
                # BS/UE number of columns in antenna array
                n_columns: 1
                ###########################################################################
                # BS/UE array horizontal element spacing (d/lambda)
                element_horiz_spacing: 0.5
                ###########################################################################
                # BS/UE array vertical element spacing (d/lambda)
                element_vert_spacing: 2.1
                ###########################################################################
                # BS/UE front to back ratio of single element [dB]
                element_am: 30
                ###########################################################################
                # BS/UE single element vertical sidelobe attenuation [dB]
                element_sla_v: 30
                ###########################################################################
                # Multiplication factor k that is used to adjust the single-element pattern.
                # According to Report ITU-R M.[IMT.AAS], this may give a closer match of the 
                # side lobes when beamforming is assumed in adjacent channel.
                #       Original value: 12 (Rec. ITU-R M.2101)
                multiplication_factor: 12
                subarray:
                    ###########################################################################
                    # to use subarray, set this to true
                    is_enabled: false
                    ###########################################################################
                    # Number of rows in subarray
                    n_rows: 3
                    ###########################################################################
                    # BS array element vertical spacing (d/lambda).
                    element_vert_spacing: 0.7
                    ###########################################################################
                    # Sub array eletrical downtilt [deg]
                    # notice that electrical tilt == -1 * downtilt
                    eletrical_downtilt: 3.0

    ###########################################################################
    # User Equipment parameters:
    ue:
        ###########################################################################
        # Number of UEs that are allocated to each cell within handover margin.
        # Remember that in macrocell network each base station has 3 cells (sectors)
        k: 1
        ###########################################################################
        # Multiplication factor that is used to ensure that the sufficient number
        # of UE's will distributed throughout ths system area such that the number
        # of K users is allocated to each cell. Normally, this values varies
        # between 2 and 10 according to the user drop method
        k_m: 1
        ###########################################################################
        # Percentage of indoor UE's [%]
        indoor_percent: 0.0
        ###########################################################################
        # Regarding the distribution of active UE's over the cell area, this
        # parameter states how the UEs will be distributed
        # Possible values: UNIFORM : UEs will be uniformly distributed within the
        #                            whole simulation area. Not applicable to
        #                            hotspots.
        #                  ANGLE_AND_DISTANCE : UEs will be distributed following
        #                                   given distributions for angle and
        #                                   distance. In this case, these must be
        #                                   defined later.
        distribution_type: UNIFORM_IN_CELL
        ###########################################################################
        # Regarding the distribution of active UE's over the cell area, this
        # parameter models the distance between UE's and BS.
        # Possible values: RAYLEIGH, UNIFORM
        distribution_distance: RAYLEIGH
        ###########################################################################
        # Regarding the distribution of active UE's over the cell area, this
        # parameter models the azimuth between UE and BS (within ±60° range).
        # Possible values: NORMAL, UNIFORM
        distribution_azimuth: UNIFORM
        ###########################################################################
        # Power control algorithm
        # tx_power_control = "ON",power control On
        # tx_power_control = "OFF",power control Off
        tx_power_control: ON
        ###########################################################################
        # Power per RB used as target value [dBm]
        p_o_pusch: -92.2
        ###########################################################################
        # Alfa is the balancing factor for UEs with bad channel
        # and UEs with good channel
        alpha: 0.8
        ###########################################################################
        # Maximum UE transmit power [dBm]
        p_cmax: 23
        ###########################################################################
        # UE power dynamic range [dB]
        # The minimum transmit power of a UE is (p_cmax - dynamic_range)
        power_dynamic_range: 63
        ###########################################################################
        # UE height [m]
        height: 1.5
        ###########################################################################
        # User equipment noise figure [dB]
        noise_figure: 9
        ###########################################################################
        # User equipment feed loss [dB]
        ohmic_loss: 0
        ###########################################################################
        # User equipment body loss [dB]
        body_loss: 4
        antenna:
            array:
                ###########################################################################
                # If normalization of M2101 should be applied for UE
                normalization: FALSE
                ###########################################################################
                # File to be used in the UE beamforming normalization
                # Normalization files can be generated with the 
                # antenna/beamforming_normalization/normalize_script.py script
                normalization_file: antenna/beamforming_normalization/ue_norm.npz
                ###########################################################################
                # Radiation pattern of each antenna element
                # Possible values: "M2101", "F1336", "FIXED"
                element_pattern: FIXED
                ###########################################################################
                # Minimum array gain for the beamforming antenna [dBi]
                minimum_array_gain: -200
                ###########################################################################
                # BS/UE maximum transmit/receive element gain [dBi]
                #                           = 15, for M.2292
                # default: element_max_g = 5, for M.2101
                #                           = -3, for M.2292
                element_max_g: -3
                ###########################################################################
                # BS/UE horizontal 3dB beamwidth of single element [degrees]
                element_phi_3db: 90
                ###########################################################################
                # BS/UE vertical 3dB beamwidth of single element [degrees]
                # For F1336: if equal to 0, then beamwidth is calculated automaticaly
                element_theta_3db: 90
                ###########################################################################
                # BS/UE number of rows in antenna array
                n_rows: 1
                ###########################################################################
                # BS/UE number of columns in antenna array
                n_columns: 1
                ###########################################################################
                # BS/UE array horizontal element spacing (d/lambda)
                element_horiz_spacing: 0.5
                ###########################################################################
                # BS/UE array vertical element spacing (d/lambda)
                element_vert_spacing: 0.5
                ###########################################################################
                # BS/UE front to back ratio of single element [dB]
                element_am: 25
                ###########################################################################
                # BS/UE single element vertical sidelobe attenuation [dB]
                element_sla_v: 25
                ###########################################################################
                # Multiplication factor k that is used to adjust the single-element pattern.
                # According to Report ITU-R M.[IMT.AAS], this may give a closer match of the 
                # side lobes when beamforming is assumed in adjacent channel.
                #       Original value: 12 (Rec. ITU-R M.2101)
                multiplication_factor: 12
    ###########################################################################
    # Uplink parameters. Only needed when using uplink on imt
    uplink:
        ###########################################################################
        # Uplink attenuation factor used in link-to-system mapping
        attenuation_factor: 0.4
        ###########################################################################
        # Uplink minimum SINR of the code set [dB]
        sinr_min: -10
        ###########################################################################
        # Uplink maximum SINR of the code set [dB]
        sinr_max: 22
    ###########################################################################
    # Downlink parameters. Only needed when using donwlink on imt
    downlink:
        ###########################################################################
        # Downlink attenuation factor used in link-to-system mapping
        attenuation_factor: 0.8
        ###########################################################################
        # Downlink minimum SINR of the code set [dB]
        sinr_min: -10
        ###########################################################################
        # Downlink maximum SINR of the code set [dB]
        sinr_max: 30
    ###########################################################################
    # Channel parameters
    # channel model, possible values are "FSPL" (free-space path loss),
    #                                    "CI" (close-in FS reference distance)
    #                                    "UMa" (Urban Macro - 3GPP)
    #                                    "UMi" (Urban Micro - 3GPP)
    #                                    "TVRO-URBAN"
    #                                    "TVRO-SUBURBAN"
    #                                    "ABG" (Alpha-Beta-Gamma)
    #                                    "P619"
    channel_model: FSPL
    season: SUMMER
    ###########################################################################
    # Adjustment factor for LoS probability in UMi path loss model.
    #       Original value: 18 (3GPP)
    los_adjustment_factor: 18
    ###########################################################################
    # If shadowing should be applied or not.
    # Used in propagation UMi, UMa, ABG, when topology == indoor and any 
    shadowing: FALSE
    ###########################################################################
    # receiver noise temperature [K]
    noise_temperature: 290
    ###########################################################################
    # P619 parameters
    param_p619:
        ###########################################################################
        # altitude of the space station [m]
        space_station_alt_m: 540000
        ###########################################################################
        # altitude of ES system [m]
        earth_station_alt_m: 1200
        ###########################################################################
        # latitude of ES system [m]
        earth_station_lat_deg: 13
        ###########################################################################
        # difference between longitudes of IMT-NTN station and FSS-ES system [deg]
        #   (positive if space-station is to the East of earth-station)
        earth_station_long_diff_deg: 0
#### System Parameters
# Single Earth Station representing an EESS Earth Station in the 2.0 GHz band.
# Referce data comes from the REPLY LIAISON STATEMENT TO WORKING PARTY 4C ON
# WRC-27 AGENDA ITEMS 1.12, 1.13, 1.14 AND 1.15 - Document 4C/196-E
single_earth_station:
  polarization_loss: 0  # dB - polarization loss
  frequency: 1575.42  # MHz - L1 Band
  bandwidth: 30  # MHz, based on ±16.5 MHz 3 dB bandwidth
  # tx power density just so simulator runs
  tx_power_density: -200
  # also just so simulator runs
  noise_temperature: 513
  # This is based in pratical data found in other documents.
  # 35-45dBs are generally assumed. We take 35 as a worst case.
  adjacent_ch_selectivity: 35
  # Channel model
  channel_model: SatelliteSimple  #FSPL, SatelliteSimple
  satellite_simple:
     # enable clutter loss
        enable_clutter_loss: false
     # Atmospheric loss in dB
        atmospheric_loss: 0.65
        
  # Earth Station parameters
  geometry:
    height: 1.5
    azimuth:
      # Type of elevation.
      type: UNIFORM_DIST
      uniform_dist:
        max: 180
        min: -180
    # Elevation angle [degrees]
    elevation:
      # Type of elevation.
      type: FIXED
      fixed: 0
    # Station 2d location [meters]:
    location:
      type: FIXED
      fixed:
        x: 0
        y: 0
  antenna:
      ###########################################################################
      # Choose the antenna pattern. Can be one of:
      # "OMNI", "ITU-R F.699", "ITU-R S.465", "ITU-R S.580", "MODIFIED ITU-R S.465",
      # "ITU-R S.1855", "ITU-R S.672", "HEMISPHERIC"
      # since 20deg beamwidth would already cover every area
      pattern: "HEMISPHERIC"
      ###########################################################################
      # Station peak receive antenna gain [dBi]
      gain: 3 
      # Hemispheric pattern parameters
      hemispheric:
        gain_upper: 3       # gain for upper hemisphere 
        gain_lower: -5      # gain for lower hemisphere 
        cutoff_angle: 10.0  # angle (in degrees) between upper and lower hemisphere
      #itu_r_s_465:
        # Diameter [m]
        # diameter: 0.2  # derived with efficiency 0.5
    """

    filename = os.path.join(SCRIPT_DIR, f"parameters_mss_d2d_to_gnss_angle_{angle}.yaml")
    with open(filename, "w") as file:
        file.write(yaml_content)
    print(f"Generated {filename}")

def main():
    for angle in ANGLES:
        generate_config(angle)


if __name__ == "__main__":
    main()
