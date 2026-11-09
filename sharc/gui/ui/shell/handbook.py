"""Handbook topics for the Help panel: (title, HTML). Kept to what the simulator actually does today."""
from ui.shell import help_content as hc


def _list(rows):
    return "<ul>" + "".join(f"<li><b>{a}</b>: {b}</li>" for a, b in rows) + "</ul>"


TOPICS = [
    ("What SHARC does",
     "<h2>What SHARC does</h2>"
     "<p>SHARC is a Monte Carlo simulator of the interference between an IMT (5G/6G) network and another radio "
     "service that shares its band: a space station, an earth station, or a radio-astronomy site. In every "
     "<b>snapshot</b> it draws random positions, fading and power control, computes the interference at the "
     "victim and stores it. After many snapshots the results give the statistics (for example the CDF of I/N) "
     "that are compared with the protection criterion.</p>"
     "<p>This interface builds the YAML configuration, shows the scenario as the simulation engine builds it, "
     "runs the simulation and plots the results.</p>"),

    ("Quick start",
     "<h2>Quick start</h2><ol>"
     "<li><b>General Settings</b>: choose the system type (the victim), the IMT link direction, the number of "
     "snapshots and the output folder.</li>"
     "<li><b>IMT System</b>: set the carrier (frequency, bandwidth), the topology, the base stations (BS) and the "
     "user equipment (UE).</li>"
     "<li><b>Space Station</b> or <b>Earth Station</b>: configure the victim system.</li>"
     "<li>Open <b>Topology Preview</b> to check the scenario in 3D. The preview is built by the same engine "
     "code that runs the simulation, so what you see is what is simulated.</li>"
     "<li>Press <b>Run</b> (Ctrl+R). Follow the progress in <b>Jobs</b> and <b>Messages</b>.</li>"
     "<li>Open <b>Analysis &amp; Results</b> to plot the output.</li></ol>"),

    ("The interface",
     "<h2>The interface</h2>" + _list([
         ("Scenario (left)", "Tree of the project. Click a page to open it; click a section to show only that "
          "section. Double-click a section, or right-click and choose Open in window, to detach it."),
         ("Properties (right)", "The parameters of the selected page or section. The search box filters the "
          "rows by name or unit. Click a section header to collapse it."),
         ("Center tabs", "3D Scene, Spectrum &amp; Link Budget, Results and Protection Contour."),
         ("Bottom docks", "Messages (log), Jobs (queue and schedule) and Plots."),
         ("Toolbar", "Run, Run later, Stop, Refresh preview, Parameter sweep, Results and Theme."),
         ("Help (?)", "The round button on the right of the toolbar, or F1, opens this panel."),
     ]) + "<p>Toolbar buttons:</p>" + _list(hc.TOOLBAR)),

    ("IMT network",
     "<h2>IMT network</h2>"
     "<p>The IMT page holds the carrier, the topology, the BS and UE parameters, and the link settings.</p>"
     + _list([
         ("General parameters", "Frequency, bandwidth, resource-block bandwidth, spectral mask, spurious "
          "emissions and the adjacent-channel antenna model."),
         ("Topology", "Layout of the base stations. Types include macro cells, hotspots, indoor, NTN, MSS_DC and "
          "Macro_countries (a country-wide network, optionally from a site database)."),
         ("BS parameters", "Conducted power, ohmic loss, height, noise figure, antenna element and array, "
          "beam steering, downtilt and network load."),
         ("UE parameters", "Number of UEs per BS (k), indoor percentage, power control (uplink), height and "
          "antenna."),
         ("UL / DL / Channel / Shadowing", "Attenuation factors, SINR limits, channel model and shadowing."),
     ])),

    ("Victim systems",
     "<h2>Victim systems</h2>"
     "<p>The system type chosen in General Settings decides which page applies.</p>" + _list([
         ("Single earth station", "A ground station with a dish antenna, placed at a fixed point or drawn "
          "around the IMT network; it has its own propagation model (for example ITU-R P.452)."),
         ("Single space station", "A satellite receiver with its geometry (altitude and sub-satellite point), "
          "pointing and antenna. The preview draws its footprint on the ground."),
         ("MSS_D2D and MSS_DC", "Satellite constellations. The preview draws the satellites, the beam "
          "footprints coloured by satellite and the UEs."),
     ])),

    ("Database and real terrain",
     "<h2>Database and real terrain</h2>"
     "<p><b>Base-Station Database</b> takes the site positions (and optionally the antenna parameters) from a CSV "
     "file instead of random placement. <b>Real Terrain</b> uses a terrain and land-cover mesh for the path "
     "loss. The CSV file is not stored in the project: keep it next to the configuration.</p>"),

    ("Terrain and map layers",
     "<h2>Terrain and map layers</h2>"
     "<p>These settings only change what the 3D preview shows and how fast it draws: streamed terrain and land "
     "cover, 3D relief, buildings and trees when close, base map and render quality. <b>Offline Region</b> "
     "downloads the data of a region so the preview and the simulation work without a connection. Access "
     "tokens (Cesium ion, Google Map Tiles) are optional and enable the satellite imagery.</p>"),

    ("Parameter sweep",
     "<h2>Parameter sweep</h2>"
     "<p>A sweep runs the simulation several times, varying chosen parameters. Each combination becomes one "
     "YAML configuration, and the file name can include the sweep variables.</p>"
     "<p><b>Important:</b> write lists in the variable table as Python literals <b>with quotes</b>, for example "
     "<code>['A', 'B']</code> or <code>['a.json', 'b.json']</code>. Without quotes the list is read as empty and "
     "the variable is ignored without a warning.</p>"
     "<p><b>Parameter sweep</b> in the toolbar generates the configurations without running them.</p>"),

    ("Running and monitoring",
     "<h2>Running and monitoring</h2>" + _list([
         ("Run (Ctrl+R)", "Starts the simulation with the current configuration."),
         ("Run later", "Schedules a run for a given time."),
         ("Stop", "Stops the runs that are in progress."),
         ("Jobs", "Queue of runs with their state; right-click a job to run, stop, reschedule, move or remove it."),
         ("Messages", "Log of the run and of the interface."),
         ("SSH Connection", "Lets you run on a remote machine."),
     ])),

    ("3D preview",
     "<h2>3D preview</h2>"
     "<p>The preview shows the scenario as the engine builds it: sites, sectors, UEs, links and the satellite "
     "geometry. The ground maps use a <b>nominal</b> model: free space, boresight gain and no power control. "
     "They are a planning footprint, not a Monte Carlo result.</p>" + _list(hc.PREVIEW_BUTTONS)),

    ("Reading the maps",
     "<h2>Reading the maps</h2>" + _list([
         ("PSD", "Aggregate IMT power spectral density on the ground, in dBm/MHz."),
         ("I/N", "Interference-to-noise ratio of that PSD against the noise floor."),
         ("Power", "Strongest single-BS power at each point."),
         ("Satellite footprint", "Antenna gain on the ground. Contours are drawn at -3 dB (bold, the beam edge), "
          "-6, -10, -15 and -20 dB below the peak."),
         ("Link colour", "UE link colour is the nominal SNR, from -10 dB (blue) to 40 dB (red)."),
     ])),

    ("Protection contour",
     "<h2>Protection contour</h2>"
     "<p>The Protection Contour tab finds, around a protected station, the boundary beyond which the IMT "
     "interference stays under the protection criterion (ITU-R RA.769). It uses a reference IMT base station, "
     "terrain and the ITU-R P.452 propagation model, and searches along rays from the station.</p>"),

    ("Results",
     "<h2>Results</h2>"
     "<p><b>Analysis &amp; Results</b> reads the output folder of a run and plots the statistics. Publication "
     "figures can be exported from the File menu.</p>"),

    ("Projects",
     "<h2>Projects</h2>"
     "<p>A <b>.sharc</b> project file stores the whole configuration, so a study can be reopened or shared. "
     "Presets (<b>.json</b>) store the parameters of a single system, for example one IMT or one earth-station "
     "configuration, and can be mixed in a parameter sweep.</p>"),

    ("Keyboard shortcuts",
     "<h2>Keyboard shortcuts</h2>" + _list([
         ("Ctrl+R", "Run the simulation."),
         ("F1", "Open or close the Help panel."),
         ("W A S D, mouse drag, Esc", "Street view in the 3D preview: move, look around, leave."),
     ])),

    ("Troubleshooting",
     "<h2>Troubleshooting</h2>" + _list([
         ("Infinite loop while creating hotspots", "The hotspots do not fit in the cell. Reduce the maximum UE "
          "distance from the hotspot centre (the default is 70 m; 100 m with 3 hotspots per cell and a 500 m "
          "inter-site distance fails) or the number of hotspots per cell."),
         ("A sweep variable has no effect", "Check that list values are written with quotes (see Parameter sweep)."),
         ("The 3D view shows 'Loading map tiles'", "Tiles are streamed. Wait, or use an offline region."),
         ("The preview is blank or a render error shows in the status line", "Click Refresh preview and read "
          "Messages. A scene error names the parameter the engine rejected."),
         ("Ground maps differ from the simulation", "They are nominal (free space, no power control); use the "
          "simulation results for statistics."),
     ])),
]
