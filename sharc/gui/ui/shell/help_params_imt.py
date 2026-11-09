"""Hover explanations for the IMT page rows (keys are the lower-case GUI labels)."""

PARAMS = {"imt": {
    # ---- IMT general ----
    "min separation distance bs ue": (
        "imt.minimum_separation_distance_bs_ue, in metres (engine default 0.0). Sets the smallest 2D BS-UE "
        "distance when UEs are placed: with the ANGLE_AND_DISTANCE distribution, Rayleigh radii are clipped to "
        "this value and UNIFORM/SQRT(UNIFORM) radii are drawn between it and the cell radius."),

    # ---- Topology: shared / selection ----
    "type": (
        "Selector of the drawing mode of its own group. For the topology it is imt.topology.type (MACROCELL, "
        "HOTSPOT, INDOOR, SINGLE_BS, NTN, MSS_DC, SAMPLING_FROM_SPHERICAL_GRID or MACRO_COUNTRIES, engine "
        "default MACROCELL). In MSS_DC it is beam_positioning.type (ANGLE_FROM_SUBSATELLITE, "
        "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE or SERVICE_GRID) or the value type of theta/phi/distance (FIXED, "
        "~U(MIN,MAX) or ~SQRT(U(0,1))*MAX)."),
    "name": (
        "MSS_DC topology only (imt.topology.mss_dc.name): label of the satellite system. Engine default is "
        "\"SystemA\". It identifies the constellation and does not change the geometry."),
    "fixed": (
        "MSS_DC beam positioning: value used when the type of theta, phi or distance_from_subsatellite is FIXED. "
        "Theta and phi are angles in degrees (phi must lie in [-180, 180]); distance_from_subsatellite must be "
        "at least 0. Engine default is 0.0."),
    "distribution min": (
        "MSS_DC beam positioning: lower bound of the ~U(MIN,MAX) distribution of theta, phi or "
        "distance_from_subsatellite (distribution.min). It is only read for that type and must be smaller than "
        "distribution.max and inside the allowed range of the quantity (phi in [-180, 180], distance >= 0)."),
    "distribution max": (
        "MSS_DC beam positioning: upper bound of the ~U(MIN,MAX) distribution, and the scale MAX of "
        "~SQRT(U(0,1))*MAX, for theta, phi or distance_from_subsatellite (distribution.max). It must be larger "
        "than distribution.min and inside the allowed range of the quantity."),
    "transform grid randomly": (
        "MSS_DC SERVICE_GRID (service_grid.transform_grid_randomly): when True, the grid of beam centres "
        "generated inside the zone gets a random transformation drawn from the simulation random generator "
        "(generate_grid_in_multipolygon). Engine default is False."),
    "enable fixed latitude lons for grid": (
        "GUI-only flag (enable_fixed_lat_lons_for_grid). The engine has no such key: the YAML builder removes "
        "it, together with fixed_lats and fixed_lons, before the run, so it has no effect on the simulation."),
    "grid margin from border": (
        "MSS_DC SERVICE_GRID, in km (grid_in_zone.from_countries.margin_from_border). Positive values shrink the "
        "country borders where the beam grid is generated, negative values enlarge them. If left unset the "
        "engine uses cell_radius / 1000."),
    "eligible sats margin from border": (
        "MSS_DC SERVICE_GRID, in km (eligible_sats_margin_from_border). Border margin applied to the country "
        "polygons that define the area in which satellites are eligible to serve the grid; positive shrinks, "
        "negative enlarges. Must be a number."),
    "grid exclusion zone type": (
        "MSS_DC SERVICE_GRID (grid_exclusion_zone.type): empty for no exclusion, or CIRCLE. Grid points that "
        "fall inside the excluded zone are removed from the beam grid."),
    "fixed lats": (
        "GUI-only list (fixed_lats) tied to enable_fixed_lat_lons_for_grid. The engine has no such key and the "
        "YAML builder drops it, so it does not change the simulation."),
    "fixed lons": (
        "GUI-only list (fixed_lons) tied to enable_fixed_lat_lons_for_grid. The engine has no such key and the "
        "YAML builder drops it, so it does not change the simulation."),
    "circle center latitude": (
        "Centre latitude of the CIRCLE exclusion zone (circle.center_lat), in degrees, in [-90, 90]. Required "
        "when the exclusion zone type is CIRCLE."),
    "circle center longitude": (
        "Centre longitude of the CIRCLE exclusion zone (circle.center_lon), in degrees, in [-180, 180]. "
        "Required when the exclusion zone type is CIRCLE."),
    "circle radius km": (
        "Radius of the CIRCLE exclusion zone (circle.radius_km), in km. It must be positive. Grid points "
        "inside this circle are not used."),
    "country shapes filename": (
        "Path to the countries shapefile used to build the MSS_DC polygons (country_shapes_filename). Engine "
        "default is sharc/data/countries/ne_110m_admin_0_countries.shp; countries are selected by the NAME "
        "field."),
    "latitude longitude inside country": (
        "Satellite-selection condition LAT_LONG_INSIDE_COUNTRY of sat_is_active_if.conditions. When ticked, a "
        "satellite only counts as active if its position lies inside the listed countries (shrunk by "
        "margin_from_border); at least one country name is then required."),
    "min elevation": (
        "Satellite-selection condition MINIMUM_ELEVATION_FROM_ES of sat_is_active_if.conditions. When ticked, "
        "min_elevation_from_es is validated and applied to decide which satellites are active."),
    "max elevation": (
        "Satellite-selection condition MAXIMUM_ELEVATION_FROM_ES of sat_is_active_if.conditions. When ticked, "
        "max_elevation_from_es is validated and applied to decide which satellites are active."),
    "min elevation from es": (
        "sat_is_active_if.minimum_elevation_from_es, in degrees, valid in [0, 90). Used when the minimum "
        "elevation condition is ticked: lower limit of the satellite elevation seen from the earth station."),
    "max elevation from es": (
        "sat_is_active_if.maximum_elevation_from_es, in degrees, valid in [0, 90) and not below the minimum. "
        "Used when the maximum elevation condition is ticked: upper limit of the satellite elevation seen from "
        "the earth station."),
    "margin from border": (
        "sat_is_active_if.lat_long_inside_country.margin_from_border, in km (engine default 0.0). Positive "
        "values shrink the country border used by the inside-country condition, negative values enlarge it."),

    # ---- Topology: macrocell / hotspot / single BS / NTN / indoor ----
    "intersite distance": (
        "Distance between neighbouring base stations, in metres. Used by MACROCELL, HOTSPOT, SINGLE_BS, INDOOR "
        "(engine default 40) and NTN. For SINGLE_BS and NTN set either this or the cell radius, not both: "
        "SINGLE_BS uses cell_radius = ISD*2/3 and NTN uses cell_radius = ISD/sqrt(3)."),
    "cell radius": (
        "Cell radius in metres. MACRO_COUNTRIES: radius of each cell (default 400, must be positive). SINGLE_BS: "
        "alternative to the intersite distance (ISD = 1.5*radius). NTN: default 90000, ISD = radius*sqrt(3). "
        "For NTN and SINGLE_BS do not set it together with the intersite distance."),
    "bs height": (
        "NTN topology (ntn.bs_height), in metres: height of the airborne or space platform acting as the base "
        "station. The engine fills it from imt.bs.height when the parameters are loaded."),
    "bs azimuth": (
        "NTN topology (ntn.bs_azimuth), in degrees: azimuth of the platform base station. Engine default is "
        "45."),
    "bs elevation": (
        "NTN topology (ntn.bs_elevation), in degrees: elevation angle of the platform base station. Engine "
        "default is 90."),
    "num sectors": (
        "NTN topology (ntn.num_sectors): number of sectors (cells) of the footprint. The engine accepts 1, 7 "
        "or 19; default is 7."),
    "bs backoff power": (
        "NTN topology (ntn.bs_backoff_power), in dB, default 3 (for the 7-sector layer 2). The source marks "
        "this parameter as not yet implemented in the simulator, so it has no effect."),
    "bs n rows layer1": (
        "NTN topology (ntn.bs_n_rows_layer1): antenna rows of layer 1, default 2. The source notes that the "
        "NTN antenna-layer parameters are not used by the simulator yet."),
    "bs n columns layer1": (
        "NTN topology (ntn.bs_n_columns_layer1): antenna columns of layer 1, default 2. The source notes that "
        "the NTN antenna-layer parameters are not used by the simulator yet."),
    "bs n rows layer2": (
        "NTN topology (ntn.bs_n_rows_layer2): antenna rows of layer 2, default 4. The source notes that the "
        "NTN antenna-layer parameters are not used by the simulator yet."),
    "bs n columns layer2": (
        "NTN topology (ntn.bs_n_columns_layer2): antenna columns of layer 2, default 2. The source notes that "
        "the NTN antenna-layer parameters are not used by the simulator yet."),
    "basic path loss": (
        "INDOOR topology (indoor.basic_path_loss): basic path-loss model, FSPL (free space) or INH_OFFICE "
        "(3GPP Indoor Hotspot Office). Engine default is INH_OFFICE."),
    "street width": (
        "INDOOR topology (indoor.street_width), in metres: separation between buildings. Engine default is "
        "30."),
    "n rows": (
        "INDOOR topology: number of rows of buildings in the scenario. Engine default is 3."),
    "n columns": (
        "INDOOR topology: number of columns of buildings in the scenario. Engine default is 2."),
    "num cells": (
        "INDOOR topology (indoor.num_cells): number of cells per floor. Engine default is 3."),
    "num floors": (
        "INDOOR topology (indoor.num_floors): number of floors per building. Engine default is 1."),
    "num imt buildings": (
        "INDOOR topology (indoor.num_imt_buildings): \"ALL\" to put IMT stations in every building, or an "
        "integer with the number of buildings that contain them. Engine default is \"ALL\"."),
    "building class": (
        "INDOOR topology (indoor.building_class): TRADITIONAL or THERMALLY_EFFICIENT. Engine default is "
        "TRADITIONAL."),
    "ue indoor percent": (
        "INDOOR topology (indoor.ue_indoor_percent): fraction of UEs placed indoors, in [0, 1]. Engine "
        "default is 0.95."),
    "num clusters": (
        "Number of clusters of the topology. MACROCELL and HOTSPOT accept 1 or 7; SINGLE_BS accepts 1 or 2. "
        "Engine default is 1."),
    "azimuth": (
        "SINGLE_BS topology (single_bs.azimuth), in degrees: list of floats with one value per cluster, or "
        "\"random\". If unset the engine uses [0, 180] truncated to num_clusters."),
    "wrap around": (
        "MACROCELL and HOTSPOT topologies (wrap_around): enables wrap-around of the cell layout. Engine "
        "default is False."),
    "num hotspots per cell": (
        "HOTSPOT topology: number of hotspots per macro cell (sector). Engine default is 1.0 and validation "
        "requires a non-negative integer."),
    "max dist hotspot ue": (
        "HOTSPOT topology, in metres: maximum 2D distance between a hotspot and its UEs, that is, the hotspot "
        "radius. Engine default is 100.0, must be non-negative. Too large a value with many hotspots can make "
        "hotspot placement fail."),
    "min dist bs hotspot": (
        "HOTSPOT topology, in metres: minimum 2D distance between the macro base station and a hotspot. "
        "Engine default is 0.0, must be non-negative."),

    # ---- Topology: MACRO_COUNTRIES ----
    "raster encoding": (
        "MACRO_COUNTRIES (macrocell_countries.raster_encoding): how the population raster values are read, "
        "\"density\" (people/km2) or \"indexed\" (0-255 palette index mapped with sedac_min/sedac_max). The GUI "
        "also offers \"uniform\", meaning no raster and uniform sampling inside the countries."),
    "dist type": (
        "MACRO_COUNTRIES (dist_type): keeps only raster areas inside a density band, Urban 1500-10000, "
        "Suburban 300-1500 or Rural 0-300 people/km2 (bands used by the topology code). Engine default is none "
        "(no filter). It only acts when a population raster is used."),
    "sedac palette mode": (
        "MACRO_COUNTRIES, indexed rasters (sedac_palette_mode): \"log\" or \"linear\" mapping from palette "
        "index to density between sedac_min and sedac_max. Engine default is \"log\"."),
    "sedac min": (
        "MACRO_COUNTRIES, indexed rasters (sedac_min), in people/km2: density at the lowest palette index. "
        "Engine default is 1.0; it must be greater than 0."),
    "sedac max": (
        "MACRO_COUNTRIES, indexed rasters (sedac_max), in people/km2: density at the highest palette index. "
        "Engine default is 1e4; it must be greater than sedac_min."),
    "min density threshold": (
        "MACRO_COUNTRIES (min_density_threshold), in people/km2: density cutoff applied only when sampling "
        "base-station positions from the raster. Engine default is 0.0."),
    "density exponent": (
        "MACRO_COUNTRIES (density_exponent): exponent applied to density in the sampling weights; values "
        "above 1 bias the base stations toward dense areas. Engine default is 1.0."),
    "num bs total": (
        "MACRO_COUNTRIES (num_bs_total): total number of base stations spread over the listed countries. "
        "Engine default is 1000 and it must be an integer greater than 0 (ignored if bs_per_country is "
        "given)."),
    "rng seed": (
        "MACRO_COUNTRIES (rng_seed): seed of the random generator used to sample base-station positions when "
        "the topology builds its own generator. The dataclass default is 122."),
    "countries shapefile": (
        "MACRO_COUNTRIES (countries_shapefile): path to the countries shapefile (WGS84). If set, the file must "
        "exist; if empty the topology falls back to its default map."),
    "population raster": (
        "MACRO_COUNTRIES (population_raster): path to the population raster (SEDAC or equivalent GeoTIFF). If "
        "set, the file must exist; without it the base stations are placed uniformly inside the countries."),

    # ---- BS antenna ----
    "element pattern": (
        "Radiation pattern of each antenna element (antenna.array.element_pattern): M2101, F1336 or FIXED. "
        "Engine default is M2101."),
    "h beamsteer": (
        "horizontal_beamsteering_range, in degrees: [minimum, maximum] horizontal steering angle of the "
        "beams. Engine default is (-180, 179.9999); both values must lie in [-180, 180) with the second "
        "larger. For the UE it must stay at the default."),
    "v beamsteer": (
        "vertical_beamsteering_range, in degrees: [minimum, maximum] vertical steering angle of the beams. "
        "Engine default is (0, 179.9999); both values must lie in [0, 180) with the second larger. For the UE "
        "it must stay at the default."),
    "element max g": (
        "Maximum gain of a single antenna element (element_max_g), in dBi. Engine default is 5.0."),
    "element phi 3db": (
        "Horizontal 3 dB beamwidth of a single element (element_phi_3db), in degrees. Engine default is "
        "65."),
    "element theta 3db": (
        "Vertical 3 dB beamwidth of a single element (element_theta_3db), in degrees. Engine default is "
        "65."),
    "element horiz spacing": (
        "Horizontal spacing between array elements (element_horiz_spacing), in wavelengths (d/lambda). "
        "Engine default is 0.5."),
    "element vert spacing": (
        "Vertical spacing between array elements (element_vert_spacing), in wavelengths (d/lambda). Engine "
        "default is 0.5."),
    "element am": (
        "Front-to-back ratio of the single element (element_am), in dB. Engine default is 30."),
    "element sla v": (
        "Vertical sidelobe attenuation of the single element (element_sla_v), in dB. Engine default is "
        "30."),
    "multiplication factor": (
        "Multiplication factor k used to adjust the single-element pattern (multiplication_factor). Engine "
        "default is 12."),
    "is enabled": (
        "subarray.is_enabled: turns on the sub-array model of R23-WP5D-C-0413 Annex 4.2, in which each "
        "column element is itself a vertical sub-array. Engine default is False."),
    "eletrical downtilt": (
        "subarray.eletrical_downtilt, in degrees: electrical downtilt of the sub-array (electrical tilt = "
        "-1 * downtilt). Engine default is 3.0; used only when the sub-array is enabled."),

    # ---- UE ----
    "k m": (
        "ue.k_m (engine default 1): UEs per beam factor. The simulator creates BSs * k * k_m UEs, and each BS "
        "serves k * k_m UEs, of which k are scheduled at a time."),
    "distribution type": (
        "ue.distribution_type (engine default ANGLE_AND_DISTANCE). UNIFORM spreads UEs over the macrocell "
        "layout (Macrocell topology only); CELL and UNIFORM_IN_CELL place them in a deterministic cell; "
        "ANGLE_AND_DISTANCE draws distance and azimuth from the two distributions below."),
    "power dynamic range": (
        "ue.power_dynamic_range, in dB (engine default 63.0). In uplink power control the UE transmit power "
        "is not allowed below p_cmax minus this range."),
    "body loss": (
        "ue.body_loss, in dB (engine default 4.0): loss from the user's body, added to the coupling loss of "
        "links involving the UE."),
    "distribution distance": (
        "ue.distribution_distance (engine default RAYLEIGH), used with ANGLE_AND_DISTANCE. RAYLEIGH puts 99% "
        "of UEs inside the cell radius; UNIFORM is uniform in distance; SQRT(UNIFORM) is uniform in area."),
    "distribution azimuth": (
        "ue.distribution_azimuth (engine default NORMAL), used with ANGLE_AND_DISTANCE. NORMAL draws the "
        "angle from a normal distribution with sigma 30 degrees cut at the azimuth range; UNIFORM draws it "
        "uniformly over the azimuth range."),
    "azimuth range": (
        "ue.azimuth_range, in degrees, as (min, max) (engine default (-60, 60)). Range of the UE azimuth "
        "angle around the BS direction; with NORMAL the largest value is the cutoff, with UNIFORM the angle is "
        "uniform between the two."),

    # ---- UL / DL / channel ----
    "uplink attenuation factor": (
        "uplink.attenuation_factor (engine default 0.4): factor multiplying the Shannon throughput "
        "log2(1+SINR) in the uplink throughput calculation."),
    "uplink.sinr_min / max": (
        "uplink.sinr_min and uplink.sinr_max, in dB (engine defaults -10 and 22). In the uplink throughput "
        "calculation, SINR below the minimum gives zero throughput and SINR above the maximum is limited to "
        "the throughput of the maximum."),
    "downlink attenuation factor": (
        "downlink.attenuation_factor (engine default 0.6): factor multiplying the Shannon throughput "
        "log2(1+SINR) in the downlink throughput calculation."),
    "downlink.sinr_min / max": (
        "downlink.sinr_min and downlink.sinr_max, in dB (engine defaults -10 and 30). In the downlink "
        "throughput calculation, SINR below the minimum gives zero throughput and SINR above the maximum is "
        "limited to the throughput of the maximum."),
    "shadowing": (
        "imt.shadowing (engine default True): enables the shadowing term of the IMT propagation model. In "
        "the ABG model the shadowing standard deviation is 6.5 dB."),
}}

SECTIONS = {
    ("imt", "imt – general parameters"): (
        "General IMT system settings that do not belong to a single topology or antenna. Here the minimum "
        "BS-UE separation used when UEs are positioned is set. The other system-wide IMT values (frequency, "
        "bandwidth, channel model) are in their own rows."),
    ("imt", "topology – imt"): (
        "Selects and parameterises the IMT network layout (imt.topology.type). Only the group of the chosen "
        "type is written to the YAML and validated by the engine: MACROCELL, HOTSPOT, INDOOR, SINGLE_BS, NTN, "
        "MSS_DC (satellite beams, with satellite selection and beam positioning) or MACRO_COUNTRIES "
        "(population-weighted sites over countries). The topology defines base-station positions and cell "
        "radius, which the UE placement then uses."),
    ("imt", "bs – parameters"): (
        "Base-station antenna array settings (imt.bs.antenna.array): element pattern and gains, beamwidths, "
        "element spacing in wavelengths, rows and columns, beam steering limits and the optional sub-array. "
        "They define the beamforming gain used in the coupling-loss calculation."),
    ("imt", "ue – parameters"): (
        "UE settings (imt.ue): number of UEs per BS, how UEs are distributed around the BS (distance and "
        "azimuth), uplink power control values, body loss and the UE antenna. They determine where UEs are "
        "placed and how much they transmit and lose."),
    ("imt", "ul / dl / channel / shadowing"): (
        "Link-level settings for IMT. The uplink and downlink attenuation factors and SINR limits shape the "
        "throughput calculation, and the shadowing flag controls the shadowing term of the channel model."),
}
