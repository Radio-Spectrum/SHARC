# GUI do SHARC: backlog e estado (atualizado em 2026-10-16)

Leia primeiro: `GUI_REDESIGN_PLAN.md` (plano), este arquivo (o que falta) e a memória `sharc-gui-redesign`.
Referências de design pedidas pelo usuário: Ansys (HFSS), Altair Feko, CST, COMSOL, Siemens (Simcenter/NX), QGIS, STK, Altium. No HFSS, cada nó da árvore abre só os seus parâmetros (não tudo numa aba).

## Feito
| Área | O que | Onde |
|---|---|---|
| Tema | Tema `graphite` (padrão), métricas profissionais, QSS gerado de tokens | `ui/theme/theme.py` |
| Casca | Docks: árvore Scenario, Properties/View, Messages/Jobs; abas centrais 3D Scene, Spectrum, Results; toolbar; status bar; layout salvo (`LAYOUT_VERSION`) | `ui/shell/workbench.py` |
| Parâmetros | Tabela de propriedades automática (nomes legíveis, unidade, seções recolhíveis); cada seção vira nó da árvore e mostra só ela | `ui/components/properties.py` |
| Preview | Cesium offline (Natural Earth II), atmosfera/sol/bloom, HUD, grade métrica, mapas-base (offline/online), relevo opcional via `CESIUM_ION_TOKEN` | `web/cesium_preview/{app.js,hud.js,hud.css,index.html}` |
| Fidelidade | Preview montado pelo motor (mesmo YAML, `Parameters`, `TopologyFactory`, `StationFactory`); erro de parâmetro vira "Scenario problem" | `core/engine_scene.py`, `core/cesium_bridge.py` |
| Run | Botão Run: gera YAML em `.sharc_gui/runs/<data>` e roda local; YAML oculto na GUI | `core/run_service.py`, `main.py` |
| Database | Aba Database (arquivo, delimiter, subsets, sites e antenas do banco, terreno real), bloco `database` no YAML, auto-centro do cenário, preview com os sites do banco (batem com as linhas do CSV) | `ui/tabs/database.py`, `core/yaml_builder.py`, `core/engine_scene.py` |
| Terrain streaming | Adaptive terrain/land-cover tiles served on demand (SRTM-based AWS Terrain Tiles; ESA WorldCover by windowed COG reads), disk cache, 3D relief, hillshade, land cover, lakes and rivers (Natural Earth), OSM buildings when close, ground heights for stations | `core/tile_service.py`, `core/hydro_service.py`, `core/buildings_service.py`, `web/cesium_preview/local_server.py`, `ui/tabs/terrain.py` |
| Site checks | Warning when a base station is on open water (background job; red markers + message) | `core/site_checks.py`, `ui/tabs/preview.py` |
| 3D models | Procedural glTF: satellite, base-station tower, earth-station dish (LOD: model near, icon far) | `core/model_factory.py`, `web/cesium_preview/app.js` |
| Job queue | Jobs panel: queue with order, parallel limit, scheduled start (Run later), pause, stop, reorder, right-click menu; Run uses the queue | `core/job_scheduler.py`, `ui/components/jobs_panel.py`, `core/run_service.py` |
| Splash | Start-up splash with self-checks (Qt modules, data libs, CesiumJS, cache, engine import, services, scene pipeline) and pre-loading; report goes to Messages; `SHARC_GUI_NO_SPLASH=1` skips | `ui/shell/splash.py`, `main.py` |
| Tray | Closing the window while jobs run hides SHARC in the system tray with a notification; tray menu (show, pause, stop all, quit), progress tooltip, finish notification | `ui/shell/tray.py` |
| Preferences | Settings menu (Preferences Ctrl+, / Theme / Font size / Resolution / Tray / Reset layout / Open cache) and a Preferences window (Appearance, Map & Terrain, Simulation, Notifications & Tray, Data & Cache, Advanced); map/terrain/parallel/theme/font persist | `ui/shell/preferences.py`, `main.py` |
| Map detail | Options for base map, map quality, relief resolution, max tile level, render resolution, building limit/distance/min height | `ui/tabs/terrain.py`, `web/cesium_preview/app.js` |
| Place scenario | Draggable centre marker, click-to-place tool, right-click menu (place here, copy coordinates, zoom), go-to box; refused when sites come from the database | `web/cesium_preview/app.js`, `ui/tabs/preview.py` |
| Antenas | Biblioteca com todos os padrões do motor (10 de 15 funcionam) | `core/antenna_service.py` (ainda sem UI) |
| Testes | Fumaça e fidelidade da GUI; tour de capturas | `tests/gui/`, `tools/screenshot_tour.py` (use `SHARC_GUI_NO_RESTORE=1`) |

## Requisitos do usuário ainda abertos (coletados em 2026-10-16)
- Tudo do simulador em inglês (regra permanente; ver memória `feedback-sharc-gui-english`). Ainda há strings/comentários em português em arquivos antigos e nos documentos `GUI_*.md`/`ai-reference`.
- Menus de contexto (botão direito) e janelas como HFSS/Feko/CST/QGIS/STK: já existe "Open in window" na árvore; faltam menus nas linhas de parâmetro (reset, copiar, ajuda), na vista 3D (zoom, medir, copiar coordenadas, definir centro) e em Jobs (parar, reiniciar, abrir resultados).
- Settings: FEITO o básico (ver tabela). Faltam atalhos de teclado customizáveis, unidades (m/ft, dBm/dBW), idioma fixo em inglês, e mais opções de simulação (pastas de saída padrão, snapshots padrão).
- Agendador de simulações: FEITO o básico (fila, ordem, limite, início agendado, pausa, menu). Falta: persistir a fila entre sessões, agendar no modo SSH, repetir/duplicar jobs, notificação ao terminar.
- Parâmetros do motor ainda sem opção na interface: criar `tools/param_coverage.py` que compara as classes `sharc/parameters` com o que `core/yaml_builder.py` emite e lista o que falta.
- Preview: opções para mostrar ganho da antena e PSD (camadas); plot do mapa de ganho da simulação; elementos 3D; plots com linhas finas; topologias revisadas (INDOOR, NTN, Macro_countries, MSS_DC com dados do motor).
- Gerador de YAML validado: 70 combinações sistema x topologia x link aceitas pelo motor e varredura de parâmetros (`tests/gui/test_yaml_generator.py`).

## Pendente (por prioridade)
1. **Parâmetros (polimento)**: coluna de unidade cortada e rolagem horizontal no dock Properties; grupo aninhado "Topology – MACROCELL" aparece vazio; abrir um nó em janela flutuante (como HFSS); Properties em tabela para Database. Revisar `restructure_page` nas abas SSH/Runner.
2. **Banco de dados (database)**: FEITO o básico (ver tabela acima). Falta: escolher o subset no preview, desenhar a antena/downtilt de cada BS do banco, botão de baixar terreno/clutter, exportar/importar preset do banco, teste com a base real `db_teste_30bs.csv` (não versionada). Contexto original: O motor já tem `parameters/database/parameters_database.py` (`select_subset`, `subset_for_snapshot`, `num_subsets`, `from_db_topology_countries`, `use_real_terrain`, bloco `terrain`) e `Results.system_database_subset`, `PostProcessor.aggregate_over_subsets`. Falta: nó "Database" na árvore (arquivo, subsets, filtros), geração desse bloco no `core/yaml_builder.py`, preview das BSs do banco, e estado em `core/state.py`. Caso de teste: `sharc/campaigns/IMT_TO_SES_Database/`.
3. **Mapa de ganho de antena**: hoje o ganho do preview usa uma antena montada só com o nome do padrão (sem os parâmetros do usuário) e engole erros, caindo em parábola. Corrigir `core/geometry_3d.py::_get_global_positions` para usar a antena do motor a partir do YAML; criar aba/painel "Antenna" com todos os padrões (`core/antenna_service.py`): cortes de ganho e mapa no globo. Falhas conhecidas: S.1528-Taylor e S.1855 exigem `theta_vec`; "MODIFIED ITU-R S.465" usa a classe errada na fábrica do motor (`AntennaS465` em vez de `AntennaModifiedS465`); RR Ap.7 Anexo 3 só vale para certos D/λ; HibleoX só perto de 2450 MHz. A Victim tab só oferece 4 padrões; o motor tem ~17.
4. **Terreno e obstáculos**: FEITO o streaming adaptativo (ver tabela). Falta: usar o terreno nos perfis P.452 do motor (`profile_raster`), mapa de clutter por BS no YAML, prédios com fonte alternativa (Overture/Microsoft) quando o Overpass estiver lento, escolher fonte de DEM (Copernicus GLO-30). Contexto original:: o motor já baixa DEM SRTM (AWS Skadi) e uso do solo ESA WorldCover e monta malha adaptativa (`propagation/real_terrain/{download_terrain,download_clutter,adaptive_mesh,terrain_reader}.py`, parâmetros em `parameters_p452.py` e `database`). Falta a GUI: nó "Terrain & Clutter" (região por bbox/país, resolução, botão baixar em segundo plano, progresso em Jobs, preenchimento automático dos parâmetros P.452/database) e mostrar no preview (heightmap local no Cesium + camada colorida de uso do solo; prédios via OSM/Overpass opcional). Precisa de internet e de `pip install requests tqdm` (faltam no ambiente).
5. **Preview**: mostrar IMT e sistema vítima juntos (corrigir `_resolve_preview_type` em `ui/tabs/preview.py`); elementos 3D (modelos de satélite/torre/antena, lóbulos de ganho, mastros); refazer os plots do preview com linhas finas (Spectrum / Link Budget em `ui/tabs/assets/preview_tab/spectrum_widget.py`); UEs e sistemas globais com dados do motor (hoje só macro/hotspot/single BS usam o motor).
6. **Run/Execution**: scenario validation before Run (use `build_engine_scene`). FIXED 2026-10-17: negative ETA, host "remote" in local mode, HUD Update NoneType.
7. **Engine/GUI bugs**: HOTSPOT with NumPy 2.5.1 FIXED (`topology_hotspot.py`); NTN default UMa channel invalid (only FSPL/P619); SINGLE_BS needs `azimuth` with `num_clusters` items. Still open: station presets not saving new antenna fields.
8. **Fases do plano** ainda abertas: F3 (propriedades com ajuda e validação inline), F4 (painel de problemas), F6 (jobs/resultados), F7 (acabamento: ícones, atalhos, tema claro).

## Como retomar
- `python sharc/gui/tools/screenshot_tour.py <pasta>` e olhe as imagens; `pytest tests/gui -q`.
- Grafo: `python -m graphify update sharc` (depois copiar para `graphify-out/`); índice: `INDEX_OUT=ai-reference/index/sharc_database python ai-reference/tools/build_index.py`.
- Gemini ajudante: skill `agy-delegate`; nunca use aspas duplas dentro do prompt no Windows.


See also `GUI_REQUESTS_MAP.md`: every user request with its status.
