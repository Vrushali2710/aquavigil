// AquaVigil Main Application Controller

let map = null;
let networkGeoJsonLayer = null;
let bufferCorridorLayer = null;
let currentPreset = null;
let selectedFile = null;
let currentOperationalStatus = null;
let lastGisResults = null;
let notificationQueue = [];

// Network Coordinates & Constants
const SECTOR_CENTER = [12.9720, 77.5945];
const SECTOR_ZOOM = 17;

document.addEventListener("DOMContentLoaded", () => {
  applyTheme('dark');
  switchDashboardTab('ingestion');
  initMap();
  loadNetworkTopology();
  loadUsgsWaterContext();
  loadWqpQualityContext();
  refreshScadaStatus();
  selectPreset(null);
  startLiveTelemetryTicker();
  setupImageUploadListeners();
  initializeAuthUI();
  renderNotifications();
  addNotification({
    title: 'System online',
    message: 'AquaVigil is operational and monitoring current network conditions.',
    level: 'info'
  });
  setInterval(loadUsgsWaterContext, 60000);
  setInterval(loadWqpQualityContext, 60000);

  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const nextTheme = document.body.classList.contains('theme-dark') ? 'light' : 'dark';
      applyTheme(nextTheme);
    });
  }
});

function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.body.classList.toggle('theme-dark', isDark);
  document.body.classList.toggle('theme-light', !isDark);

  const toggle = document.getElementById('theme-toggle');
  if (toggle) {
    const icon = toggle.querySelector('i');
    const label = toggle.querySelector('span');
    if (icon) {
      icon.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
      if (window.lucide) lucide.createIcons();
    }
    if (label) label.textContent = isDark ? 'Light mode' : 'Dark mode';
    toggle.classList.toggle('bg-sky-100', !isDark);
    toggle.classList.toggle('border-sky-200', !isDark);
    toggle.classList.toggle('text-sky-700', !isDark);
    toggle.classList.toggle('bg-slate-800', isDark);
    toggle.classList.toggle('border-slate-700', isDark);
    toggle.classList.toggle('text-slate-100', isDark);
  }
}

function addNotification({ title, message, level = 'info', duration = 6000 }) {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const item = { id, title, message, level, timestamp: new Date().toISOString(), duration };
  notificationQueue.unshift(item);
  notificationQueue = notificationQueue.slice(0, 6);
  renderNotifications();

  setTimeout(() => {
    notificationQueue = notificationQueue.filter(n => n.id !== id);
    renderNotifications();
  }, duration);
}

function renderNotifications() {
  const center = document.getElementById('notification-center');
  if (!center) return;

  center.innerHTML = notificationQueue.map(n => `
    <div class="notification-card border rounded-xl p-2.5 ${n.level === 'danger' ? 'text-rose-100' : n.level === 'success' ? 'text-emerald-100' : n.level === 'warning' ? 'text-amber-100' : 'text-sky-100'}" data-level="${n.level}">
      <div class="flex items-start justify-between gap-2">
        <div>
          <div class="text-[10px] uppercase tracking-[0.18em] opacity-75">${n.level}</div>
          <div class="text-xs font-bold mt-0.5">${n.title}</div>
        </div>
        <button type="button" onclick="dismissNotification('${n.id}')" class="text-[10px] opacity-70 hover:opacity-100">×</button>
      </div>
      <p class="mt-1 text-[11px] leading-relaxed opacity-90">${n.message}</p>
    </div>
  `).join('') || `
    <div class="bg-slate-950 border border-slate-800 rounded-xl p-3 text-[11px] text-slate-400">
      No active alerts. System is steady.
    </div>
  `;
}

function dismissNotification(id) {
  notificationQueue = notificationQueue.filter(n => n.id !== id);
  renderNotifications();
}

function dismissAllNotifications() {
  notificationQueue = [];
  renderNotifications();
}

let currentUserSession = null;
let authMode = 'login';
let authRole = 'citizen';

function getStoredUsers() {
  try {
    const saved = localStorage.getItem('aquavigil-users');
    return saved ? JSON.parse(saved) : [];
  } catch (err) {
    return [];
  }
}

function saveStoredUsers(users) {
  try {
    localStorage.setItem('aquavigil-users', JSON.stringify(users));
  } catch (err) {
    console.warn('Unable to persist local user list.', err);
  }
}

function findStoredUser(email, password, role) {
  const normalizedEmail = String(email || '').trim().toLowerCase();
  const normalizedPassword = String(password || '').trim();
  if (!normalizedEmail || !normalizedPassword) return null;

  return getStoredUsers().find((user) => {
    return user.email && user.email.toLowerCase() === normalizedEmail && user.password === normalizedPassword && user.role === role;
  }) || null;
}

function openAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (modal) modal.classList.remove('hidden');
  modal?.classList.add('flex');
}

function closeAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (modal) modal.classList.add('hidden');
  modal?.classList.remove('flex');
}

function setAuthMode(mode) {
  authMode = mode;
  const submitBtn = document.getElementById('auth-submit');
  const nameWrap = document.getElementById('auth-name-wrap');
  const agencyWrap = document.getElementById('auth-agency-wrap');
  const tabs = document.querySelectorAll('.auth-tab');
  const isSignup = mode === 'signup';
  const isReset = mode === 'reset';

  tabs.forEach(tab => {
    const active = tab.dataset.authTab === mode;
    tab.classList.toggle('bg-sky-950', active);
    tab.classList.toggle('border-sky-800', active);
    tab.classList.toggle('text-sky-300', active);
    tab.classList.toggle('bg-slate-950', !active);
    tab.classList.toggle('border-slate-800', !active);
    tab.classList.toggle('text-slate-300', !active);
  });

  if (nameWrap) nameWrap.classList.toggle('hidden', !isSignup);
  if (agencyWrap) agencyWrap.classList.toggle('hidden', !(isSignup && authRole === 'municipal'));
  if (submitBtn) submitBtn.textContent = isSignup ? 'Create account' : isReset ? 'Reset password' : 'Login';

  const resetTrigger = document.getElementById('auth-reset-trigger');
  if (resetTrigger) {
    resetTrigger.textContent = isReset ? 'Back to login' : 'Forgot password?';
  }
}

function setAuthRole(role) {
  authRole = role;
  document.querySelectorAll('.auth-role-btn').forEach(btn => {
    const active = btn.dataset.authRole === role;
    btn.classList.toggle('bg-emerald-950/60', active && role === 'citizen');
    btn.classList.toggle('border-emerald-800', active && role === 'citizen');
    btn.classList.toggle('text-emerald-300', active && role === 'citizen');
    btn.classList.toggle('bg-sky-950/60', active && role === 'municipal');
    btn.classList.toggle('border-sky-800', active && role === 'municipal');
    btn.classList.toggle('text-sky-300', active && role === 'municipal');
    btn.classList.toggle('bg-slate-950', !active);
    btn.classList.toggle('border-slate-800', !active);
    btn.classList.toggle('text-slate-300', !active);
  });
  const agencyWrap = document.getElementById('auth-agency-wrap');
  if (agencyWrap) agencyWrap.classList.toggle('hidden', !(authMode === 'signup' && authRole === 'municipal'));
}

function showAuthMessage(text, type = 'warning') {
  const msg = document.getElementById('auth-message');
  if (!msg) return;
  msg.textContent = text;
  msg.classList.remove('hidden');
  msg.classList.remove('border-amber-800', 'border-emerald-800', 'border-rose-800');
  msg.classList.add(type === 'success' ? 'border-emerald-800' : type === 'error' ? 'border-rose-800' : 'border-amber-800');
  msg.classList.add(type === 'success' ? 'bg-emerald-950/40' : type === 'error' ? 'bg-rose-950/40' : 'bg-amber-950/40');
  msg.classList.add(type === 'success' ? 'text-emerald-200' : type === 'error' ? 'text-rose-200' : 'text-amber-200');
}

function ensureAccountMenu() {
  const authBtn = document.getElementById('auth-button');
  if (!authBtn || document.getElementById('aquavigil-account-menu')) return;

  const container = authBtn.parentElement;
  if (!container) return;
  container.classList.add('relative');

  const menu = document.createElement('div');
  menu.id = 'aquavigil-account-menu';
  menu.className = 'hidden absolute right-0 top-full mt-2 w-52 rounded-xl border border-slate-700 bg-slate-900/95 p-2 shadow-2xl shadow-slate-950/50 backdrop-blur-md';
  menu.innerHTML = `
    <div class="px-2 pb-2 pt-1 border-b border-slate-800 text-[10px] uppercase tracking-[0.2em] text-slate-400">My account</div>
    <button type="button" data-account-action="profile" class="mt-2 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs text-slate-200 hover:bg-slate-800">
      <i data-lucide="user-round" class="w-3.5 h-3.5 text-sky-400"></i>
      <span>Profile</span>
    </button>
    <button type="button" data-account-action="logout" class="mt-1 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs text-rose-200 hover:bg-rose-950/40">
      <i data-lucide="log-out" class="w-3.5 h-3.5 text-rose-300"></i>
      <span>Logout</span>
    </button>
  `;
  menu.querySelector('[data-account-action="logout"]').addEventListener('click', logoutCurrentUser);
  menu.querySelector('[data-account-action="profile"]').addEventListener('click', () => {
    const currentUser = getCurrentUser();
    addNotification({
      title: 'Profile active',
      message: currentUser ? `${currentUser.full_name} is signed in as a ${currentUser.role} user.` : 'No active account found.',
      level: 'info',
      duration: 4000
    });
    hideAccountMenu();
  });
  container.appendChild(menu);
  if (window.lucide) lucide.createIcons();
}

function getCurrentUser() {
  return currentUserSession;
}

function toggleAccountMenu() {
  const menu = document.getElementById('aquavigil-account-menu');
  if (!menu) return;
  const isHidden = menu.classList.contains('hidden');
  menu.classList.toggle('hidden', !isHidden);
  const authBtn = document.getElementById('auth-button');
  if (authBtn) authBtn.setAttribute('aria-expanded', String(isHidden));
}

function hideAccountMenu() {
  const menu = document.getElementById('aquavigil-account-menu');
  if (menu) menu.classList.add('hidden');
  const authBtn = document.getElementById('auth-button');
  if (authBtn) authBtn.setAttribute('aria-expanded', 'false');
}

function logoutCurrentUser() {
  currentUserSession = null;
  hideAccountMenu();
  renderLoggedInState(null);
  addNotification({
    title: 'Signed out',
    message: 'Your AquaVigil session has been closed successfully.',
    level: 'success',
    duration: 4000
  });
}

function applyRoleBasedUI(user) {
  const civicRole = user?.role || 'guest';
  const isMunicipal = civicRole === 'municipal';
  const isCitizen = civicRole === 'citizen';

  const municipalPanel = document.getElementById('municipal-only-panel');
  const citizenPanel = document.getElementById('citizen-only-panel');
  const roleBanner = document.getElementById('role-banner');

  if (municipalPanel) municipalPanel.classList.toggle('hidden', !isMunicipal);
  if (citizenPanel) citizenPanel.classList.toggle('hidden', !isCitizen);
  if (roleBanner) {
    roleBanner.classList.toggle('hidden', !isMunicipal && !isCitizen);
    roleBanner.textContent = isMunicipal ? 'Municipal operator console active' : isCitizen ? 'Citizen portal active' : 'Please log in to access role-based panels';
  }

  const municipalBtns = [
    document.getElementById('btn-cessation'),
    document.getElementById('btn-repressurize')
  ];

  municipalBtns.forEach((btn) => {
    if (!btn) return;
    const isLocked = !isMunicipal;
    btn.disabled = isLocked;
    btn.classList.toggle('opacity-50', isLocked);
    btn.classList.toggle('cursor-not-allowed', isLocked);
    btn.title = isLocked ? 'Municipal operators only' : btn.dataset.originalTitle || btn.title;
  });

  const authBtn = document.getElementById('auth-button');
  if (authBtn && user) {
    authBtn.classList.toggle('border-sky-800', !isMunicipal);
    authBtn.classList.toggle('border-amber-700', isMunicipal);
    authBtn.classList.toggle('text-amber-300', isMunicipal);
  }
}

function renderLoggedInState(user) {
  const authBtn = document.getElementById('auth-button');
  if (!authBtn) return;
  if (user) {
    const name = user.full_name || 'My account';
    authBtn.innerHTML = `<i data-lucide="user-check" class="w-3.5 h-3.5 text-emerald-400"></i><span>${name} (${user.role})</span>`;
    authBtn.onclick = () => toggleAccountMenu();
    authBtn.title = `Signed in as ${name} (${user.role})`;
    authBtn.setAttribute('aria-expanded', 'false');
    ensureAccountMenu();
  } else {
    authBtn.innerHTML = `<i data-lucide="user-round" class="w-3.5 h-3.5 text-sky-400"></i><span>Login / Sign up</span>`;
    authBtn.onclick = openAuthModal;
    authBtn.title = 'Login or sign up';
    authBtn.setAttribute('aria-expanded', 'false');
    hideAccountMenu();
  }
  applyRoleBasedUI(user);
  if (window.lucide) lucide.createIcons();
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const name = document.getElementById('auth-name')?.value || '';
  const email = document.getElementById('auth-email')?.value || '';
  const password = document.getElementById('auth-password')?.value || '';
  const agency = document.getElementById('auth-agency')?.value || '';

  const payload = {
    full_name: name,
    email,
    password,
    role: authRole,
    agency: authRole === 'municipal' ? agency : ''
  };

  if (authMode === 'signup') {
    if (!payload.full_name.trim()) {
      showAuthMessage('Please enter your full name to create an account.', 'error');
      return;
    }
  }

  if (!payload.email.trim() || !payload.password.trim()) {
    showAuthMessage('Email and password are required.', 'error');
    return;
  }

  if (authMode === 'signup') {
    const existing = getStoredUsers().find((user) => user.email && user.email.toLowerCase() === payload.email.trim().toLowerCase() && user.role === authRole);
    if (existing) {
      showAuthMessage('That account already exists. Please log in with the existing email and password.', 'error');
      setAuthMode('login');
      return;
    }

    const nextUsers = [...getStoredUsers(), { ...payload, email: payload.email.trim().toLowerCase() }];
    saveStoredUsers(nextUsers);
    showAuthMessage('Account created successfully. Please log in with your email and password to continue.', 'success');
    addNotification({
      title: 'Account created',
      message: `${payload.full_name} can now log in as a ${payload.role} user.`,
      level: 'success',
      duration: 6000
    });
    setAuthMode('login');
    const form = document.getElementById('auth-form');
    if (form) form.reset();
    return;
  }

  const endpoint = authMode === 'reset' ? '/api/auth/reset-password' : '/api/auth/login';
  const resetPayload = authMode === 'reset' ? { email, role: authRole, new_password: password } : payload;

  if (authMode === 'reset') {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(resetPayload)
      });
      const data = await res.json();
      if (!res.ok || data.status === 'ERROR') {
        showAuthMessage(data.error || 'Password reset failed.', 'error');
        return;
      }
      showAuthMessage('Password reset successful. You can now login with your new password.', 'success');
      setAuthMode('login');
      document.getElementById('auth-password').value = '';
      return;
    } catch (err) {
      showAuthMessage('Could not reach the authentication service. Please try again shortly.', 'error');
      return;
    }
  }

  const localUser = findStoredUser(email, password, authRole);
  if (localUser) {
    currentUserSession = localUser;
    renderLoggedInState(localUser);
    closeAuthModal();
    showAuthMessage('Login successful.', 'success');
    addNotification({
      title: 'Login successful',
      message: `${localUser.full_name} is now active as a ${localUser.role} user.`,
      level: 'success',
      duration: 6000
    });
    return;
  }

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok || data.status === 'ERROR') {
      showAuthMessage(data.error || 'Authentication failed. Please create an account or try a different email/password.', 'error');
      return;
    }

    const user = data.user || payload;
    currentUserSession = user;
    renderLoggedInState(user);
    closeAuthModal();
    showAuthMessage('Login successful.', 'success');
    addNotification({
      title: 'Login successful',
      message: `${user.full_name} is now active as a ${user.role} user.`,
      level: 'success',
      duration: 6000
    });
  } catch (err) {
    console.error('Auth request failed:', err);
    showAuthMessage('Could not reach the authentication service. Please ensure the app backend is running and try again.', 'error');
  }
}

function initializeAuthUI() {
  const modal = document.getElementById('auth-modal');
  const form = document.getElementById('auth-form');

  document.querySelectorAll('.auth-tab').forEach(btn => {
    btn.addEventListener('click', () => setAuthMode(btn.dataset.authTab));
  });
  document.querySelectorAll('.auth-role-btn').forEach(btn => {
    btn.addEventListener('click', () => setAuthRole(btn.dataset.authRole));
  });

  if (form) form.addEventListener('submit', handleAuthSubmit);
  const resetTrigger = document.getElementById('auth-reset-trigger');
  if (resetTrigger) {
    resetTrigger.addEventListener('click', () => {
      setAuthMode(authMode === 'reset' ? 'login' : 'reset');
      if (authMode === 'reset') {
        showAuthMessage('Enter your email and choose a new password.', 'warning');
      }
    });
  }
  if (modal) modal.addEventListener('click', (event) => {
    if (event.target === modal) closeAuthModal();
  });

  setAuthMode('login');
  setAuthRole('citizen');
  currentUserSession = null;
  renderLoggedInState(null);
}

function updateContextualScore(score) {
  const scoreEl = document.getElementById('contextual-escalation-score');
  if (scoreEl) {
    scoreEl.textContent = Number(score || 0).toFixed(2);
  }
}

async function loadUsgsWaterContext() {
  try {
    const res = await fetch('/api/usgs/live-water?site=01646500&parameter=00060');
    const data = await res.json();
    const summaryEl = document.getElementById('metric-threat-summary');
    const siteEl = document.getElementById('usgs-site-name');
    const streamEl = document.getElementById('usgs-streamflow');
    const paramEl = document.getElementById('usgs-parameter');
    const tsEl = document.getElementById('usgs-timestamp');
    const statusEl = document.getElementById('usgs-feed-status');

    if (data.status === 'SUCCESS' && data.value !== null && data.value !== undefined) {
      const unit = data.unit || 'ft3/s';
      const value = Number(data.value ?? 0).toFixed(1);
      if (summaryEl) {
        summaryEl.textContent = `${data.site_name || data.site_code || 'USGS station'}: ${value} ${unit} live streamflow`;
        summaryEl.className = 'ml-1 text-emerald-300';
      }
      if (siteEl) siteEl.textContent = data.site_name || data.site_code || 'USGS station';
      if (streamEl) streamEl.textContent = `${value} ${unit}`;
      if (paramEl) paramEl.textContent = data.parameter_code || '';
      if (tsEl) tsEl.textContent = data.timestamp ? new Date(data.timestamp).toLocaleString() : '';
      if (statusEl) {
        statusEl.textContent = 'LIVE';
        statusEl.className = 'rounded-full border border-emerald-800 bg-emerald-950/40 px-2 py-0.5 text-[9px] font-bold text-emerald-300';
      }
      return;
    }

    if (summaryEl) summaryEl.textContent = '';
    if (siteEl) siteEl.textContent = '';
    if (streamEl) streamEl.textContent = '';
    if (paramEl) paramEl.textContent = '';
    if (tsEl) tsEl.textContent = '';
    if (statusEl) {
      statusEl.textContent = '';
      statusEl.className = 'rounded-full border border-slate-700 bg-slate-950/40 px-2 py-0.5 text-[9px] font-bold text-slate-400';
    }
  } catch (err) {
    const summaryEl = document.getElementById('metric-threat-summary');
    const statusEl = document.getElementById('usgs-feed-status');
    if (summaryEl) summaryEl.textContent = '';
    if (statusEl) {
      statusEl.textContent = '';
      statusEl.className = 'rounded-full border border-slate-700 bg-slate-950/40 px-2 py-0.5 text-[9px] font-bold text-slate-400';
    }
  }
}

async function loadWqpQualityContext() {
  try {
    const res = await fetch('/api/wqp/live-quality?bbox=-74.05,40.70,-73.95,40.80&characteristic=Turbidity');
    const data = await res.json();

    const stationEl = document.getElementById('wqp-station-id');
    const turbidityEl = document.getElementById('wqp-turbidity');
    const characteristicEl = document.getElementById('wqp-characteristic');
    const timestampEl = document.getElementById('wqp-timestamp');
    const statusEl = document.getElementById('wqp-feed-status');
    const clearErrorState = (fallbackMessage = 'WQP data unavailable') => {
      if (stationEl) stationEl.textContent = '—';
      if (turbidityEl) turbidityEl.textContent = fallbackMessage;
      if (characteristicEl) characteristicEl.textContent = 'Turbidity';
      if (timestampEl) timestampEl.textContent = 'n/a';
      if (statusEl) {
        statusEl.textContent = 'ERROR';
        statusEl.className = 'rounded-full border border-red-800 bg-red-950/40 px-2 py-0.5 text-[9px] font-bold text-red-300';
      }
    };

    if (data.status === 'SUCCESS' && data.value !== null && data.value !== undefined) {
      const value = Number(data.value ?? 0).toFixed(2);
      const unit = data.unit || 'NTU';
      if (stationEl) stationEl.textContent = data.station_id || '';
      if (turbidityEl) turbidityEl.textContent = `${value} ${unit}`;
      if (characteristicEl) characteristicEl.textContent = data.characteristic_name || '';
      if (timestampEl) timestampEl.textContent = data.timestamp ? new Date(data.timestamp).toLocaleString() : '';
      if (statusEl) {
        statusEl.textContent = 'LIVE';
        statusEl.className = 'rounded-full border border-emerald-800 bg-emerald-950/40 px-2 py-0.5 text-[9px] font-bold text-emerald-300';
      }
      return;
    }

    if (data && data.message) {
      clearErrorState(data.message);
      return;
    }

    clearErrorState();
  } catch (err) {
    const stationEl = document.getElementById('wqp-station-id');
    const turbidityEl = document.getElementById('wqp-turbidity');
    const characteristicEl = document.getElementById('wqp-characteristic');
    const timestampEl = document.getElementById('wqp-timestamp');
    const statusEl = document.getElementById('wqp-feed-status');
    const message = err && err.message ? err.message : 'Could not reach the WQP service.';

    if (stationEl) stationEl.textContent = '—';
    if (turbidityEl) turbidityEl.textContent = message;
    if (characteristicEl) characteristicEl.textContent = 'Turbidity';
    if (timestampEl) timestampEl.textContent = 'n/a';
    if (statusEl) {
      statusEl.textContent = 'ERROR';
      statusEl.className = 'rounded-full border border-red-800 bg-red-950/40 px-2 py-0.5 text-[9px] font-bold text-red-300';
    }
  }
}

async function submitHouseholdObservation() {
  const text = document.getElementById('household-observation-text');
  const feedback = document.getElementById('observation-feedback');
  if (!text || !text.value.trim()) {
    if (feedback) feedback.textContent = 'Add a note before sending.';
    return;
  }

  const payload = {
    incident_id: `OBS-${Date.now()}`,
    source: 'citizen_observation',
    address: document.getElementById('citizen-address-select')?.value || 'HOUSE-PIN-01',
    note: text.value.trim(),
    timestamp: new Date().toISOString(),
    household_risk_boost: 0.12,
    street: 'Pine Avenue Corridor'
  };

  try {
    const res = await fetch('/api/incidents/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (feedback) {
      feedback.textContent = data.status === 'SUCCESS' ? 'Observation saved to incident archive.' : 'Save failed.';
    }
    if (data.status === 'SUCCESS') {
      const score = Number(document.getElementById('contextual-escalation-score')?.textContent || '0.00');
      updateContextualScore(Math.min(0.99, score + 0.08));
      addNotification({
        title: 'Citizen observation saved',
        message: 'Household report has been archived and included in the risk context.',
        level: 'success',
        duration: 7000
      });
      text.value = '';
    }
  } catch (err) {
    console.error('Observation save failed:', err);
    if (feedback) feedback.textContent = 'Could not save the observation.';
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

  // Resize map to fit available viewport space
  function resizeMapToViewport() {
    try {
      const header = document.querySelector('header');
      const rect = mapElement.getBoundingClientRect();
      const topOffset = (header ? header.getBoundingClientRect().bottom : rect.top) || 0;
      const available = window.innerHeight - topOffset - 40; // 40px bottom padding
      const heightPx = Math.max(360, Math.floor(available));
      mapElement.style.height = `${heightPx}px`;
      if (map) {
        map.invalidateSize();
      }
    } catch (e) {
      console.error('resizeMapToViewport error', e);
    }
  }

  // Initial resize and bind to window changes
  resizeMapToViewport();
  if (map && typeof map.whenReady === 'function') {
    map.whenReady(() => {
      setTimeout(() => resizeMapToViewport(), 120);
    });
  }
  window.addEventListener('resize', () => {
    resizeMapToViewport();
  });
  // Expose for other UI actions that show/hide panels
  window.resizeMapToViewport = resizeMapToViewport;
}

// Fit Map
function fitMapBounds() {
  if (map) {
    map.setView(SECTOR_CENTER, SECTOR_ZOOM);
    // ensure map sizing correct after programmatic pan/zoom
    try { map.invalidateSize(); } catch (e) { }
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
    addNotification({
      title: 'Supply cessation detected',
      message: 'Valve VLV-SEC4-WEST-02 triggered a shutdown; low-pressure ingress risk is now active.',
      level: 'danger',
      duration: 9000
    });
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
    addNotification({
      title: 'System restored',
      message: 'Network pressure has been restored and the incident state was cleared.',
      level: 'success',
      duration: 7000
    });
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

    const latEl = document.getElementById('metric-latency');
    if (latEl) {
      const latency = data && typeof data.execution_latency_ms !== 'undefined' ? data.execution_latency_ms : null;
      latEl.textContent = latency !== null && latency !== undefined ? `${latency} ms` : '';
    }

    const threatScoreEl = document.getElementById('metric-threat-score');
    const threatBadgeEl = document.getElementById('metric-threat-badge');
    const threatSummaryEl = document.getElementById('metric-threat-summary');
    const results = Array.isArray(data && data.results) ? data.results : [];

    if (results.length > 0) {
      const top = results[0];
      if (threatScoreEl) {
        const score = Number(top.intrusion_risk_score ?? 0);
        threatScoreEl.textContent = Number.isFinite(score) ? score.toFixed(2) : '0.00';
        threatScoreEl.className = 'mt-1 text-sm font-black text-rose-400';
      }
      if (threatBadgeEl) {
        const label = top.threat_level || 'HIGH';
        threatBadgeEl.textContent = label;
        threatBadgeEl.className = 'mt-1 text-[10px] px-2 py-1 rounded bg-rose-950 text-rose-400 font-bold border border-rose-800 inline-flex';
      }
      if (threatSummaryEl) {
        const street = top.street || top.sector_id || '';
        const proximity = top.proximity_m ?? null;
        threatSummaryEl.textContent = street ? (proximity !== null && proximity !== undefined ? `${street} (Proximity: ${proximity}m)` : street) : '';
        threatSummaryEl.className = 'ml-1 text-rose-300 font-medium';
      }

      const corridorLengthLabel = document.getElementById('corridor-length-label');
      if (corridorLengthLabel) {
        corridorLengthLabel.textContent = top.corridor_length_m !== null && top.corridor_length_m !== undefined ? `${Number(top.corridor_length_m).toFixed(0)} m` : '';
      }

      if (bufferCorridorLayer && data.corridor_geojson) {
        bufferCorridorLayer.clearLayers();
        bufferCorridorLayer.addData(data.corridor_geojson);
      }

      addNotification({
        title: 'Spatial risk update',
        message: `High intrusion risk corridor detected near ${results[0].water_pipe_id || 'main'} with score ${Number(results[0].intrusion_risk_score || 0).toFixed(2)}.`,
        level: results[0].intrusion_risk_score >= 0.8 ? 'danger' : 'warning',
        duration: 8000
      });

      renderCorridorTable(results);
    } else {
      clearBufferCorridors();
    }

    const sqlContentEl = document.getElementById('modal-sql-content');
    if (sqlContentEl) {
      sqlContentEl.innerHTML = `
        <div class="font-mono text-sky-300">Network topology + valve event stream + asset condition signals are aggregated to highlight vulnerable corridors.</div>
        <div class="text-slate-400">The engine evaluates proximity, pressure loss, and infrastructure condition to prioritize public safety interventions.</div>
        <div class="text-slate-400">Risk outputs are displayed as corridor alerts, municipal dispatch guidance, and household advisories.</div>
      `;
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
    threatBadgeEl.textContent = '';
    threatBadgeEl.className = 'text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300';
  }
  if (threatSummaryEl) {
    threatSummaryEl.textContent = '';
    threatSummaryEl.className = 'text-xs text-slate-400';
  }

  const corridorLengthLabel = document.getElementById('corridor-length-label');
  if (corridorLengthLabel) corridorLengthLabel.textContent = '';

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

  const safeResults = Array.isArray(results) ? results : [];
  let html = `<div class="space-y-2.5">`;
  safeResults.forEach(r => {
    const street = r.street || r.sector_id || '';
    const threatLevel = r.threat_level || '';
    const score = Number(r.intrusion_risk_score ?? 0);
    const proximity = r.proximity_m ?? null;
    const sewerRating = r.pipe_condition_rating ?? null;
    const corridorLength = r.corridor_length_m ?? null;
    const rationale = r.rationale || '';

    html += `
      <div class="bg-slate-950 p-3.5 rounded-xl border border-rose-900/60 flex items-start justify-between">
        <div class="space-y-1">
          <div class="flex items-center space-x-2">
            ${street ? `<span class="text-xs font-bold text-white">${street}</span>` : ''}
            ${threatLevel ? `<span class="text-[10px] px-1.5 py-0.2 rounded bg-rose-950 text-rose-400 font-bold border border-rose-800">${threatLevel}</span>` : ''}
          </div>
          <div class="text-[11px] text-slate-300">
            Water: <strong class="text-sky-400">${r.water_pipe_id || ''}</strong> ${r.sewer_id ? '⟂ Sewer: ' : ''}<strong class="text-amber-400">${r.sewer_id || ''}</strong>
          </div>
          <div class="text-[10px] text-slate-400">
            ${proximity !== null && proximity !== undefined ? `<strong class="text-white">${proximity}m</strong> | ` : ''}
            ${sewerRating !== null && sewerRating !== undefined ? `<strong class="text-rose-400">${sewerRating}/5.0</strong>` : ''}
          </div>
          ${rationale ? `<p class="text-[10px] text-slate-400 italic pt-1">${rationale}</p>` : ''}
        </div>
        <div class="text-right">
          <div class="text-[10px] text-slate-400 uppercase">Intrusion Score</div>
          <div class="text-xl font-black text-rose-400">${Number.isFinite(score) ? score.toFixed(2) : '0.00'}</div>
          ${corridorLength !== null && corridorLength !== undefined ? `<div class="text-[9px] text-slate-500">${corridorLength}m corridor</div>` : ''}
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
  ['severe'].forEach(p => {
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

function showFilterInfo() {
  const panel = document.getElementById('filter-info-panel');
  if (!panel) return;
  panel.classList.toggle('hidden');
  if (window.lucide) lucide.createIcons();
}

// Preset selection
function selectPreset(preset) {
  currentPreset = preset;
  selectedFile = null;

  updatePresetButtons(preset);

  const previewImg = document.getElementById('filter-preview-img');
  if (previewImg) {
    previewImg.removeAttribute('src');
    previewImg.alt = 'No image uploaded';
    previewImg.classList.add('hidden');
  }

  const badge = document.getElementById('active-image-source');
  if (badge) {
    badge.textContent = 'No image uploaded';
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
    if (previewImg) {
      previewImg.src = event.target.result;
      previewImg.classList.remove('hidden');
    }
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
      formData.append('preset', 'custom_upload');
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

    const contextualScore = Number(escData.contextual_escalation_score ?? 0.0);
    const contextualScoreEl = document.getElementById('contextual-escalation-score');
    if (contextualScoreEl) {
      contextualScoreEl.textContent = contextualScore.toFixed(2);
    }

    // Update Tier 1 & Tier 2 messages
    document.getElementById('tier1-message').textContent = escData.tier1_household.message;
    document.getElementById('tier2-message').textContent = escData.tier2_municipal.action_required + " (" + escData.tier2_municipal.defensibility_note + ")";

    addNotification({
      title: 'Escalation triggered',
      message: `${escData.tier1_household.headline} issued for ${addressText}. Municipal dispatch queued.`,
      level: escData.escalation_level && escData.escalation_level.includes('TIER_2') ? 'warning' : 'info',
      duration: 9000
    });

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
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    switchModalTab(tab || 'bigquery');
    lucide.createIcons();
  }
}

function closeArchitectureModal() {
  const modal = document.getElementById('architecture-modal');
  if (modal) {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
  }
  document.body.classList.remove('modal-open');
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

function switchDashboardTab(tabName) {
  ['ingestion', 'risk', 'forensics'].forEach((tab) => {
    const button = document.getElementById(`dashboard-tab-${tab}`);
    const panel = document.getElementById(`dashboard-panel-${tab}`);

    if (button) {
      const isActive = tab === tabName;
      button.classList.toggle('bg-sky-600', isActive);
      button.classList.toggle('text-white', isActive);
      button.classList.toggle('border-sky-500', isActive);
      button.classList.toggle('bg-slate-950', !isActive);
      button.classList.toggle('text-slate-300', !isActive);
      button.classList.toggle('border-slate-800', !isActive);
    }

    if (panel) {
      panel.classList.toggle('hidden', tab !== tabName);
    }
  });

  const leftColumn = document.getElementById('dashboard-left-column');
  const sideColumn = document.getElementById('dashboard-side-column');
  const mainGrid = document.querySelector('main');
  const isForensicsView = tabName === 'forensics';
  const isSideVisible = tabName === 'forensics' || tabName === 'risk';

  if (mainGrid) {
    mainGrid.classList.toggle('lg:grid-cols-1', !isSideVisible);
    mainGrid.classList.toggle('lg:grid-cols-12', isSideVisible);
  }

  if (leftColumn) {
    leftColumn.classList.toggle('lg:col-span-12', !isSideVisible);
    leftColumn.classList.toggle('lg:col-span-7', isSideVisible);
    leftColumn.style.width = !isSideVisible ? '100%' : '';
    leftColumn.style.maxWidth = !isSideVisible ? '100%' : '';
  }

  if (sideColumn) {
    sideColumn.classList.toggle('hidden', !isSideVisible);
    sideColumn.classList.toggle('lg:block', isSideVisible);
    sideColumn.style.display = isSideVisible ? '' : 'none';
  }
  // After switching panels, ensure map is resized when it's visible
  setTimeout(() => {
    try {
      if (window.resizeMapToViewport) window.resizeMapToViewport();
      if (map && typeof map.invalidateSize === 'function') map.invalidateSize();
    } catch (e) { console.error('Error resizing map after tab switch', e); }
  }, 150);
}

// ==================== LIVE DATA INTEGRATIONS ====================

let liveCameraStream = null;
let liveTelemetryTimer = null;
let liveTelemetryInFlight = false;

if (!window.__AQUAVIGIL_LIVE_TICKER__) {
  window.__AQUAVIGIL_LIVE_TICKER__ = { started: false };
}

// 1. Live SCADA Stream Ticker
function startLiveTelemetryTicker() {
  if (window.__AQUAVIGIL_LIVE_TICKER__.started) {
    return;
  }

  if (liveTelemetryTimer) {
    clearInterval(liveTelemetryTimer);
  }

  window.__AQUAVIGIL_LIVE_TICKER__.started = true;
  liveTelemetryTimer = setInterval(async () => {
    if (liveTelemetryInFlight) return;
    liveTelemetryInFlight = true;

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
    } finally {
      liveTelemetryInFlight = false;
    }
  }, 1500);

  window.addEventListener('beforeunload', () => {
    clearInterval(liveTelemetryTimer);
    liveTelemetryTimer = null;
    window.__AQUAVIGIL_LIVE_TICKER__.started = false;
  }, { once: true });
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
    addNotification({
      title: 'Camera unavailable',
      message: err?.message || 'Please allow webcam permission to capture a live filter photo.',
      level: 'warning',
      duration: 6000
    });
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
    img.classList.remove('hidden');

    toggleLiveCamera();
    await executeFilterAnalysis();
  }, 'image/jpeg', 0.9);
}

// 3. Live GPS & Real OpenStreetMap Corridors
function useLiveGpsCorridor() {
  if (!navigator.geolocation) {
    addNotification({
      title: 'Location not supported',
      message: 'Geolocation is not available in this browser.',
      level: 'warning',
      duration: 6000
    });
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
        const osmLabel = document.getElementById('osm-baseline-label');
        if (osmLabel) osmLabel.textContent = `Road corridor: ${data.features.length} ways`;
        const corrLabel = document.getElementById('corridor-length-label');
        if (corrLabel) corrLabel.textContent = `${Math.max(120, data.features.length * 26)} m`;
        addNotification({
          title: 'OSM corridor added',
          message: data.message || `OpenStreetMap baseline loaded for ${lat.toFixed(4)}, ${lon.toFixed(4)}.`,
          level: 'info',
          duration: 7000
        });
      } else {
        const msg = data.message || 'No data available for this location.';
        addNotification({
          title: 'No data available',
          message: msg,
          level: 'warning',
          duration: 8000
        });
      }

      try {
        const elevationRes = await fetch(`https://api.open-elevation.com/api/v1/lookup?locations=${lat},${lon}`);
        const elevationData = await elevationRes.json();
        const elev = elevationData.results && elevationData.results[0] ? elevationData.results[0].elevation : null;
        const elevationEl = document.getElementById('elevation-baseline-label');
        if (elevationEl) {
          elevationEl.textContent = elev !== null ? `${Math.round(elev)} m` : '-- m';
        }
      } catch (e) {
        const elevationEl = document.getElementById('elevation-baseline-label');
        if (elevationEl) elevationEl.textContent = 'Baseline unavailable';
      }

      addNotification({
        title: 'Location mapped',
        message: `Live OpenStreetMap corridors loaded around ${lat.toFixed(4)}, ${lon.toFixed(4)}.`,
        level: 'success',
        duration: 6000
      });
    } catch (e) {
      console.warn("Could not load OSM corridors:", e);
      addNotification({
        title: 'Corridor update failed',
        message: 'The live network corridor could not be loaded. Please try again.',
        level: 'danger',
        duration: 6000
      });
    } finally {
      if (btn) {
        btn.innerHTML = `<i data-lucide="crosshair" class="w-3 h-3"></i><span>Live GPS</span>`;
        lucide.createIcons();
      }
    }
  }, (err) => {
    addNotification({
      title: 'Location unavailable',
      message: err?.message || 'Could not retrieve your live GPS location.',
      level: 'warning',
      duration: 6000
    });
    if (btn) {
      btn.innerHTML = `<i data-lucide="crosshair" class="w-3 h-3"></i><span>Live GPS</span>`;
      lucide.createIcons();
    }
  });
}
