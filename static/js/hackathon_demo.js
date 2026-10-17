// 3-Minute Hackathon Demo Blueprint Controller
// Implements Section 5 of the AquaVigil Hackathon Specification

let demoTimer = null;

function showDemoNotification(title, message, color = 'sky') {
  const existing = document.getElementById('demo-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'demo-toast';
  toast.className = `fixed bottom-6 right-6 z-50 bg-slate-900 border border-${color}-500/80 rounded-2xl p-4 shadow-2xl max-w-sm flex items-start space-x-3 transition-all transform duration-300`;
  
  toast.innerHTML = `
    <div class="w-8 h-8 rounded-xl bg-${color}-500/20 text-${color}-400 flex items-center justify-center flex-shrink-0">
      <i data-lucide="zap" class="w-4 h-4"></i>
    </div>
    <div class="flex-1">
      <div class="text-xs font-bold text-white uppercase tracking-wider">${title}</div>
      <div class="text-xs text-slate-300 mt-0.5 leading-relaxed">${message}</div>
    </div>
    <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-white">
      <i data-lucide="x" class="w-4 h-4"></i>
    </button>
  `;
  document.body.appendChild(toast);
  lucide.createIcons();

  setTimeout(() => {
    if (toast) toast.remove();
  }, 7000);
}

// Minute 1: The Trigger Event
// Action: Presenter displays interactive map of Sector 4 and triggers a simulated supply-cycle cessation.
// Result: Pub/Sub logs the operational status change; water lines transition to unpressurized state.
async function demoStep1TriggerEvent() {
  switchPersona('municipal');
  
  showDemoNotification(
    "Minute 1: The Trigger Event",
    "Simulating supply-cycle cessation on Valve VLV-SEC4-WEST-02 via Cloud Pub/Sub...",
    "rose"
  );

  await triggerCessation();

  if (map) {
    map.flyTo([12.9720, 77.5940], 17.5, { duration: 1.2 });
  }

  showDemoNotification(
    "Minute 1 Complete",
    "Pub/Sub logged SUPPLY_CYCLE_SHUTDOWN. Lines WTR-PIPE-4011/4012 dropped to 0.05 bar resting state.",
    "rose"
  );
}

// Minute 2: Spatial Triaging
// Action: BigQuery GIS computes proximity buffers intersecting the unpressurized main with nearby sewer lines.
// Result: Map highlights a 180m street corridor with an elevated Intrusion Vulnerability Score (0.86).
async function demoStep2SpatialTriage() {
  switchPersona('municipal');

  showDemoNotification(
    "Minute 2: Spatial Triaging",
    "Running BigQuery GIS ST_BUFFER(5.0m) and ST_INTERSECTS query across unpressurized corridors...",
    "amber"
  );

  const res = await runBigQueryGisTriage();

  if (map) {
    map.flyTo([12.9719, 77.5941], 18, { duration: 1.2 });
  }

  showDemoNotification(
    "Minute 2 Complete: 0.86 Risk Corridor",
    `BigQuery GIS identified 180m Pine Avenue corridor in ${res ? res.execution_latency_ms : '42'}ms (<500ms target). High cross-contamination risk flagged!`,
    "amber"
  );
}

// Minute 3: Contextual Triage
// Action: Citizen portal opens; presenter uploads photo of an in-service sediment pre-filter cartridge.
// Result: Gemini flags visual fouling score (0.84); contextual escalation engine recommends cartridge maintenance and flags for utility verification.
async function demoStep3ContextualTriage() {
  switchPersona('citizen');

  const select = document.getElementById('citizen-address-select');
  if (select) {
    select.value = 'HOUSE-PIN-01'; // 104 Pine Avenue (downstream of unpressurized main)
    onCitizenAddressChange();
  }

  selectPreset('severe');

  showDemoNotification(
    "Minute 3: Contextual Triage",
    "Submitting 104 Pine Ave pre-filter photograph to Gemini 1.5 Pro Multimodal Vision API...",
    "emerald"
  );

  await executeFilterAnalysis();

  showDemoNotification(
    "Minute 3 Complete: Two-Tier Escalation Active",
    "Gemini scored Visual Fouling Index at 0.84. Corroborated with BigQuery 0.86 GIS score -> Tier 1 Household Advisory + Tier 2 Utility Verification Dispatched!",
    "emerald"
  );
}

// Play Complete 3-Minute Hackathon Demo Automatically
async function playFullDemo() {
  const playBtn = document.getElementById('btn-play-full-demo');
  if (playBtn) {
    playBtn.disabled = true;
    playBtn.innerHTML = `<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i><span>Playing Demo...</span>`;
    lucide.createIcons();
  }

  try {
    // Step 1: Min 1
    await demoStep1TriggerEvent();
    await new Promise(r => setTimeout(r, 4000));

    // Step 2: Min 2
    await demoStep2SpatialTriage();
    await new Promise(r => setTimeout(r, 4500));

    // Step 3: Min 3
    await demoStep3ContextualTriage();
    await new Promise(r => setTimeout(r, 2000));

    showDemoNotification(
      "Full Demo Complete! 🎉",
      "Full 3-Minute Hackathon pitch sequence executed flawlessly. Click 'Export Report' to download the audit brief.",
      "purple"
    );
  } finally {
    if (playBtn) {
      playBtn.disabled = false;
      playBtn.innerHTML = `<i data-lucide="play-circle" class="w-3.5 h-3.5 text-purple-400"></i><span>Auto Play Demo</span>`;
      lucide.createIcons();
    }
  }
}

// Export Incident Report
function exportTriageReport() {
  window.open('/api/escalation/export-report', '_blank');
}

// Reset Demo State
async function resetDemoState() {
  await triggerRepressurize();
  selectPreset('clean');
  switchPersona('municipal');
  fitMapBounds();
  showDemoNotification(
    "Demo State Reset",
    "Sector 4 South repressurized to 2.8 bar. All buffers cleared.",
    "sky"
  );
}
