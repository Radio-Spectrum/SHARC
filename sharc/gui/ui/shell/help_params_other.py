# -*- coding: utf-8 -*-
"""Hover explanations for the Database, Terrain, Victim and Station pages.

PARAMS key = GUI row label, lower-case. SECTIONS key = (page, lower-case section title).
Sources: sharc/gui/ui/tabs/database.py, terrain.py, assets/victim_tab, assets/ses_tab,
sharc/gui/core/yaml_builder.py, state.py and sharc/parameters/*.
"""

PARAMS = {
    "database": {
        "use database": (
            "Turns the base-station database on. When off, no `database` block is written to the YAML and the "
            "simulation runs unchanged. Default: off."),
        "database file": (
            "Path to the .csv or .xlsx file whose rows describe real IMT sites (written as database_file_name, "
            "converted to an absolute path). The page reads it with pandas and reports the row count, the extent "
            "and any missing columns."),
        "delimiter": (
            "Column separator used to read a .csv database (comma, tab or pipe); ignored for .xlsx. "
            "Default: comma."),
        "number of subsets": (
            "Splits the database into this many consecutive subsets (num_subsets). Each snapshot simulates one "
            "subset and every subset gets general.num_snapshots snapshots, so the run has "
            "num_snapshots x num_subsets snapshots in total. Default: 1."),
        "take sites from database": (
            "Takes the MACRO_COUNTRIES base-station sites (columns latitude, longitude, azimute, altura) from the "
            "database instead of sampling them (from_db_topology_countries). Switching it on sets the IMT "
            "topology to Macro_countries and centres the scenario on the database extent. Default: off."),
        "take antenna parameters from database": (
            "Takes the array antenna, downtilt and total power of each base station from the database columns "
            "(n_rows, n_columns, beamforming_gain, element_max_g, tx_power, sub_num_rows, downtilt). "
            "The engine requires 'Take sites from database' to be on as well. Default: off."),
        "use real terrain": (
            "Uses real terrain between each base station and the victim station: ground altitude of every site "
            "and, with the P452 channel model, the P.452 loss of each base station computed once per run over "
            "the terrain profile (use_real_terrain). Default: off."),
        "adaptive mesh file (.gpkg)": (
            "Optional GeoPackage with an already built adaptive mesh (terrain.ref_gpkg). When empty, the engine "
            "downloads terrain and land cover around the database and builds the mesh in the terrain cache folder."),
        "terrain/land-cover grid resolution": (
            "Resolution in metres of the terrain and land-cover grids that are downloaded (terrain.mesh_resolution_m). "
            "Must be positive. Default: 100 m."),
        "mesh resolution, urban": (
            "Target mesh cell size in metres over urban land cover (terrain.mesh_urban_res_m, positive integer). "
            "Default: 30 m."),
        "mesh resolution, suburban": (
            "Target mesh cell size in metres over suburban land cover (terrain.mesh_suburban_res_m, positive "
            "integer). Default: 150 m."),
        "mesh resolution, rural": (
            "Target mesh cell size in metres over rural land cover (terrain.mesh_rural_res_m, positive integer). "
            "Default: 500 m."),
        "water in mesh": (
            "How water areas enter the adaptive mesh (terrain.mesh_water): 'exclude' or 'coarse'. "
            "Default: exclude."),
        "terrain cache folder": (
            "Folder (terrain.mesh_output_dir) where the downloaded grids and the mesh built from them are stored. "
            "When left empty the GUI uses a 'terrain_cache' folder next to the run folders; the engine's own "
            "default is 'data'."),
    },
    "terrain": {
        "stream terrain and land cover": (
            "Master switch of the streamed terrain layers in the 3D preview. When off, the preview shows none of "
            "the terrain, land-cover, water, building or tree layers and ground heights are not looked up. "
            "Preview only; it does not change the simulation. Default: on."),
        "show 3d relief": (
            "Draws the terrain elevation (SRTM tiles from AWS Terrain Tiles, or Cesium World Terrain if selected "
            "as relief source) as 3D relief in the preview. Preview only. Default: on."),
        "show land cover": (
            "Paints the ESA WorldCover land-cover classes over the terrain in the preview, with a legend. "
            "It is hidden automatically in the Realistic, City and Photorealistic scene looks. Preview only. "
            "Default: on."),
        "show hillshade": (
            "Adds a shaded-relief overlay to the preview so slopes are easier to read. Preview only. "
            "Default: off."),
        "show lakes and rivers": (
            "Overlays rivers and lakes (Natural Earth, public domain) on the map. Preview only. Default: on."),
        "show buildings when close": (
            "Shows OpenStreetMap buildings once the camera is closer than the 'Show buildings when closer than' "
            "distance, up to the building limit. Preview only. Default: on."),
        "show trees when close": (
            "Shows trees (OpenStreetMap plus vegetation data) when the camera is close, up to the tree limit. "
            "Preview only. Default: on."),
        "warn if a base station is on water": (
            "Checks the base-station positions of the current scenario against the water layer and warns in the "
            "3D view and in Messages when a site falls on water. Skipped for NTN and MSS_DC topologies. "
            "Preview only. Default: on."),
        "vertical exaggeration": (
            "Scale factor applied to terrain heights in the 3D scene; 1 is true scale, larger values exaggerate "
            "relief. Preview only. Default: 1.0."),
        "land-cover opacity": (
            "Opacity of the land-cover overlay, from 0 (transparent) to 1 (opaque). The Clean city look "
            "overrides it with 0.85. Preview only. Default: 0.45."),
        "base map": (
            "Globe base imagery: Natural Earth II (offline), Dark political (offline) or Esri World Imagery "
            "(online). The Realistic, City and Photorealistic looks always use Esri imagery. Preview only. "
            "Default: Natural Earth II."),
        "map quality": (
            "Level of detail of the globe: Low, Medium, High or Ultra, mapped to a screen-space error of 4.0, 2.0, "
            "1.5 and 1.0. Higher quality loads more tiles and needs a faster computer and network. Preview only. "
            "Default: High."),
        "relief resolution": (
            "Number of elevation samples per terrain tile side: 33, 65, 129 or 257. More samples give finer relief "
            "but heavier tiles. Preview only. Default: 65 x 65."),
        "maximum tile detail level": (
            "Deepest zoom level (10 to 15) at which land-cover and relief tiles are requested. Higher levels give "
            "sharper close-ups and more downloads. Preview only. Default: 14."),
        "render resolution": (
            "Rendering scale of the 3D view (50 %, 75 %, 100 %, 150 % or 200 % of the window resolution). Lower it "
            "if the view is slow; raise it for sharper screenshots. Preview only. Default: 100 %."),
        "building limit": (
            "Maximum number of buildings drawn at once (500, 1000, 3000, 6000 or 10000). Preview only. "
            "Default: 3000."),
        "scene look": (
            "Visual style of the 3D scene: Analysis (land cover), Clean city model, Realistic (satellite imagery), "
            "City buildings (Cesium OSM Buildings, needs an ion token) or Photorealistic 3D (Google tiles, needs "
            "an ion token or a Google key). Preview only. Default: Analysis (land cover)."),
        "relief source": (
            "Where terrain heights come from: Local SRTM (offline, the streamed tiles) or Cesium World Terrain "
            "(needs a Cesium ion token). Preview only. Default: Local SRTM."),
        "cinematic tone mapping": (
            "Switches the preview tone mapper from Reinhard to ACES for a more cinematic contrast. Preview only. "
            "Default: on."),
        "time of day": (
            "Sun position used to light the 3D scene (Sunrise 06:30, Morning 09:00, Midday 12:30, Afternoon 15:30, "
            "Golden hour 17:30, Night 22:00), as local solar time on 21 March. Preview only. Default: Midday."),
        "cesium ion access token": (
            "Free access token from ion.cesium.com. It is needed for Cesium World Terrain, Cesium OSM Buildings "
            "and, as an alternative to a Google key, the photorealistic tiles. Stored in the GUI settings and used "
            "only by the preview."),
        "google map tiles api key": (
            "Google Map Tiles API key used for the Photorealistic 3D look when no Cesium ion token is given. "
            "Use the 'Test Google / ion access' button to check it. Preview only."),
        "tree limit": (
            "Maximum number of trees drawn at once (500, 1000, 2500 or 5000). Preview only. Default: 2500."),
        "show buildings when closer than": (
            "Camera distance below which buildings are loaded: Close 1.5 km, Normal 3.5 km or Far 6 km. "
            "Preview only. Default: Normal (3.5 km)."),
        "hide buildings lower than": (
            "Buildings shorter than this height in metres (0, 3, 6, 10 or 20) are not drawn. Preview only. "
            "Default: 0."),
        "region from": (
            "How the offline terrain region to download is chosen: Scenario area (a square around the IMT "
            "reference point), Database extent (the database bounding box plus the margin) or Custom (the four "
            "bounds below). Default: Scenario area."),
        "scenario radius": (
            "Half-size in km of the region downloaded around the IMT reference point when the region comes from "
            "the Scenario area. Default: 10 km."),
        "database margin": (
            "Margin in km added around the database bounding box when the region comes from the Database extent. "
            "Default: 5 km."),
        "west": (
            "Western bound of the Custom download region, in degrees of longitude. Used only when 'Region from' is "
            "Custom."),
        "south": (
            "Southern bound of the Custom download region, in degrees of latitude. Used only when 'Region from' is "
            "Custom."),
        "east": (
            "Eastern bound of the Custom download region, in degrees of longitude. Used only when 'Region from' is "
            "Custom."),
        "north": (
            "Northern bound of the Custom download region, in degrees of latitude. Used only when 'Region from' is "
            "Custom."),
        "grid resolution": (
            "Cell size in metres of the elevation and land-cover grid built by 'Download terrain and land cover'. "
            "The region label shows the estimated number of grid cells for this value. Default: 100 m."),
    },
    "victim": {
        "season": (
            "Season (SUMMER or WINTER) passed to the single space station and to the P.619 propagation model, "
            "which rejects any other value. Written as single_space_station.season; the engine default is SUMMER."),
        "spherical earth?": (
            "Written as single_space_station.is_global_coordinate_system. The parameter exists in the engine "
            "(default false), but no other engine code reads it in this version, so its effect could not be "
            "verified."),
        "location fixed latitude deg": (
            "Latitude in degrees of the satellite location (geometry.location.fixed.lat_deg, location type FIXED). "
            "The engine uses it as the latitude of the satellite reference frame, together with the altitude."),
        "location fixed longitude deg": (
            "Longitude in degrees of the satellite location (geometry.location.fixed.long_deg, location type "
            "FIXED). The engine uses it as the longitude of the satellite reference frame, together with the "
            "altitude."),
        "es latitude deg": (
            "Latitude in degrees of the reference point on Earth (geometry.es_lat_deg). It becomes the origin of "
            "the simulator coordinate system when none is given, and is propagated to the P.619 model as "
            "earth_station_lat_deg. Engine default: -15.793889."),
        "es longitude deg": (
            "Longitude in degrees of the reference point on Earth (geometry.es_long_deg). It becomes the origin of "
            "the simulator coordinate system when none is given. Engine default: -47.882778."),
        "azimuth type": (
            "How the satellite antenna azimuth is defined (geometry.azimuth.type). The GUI offers POINTING_AT_IMT "
            "and FIXED; the engine also knows POINTING_AT_LAT_LONG_ALT and RANDOM_RANGE. FIXED needs a fixed "
            "value that this page does not write. Default: POINTING_AT_IMT."),
        "elevation type": (
            "How the satellite antenna elevation is defined (geometry.elevation.type). The GUI offers "
            "POINTING_AT_IMT and FIXED; the engine also knows POINTING_AT_LAT_LONG_ALT and RANDOM_RANGE. FIXED "
            "needs a fixed value that this page does not write. Default: POINTING_AT_IMT."),
    },
    "station": {
        "adjacent channel reception": (
            "Adjacent-channel filter applied when this station is the victim (adjacent_ch_reception): ACS "
            "applies the adjacent_ch_selectivity value, OFF disables it. Engine default: OFF."),
        "adjacent channel emissions": (
            "How this station's out-of-band emissions are modelled when it interferes (adjacent_ch_emissions): "
            "ACLR uses the leakage ratio, SPECTRAL_MASK uses the spectral mask and spurious emissions, OFF "
            "disables them. Engine default: OFF."),
        "location type": (
            "How the station position is chosen (geometry.location.type): FIXED (x, y in metres), FIXED_GEO "
            "(latitude, longitude, ground altitude), CELL or NETWORK (random with a minimum distance to the base "
            "stations) or UNIFORM_DIST (random between a minimum and maximum distance to the centre). "
            "The P.452-over-database setup requires FIXED_GEO."),
        "ground altitude": (
            "Altitude in metres of the ground at the FIXED_GEO site (location.fixed_geo.altitude). The antenna "
            "sits geometry.height above it. Engine default: 0."),
        "x": (
            "X coordinate in metres of the station in the simulator frame, used when the location type is FIXED "
            "(location.fixed.x)."),
        "y": (
            "Y coordinate in metres of the station in the simulator frame, used when the location type is FIXED "
            "(location.fixed.y)."),
        "type": (
            "How the antenna azimuth or elevation is set: FIXED (uses the fixed angle in degrees), UNIFORM_DIST "
            "(drawn between the min and max angles) or POINTING_AT_IMT_CENTER (points at the simulator reference "
            "point). The same three options exist for azimuth and for elevation."),
        "atmospheric pressure": (
            "Total air pressure in hPa given to the P.452 clear-air model (param_p452.atmospheric_pressure). "
            "GUI default 1013.25; engine default 935."),
        "air temperature": (
            "Air temperature in kelvin given to the P.452 model (param_p452.air_temperature). "
            "GUI default 293.15; engine default 300."),
        "p 452": (
            "Time percentage p used by the P.452 model (param_p452.percentage_p), a number from 0 to 100 "
            "(the engine also accepts RANDOM). The loss is the one not exceeded for that percentage of time. "
            "GUI default 20; engine default 0.2."),
        "n0": (
            "Sea-level surface refractivity N0 (N-units) used by the P.452 model; the engine comment says to take "
            "it from the refractivity map. GUI default 315; engine default 352.58."),
        "delta n": (
            "Average radio-refractive-index lapse rate delta N (N-units/km) used by the P.452 model; the engine "
            "comment says to take it from the map. GUI default 45; engine default 43.127."),
        "polarization": (
            "Antenna polarization for the P.452 diffraction calculation: horizontal or vertical (any other value "
            "raises an error). GUI and engine default: horizontal."),
        "dct": (
            "Distance over land in km from the transmit antenna to the coast (param_p452.Dct), used by the P.452 "
            "clutter and path corrections. It is replaced by the value from the profile when a zone raster is "
            "set. GUI default 500; engine default 70."),
        "dcr": (
            "Distance over land in km from the receive antenna to the coast (param_p452.Dcr), used by the P.452 "
            "clutter and path corrections. It is replaced by the value from the profile when a zone raster is "
            "set. GUI default 500; engine default 70."),
        "hte": (
            "Effective height in metres of the interfering (transmit) antenna in P.452. Read-only: the GUI copies "
            "it from the IMT base-station height (downlink) or UE height (uplink). Engine default: 20."),
        "hre": (
            "Effective height in metres of the interfered-with (receive) antenna in P.452. Read-only: the GUI "
            "copies it from the earth-station height. Engine default: 3."),
        "clutter loss": (
            "When on, a clutter loss is added to the P.452 basic loss (the engine comment cites ITU-R P.2108). "
            "GUI default off; engine default on."),
        "tx latitude": (
            "Latitude in degrees of the transmitter, in P.452 averaged with the receiver latitude to get the path "
            "centre latitude (param_p452.tx_lat). GUI default 45; engine default -23.55028."),
        "rx latitude": (
            "Latitude in degrees of the receiver, in P.452 averaged with the transmitter latitude to get the path "
            "centre latitude (param_p452.rx_lat). GUI default 45; engine default -23.17889."),
        "override from db": (
            "Uses the P.452 loss of each base station precomputed once per run over the real terrain "
            "(param_p452.override_from_db) instead of computing P.452 on every snapshot. Needs the database, its "
            "sites and real terrain enabled. Default: off."),
        "hte from db": (
            "Takes the transmit height Hte of each base station from the database column 'altura' instead of the "
            "single Hte value (param_p452.hte_from_db). Default: off."),
        "profile source": (
            "Where the terrain profiles for the precomputed P.452 come from: 'mesh' (the adaptive mesh of the "
            "database terrain) or 'grid' (a terrain GeoTIFF, interpolated bilinearly). 'grid' needs a profile "
            "raster. Default: mesh."),
        "profile step m": (
            "Spacing in metres of the points along each terrain profile (param_p452.profile_step_m). Zero keeps "
            "301 points per profile; negative values are rejected. Default: 0."),
    },
}

SECTIONS = {
    ("database", "base-station database"): (
        "Loads a CSV or XLSX list of real IMT sites into the simulation. The file is split into subsets that are "
        "simulated one after another, and can supply the site positions and the array antenna parameters. The GUI "
        "writes this as the engine's `database` block."),
    ("database", "real terrain"): (
        "Settings for using real terrain with the database: the downloaded terrain and land-cover grid, the "
        "adaptive mesh resolution per area type, how water is meshed and where the cache is stored. They map to "
        "`database.use_real_terrain` and `database.terrain` in the YAML."),
    ("terrain", "map layers (streamed on demand)"): (
        "Chooses which streamed layers the 3D preview shows: relief, land cover, hillshade, water, buildings and "
        "trees. Tiles are requested only for the area in view and cached on disk. These settings affect the preview "
        "only, not the simulation."),
    ("terrain", "detail and performance"): (
        "Trade-offs between detail and speed of the 3D preview (map quality, tile level, render scale, object "
        "limits), the scene look and lighting, and the Cesium ion token or Google key for premium imagery. "
        "Preview only; the simulation is not affected."),
    ("terrain", "offline region (for the simulation)"): (
        "Defines the geographic box whose terrain and land cover are downloaded for offline use: around the "
        "scenario, around the database extent plus a margin, or custom bounds. The region label shows its size "
        "and number of grid cells."),
    ("terrain", "data"): (
        "Grid resolution of the downloaded data. The elevation comes from SRTM (AWS Terrain Tiles) and the land "
        "cover from ESA WorldCover 10 m (2021), as shown in the page."),
    ("victim", "basic parameters"): (
        "Basic parameters of the single space station (satellite) victim system: frequency, bandwidth, "
        "transmit power density, noise temperature, polarization loss, channel model and season. They are written "
        "to the `single_space_station` block."),
    ("victim", "geometry – classes"): (
        "Geometry of the satellite and of the reference point on Earth: satellite altitude and fixed location, "
        "earth-station altitude, latitude and longitude, and the pointing type of the satellite antenna. "
        "Written to `single_space_station.geometry`."),
    ("station", "basic parameters"): (
        "Basic parameters of the single earth station: frequency, bandwidth, noise temperature, adjacent-channel "
        "reception and emission models, transmit power density, antenna height and polarization loss. They are "
        "written to the `single_earth_station` block."),
    ("station", "geometry"): (
        "Where the earth station is and where its antenna points: location type with its coordinates, and the "
        "azimuth and elevation types. Written to `single_earth_station.geometry`."),
    ("station", "channel model"): (
        "Propagation model between the earth station and IMT. With P452 the extra inputs (atmospheric pressure, "
        "refractivity, distances to coast, heights, clutter, and the terrain-over-database options) are "
        "written to `param_p452`."),
}
