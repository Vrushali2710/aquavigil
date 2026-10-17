// AquaVigil Main Application Controller

let map = null;
let networkGeoJsonLayer = null;
let bufferCorridorLayer = null;
let currentPreset = 'severe';
let selectedFile = null;
let currentOperationalStatus = null;
let lastGisResults = null;

// Network Coordinates & Constants
const SECTOR_CENTER = [12.9720, 77.5945];
const SECTOR_ZOOM = 17;

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  loadNetworkTopology();
  refreshScadaStatus();
  selectPreset('severe');
  startLiveTelemetryTicker();
  setupImageUploadListeners();
});

// Switch Between Personas & Views (Safe for unified layout)
function switchPersona(persona) {
  if (map) {
    setTimeout(() => { map.invalidateSize(); }, 150);
  }
}

// Leaflet Map Initialization
function initMap() {
  const mapElement = document.getElementById('map');
  if (!mapElement) return;

  map = L.map('map', {
    zoomControl: true,
    attributionControl: false
  }).setView(SECTOR_CENTER, SECTOR_ZOOM);

  // OpenStreetMap Tile Layer (100% Free, Zero API Key, Zero Watermarks)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  }).addTo(map);

  bufferCorridorLayer = L.geoJSON(null, {
    style: (feature) => ({
      color: '#ef4444',
      weight: 2,
      opacity: 0.9,
      fillColor: '#ef4444',
      fillOpacity: 0.35,
      className: 'pulsing-corridor'
    }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      layer.bindPopup(`
        <div class="text-xs space-y-1">
          <div class="font-bold text-rose-400 uppercase tracking-wide">Intrusion Risk Corridor</div>
          <div><span class="text-slate-400">Main:</span> <strong class="text-white">${p.water_pipe_id}</strong></div>
          <div><span class="text-slate-400">Adjacent Sewer:</span> <strong class="text-white">${p.sewer_id}</strong></div>
          <div><span class="text-slate-400">Separation Distance:</span> <strong class="text-amber-400">${p.proximity_m} m</strong></div>
          <div><span class="text-slate-400">Intrusion Score:</span> <strong class="text-rose-400 text-sm">${p.intrusion_risk_score}</strong> (${p.threat_level})</div>
          <div class="text-[10px] text-slate-400 pt-1 border-t border-slate-700">${p.street} (5.0m BigQuery buffer)</div>
        </div>
      `);
    }
  }).addTo(map);
}

// Fit Map
function fitMapBounds() {
  if (map) {
    map.setView(SECTOR_CENTER, SECTOR_ZOOM);
  }
}

// Load Network Topology & Overlay
async function loadNetworkTopology() {
  try {
    const res = await fetch('/api/network/geojson');
    const geojsonData = await res.json();

    if (networkGeoJsonLayer) {
      map.removeLayer(networkGeoJsonLayer);
    }

    networkGeoJsonLayer = L.geoJSON(geojsonData, {
      style: (feature) => {
        const type = feature.properties.asset_type;
        if (type === 'water_main') {
          const isUnpressurized = (feature.properties.current_status === 'UNPRESSURIZED_RESTING');
          return {
            color: isUnpressurized ? '#ef4444' : '#0284c7',
            weight: isUnpressurized ? 5 : 4,
            opacity: 0.95,
            dashArray: isUnpressurized ? '6, 6' : null
          };
        } else if (type === 'gravity_sewer') {
          return {
            color: '#f59e0b',
            weight: 3,
            opacity: 0.8,
            dashArray: '4, 8'
          };
        }
        return { color: '#94a3b8', weight: 2 };
      },
      pointToLayer: (feature, latlng) => {
        const type = feature.properties.asset_type;
        if (type === 'scada_valve') {
          const isOpen = (feature.properties.status === 'OPEN' || feature.properties.actuator_state === 'OPEN');
          const color = isOpen ? '#10b981' : '#ef4444';
          return L.circleMarker(latlng, {
            radius: 8,
            fillColor: color,
            color: '#ffffff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.9
          });
        } else if (type === 'household_endpoint') {
          return L.circleMarker(latlng, {
            radius: 6,
            fillColor: '#38bdf8',
            color: '#0369a1',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.85
          });
        }
        return L.marker(latlng);
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        let content = `<div class="text-xs space-y-1">`;
        if (p.asset_type === 'water_main') {
          content += `
            <div class="font-bold text-sky-400">Potable Water Main: ${p.pipe_id}</div>
            <div>Status: <span class="${p.current_status === 'PRESSURIZED' ? 'text-emerald-400' : 'text-rose-400'} font-bold">${p.current_status}</span></div>
            <div>Pressure: <strong>${p.residual_pressure_bar} bar</strong></div>
            <div>Material: ${p.material} (${p.installation_decade})</div>
            <div>Street: ${p.street}</div>
          `;
        } else if (p.asset_type === 'gravity_sewer') {
          content += `
            <div class="font-bold text-amber-400">Gravity Sewer: ${p.sewer_id}</div>
            <div>Material: ${p.material} (${p.installation_year})</div>
            <div>Condition Rating: <strong class="text-rose-400">${p.condition_rating} / 5.0</strong></div>
            <div>Exfiltration Risk: <strong class="text-rose-400">${p.exfiltration_risk}</strong></div>
          `;
        } else if (p.asset_type === 'scada_valve') {
          content += `
            <div class="font-bold text-emerald-400">SCADA Valve: ${p.valve_id}</div>
            <div>Type: ${p.type}</div>
            <div>Actuator State: <strong>${p.status || p.actuator_state}</strong></div>
            <div>Sector: ${p.sector_id}</div>
          `;
        } else if (p.asset_type === 'household_endpoint') {
          content += `
            <div class="font-bold text-sky-300">Household: ${p.address}</div>
            <div>Resident: ${p.resident_name}</div>
            <div>Purifier: ${p.purifier_type}</div>
            <div>Connected Main: <strong>${p.connected_pipe_id}</strong></div>
          `;
        }
        content += `</div>`;
        layer.bindPopup(content);
      }
    }).addTo(map);

  } catch (err) {
    console.error("Error loading network GeoJSON:", err);
  }
}

// Refresh SCADA Status & Pub/Sub telemetry
async function refreshScadaStatus() {
  try {
    const res = await fetch('/api/scada/status');
    const data = await res.json();
    currentOperationalStatus = data;

    const valveState = data.valves["VLV-SEC4-WEST-02"] || "OPEN";
    const valveStateEl = document.getElementById('scada-valve-state');
    if (valveStateEl) {
      if (valveState === 'OPEN') {
        valveStateEl.textContent = 'OPEN (100%)';
        valveStateEl.className = 'text-sm font-bold text-emerald-400';
      } else {
        valveStateEl.textContent = 'CLOSED (0%) - SHUTOFF';
        valveStateEl.className = 'text-sm font-bold text-rose-400';
      }
    }

    // Pressure Gauge & Threat Metrics
    const pipe4011 = data.pipe_states["WTR-PIPE-4011"];
    const pressureEl = document.getElementById('metric-pressure');
    const pressureLabel = document.getElementById('metric-pressure-label');

    if (pipe4011) {
      if (pressureEl) pressureEl.textContent = pipe4011.pressure_bar.toFixed(2);
      if (pressureLabel) {
        if (pipe4011.status === 'UNPRESSURIZED_RESTING') {
          pressureLabel.textContent = 'Resting Supply Cessation (Low Pressure Ingress Risk)';
          pressureLabel.className = 'text-xs text-rose-400 font-medium';
          if (pressureEl) pressureEl.className = 'text-2xl font-black text-rose-400';
        } else {
          pressureLabel.textContent = 'Fully Pressurized Active Supply';
          pressureLabel.className = 'text-xs text-emerald-400 font-medium';
          if (pressureEl) pressureEl.className = 'text-2xl font-black text-emerald-400';
        }
      }
    }

    // Recent payload preview
    if (data.recent_events && data.recent_events.length > 0) {
      const latest = data.recent_events[0];
      const previewEl = document.getElementById('scada-payload-preview');
      const timeEl = document.getElementById('payload-timestamp');
      if (previewEl) previewEl.textContent = JSON.stringify(latest, null, 2);
      if (timeEl) timeEl.textContent = new Date(latest.timestamp).toLocaleTimeString();
    }

    updateCitizenPipeIndicator();

  } catch (err) {
    console.error("Error fetching SCADA status:", err);
  }
}

// Trigger Supply Cessation (Minute 1 of Blueprint)
async function triggerCessation() {
  try {
    const res = await fetch('/api/scada/simulate-cessation', { method: 'POST' });
    const data = await res.json();
    await refreshScadaStatus();
    await loadNetworkTopology();
    await runBigQueryGisTriage();
  } catch (err) {
    console.error("Error triggering cessation:", err);
  }
}

// Trigger Repressurize
async function triggerRepressurize() {
  try {
    const res = await fetch('/api/scada/simulate-repressurize', { method: 'POST' });
    const data = await res.json();
    await refreshScadaStatus();
    await loadNetworkTopology();
    clearBufferCorridors();
  } catch (err) {
    console.error("Error repressurizing:", err);
  }
}

// Run BigQuery GIS Spatial Risk Query (Minute 2 of Blueprint)
async function runBigQueryGisTriage() {
  try {
    const res = await fetch('/api/gis/correlation-query');
    const data = await res.json();
    lastGisResults = data;

    // Latency
    const latEl = document.getElementById('metric-latency');
    if (latEl) latEl.textContent = data.execution_latency_ms;

    // Threat Score
    const threatScoreEl = document.getElementById('metric-threat-score');
    const threatBadgeEl = document.getElementById('metric-threat-badge');
    const threatSummaryEl = document.getElementById('metric-threat-summary');

    if (data.results && data.results.length > 0) {
      const top = data.results[0];
      if (threatScoreEl) {
        threatScoreEl.textContent = top.intrusion_risk_score.toFixed(2);
        threatScoreEl.className = 'text-2xl font-black text-rose-400';
      }
      if (threatBadgeEl) {
        threatBadgeEl.textContent = top.threat_level;
        threatBadgeEl.className = 'text-xs px-2 py-0.5 rounded bg-rose-950 text-rose-400 font-bold border border-rose-800';
      }
      if (threatSummaryEl) {
        threatSummaryEl.textContent = `${top.street} (Proximity: ${top.proximity_m}m)`;
        threatSummaryEl.className = 'text-xs text-rose-400 font-medium';
      }

      // Render Corridor GeoJSON on Leaflet Map
      if (bufferCorridorLayer && data.corridor_geojson) {
        bufferCorridorLayer.clearLayers();
        bufferCorridorLayer.addData(data.corridor_geojson);
      }

      renderCorridorTable(data.results);
    } else {
      clearBufferCorridors();
    }

    // Update SQL modal template
    const sqlContentEl = document.getElementById('modal-sql-content');
    if (sqlContentEl && data.sql_query) {
      sqlContentEl.textContent = data.sql_query;
    }

    return data;
  } catch (err) {
    console.error("Error executing GIS query:", err);
  }
}

function clearBufferCorridors() {
  if (bufferCorridorLayer) bufferCorridorLayer.clearLayers();
  const threatScoreEl = document.getElementById('metric-threat-score');
  const threatBadgeEl = document.getElementById('metric-threat-badge');
  const threatSummaryEl = document.getElementById('metric-threat-summary');
  if (threatScoreEl) {
    threatScoreEl.textContent = '0.00';
    threatScoreEl.className = 'text-2xl font-black text-slate-400';
  }
  if (threatBadgeEl) {
    threatBadgeEl.textContent = 'NOMINAL';
    threatBadgeEl.className = 'text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300';
  }
  if (threatSummaryEl) {
    threatSummaryEl.textContent = 'All potable lines pressurized';
    threatSummaryEl.className = 'text-xs text-slate-400';
  }

  const container = document.getElementById('corridor-results-container');
  if (container) {
    container.innerHTML = `
      <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs text-slate-400 flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <i data-lucide="info" class="w-4 h-4 text-sky-400 flex-shrink-0"></i>
          <span>Click <strong>"Shutoff"</strong> above to calculate BigQuery GIS 5m buffer intersections.</span>
        </div>
        <span class="text-[10px] text-slate-500">Target SLA: &lt;500ms</span>
      </div>
    `;
    lucide.createIcons();
  }
}

function renderCorridorTable(results) {
  const container = document.getElementById('corridor-results-container');
  if (!container) return;

  let html = `<div class="space-y-2.5">`;
  results.forEach(r => {
    html += `
      <div class="bg-slate-950 p-3.5 rounded-xl border border-rose-900/60 flex items-start justify-between">
        <div class="space-y-1">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold text-white">${r.street}</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded bg-rose-950 text-rose-400 font-bold border border-rose-800">${r.threat_level}</span>
          </div>
          <div class="text-[11px] text-slate-300">
            Water: <strong class="text-sky-400">${r.water_pipe_id}</strong> ⟂ Sewer: <strong class="text-amber-400">${r.sewer_id}</strong>
          </div>
          <div class="text-[10px] text-slate-400">
            Separation: <strong class="text-white">${r.proximity_m}m</strong> | Sewer Rating: <strong class="text-rose-400">${r.pipe_condition_rating}/5.0</strong>
          </div>
          <p class="text-[10px] text-slate-400 italic pt-1">${r.rationale}</p>
        </div>
        <div class="text-right">
          <div class="text-[10px] text-slate-400 uppercase">Intrusion Score</div>
          <div class="text-xl font-black text-rose-400">${r.intrusion_risk_score.toFixed(2)}</div>
          <div class="text-[9px] text-slate-500">${r.corridor_length_m}m corridor</div>
        </div>
      </div>
    `;
  });
  html += `</div>`;
  container.innerHTML = html;
  lucide.createIcons();
}

// Citizen Portal Functions
function updateCitizenPipeIndicator() {
  const select = document.getElementById('citizen-address-select');
  const indicator = document.getElementById('citizen-pipe-status');
  if (!select || !indicator || !currentOperationalStatus) return;

  const addrVal = select.value;
  let pipeId = (addrVal === 'HOUSE-ELM-03') ? 'WTR-PIPE-4012' : 'WTR-PIPE-4011';
  const pipeState = currentOperationalStatus.pipe_states[pipeId];

  if (pipeState && pipeState.status === 'UNPRESSURIZED_RESTING') {
    indicator.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span>
      <span class="text-rose-400 font-bold">Network Resting (Intermittent Supply Shutoff Detected - 0.05 bar)</span>
    `;
  } else {
    indicator.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
      <span class="text-emerald-400 font-medium">Water Main: Pressurized (2.80 bar)</span>
    `;
  }
}

function onCitizenAddressChange() {
  updateCitizenPipeIndicator();
}

// Setup Image Upload & Drag/Drop/Paste Listeners
function setupImageUploadListeners() {
  window.addEventListener('paste', handleGlobalPaste);

  const previewBox = document.getElementById('filter-preview-box');
  if (previewBox) {
    previewBox.addEventListener('dragover', (e) => {
      e.preventDefault();
      previewBox.classList.add('ring-2', 'ring-sky-500');
    });
    previewBox.addEventListener('dragleave', (e) => {
      e.preventDefault();
      previewBox.classList.remove('ring-2', 'ring-sky-500');
    });
    previewBox.addEventListener('drop', (e) => {
      e.preventDefault();
      previewBox.classList.remove('ring-2', 'ring-sky-500');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileUpload({ target: { files: e.dataTransfer.files } });
      }
    });
  }
}

function handleGlobalPaste(e) {
  if (e.clipboardData && e.clipboardData.items) {
    for (let i = 0; i < e.clipboardData.items.length; i++) {
      const item = e.clipboardData.items[i];
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        if (file) {
          handleFileUpload({ target: { files: [file] } });
          const badge = document.getElementById('active-image-source');
          if (badge) badge.textContent = "Uploaded: Clipboard Image";
          return;
        }
      }
    }
  }
}

function updatePresetButtons(activePreset) {
  ['clean', 'moderate', 'severe'].forEach(p => {
    const btn = document.getElementById(`preset-btn-${p}`);
    if (btn) {
      if (p === activePreset) {
        btn.classList.add('active-preset');
      } else {
        btn.classList.remove('active-preset');
      }
    }
  });
}

// Preset selection
function selectPreset(preset) {
  currentPreset = preset;
  selectedFile = null;

  updatePresetButtons(preset);

  const previewImg = document.getElementById('filter-preview-img');
  if (previewImg) {
    if (preset === 'severe') {
      previewImg.src = '/api/samples/severe_biofilm_rust_filter.svg';
    } else if (preset === 'moderate') {
      previewImg.src = '/api/samples/moderate_silt_filter.svg';
    } else {
      previewImg.src = '/api/samples/clean_filter.svg';
    }
  }

  const badge = document.getElementById('active-image-source');
  if (badge) {
    const labels = { clean: 'Clean Filter (0.08)', moderate: 'Silt Filter (0.52)', severe: 'Biofilm Preset (0.84)' };
    badge.textContent = labels[preset] || preset;
  }
}

function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  selectedFile = file;
  currentPreset = null;

  updatePresetButtons(null);

  const reader = new FileReader();
  reader.onload = (event) => {
    const previewImg = document.getElementById('filter-preview-img');
    if (previewImg) previewImg.src = event.target.result;
  };
  reader.readAsDataURL(file);

  const badge = document.getElementById('active-image-source');
  if (badge) badge.textContent = `Uploaded: ${file.name}`;
}

// Execute Gemini Multimodal Visual Analysis & Two-Tier Escalation
async function executeFilterAnalysis() {
  const btn = document.getElementById('btn-run-analysis');
  if (btn) {
    btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin"></i><span>Analyzing with Gemini 2.0 Flash...</span>`;
    lucide.createIcons();
  }

  try {
    let formData = new FormData();
    if (selectedFile) {
      formData.append('file', selectedFile);
    } else if (currentPreset) {
      formData.append('preset', currentPreset);
    } else {
      formData.append('preset', 'severe');
    }

    const res = await fetch('/api/gemini/analyze-filter', {
      method: 'POST',
      body: formData
    });
    const visualData = await res.json();

    // Render Gemini results
    document.getElementById('res-fouling-score').textContent = visualData.visual_fouling_index.toFixed(2);
    document.getElementById('res-fouling-bar').style.width = `${Math.round(visualData.visual_fouling_index * 100)}%`;
    document.getElementById('res-deposit-badge').textContent = visualData.deposit_indicators;
    document.getElementById('res-severity-badge').textContent = visualData.fouling_severity;
    document.getElementById('res-rationale').textContent = visualData.rationale;

    const turbEl = document.getElementById('res-turbidity');
    if (turbEl) turbEl.textContent = `${visualData.estimated_turbidity_ntu || 340.0} NTU`;

    const opacEl = document.getElementById('res-opacity');
    if (opacEl) opacEl.textContent = `${visualData.optical_opacity_percent || 88.5}%`;

    const colifEl = document.getElementById('res-coliform');
    if (colifEl) colifEl.textContent = visualData.coliform_biofilm_likelihood || 'CRITICAL';
    
    if (visualData.analysis_source) {
      document.getElementById('analysis-source-tag').textContent = `Source: ${visualData.analysis_source}`;
    }

    // Call Two-Tier Escalation Engine
    const select = document.getElementById('citizen-address-select');
    const householdId = select.value;
    const addressText = select.options[select.selectedIndex].text;
    const connectedPipeId = (householdId === 'HOUSE-ELM-03') ? 'WTR-PIPE-4012' : 'WTR-PIPE-4011';
    
    const pipeState = currentOperationalStatus ? (currentOperationalStatus.pipe_states[connectedPipeId] || {}) : {};
    const operationalStatus = pipeState.status || 'PRESSURIZED';
    
    // Spatial risk score from active correlation results
    let spatialRisk = 0.0;
    if (lastGisResults && lastGisResults.results) {
      const match = lastGisResults.results.find(r => r.water_pipe_id === connectedPipeId);
      if (match) spatialRisk = match.intrusion_risk_score;
    }

    const escRes = await fetch('/api/escalation/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        household_id: householdId,
        address: addressText,
        connected_pipe_id: connectedPipeId,
        visual_analysis: visualData,
        spatial_risk_score: spatialRisk,
        pipe_operational_status: operationalStatus
      })
    });
    const escData = await escRes.json();

    // Update Tier 1 & Tier 2 messages
    document.getElementById('tier1-message').textContent = escData.tier1_household.message;
    document.getElementById('tier2-message').textContent = escData.tier2_municipal.action_required + " (" + escData.tier2_municipal.defensibility_note + ")";

    const sopBadge = document.getElementById('tier2-sop-badge');
    if (sopBadge && escData.technical_metrics) {
      sopBadge.textContent = escData.technical_metrics.sop_protocol_code;
    }

  } catch (err) {
    console.error("Error analyzing filter:", err);
  } finally {
    if (btn) {
      btn.innerHTML = `<i data-lucide="sparkles" class="w-4 h-4"></i><span>Analyze with Gemini 2.0 Flash</span>`;
      lucide.createIcons();
    }
  }
}

// Draw Live Hydraulic Pressure Waveform on Canvas
function drawPressureSparkline(history) {
  const canvas = document.getElementById('scada-pressure-canvas');
  if (!canvas || !history || history.length === 0) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const minP = 0.0;
  const maxP = 3.2;
  const step = w / (history.length - 1 || 1);
  const lastVal = history[history.length - 1];

  // Draw area gradient
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  if (lastVal < 0.5) {
    grad.addColorStop(0, 'rgba(239, 68, 68, 0.45)');
    grad.addColorStop(1, 'rgba(239, 68, 68, 0.05)');
  } else {
    grad.addColorStop(0, 'rgba(16, 185, 129, 0.4)');
    grad.addColorStop(1, 'rgba(16, 185, 129, 0.05)');
  }

  ctx.beginPath();
  history.forEach((val, i) => {
    const x = i * step;
    const norm = Math.max(0, Math.min(1, (val - minP) / (maxP - minP)));
    const y = h - (norm * (h - 10) + 5);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Draw line
  ctx.beginPath();
  history.forEach((val, i) => {
    const x = i * step;
    const norm = Math.max(0, Math.min(1, (val - minP) / (maxP - minP)));
    const y = h - (norm * (h - 10) + 5);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = (lastVal < 0.5) ? '#ef4444' : '#10b981';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Draw last point
  const lastX = (history.length - 1) * step;
  const lastNorm = Math.max(0, Math.min(1, (lastVal - minP) / (maxP - minP)));
  const lastY = h - (lastNorm * (h - 10) + 5);
  ctx.beginPath();
  ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
  ctx.fillStyle = (lastVal < 0.5) ? '#ef4444' : '#10b981';
  ctx.fill();
}

// Architecture Inspector Modal Functions
function openArchitectureModal(tab) {
  const modal = document.getElementById('architecture-modal');
  if (modal) {
    modal.classList.remove('hidden');
    switchModalTab(tab || 'bigquery');
    lucide.createIcons();
  }
}

function closeArchitectureModal() {
  const modal = document.getElementById('architecture-modal');
  if (modal) modal.classList.add('hidden');
}

function switchModalTab(tabName) {
  ['bigquery', 'pubsub', 'gemini', 'hydraulics'].forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const content = document.getElementById(`tab-content-${t}`);
    if (btn) {
      if (t === tabName) {
        btn.className = 'py-2.5 px-3 border-b-2 border-sky-400 text-sky-400 font-bold flex items-center space-x-1.5';
      } else {
        btn.className = 'py-2.5 px-3 border-b-2 border-transparent text-slate-400 hover:text-white flex items-center space-x-1.5';
      }
    }
    if (content) {
      if (t === tabName) {
        content.classList.remove('hidden');
      } else {
        content.classList.add('hidden');
      }
    }
  });
}

// ==================== LIVE DATA INTEGRATIONS ====================

let liveCameraStream = null;
let liveTelemetryTimer = null;

// 1. Live SCADA Stream Ticker
function startLiveTelemetryTicker() {
  if (liveTelemetryTimer) clearInterval(liveTelemetryTimer);

  liveTelemetryTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/scada/live-tick');
      if (!res.ok) return;
      const tick = await res.json();

      const pressureEl = document.getElementById('metric-pressure');
      if (pressureEl) {
        pressureEl.textContent = tick.residual_pressure_bar.toFixed(2);
        pressureEl.className = (tick.residual_pressure_bar < 0.5) ? 'text-base font-black text-rose-400' : 'text-base font-black text-emerald-400';
      }

      const clockEl = document.getElementById('live-clock');
      if (clockEl) {
        clockEl.textContent = new Date(tick.timestamp).toLocaleTimeString() + " UTC";
      }

      const valveEl = document.getElementById('scada-valve-state');
      if (valveEl) {
        if (tick.actuator_state === 'OPEN') {
          valveEl.textContent = 'OPEN (100%)';
          valveEl.className = 'text-xs font-bold text-emerald-400 mt-0.5';
        } else {
          valveEl.textContent = 'CLOSED (0%) - SHUTOFF';
          valveEl.className = 'text-xs font-bold text-rose-400 mt-0.5';
        }
      }

      const dpdtEl = document.getElementById('metric-dp-dt');
      if (dpdtEl && tick.pressure_gradient_dp_dt !== undefined) {
        const sign = tick.pressure_gradient_dp_dt >= 0 ? '+' : '';
        dpdtEl.textContent = `${sign}${tick.pressure_gradient_dp_dt.toFixed(2)} bar/s`;
        dpdtEl.className = (tick.pressure_gradient_dp_dt < -0.1) ? 'font-mono text-rose-400 font-bold' : 'font-mono text-emerald-400 font-bold';
      }

      const flowEl = document.getElementById('metric-flow-rate');
      if (flowEl && tick.flow_rate_lps !== undefined) {
        flowEl.textContent = `${tick.flow_rate_lps.toFixed(1)} L/s`;
      }

      const regimeEl = document.getElementById('metric-transient-regime');
      if (regimeEl && tick.transient_hydraulic_regime) {
        regimeEl.textContent = tick.transient_hydraulic_regime;
        if (tick.transient_hydraulic_regime.includes('SIPHONAGE') || tick.transient_hydraulic_regime.includes('DRAIN')) {
          regimeEl.className = 'px-2 py-0.5 rounded bg-rose-950/80 text-rose-400 border border-rose-800 text-[10px] font-mono font-bold animate-pulse';
        } else {
          regimeEl.className = 'px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800 text-[10px] font-mono font-bold';
        }
      }

      if (tick.pressure_history) {
        drawPressureSparkline(tick.pressure_history);
      }

      updateCitizenPipeIndicator();
    } catch (e) {
      // Background poll
    }
  }, 1500);
}

// 2. Live Device Camera Capture
async function toggleLiveCamera() {
  const video = document.getElementById('live-camera-feed');
  const img = document.getElementById('filter-preview-img');
  const btnSnap = document.getElementById('btn-snap-camera');
  const btnAnalyze = document.getElementById('btn-run-analysis');
  const btnCam = document.getElementById('btn-camera');

  if (liveCameraStream) {
    liveCameraStream.getTracks().forEach(t => t.stop());
    liveCameraStream = null;
    video.classList.add('hidden');
    img.classList.remove('hidden');
    btnSnap.classList.add('hidden');
    btnAnalyze.classList.remove('hidden');
    btnCam.classList.remove('bg-rose-950', 'text-rose-300', 'border-rose-800');
    btnCam.classList.add('bg-sky-950', 'text-sky-300', 'border-sky-800');
    btnCam.innerHTML = `<i data-lucide="camera" class="w-3 h-3"></i><span>Live Cam</span>`;
    lucide.createIcons();
    return;
  }

  try {
    liveCameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } }
    });
    video.srcObject = liveCameraStream;
    video.classList.remove('hidden');
    img.classList.add('hidden');
    btnSnap.classList.remove('hidden');
    btnAnalyze.classList.add('hidden');

    btnCam.classList.remove('bg-sky-950', 'text-sky-300', 'border-sky-800');
    btnCam.classList.add('bg-rose-950', 'text-rose-300', 'border-rose-800');
    btnCam.innerHTML = `<i data-lucide="x" class="w-3 h-3"></i><span>Close Cam</span>`;
    lucide.createIcons();
  } catch (err) {
    alert("Camera access notice: " + (err.message || "Please allow webcam permission to capture live filter photo."));
  }
}

async function snapLivePhoto() {
  const video = document.getElementById('live-camera-feed');
  const canvas = document.getElementById('camera-canvas');
  if (!video || !canvas) return;

  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(async (blob) => {
    selectedFile = new File([blob], "live_camera_capture.jpg", { type: "image/jpeg" });
    currentPreset = null;

    const img = document.getElementById('filter-preview-img');
    img.src = canvas.toDataURL('image/jpeg');

    toggleLiveCamera();
    await executeFilterAnalysis();
  }, 'image/jpeg', 0.9);
}

// 3. Live GPS & Real OpenStreetMap Corridors
function useLiveGpsCorridor() {
  if (!navigator.geolocation) {
    alert("Geolocation is not supported by your browser.");
    return;
  }

  const btn = event.currentTarget;
  if (btn) btn.innerHTML = `<i data-lucide="loader" class="w-3 h-3 animate-spin"></i><span>Locating...</span>`;
  lucide.createIcons();

  navigator.geolocation.getCurrentPosition(async (pos) => {
    const lat = pos.coords.latitude;
    const lon = pos.coords.longitude;

    if (map) {
      map.flyTo([lat, lon], 17, { duration: 1.5 });
    }

    try {
      const res = await fetch(`/api/network/fetch-live-osm?lat=${lat}&lon=${lon}`);
      const data = await res.json();
      if (data.status === 'SUCCESS' && data.features) {
        L.geoJSON(data, {
          style: { color: '#0284c7', weight: 4, opacity: 0.85 }
        }).addTo(map);
        alert(`✓ Loaded live OpenStreetMap corridors around your location (${lat.toFixed(4)}, ${lon.toFixed(4)})`);
      }
    } catch (e) {
      console.warn("Could not load OSM corridors:", e);
    } finally {
      if (btn) {
        btn.innerHTML = `<i data-lucide="crosshair" class="w-3 h-3"></i><span>Live GPS</span>`;
        lucide.createIcons();
      }
    }
  }, (err) => {
    alert("Location notice: " + (err.message || "Could not retrieve live GPS location."));
    if (btn) {
      btn.innerHTML = `<i data-lucide="crosshair" class="w-3 h-3"></i><span>Live GPS</span>`;
      lucide.createIcons();
    }
  });
}
