/**
 * script.js — Frontend de la Simulación de Active Inference
 * 
 * Responsabilidades:
 * - Renderizado del canvas (mundo real y creencias)
 * - Conexión WebSocket con el backend
 * - Animación del vehículo (movimiento fluido)
 * - Controles de velocidad, edición, mapas
 * - Actualización de paneles de UI en tiempo real
 */

// ============================================================
// ESTADO GLOBAL
// ============================================================
let ws = null;
let state = null;
let currentView = 'real';   // 'real', 'beliefs', 'both'
let currentTool = 'none';
let isRunning = false;
let isPaused = true;
let currentMapId = 1;
let speedMode = 'normal';

// Evita que el modal de llegada se abra en bucle
let arrivalModalShown = false;

// Animación del vehículo
let animCarX = 0, animCarY = 0;
let targetCarX = 0, targetCarY = 0;
const ANIM_SPEED = 0.15;

// Canvas
const canvas = document.getElementById('simulationCanvas');
const ctx = canvas.getContext('2d');
let cellSize = 42;
let canvasRows = 10, canvasCols = 12;
let animFrameId = null;

// Escenarios cargados
let scenarios = {};

// ============================================================
// CONEXIÓN WEBSOCKET
// ============================================================
function connectWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => { console.log('WS connected'); };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.real_world) {
            state = data;
            if (data.scenarios) scenarios = data.scenarios;
            updateUI(data);
        }
    };

    ws.onclose = () => { setTimeout(connectWS, 2000); };
    ws.onerror = () => { ws.close(); };
}

function sendWS(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
    }
}

// ============================================================
// INICIALIZACIÓN
// ============================================================
window.addEventListener('DOMContentLoaded', () => {
    connectWS();
    loadScenarios();
    canvas.addEventListener('click', onCanvasClick);
    canvas.addEventListener('mousemove', onCanvasHover);
    requestAnimationFrame(renderLoop);
});

async function loadScenarios() {
    try {
        const res = await fetch('/api/scenarios');
        scenarios = await res.json();
        renderMapList();
    } catch (e) { console.error('Failed to load scenarios', e); }
}

async function loadInitialState() {
    try {
        const res = await fetch('/api/state');
        state = await res.json();
        if (state.scenarios) scenarios = state.scenarios;
        updateUI(state);
        renderMapList();
    } catch (e) { console.error('Failed to load state', e); }
}

// ============================================================
// CONTROLES DE SIMULACIÓN
// ============================================================
function toggleSimulation() {
    if (!isRunning) {
        isRunning = true; isPaused = false;
        sendWS({ command: 'start' });
        document.getElementById('btnStartPause').innerHTML = '⏸ Pausar';
    } else if (!isPaused) {
        isPaused = true;
        sendWS({ command: 'pause' });
        document.getElementById('btnStartPause').innerHTML = '▶ Reanudar';
    } else {
        isPaused = false;
        sendWS({ command: 'resume' });
        document.getElementById('btnStartPause').innerHTML = '⏸ Pausar';
    }
    updateStatusDot();
}

function executeStep() {
    sendWS({ command: 'step' });
}

function resetSimulation() {
    isRunning = false;
    isPaused = true;
    arrivalModalShown = false;

    animCarX = 0;
    animCarY = 0;
    targetCarX = 0;
    targetCarY = 0;

    const modal = document.getElementById('arrivalModal');
    if (modal) {
        modal.classList.remove('show');
    }

    sendWS({ command: 'reset' });
    document.getElementById('btnStartPause').innerHTML = '▶ Iniciar';
    updateStatusDot();
}

function setSpeed(speed) {
    speedMode = speed;
    sendWS({ command: 'speed', speed });
    document.querySelectorAll('#speedButtons .btn').forEach(b => {
        b.classList.toggle('active', b.dataset.speed === speed);
    });
    const ms = { slow: 5000, normal: 3000, fast: 1000, turbo: 500 }[speed] || 3000;
    document.getElementById('speedInfo').textContent = `Intervalo: ${ms}ms`;
}

function setView(view) {
    currentView = view;
    document.getElementById('viewReal').classList.toggle('active', view === 'real');
    document.getElementById('viewBeliefs').classList.toggle('active', view === 'beliefs');
    document.getElementById('viewBoth').classList.toggle('active', view === 'both');
}

function setTool(tool) {
    currentTool = tool;
    document.querySelectorAll('#editTools .btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tool === tool);
    });
}

function changeMap(mapId) {
    currentMapId = mapId;
    isRunning = false;
    isPaused = true;
    arrivalModalShown = false;

    animCarX = 0;
    animCarY = 0;
    targetCarX = 0;
    targetCarY = 0;

    const modal = document.getElementById('arrivalModal');
    if (modal) {
        modal.classList.remove('show');
    }

    sendWS({ command: 'map', map_id: mapId });
    document.getElementById('btnStartPause').innerHTML = '▶ Iniciar';
    renderMapList();
    updateStatusDot();
}

function randomMap() {
    isRunning = false;
    isPaused = true;
    arrivalModalShown = false;

    animCarX = 0;
    animCarY = 0;
    targetCarX = 0;
    targetCarY = 0;

    const modal = document.getElementById('arrivalModal');
    if (modal) {
        modal.classList.remove('show');
    }

    sendWS({ command: 'random_map' });
    document.getElementById('btnStartPause').innerHTML = '▶ Iniciar';
    currentMapId = 5;
    renderMapList();
    updateStatusDot();
}

function closeArrival() {
    document.getElementById('arrivalModal').classList.remove('show');
}

// ============================================================
// RENDER MAP LIST
// ============================================================
function renderMapList() {
    const container = document.getElementById('mapList');
    container.innerHTML = '';
    for (const [id, info] of Object.entries(scenarios)) {
        const div = document.createElement('div');
        div.className = `map-item${parseInt(id) === currentMapId ? ' active' : ''}`;
        div.innerHTML = `<div class="map-name">${info.name}</div><div class="map-diff">${info.difficulty}</div>`;
        div.onclick = () => changeMap(parseInt(id));
        container.appendChild(div);
    }
}

// ============================================================
// CANVAS CLICK — Edición / selección
// ============================================================
function onCanvasClick(e) {
    if (!state) return;
    const rect = canvas.getBoundingClientRect();
    const offsetX = (currentView === 'both') ? 0 : 0;
    const x = e.clientX - rect.left - offsetX;
    const y = e.clientY - rect.top;
    const col = Math.floor(x / cellSize);
    const row = Math.floor(y / cellSize);

    if (row < 0 || col < 0) return;

    const toolMap = { free: 0, blocked: 1, traffic: 2, semaphore: 3, accident: 4, rain: 5, erase: 0 };

    if (currentTool === 'set_start') {
        sendWS({ command: 'set_start', row, col });
    } else if (currentTool === 'set_destination') {
        sendWS({ command: 'set_destination', row, col });
    } else if (currentTool !== 'none' && toolMap[currentTool] !== undefined) {
        sendWS({ command: 'edit_cell', row, col, cell_type: toolMap[currentTool] });
    }
}

function onCanvasHover(e) {
    if (!state) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const col = Math.floor(x / cellSize);
    const row = Math.floor(y / cellSize);
    const tooltip = document.getElementById('tooltip');
    if (row >= 0 && row < canvasRows && col >= 0 && col < canvasCols && state.real_world) {
        const cellVal = state.real_world[row]?.[col];
        const names = { 0: 'Libre', 1: 'Bloqueado', 2: 'Tráfico', 3: 'Semáforo', 4: 'Accidente', 5: 'Lluvia' };
        tooltip.style.display = 'block';
        tooltip.style.left = (e.clientX + 12) + 'px';
        tooltip.style.top = (e.clientY + 12) + 'px';
        tooltip.textContent = `(${row},${col}) — ${names[cellVal] || 'Desconocido'}`;
    } else {
        tooltip.style.display = 'none';
    }
}

function getAgentPosition(data) {
    return data.agent_position || data.position || null;
}

// ============================================================
// UPDATE UI — Actualizar todos los paneles
// ============================================================

function updateUI(data) {
    if (!data || !data.real_world) return;

    canvasRows = data.real_world.length;
    canvasCols = data.real_world[0]?.length || 1;
    currentMapId = data.map_id || currentMapId;

    // Resize canvas
    resizeCanvas();

    // Actualizar posición objetivo para animación
    const agentPos = getAgentPosition(data);

    if (agentPos) {
        targetCarX = agentPos[1] * cellSize + cellSize / 2;
        targetCarY = agentPos[0] * cellSize + cellSize / 2;

        // Si es la primera vez, colocar el carro exactamente en su posición real
        if (animCarX === 0 && animCarY === 0) {
            animCarX = targetCarX;
            animCarY = targetCarY;
        }
    }

    // Header
    document.getElementById('cycleCount').textContent = `Ciclo: ${data.cycle || 0}`;
    document.getElementById('timeDisplay').textContent = `${data.total_time || 0}s`;
    isPaused = data.is_paused !== undefined ? data.is_paused : isPaused;
    updateStatusDot();

    // Status text
    const statusMap = {
        MOVING: '🚗 Moviéndose', SEARCHING: '🔍 Buscando ruta', WAITING: '⏳ Esperando',
        ANALYZING: '🔬 Analizando', RECALCULATING: '🔄 Recalculando', EXPLORING: '🧭 Explorando',
        STOPPED: '⛔ Detenido', ARRIVED: '🏁 Llegó'
    };
    document.getElementById('statusText').textContent = statusMap[data.agent_state] || data.agent_state;

    // Mode badge
    const modeBadge = document.getElementById('modeBadge');
    modeBadge.className = `overlay-badge ${data.mode === 'PRAGMATIC' ? 'pragmatic' : 'epistemic'}`;
    document.getElementById('modeIcon').textContent = data.mode === 'PRAGMATIC' ? '➡️' : '🔍';
    document.getElementById('modeText').textContent = data.mode;

    // State badge
    document.getElementById('stateIcon').textContent = statusMap[data.agent_state]?.charAt(0) || '⏳';
    document.getElementById('stateText').textContent = data.agent_state;

    // Agent info
    const dirArrows = { up: '↑', down: '↓', left: '←', right: '→' };
    document.getElementById('agentPos').textContent = agentPos? `(${agentPos[0]}, ${agentPos[1]})`: '(?, ?)';
    document.getElementById('agentDir').textContent = dirArrows[data.direction] || '→';
    document.getElementById('agentDest').textContent = `(${data.destination?.[0]}, ${data.destination?.[1]})`;

    // State badge class
    const badge = document.getElementById('agentStateBadge');
    badge.className = `state-badge state-${data.agent_state}`;
    badge.textContent = `${statusMap[data.agent_state] || data.agent_state}`;

    // Radar
    updateRadar(data.observations || {});

    // Homeostasis
    if (data.homeostasis) {
        const h = data.homeostasis;
        setMetric('Safety', h.safety); setMetric('Energy', h.energy);
        setMetric('Uncertainty', h.uncertainty); setMetric('Progress', h.progress);
        setMetric('Risk', h.risk_level);
    }

    // Metrics
    if (data.metrics) {
        const m = data.metrics;
        document.getElementById('metSteps').textContent = m.steps_taken;
        document.getElementById('metBlocks').textContent = m.blocks_detected;
        document.getElementById('metRecalc').textContent = m.recalculations;
        document.getElementById('metDiscovered').textContent = m.map_discovered_pct + '%';
        document.getElementById('metPragmatic').textContent = m.pragmatic_actions;
        document.getElementById('metEpistemic').textContent = m.epistemic_actions;
    }

    // Logs
    if (data.logs) {
        const logContainer = document.getElementById('logContainer');
        logContainer.innerHTML = data.logs.map(l => `<div class="log-entry">${l}</div>`).join('');
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Arrival
    if (data.agent_state === 'ARRIVED' && !arrivalModalShown) {
        arrivalModalShown = true;
        isRunning = false;
        isPaused = true;

        document.getElementById('btnStartPause').innerHTML = '▶ Iniciar';
        updateStatusDot();

        showArrival(data);
    }
}

function setMetric(name, value) {
    const pct = Math.round(value * 100);
    document.getElementById('met' + name).textContent = pct + '%';
    document.getElementById('bar' + name).style.width = pct + '%';
}

function updateStatusDot() {
    const dot = document.getElementById('statusDot');
    dot.className = isPaused ? 'status-dot paused' : (isRunning ? 'status-dot' : 'status-dot stopped');
}

function updateRadar(obs) {
    const dirs = ['front', 'back', 'left', 'right'];
    const ids = ['radarFront', 'radarBack', 'radarLeft', 'radarRight'];
    const labels = { free: '✓', blocked: '✗', traffic: '🚗', accident: '💥',
        semaphore_green: '🟢', semaphore_red: '🔴', rain: '🌧', wall: '▪', unknown: '?' };
    dirs.forEach((d, i) => {
        const el = document.getElementById(ids[i]);
        const val = obs[d] || 'unknown';
        const base = val.split('_')[0];
        el.textContent = labels[val] || labels[base] || val;
        el.className = `radar-label ${d} ${base}`;
    });
}

function showArrival(data) {
    const m = data.metrics || {};
    const modal = document.getElementById('arrivalModal');
    document.getElementById('arrivalMetrics').innerHTML = `
        <div class="arrival-metric"><div class="label">Pasos</div><div class="value">${m.steps_taken}</div></div>
        <div class="arrival-metric"><div class="label">Tiempo</div><div class="value">${data.total_time || 0}s</div></div>
        <div class="arrival-metric"><div class="label">Bloqueos</div><div class="value">${m.blocks_detected}</div></div>
        <div class="arrival-metric"><div class="label">Recalculaciones</div><div class="value">${m.recalculations}</div></div>
        <div class="arrival-metric"><div class="label">Mapa descubierto</div><div class="value">${m.map_discovered_pct}%</div></div>
        <div class="arrival-metric"><div class="label">Incertidumbre final</div><div class="value">${m.final_uncertainty}</div></div>
        <div class="arrival-metric"><div class="label">Pragmáticas</div><div class="value">${m.pragmatic_actions}</div></div>
        <div class="arrival-metric"><div class="label">Epistémicas</div><div class="value">${m.epistemic_actions}</div></div>
    `;
    modal.classList.add('show');
}

// ============================================================
// CANVAS RENDERING
// ============================================================
function resizeCanvas() {
    const container = document.getElementById('canvasContainer');
    const maxW = container.clientWidth - 20;
    const maxH = container.clientHeight - 20;
    const cols = currentView === 'both' ? canvasCols * 2 + 2 : canvasCols;
    cellSize = Math.floor(Math.min(maxW / cols, maxH / canvasRows, 50));
    cellSize = Math.max(cellSize, 20);
    canvas.width = cols * cellSize;
    canvas.height = canvasRows * cellSize;
}

function renderLoop() {
    // Animate car position
    animCarX += (targetCarX - animCarX) * ANIM_SPEED;
    animCarY += (targetCarY - animCarY) * ANIM_SPEED;
    drawCanvas();
    animFrameId = requestAnimationFrame(renderLoop);
}

function drawCanvas() {
    if (!state || !state.real_world) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (currentView === 'real') {
        drawGrid(state.real_world, 0, false);
        drawRoute(state.route, 0);
        drawCar(0);
    } else if (currentView === 'beliefs') {
        drawGrid(state.belief_map, 0, true);
        drawRoute(state.route, 0);
        drawCar(0);
    } else {
        // Both side by side
        drawGrid(state.real_world, 0, false);
        drawCar(0);
        const offset = (canvasCols + 2) * cellSize;
        drawGrid(state.belief_map, offset, true);
        drawRoute(state.route, offset);
        drawCarAt(offset, true);
        // Labels
        ctx.fillStyle = 'rgba(0,229,255,0.7)';
        ctx.font = `bold ${Math.max(10, cellSize * 0.3)}px Orbitron`;
        ctx.textAlign = 'center';
        ctx.fillText('η — Mundo Real', (canvasCols * cellSize) / 2, cellSize * 0.4);
        ctx.fillText('μ — Creencias', offset + (canvasCols * cellSize) / 2, cellSize * 0.4);
    }
}

function drawGrid(grid, offsetX, isBeliefs) {
    if (!grid) return;
    const colors = {
        0: '#1e2d3d',   // free
        1: '#37474f',   // blocked
        2: '#bf360c',   // traffic
        3: '#2e7d32',   // semaphore (default green)
        4: '#b71c1c',   // accident
        5: '#01579b',   // rain
        '-1': '#12121f', // unknown
    };
    const icons = { 1: '🚧', 2: '🚗', 3: '🚦', 4: '💥', 5: '🌧️' };
    const startPos = state.start || [0, 0];
    const destPos = state.destination || [0, 0];
    const exploredSet = new Set((state.explored_cells || []).map(c => `${c[0]},${c[1]}`));

    for (let r = 0; r < grid.length; r++) {
        for (let c = 0; c < (grid[r]?.length || 0); c++) {
            const val = grid[r][c];
            const x = offsetX + c * cellSize;
            const y = r * cellSize;

            // Cell background
            let bg = colors[val] || colors[0];
            if (isBeliefs && val === -1) bg = '#0d0d1a';
            ctx.fillStyle = bg;
            ctx.fillRect(x, y, cellSize, cellSize);

            // Explored highlight for beliefs
            if (isBeliefs && val !== -1) {
                ctx.fillStyle = 'rgba(0,229,255,0.05)';
                ctx.fillRect(x, y, cellSize, cellSize);
            }

            // Grid lines
            ctx.strokeStyle = 'rgba(100,200,255,0.08)';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x, y, cellSize, cellSize);

            // Icons
            const fontSize = Math.max(10, cellSize * 0.45);
            ctx.font = `${fontSize}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            if (r === startPos[0] && c === startPos[1]) {
                ctx.fillStyle = '#00e676';
                ctx.font = `bold ${fontSize}px Orbitron, sans-serif`;
                ctx.fillText('A', x + cellSize / 2, y + cellSize / 2);
            } else if (r === destPos[0] && c === destPos[1]) {
                ctx.fillStyle = '#f50057';
                ctx.font = `bold ${fontSize}px Orbitron, sans-serif`;
                ctx.fillText('B', x + cellSize / 2, y + cellSize / 2);
            } else if (val === -1 && isBeliefs) {
                ctx.fillStyle = 'rgba(255,255,255,0.15)';
                ctx.fillText('?', x + cellSize / 2, y + cellSize / 2);
            } else if (icons[val]) {
                ctx.fillText(icons[val], x + cellSize / 2, y + cellSize / 2);
            }
        }
    }
}

function drawRoute(route, offsetX) {
    if (!route || route.length < 2) return;
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(0, 229, 255, 0.4)';
    ctx.lineWidth = Math.max(2, cellSize * 0.08);
    ctx.setLineDash([cellSize * 0.15, cellSize * 0.1]);
    for (let i = 0; i < route.length; i++) {
        const x = offsetX + route[i][1] * cellSize + cellSize / 2;
        const y = route[i][0] * cellSize + cellSize / 2;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);
}

function drawCar(offsetX) {
    const x = offsetX + animCarX;
    const y = animCarY;
    _drawVehicle(x, y, state?.direction || 'right', state?.mode || 'PRAGMATIC', state?.agent_state);
}

function drawCarAt(offsetX, isBeliefView) {
    const agentPos = getAgentPosition(state);
    if (!agentPos) return;

    const x = offsetX + agentPos[1] * cellSize + cellSize / 2;
    const y = agentPos[0] * cellSize + cellSize / 2;

    _drawVehicle(x, y, state.direction, state.mode, state.agent_state);
}

function _drawVehicle(x, y, direction, mode, agentState) {
    const r = cellSize * 0.35;

    // Sensor glow / radar effect
    ctx.beginPath();
    const gradient = ctx.createRadialGradient(x, y, r * 0.5, x, y, cellSize * 1.2);
    gradient.addColorStop(0, mode === 'EPISTEMIC' ? 'rgba(213,0,249,0.15)' : 'rgba(0,229,255,0.12)');
    gradient.addColorStop(1, 'transparent');
    ctx.fillStyle = gradient;
    ctx.arc(x, y, cellSize * 1.2, 0, Math.PI * 2);
    ctx.fill();

    // Sensor lines
    const sensorColor = mode === 'EPISTEMIC' ? 'rgba(213,0,249,0.3)' : 'rgba(0,229,255,0.25)';
    ctx.strokeStyle = sensorColor;
    ctx.lineWidth = 1;
    const dirs = [[-1, 0], [1, 0], [0, -1], [0, 1]];
    dirs.forEach(([dr, dc]) => {
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + dc * cellSize * 0.9, y + dr * cellSize * 0.9);
        ctx.stroke();
    });

    // Headlight
    const headlight = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[direction] || [1, 0];
    ctx.beginPath();
    const hlGrad = ctx.createRadialGradient(x + headlight[0] * r, y + headlight[1] * r, 0,
        x + headlight[0] * cellSize * 0.7, y + headlight[1] * cellSize * 0.7, cellSize * 0.5);
    hlGrad.addColorStop(0, 'rgba(255,255,200,0.25)');
    hlGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = hlGrad;
    ctx.arc(x + headlight[0] * cellSize * 0.4, y + headlight[1] * cellSize * 0.4, cellSize * 0.5, 0, Math.PI * 2);
    ctx.fill();

    // Car body
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    let bodyColor = '#00e5ff';
    if (agentState === 'ARRIVED') bodyColor = '#00e676';
    else if (agentState === 'STOPPED') bodyColor = '#ff1744';
    else if (agentState === 'WAITING') bodyColor = '#ffd600';
    else if (mode === 'EPISTEMIC') bodyColor = '#d500f9';
    ctx.fillStyle = bodyColor;
    ctx.shadowColor = bodyColor;
    ctx.shadowBlur = 15;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Direction arrow
    ctx.fillStyle = '#0a0e1a';
    ctx.font = `bold ${r}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const arrows = { up: '▲', down: '▼', left: '◄', right: '►' };
    ctx.fillText(arrows[direction] || '►', x, y);

    // Danger flash
    if (agentState === 'RECALCULATING' || agentState === 'ANALYZING') {
        ctx.beginPath();
        ctx.arc(x, y, r + 4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255,145,0,${0.3 + Math.sin(Date.now() * 0.01) * 0.3})`;
        ctx.lineWidth = 2;
        ctx.stroke();
    }
}

// ============================================================
// WINDOW RESIZE
// ============================================================
window.addEventListener('resize', () => {
    if (state) resizeCanvas();
});
