"""Help texts shown by the "?" panel. Parameters are keyed by page, then by the lower-case row label."""

PAGES = {
    "general": "Run-wide settings: how many snapshots to simulate, the random seed, which system shares the band with the IMT network, and where results are written.",
    "imt": "The IMT (5G/6G) network: carrier, topology, base stations (BS) and user equipment (UE).",
    "database": "Optional base-station database (CSV) and real terrain mesh used to place sites and compute propagation.",
    "terrain": "Map layers, 3D detail and offline regions for the preview, and the terrain and land-cover data they stream.",
    "victim": "The space station that shares the band with the IMT network: carrier, geometry and antenna.",
    "station": "The earth station that shares the band with the IMT network: carrier, geometry, antenna and propagation.",
    "preview": "Interactive 3D/2D view of the scenario exactly as the simulation engine builds it.",
    "ssh": "Connection to a remote machine for running simulations there.",
    "runner": "Starts, stops and monitors simulation runs; shows the log.",
    "results": "Plots and statistics of finished simulations.",
    "contour": "Protection contour: the distance around a protected station beyond which the IMT interference stays under the protection criterion.",
}

SECTIONS = {
    ("general", "simulation"): "Number of Monte Carlo snapshots, random seed, system type and IMT link direction.",
    ("general", "interference channels"): "Which interference mechanisms are included in the calculation.",
    ("general", "output"): "Folder and file-name prefix of the result files.",
    ("general", "parameter sweep"): "Runs the simulation several times, varying chosen parameters. Each combination becomes one YAML configuration. In the variable table write lists as Python literals with quotes, for example ['A', 'B'].",
    ("imt", "imt"): "Carrier and spectrum parameters of the IMT network.",
    ("imt", "topology"): "Layout of the base stations: macro cells, hotspots, indoor, NTN, MSS_DC or a country-wide network.",
    ("imt", "bs"): "Transmit power, losses, height and antenna of the base stations.",
    ("imt", "ue"): "UE distribution, power control and antenna.",
    ("imt", "ul / dl"): "Uplink and downlink attenuation, SINR limits, channel model and shadowing.",
    ("database", "base-station database"): "Takes site positions and antenna data from a CSV file instead of random placement.",
    ("database", "real terrain"): "Uses a terrain and land-cover mesh for path loss instead of a flat Earth.",
    ("terrain", "map layers"): "Layers drawn in the 3D preview. They are streamed on demand.",
    ("terrain", "detail and performance"): "Trade-off between visual detail and speed in the 3D preview.",
    ("terrain", "offline region"): "Downloads data for a region so the simulation and preview work without a connection.",
    ("victim", "basic"): "Carrier and noise parameters of the space station receiver.",
    ("victim", "geometry"): "Altitude and ground position of the space station and of the associated earth station.",
    ("victim", "antenna"): "Radiation pattern of the space station antenna.",
    ("station", "basic"): "Carrier, noise and adjacent-channel parameters of the earth station.",
    ("station", "geometry"): "Where the earth station is placed relative to the IMT network.",
    ("station", "antenna"): "Radiation pattern of the earth station antenna.",
    ("station", "channel model"): "Propagation model between the IMT network and the earth station, and its inputs.",
}

_COMMON = {
    "frequency": "Carrier centre frequency.",
    "bandwidth": "Channel bandwidth.",
    "noise temperature": "System noise temperature of the receiver. Together with the bandwidth it sets the noise floor, N = k T B.",
    "polarization loss": "Loss caused by polarization mismatch between the transmitting and the receiving antenna.",
    "pattern": "Radiation-pattern model that gives the antenna gain as a function of angle.",
    "peak gain": "Maximum (boresight) antenna gain.",
    "height": "Antenna height above ground.",
    "noise figure": "Noise figure of the receiver.",
    "ohmic loss": "Cable and feeder losses between the transmitter and its antenna. They are subtracted from the conducted power.",
    "channel model": "Propagation model used for the path loss.",
    "spectral mask": "Out-of-band emission mask of the transmitter.",
    "spurious emissions": "Level of spurious emissions outside the necessary bandwidth.",
}

PARAMS = {
    "general": {
        "num snapshots": "Number of Monte Carlo snapshots. Each snapshot draws new random positions and fading and evaluates the interference once.",
        "seed": "Seed of the random number generator. The same seed reproduces the same results.",
        "system type": "Type of the system that shares the band with the IMT network.",
        "imt link direction": "DOWNLINK: base stations transmit. UPLINK: user equipment transmits.",
        "co-channel interference": "Include interference from carriers on the same frequency.",
        "adjacent-channel interference": "Include interference leaking from adjacent channels (emission mask and receiver selectivity).",
        "output dir": "Folder where result files are written.",
        "filename prefix": "Prefix of the result file names. It may contain sweep variables, shown in the preview line below.",
        "overwrite existing results": "Replace result files that already exist. When off, existing results are kept.",
    },
    "imt": {
        "interfered with": "On: the IMT network is the victim. Off: the IMT network is the interferer.",
        "rb bandwidth": "Bandwidth of one resource block.",
        "guard band ratio": "Fraction of the channel bandwidth reserved as guard band.",
        "adjacent antenna model": "Antenna model used for adjacent-channel interference: BEAMFORMING (full array) or SINGLE_ELEMENT.",
        "conducted power": "Transmit power at the antenna port, before array gain. Ohmic loss is subtracted from it.",
        "load probability": "Probability that a base station is transmitting in a snapshot (network load, 0 to 1).",
        "downtilt": "Mechanical downtilt of the antenna below the horizon.",
        "min array gain": "Floor applied to the array gain. A very low value such as -200 dB means there is no floor.",
        "normalization": "Apply the beamforming normalization table to the array gain.",
        "k": "Number of UEs served by each base station in a snapshot.",
        "indoor percent": "Percentage of UEs placed indoors.",
        "tx power control": "Uplink power control. When on, the UE power follows the open-loop rule limited by Pcmax.",
        "p o pusch": "Open-loop uplink power-control target (P0 PUSCH).",
        "alpha": "Path-loss compensation factor of the open-loop uplink power control, from 0 to 1.",
        "p cmax": "Maximum UE transmit power.",
        "central latitude": "Latitude of the network centre.",
        "central longitude": "Longitude of the network centre.",
        "central altitude": "Altitude of the network centre.",
        "num beams": "Number of beams.",
        "beam radius": "Radius of each beam footprint on the ground.",
    },
    "victim": {
        "tx power density": "Transmit power spectral density of the space station.",
        "noise temperature": "System noise temperature of the space-station receiver. Together with the bandwidth it sets the noise floor.",
        "altitude": "Altitude of the space station above the Earth surface.",
        "es altitude": "Altitude of the earth station.",
        "3 db beamwidth": "Angle between the two directions where the gain is 3 dB below the peak.",
        "side-lobe level ls": "Near-in side-lobe level relative to the peak gain (ITU-R S.672 pattern).",
        "mean clutter height": "Mean height of the clutter (buildings, trees) around the earth station, used by the P.619 model.",
        "below rooftop": "Earth station antenna is below the rooftop level.",
    },
    "station": {
        "tx power density": "Transmit power spectral density of the earth station.",
        "diameter": "Dish diameter. It sets the gain and beamwidth of the dish patterns.",
        "latitude": "Latitude of the earth station.",
        "longitude": "Longitude of the earth station.",
        "min dist to center": "Minimum distance from the IMT network centre when the position is drawn at random.",
        "max dist to center": "Maximum distance from the IMT network centre when the position is drawn at random.",
        "adjacent channel selectivity": "Receiver attenuation of signals in the adjacent channel.",
        "adjacent channel leak ratio": "Ratio of the power leaked into the adjacent channel to the in-channel power.",
    },
}

TOOLBAR = (
    ("Run (Ctrl+R)", "Runs the simulation with the current configuration."),
    ("Run later", "Schedules the simulation for a later time."),
    ("Stop", "Stops the simulations that are running."),
    ("Refresh preview", "Rebuilds the scene preview from the current parameters."),
    ("Parameter sweep", "Generates the sweep configurations without running them."),
    ("Results", "Opens Analysis and Results."),
    ("Theme", "Switches between the graphite and light themes."),
)

PREVIEW_BUTTONS = (
    ("Zoom to scene", "Frames the whole scenario."),
    ("3D / 2D", "Switches the view between globe and flat map."),
    ("Base map", "Cycles through the available base maps."),
    ("Graticule and city labels", "Shows or hides the latitude/longitude grid and city names."),
    ("Sun lighting", "Turns the sun lighting on or off."),
    ("Place scenario", "Click the map to move the scenario centre."),
    ("Street view", "Walk through the scene at eye level: W A S D to move, drag to look, Esc to leave."),
    ("UE links", "UE links coloured by SNR. Click a link to see its link budget."),
    ("Play snapshots", "Plays the snapshot sequence; UEs are redrawn as in the simulation."),
    ("Interferer vs victim", "Base stations coloured by their contribution to the interference, with the paths to the victim."),
    ("Ground heat map", "Cycles through aggregate IMT PSD, I/N and strongest-BS power on the ground. With a satellite it also cycles the footprint maps."),
    ("Antenna gain lobes", "3D heat map of the base-station pattern: cold is side lobes, hot is main beam."),
    ("Screenshot", "Saves the current 3D view as an image."),
)


def lookup(page_key, text):
    """Description of the row `text` on `page_key`, or an empty string."""
    low = (text or "").strip().lower()
    return PARAMS.get(page_key, {}).get(low) or _COMMON.get(low, "")


def _merge_generated():
    """Descriptions written from the engine source live in help_params_*.py; hand-written ones win on conflict."""
    import importlib
    for name in ("help_params_imt", "help_params_other"):
        try:
            mod = importlib.import_module(f"ui.shell.{name}")
        except ImportError:
            continue
        for page, rows in getattr(mod, "PARAMS", {}).items():
            for label, text in rows.items():
                PARAMS.setdefault(page, {}).setdefault(label, text)
        for key, text in getattr(mod, "SECTIONS", {}).items():
            SECTIONS.setdefault(key, text)


_merge_generated()


def section_text(page_key, title):
    low = (title or "").strip().lower()
    best = ""
    text_out = ""
    for (key, prefix), text in SECTIONS.items():
        if key == page_key and low.startswith(prefix) and len(prefix) > len(best):
            best, text_out = prefix, text
    return text_out
