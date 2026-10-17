# GUI requests map

Every request the user made for the SHARC GUI, grouped by theme, with status and where it lives.
Status: DONE (implemented and tested), PARTIAL, TODO. Keep this file current; `GUI_BACKLOG.md` has the
technical detail and the resume instructions.

## Standing rules (always apply)
- Review and validate everything, always (`python sharc/gui/tools/validate_gui.py`, `pytest tests/gui`).
- Register everything: memory, `GUI_BACKLOG.md`, this map, `ai-reference/`, graphify graph.
- All simulator text in English. Chat with the user in Portuguese.
- Use skills, plugins and Gemini (agy-delegate, argon model) for complex or bulk tasks to save tokens.
- Free to change modules, frameworks or engines; use the best available. Quality bar: Ansys HFSS, Altair Feko,
  CST, COMSOL, Siemens, QGIS, STK, Altium. "Professional simulator", not just colours.
- Work branch: `sharc_database` (= `feat/macro_database` + GUI).

## 0. Project mapping and registration (first requests)
| Request | Status | Where |
|---|---|---|
| Read the SHARC reference/map; graph in graphify structure and well documented | DONE | `ai-reference/`, `graphify-out/` |
| Save tokens: map once, never re-map (strong reference, avoid errors) | DONE | `CLAUDE.md` read order: ai-reference, graphify, AST index |
| Work on `feat/macro_database` (now branch `sharc_database` with the GUI merged) | DONE | `ai-reference/index/sharc_database/` |
| Register in memory; update work map and graph after changes | DONE (repeat after every change) | memory dir, `CLAUDE.md`, `GUI_BACKLOG.md`, this map |

## 1. Look and structure (professional simulator)
| Request | Status | Where |
|---|---|---|
| Professional look, not "cheap app" | DONE | `ui/theme/theme.py` (graphite theme, QSS tokens) |
| HFSS-style workbench: tree, docks, windows | DONE | `ui/shell/workbench.py` |
| Parameters NOT in a single tab; each tree node opens its own parameters | DONE | `ui/tabs/*`, `ui/components/properties.py`, `SectionWindow` |
| Right-click menus and windows like HFSS/Feko/CST/QGIS | PARTIAL | done: tree, Jobs, 3D view; TODO: parameter rows (reset/copy/help), distance-measure tool |
| Organised parameter layout (sections, groups) | DONE | `properties.py` (`restructure_page`) |
| Expanded toolbar, Settings, customisable options | PARTIAL | Preferences + Settings menu done; TODO: shortcuts, units, defaults |
| Fancy visual interface that sells | DONE | graphite theme, HUD, legend, models |
| Splash screen, start-up checks and pre-loading | DONE | `ui/shell/splash.py` |
| Run tests on every start | PARTIAL | install/engine self-checks run on start; the full pytest suite does not (about 1 min). Option: a background self-test mode |
| Pre-acceleration (warm caches) | PARTIAL | modules pre-loaded; TODO warm the tile cache of the last scenario location |

## 2. YAML and running
| Request | Status | Where |
|---|---|---|
| YAML is a background process; user only presses Run | DONE | `core/run_service.py`, `core/yaml_builder.py` |
| Test the YAML generator 100% | DONE | `tests/gui/test_yaml_generator.py` (70 combinations) |
| Validate the multi-combination parameter distributor (sweep) | DONE | `test_parameter_sweep_generates_cartesian_product` |
| Parameters the engine has but the GUI does not expose | TODO | create `tools/param_coverage.py` |
| Job queue / schedule of running simulations | DONE | `core/job_scheduler.py`, `ui/components/jobs_panel.py` |
| Run in background when closing; tray icon; warn it keeps running | DONE (user did not see the notice: added an always-visible corner notice besides the system toast; re-verify on the real desktop) | `ui/shell/tray.py` (system toast + always-visible corner notice) |
| Validation panel before Run | TODO | backlog F3/F4 |

## 3. Preview (3D scene)
| Request | Status | Where |
|---|---|---|
| Cesium 3D preview inside the GUI (was "CesiumJS not available", not drawing) | DONE | `web/cesium_preview/`, `core/cesium_bridge.py` |
| Preview must reflect what the simulator really does | DONE | `core/engine_scene.py`, `tests/gui/test_preview_fidelity.py` |
| Fix macrocell rendering; review all topologies | DONE (MACROCELL, HOTSPOT, SINGLE_BS); TODO INDOOR, NTN, MSS_DC | `engine_scene.py` |
| Antenna gain map for many antenna types | DONE | `core/antenna_service.py` (15 patterns) |
| Gain-map plot of the simulation, PSD and antenna gain as options | TODO | backlog |
| Gain map bug seen in screenshot (map and buildings glitchy) | DONE | fixed earlier; re-check on each visual validation |
| Confirm clutter/relief are real data | DONE | answered: NASA SRTM, ESA WorldCover, OSM, Natural Earth; not synthesised |
| Thin plot lines (Spectrum / Link Budget) | TODO | backlog |
| 3D models of antenna, satellite, tower | DONE | `core/model_factory.py` |
| Impressive realistic look | DONE | `web/cesium_preview/app.js` |
| Download terrain and obstacles and place them in the scenario | DONE | `core/terrain_service.py` (offline region), `tile_service.py` (streaming) |
| Real terrain relief | DONE | AWS Terrain Tiles (NASA SRTM) via `core/tile_service.py` |
| Clutter on the map | DONE | ESA WorldCover 10 m |
| Buildings with clutter | DONE | OpenStreetMap via Overpass (`core/buildings_service.py`) |
| Lakes and rivers | DONE | Natural Earth (`core/hydro_service.py`) |
| Adaptive tiles (not downloading the world), reliable sources | DONE | `tile_service.py`, `MIN_CLUTTER_ZOOM=9` |
| Warning if a base station is on water | DONE | `core/site_checks.py` |
| Options to change map/tile/relief resolution and number of buildings | DONE | `ui/tabs/terrain.py`, Preferences |
| Place the scenario on the map | DONE | `app.js` place tools, `ui/tabs/preview.py` |
| See Brasilia in 3D in the scenario | DONE | verified by screenshot: relief, clutter, lake, OSM buildings (Asa Norte blocks). Needs `rasterio requests tqdm` in the Python that runs the GUI (the repo `.venv` lacked them: installed; start-up now shows a warning with the exact pip command). Buildings render only within ~3.5 km camera height and ~500 m around the view centre |
| Progress bar and loading indicator while loading scene/tiles | DONE | `Loading` in `app.js`, `hud.css` |
| Trees (OSM `natural=tree` + vegetation-based, deterministic) | DONE | `core/buildings_service.py`, `app.js` `setTrees`, Terrain tab |
| Street-view style 3D (eye-level camera, sky, fog, WASD) | DONE (procedural; blurry satellite at eye level) | `app.js` `enterStreet`, button in the 3D toolbar |
| Realistic look (satellite imagery, white extruded buildings) | DONE | Terrain tab "Scene look" |
| City-scale buildings (Philadelphia-style) and photogrammetry (Melbourne-style) | PARTIAL: implemented through a free Cesium ion token (Cesium OSM Buildings, Google Photorealistic via ion asset 2275207) or a Google key, NOT tested without a token. Our own streamed OSM extrusions work everywhere but are limited to ~500 m around the view centre |
| (details) all buildings in 3D | PARTIAL | open data (OSM/Overture) has only ~40-190 footprints per 600 m tile in Brasilia; fix = Google Photorealistic 3D Tiles (field "API key" in Terrain tab, implemented, NOT tested without a key) |
| Beauty captures (3D buildings on satellite, trees, simulation overlay) | DONE | `screenshots/beauty/` (Rio, Copacabana, Fortaleza; Sao Paulo still has few buildings and terrain waves) |
| Bare-earth terrain in cities (DSM waves) and ocean at sea level | DONE (server side, `tile_service._bare_earth`) | `core/tile_service.py` |
| Downloaded terrain in P.452 profiles | TODO | backlog |

## 4. Database
| Request | Status | Where |
|---|---|---|
| GUI must accept the base-station database | DONE | `ui/tabs/database.py` |
| GUI must accept real-terrain data | DONE | `ui/tabs/terrain.py`, `core/terrain_service.py` |
| Subset selection in preview, per-BS antenna/downtilt, test with real `db_teste_30bs.csv` | TODO | backlog |

## 5. Known bugs
| Bug | Status |
|---|---|
| Negative ETA | FIXED (clamped) in `managers/ssh_runner.py` |
| Host "remote" shown in local mode | FIXED (`localhost`) in `ui/tabs/runner.py` |
| "HUD Update Error: NoneType" | FIXED (None-safe parsing) in `main.py` |
| HOTSPOT broken by NumPy 2.5 | FIXED in `sharc/topology/topology_hotspot.py` |
| Blank area around the scenario (tiles that failed once stayed blank) | FIXED, re-verify visually |
| Station presets not saving the new antenna fields | TODO |

## How to resume
1. Read `CLAUDE.md`, `GUI_BACKLOG.md` and this map.
2. `pytest tests/gui` with `SHARC_GUI_NO_RESTORE=1`, then `python sharc/gui/tools/validate_gui.py`.
3. After changes: rebuild the AST index and the graphify graph (commands in `CLAUDE.md`).
