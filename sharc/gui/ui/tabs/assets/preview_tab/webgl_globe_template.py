HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SHARC 3D WebGL Visualizer</title>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        #chart { width: 100vw; height: 100vh; }
        .glass-panel {
            position: absolute;
            top: 20px;
            right: 20px;
            width: 320px;
            background: rgba(22, 27, 34, 0.75);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            z-index: 10;
        }
        .glass-panel h2 { margin-top: 0; margin-bottom: 15px; font-size: 1.2rem; color: #58a6ff; font-weight: 600; }
        .glass-panel .row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.9rem; }
        .glass-panel .label { color: #8b949e; }
        .glass-panel .value { font-weight: bold; color: #e6edf3; }
        .controls { margin-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 15px; }
        .toggle-btn {
            background: rgba(33, 38, 45, 0.8);
            border: 1px solid rgba(240, 246, 252, 0.1);
            color: #c9d1d9;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            width: 100%;
            margin-bottom: 10px;
            transition: all 0.2s;
            font-size: 0.85rem;
        }
        .toggle-btn:hover { background: rgba(48, 54, 61, 0.8); }
        .toggle-btn.active { background: rgba(31, 111, 235, 0.3); border-color: rgba(31, 111, 235, 0.5); color: #58a6ff; }
    </style>
    <script src="https://unpkg.com/three@0.136.0/build/three.min.js"></script>
    <script src="https://unpkg.com/three@0.136.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://unpkg.com/globe.gl"></script>
</head>
<body>
    <div id="chart"></div>
    <div class="glass-panel">
        <h2>SHARC Visualizer</h2>
        <div id="info-content"></div>
        <div class="controls" id="controls">
            <!-- Toggles injected here -->
        </div>
    </div>

    <script>
        // Scenario data injected by Python
        const scenarioData = __SCENARIO_DATA_PLACEHOLDER__;

        const infoContent = document.getElementById('info-content');
        const controlsDiv = document.getElementById('controls');

        function addRow(label, value) {
            infoContent.innerHTML += `<div class="row"><span class="label">${label}</span><span class="value">${value}</span></div>`;
        }
        
        addRow("Topology", scenarioData.topo_type);
        if (scenarioData.sys_type) addRow("System", scenarioData.sys_type);
        if (scenarioData.system_info && scenarioData.system_info.frequency) addRow("Frequency", scenarioData.system_info.frequency + " MHz");
        if (scenarioData.local_geometry && scenarioData.local_geometry.bs_height) addRow("BS Height", scenarioData.local_geometry.bs_height + " m");

        // UI States
        const uiState = {
            showBorders: true,
            showFootprint: true,
            showUes: true,
            showSectors: true,
            autoRotate: false
        };

        function createToggle(label, key, callback) {
            const btn = document.createElement('button');
            btn.className = 'toggle-btn' + (uiState[key] ? ' active' : '');
            btn.innerText = (uiState[key] ? 'Disable ' : 'Enable ') + label;
            btn.onclick = () => {
                uiState[key] = !uiState[key];
                btn.className = 'toggle-btn' + (uiState[key] ? ' active' : '');
                btn.innerText = (uiState[key] ? 'Disable ' : 'Enable ') + label;
                callback();
            };
            controlsDiv.appendChild(btn);
        }

        const chartDiv = document.getElementById('chart');

        if (scenarioData.is_global) {
            // ==========================================
            // GLOBAL GLOBE VIEW
            // ==========================================
            const globe = Globe()
                (chartDiv)
                .globeImageUrl('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
                .bumpImageUrl('https://unpkg.com/three-globe/example/img/earth-topology.png')
                .backgroundImageUrl('https://unpkg.com/three-globe/example/img/night-sky.png')
                .pointOfView({ altitude: 3.5 });

            // Borders logic
            let bordersData = [];
            fetch('https://unpkg.com/three-globe/example/dataset/ne_110m_admin_0_countries.geojson')
                .then(res => res.json())
                .then(countries => {
                    bordersData = countries.features;
                    updateBorders();
                });
            
            const selectedCountries = (scenarioData.countries || []).map(c => c.toLowerCase().trim());
            
            function updateBorders() {
                if (!uiState.showBorders) {
                    globe.polygonsData([]);
                } else {
                    globe.polygonsData(bordersData)
                        .polygonAltitude(0.005)
                        .polygonCapColor(d => {
                            const name = (d.properties.ADMIN || d.properties.NAME || "").toLowerCase().trim();
                            return selectedCountries.includes(name) ? 'rgba(0, 255, 0, 0.4)' : 'rgba(255, 255, 255, 0.0)';
                        })
                        .polygonSideColor(() => 'rgba(0, 255, 0, 0.1)')
                        .polygonStrokeColor(() => 'rgba(255, 255, 255, 0.3)');
                }
            }

            // Satellite & Earth Station Points
            const points = [];
            if (scenarioData.satellite && scenarioData.satellite.alt > 0) {
                points.push({
                    lat: scenarioData.satellite.lat,
                    lng: scenarioData.satellite.lon,
                    alt: scenarioData.satellite.alt / 6378137.0, // relative to earth radius
                    size: 1.5,
                    color: '#ff5252',
                    label: 'Satellite'
                });
            }
            if (scenarioData.earth_station && scenarioData.earth_station.lat !== null) {
                points.push({
                    lat: scenarioData.earth_station.lat,
                    lng: scenarioData.earth_station.lon,
                    alt: (scenarioData.earth_station.alt || 0) / 6378137.0,
                    size: 1.0,
                    color: '#4fc3f7',
                    label: 'Earth Station'
                });
            }
            // Country Base Stations
            (scenarioData.base_stations || []).forEach(bs => {
                if (bs.lat !== undefined && bs.lon !== undefined) {
                    points.push({
                        lat: bs.lat,
                        lng: bs.lon,
                        alt: 0.002,
                        size: 0.1,
                        color: '#4fc3f7',
                        label: 'Base Station'
                    });
                }
            });

            globe.pointsData(points)
                .pointAltitude('alt')
                .pointColor('color')
                .pointRadius('size')
                .pointLabel('label');

            // Link Arcs
            const arcs = [];
            if (scenarioData.satellite && scenarioData.satellite.alt > 0 && scenarioData.earth_station && scenarioData.earth_station.lat !== null) {
                arcs.push({
                    startLat: scenarioData.satellite.lat,
                    startLng: scenarioData.satellite.lon,
                    startAlt: scenarioData.satellite.alt / 6378137.0,
                    endLat: scenarioData.earth_station.lat,
                    endLng: scenarioData.earth_station.lon,
                    endAlt: (scenarioData.earth_station.alt || 0) / 6378137.0,
                    color: '#ffab40'
                });
            }
            globe.arcsData(arcs)
                .arcStartLat('startLat')
                .arcStartLng('startLng')
                .arcEndLat('endLat')
                .arcEndLng('endLng')
                .arcColor('color')
                .arcAltitudeAutoScale(0.2)
                .arcDashLength(0.5)
                .arcDashGap(1)
                .arcDashInitialGap(() => Math.random())
                .arcDashAnimateTime(2000);
            
            // Custom rings for footprint
            function updateFootprint() {
                if (uiState.showFootprint && scenarioData.satellite && scenarioData.satellite.alt > 0 && scenarioData.earth_station && scenarioData.earth_station.lat !== null) {
                    globe.ringsData([{
                        lat: scenarioData.earth_station.lat,
                        lng: scenarioData.earth_station.lon,
                        maxR: (scenarioData.satellite.beamwidth || 4.5) * 5,
                        propagationSpeed: 0,
                        repeatPeriod: 0
                    }])
                    .ringColor(() => 'rgba(255, 0, 255, 0.5)')
                    .ringMaxRadius('maxR')
                    .ringPropagationSpeed(1)
                    .ringRepeatPeriod(700);
                } else {
                    globe.ringsData([]);
                }
            }
            updateFootprint();

            createToggle('Country Borders', 'showBorders', updateBorders);
            createToggle('Satellite Footprint', 'showFootprint', updateFootprint);
            createToggle('Auto-Rotate', 'autoRotate', () => {
                globe.controls().autoRotate = uiState.autoRotate;
            });
            
            globe.controls().autoRotateSpeed = 1.0;

        } else {
            // ==========================================
            // LOCAL FLAT 3D VIEW
            // ==========================================
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0d1117);
            const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 500000);
            const renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            chartDiv.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            
            // Grid Helper
            const gridHelper = new THREE.GridHelper(10000, 100, 0x30363d, 0x21262d);
            scene.add(gridHelper);

            // Lighting
            scene.add(new THREE.AmbientLight(0xffffff, 0.4));
            const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
            dirLight.position.set(5000, 10000, 5000);
            scene.add(dirLight);

            const bsGroup = new THREE.Group();
            scene.add(bsGroup);
            const ueGroup = new THREE.Group();
            scene.add(ueGroup);
            const hexGroup = new THREE.Group();
            scene.add(hexGroup);

            // Add BS
            const bsMat = new THREE.MeshPhongMaterial({ color: 0x4fc3f7 });
            const bsGeom = new THREE.CylinderGeometry(2, 2, scenarioData.local_geometry.bs_height || 30, 8);
            
            (scenarioData.base_stations || []).forEach(bs => {
                const h = scenarioData.local_geometry.bs_height || 30;
                const mesh = new THREE.Mesh(bsGeom, bsMat);
                mesh.position.set(bs.x, h/2, -bs.y); // Threejs z is -y in our coords
                bsGroup.add(mesh);
                
                // Add simple sphere top
                const topGeom = new THREE.SphereGeometry(6, 8, 8);
                const top = new THREE.Mesh(topGeom, bsMat);
                top.position.set(bs.x, h, -bs.y);
                bsGroup.add(top);
            });

            // Add UEs
            const ueMat = new THREE.MeshBasicMaterial({ color: 0xff6b6b });
            const ueGeom = new THREE.SphereGeometry(2, 8, 8);
            (scenarioData.user_equipments || []).forEach(ue => {
                const mesh = new THREE.Mesh(ueGeom, ueMat);
                mesh.position.set(ue.x, scenarioData.local_geometry.ue_height || 1.5, -ue.y);
                ueGroup.add(mesh);
            });

            // Add Hexagons
            if (scenarioData.local_geometry.draw_hex && scenarioData.local_geometry.hex_centers) {
                const hexMat = new THREE.LineBasicMaterial({ color: 0x4a5a8a, transparent: true, opacity: 0.5 });
                const r = scenarioData.local_geometry.hex_radius;
                scenarioData.local_geometry.hex_centers.forEach(center => {
                    const points = [];
                    for(let i=0; i<=6; i++) {
                        const angle = i * Math.PI / 3 + Math.PI/6;
                        points.push(new THREE.Vector3(center[0] + r*Math.cos(angle), 0, -(center[1] + r*Math.sin(angle))));
                    }
                    const geom = new THREE.BufferGeometry().setFromPoints(points);
                    const line = new THREE.Line(geom, hexMat);
                    hexGroup.add(line);
                });
            }

            // Adjust Camera
            let maxSpan = 2000;
            if (scenarioData.base_stations && scenarioData.base_stations.length > 0) {
                let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
                scenarioData.base_stations.forEach(bs => {
                    if (bs.x < minX) minX = bs.x;
                    if (bs.x > maxX) maxX = bs.x;
                    if (bs.y < minY) minY = bs.y;
                    if (bs.y > maxY) maxY = bs.y;
                });
                maxSpan = Math.max(maxX - minX, maxY - minY, 500);
                controls.target.set((minX+maxX)/2, 0, -(minY+maxY)/2);
            }
            camera.position.set(controls.target.x, maxSpan, controls.target.z + maxSpan * 0.8);
            controls.update();

            // Toggles
            createToggle('Grid / Cells', 'showSectors', () => { hexGroup.visible = uiState.showSectors; gridHelper.visible = uiState.showSectors; });
            createToggle('UEs', 'showUes', () => { ueGroup.visible = uiState.showUes; });

            function animate() {
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }
            animate();

            window.addEventListener('resize', () => {
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            });
        }
    </script>
</body>
</html>
"""
