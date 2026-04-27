import {
  POLICY_NAME_PATTERN,
  state
} from './state.js';
import { chip, escapeHtml, fieldBlock, qs } from './dom.js';
import { request, runSingleFlight } from './api.js';
import { sanitizeIdentifier } from './auth.js';
import { renderKioskController } from './kiosk_controller.js';

const policyHooks = {
  setBanner() {},
  addToActivityLog() {},
  loadDashboard() {
    return Promise.resolve();
  },
  requestConfirm() {
    return Promise.resolve(true);
  }
};

const POOL_WIZARD_STEPS = 4;
let poolWizardStep = 1;
let gamingMetricsLoadInFlight = null;
let handoverHistoryLoadInFlight = null;
const poolGpuInventoryHints = {
  mdevTypes: null,
  sriovDevices: null,
  loading: null
};

export function configurePolicies(nextHooks) {
  Object.assign(policyHooks, nextHooks || {});
}

function parseCommaList(rawValue) {
  return String(rawValue || '')
    .split(',')
    .map((item) => String(item || '').trim())
    .filter((item, idx, all) => item && all.indexOf(item) === idx);
}

function parseMinuteList(rawValue) {
  return String(rawValue || '')
    .split(',')
    .map((item) => Number(String(item || '').trim()))
    .filter((item, idx, all) => Number.isFinite(item) && item > 0 && item <= 480 && all.indexOf(item) === idx)
    .sort((a, b) => a - b);
}

function slugToken(rawValue) {
  return String(rawValue || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function normalizedGpuModelToken(rawValue) {
  let text = String(rawValue || '').trim();
  if (!text) {
    return '';
  }
  text = text.replace(/^[0-9a-f:.]+\s+[^:]+:\s*/i, '');
  text = text.replace(/\[[0-9a-f]{4}:[0-9a-f]{4}\]/ig, '');
  text = text.replace(/\(rev[^)]*\)/ig, '');
  text = text.replace(/\bNVIDIA Corporation\b/ig, '');
  text = text.replace(/\bAdvanced Micro Devices, Inc\.\s*\[AMD\/ATI\]\b/ig, '');
  text = text.replace(/\bIntel Corporation\b/ig, '');
  const bracketLabels = Array.from(text.matchAll(/\[([^\]]+)\]/g)).map((match) => String(match[1] || '').trim()).filter(Boolean);
  if (bracketLabels.length) {
    text = bracketLabels[0];
  }
  return slugToken(text);
}

function buildPassthroughGpuClass(item) {
  const vendor = slugToken(item && item.vendor);
  const model = normalizedGpuModelToken(item && item.model);
  return ['passthrough', vendor, model].filter(Boolean).join('-');
}

function poolTypeRequiresGpuClass(poolType) {
  return ['gaming', 'gpu_passthrough'].includes(String(poolType || '').trim());
}

function summarizePoolGpuClassOptions() {
  const overview = state.virtualizationOverview || {};
  const gpus = Array.isArray(overview.gpus) ? overview.gpus : [];
  const byClass = new Map();
  gpus.forEach((item) => {
    const gpuClass = buildPassthroughGpuClass(item);
    if (!gpuClass) {
      return;
    }
    const existing = byClass.get(gpuClass) || {
      value: gpuClass,
      label: gpuClass,
      total: 0,
      ready: 0,
      blocked: 0,
      nodes: new Set(),
      models: new Set(),
    };
    existing.total += 1;
    if (item && item.passthrough_ready) {
      existing.ready += 1;
    } else {
      existing.blocked += 1;
    }
    if (item && item.node) {
      existing.nodes.add(String(item.node).trim());
    }
    if (item && item.model) {
      existing.models.add(String(item.model).trim());
    }
    byClass.set(gpuClass, existing);
  });
  return Array.from(byClass.values()).sort((a, b) => a.value.localeCompare(b.value));
}

export function renderPoolGpuClassOptions() {
  const select = qs('pool-gpu-class');
  const help = qs('pool-gpu-class-help');
  const poolType = String(qs('pool-type') ? qs('pool-type').value : 'desktop').trim() || 'desktop';
  if (!select) {
    return;
  }
  const options = summarizePoolGpuClassOptions();
  const previousValue = String(select.value || '').trim();
  const required = poolTypeRequiresGpuClass(poolType);
  const optionMarkup = [];
  if (!required) {
    optionMarkup.push('<option value="" selected>Keine GPU-Klasse erforderlich</option>');
    select.innerHTML = optionMarkup.join('');
    select.disabled = true;
    if (help) {
      help.textContent = 'Live erkannt: ' + String(options.length) + ' Passthrough-Klassen, '
        + String(Array.isArray(poolGpuInventoryHints.mdevTypes) ? poolGpuInventoryHints.mdevTypes.length : 0) + ' mdev-Typen, '
        + String(Array.isArray(poolGpuInventoryHints.sriovDevices) ? poolGpuInventoryHints.sriovDevices.length : 0) + ' SR-IOV-Geraete.';
    }
    return;
  }
  optionMarkup.push('<option value="">GPU-Klasse aus Live-Inventar waehlen</option>');
  options.forEach((item) => {
    const modelLabel = Array.from(item.models).slice(0, 2).join(' / ') || item.value;
    const hostLabel = item.nodes.size ? (Array.from(item.nodes).join(', ')) : 'ohne Host';
    const statusLabel = item.ready > 0
      ? (String(item.ready) + '/' + String(item.total) + ' bereit')
      : ('aktuell blockiert (' + String(item.blocked) + ')');
    optionMarkup.push(
      '<option value="' + escapeHtml(item.value) + '">' +
      escapeHtml(modelLabel + ' · ' + hostLabel + ' · ' + statusLabel) +
      '</option>'
    );
  });
  select.innerHTML = optionMarkup.join('');
  select.disabled = false;
  const validValues = new Set(options.map((item) => item.value));
  if (previousValue && validValues.has(previousValue)) {
    select.value = previousValue;
  } else if (options.length === 1) {
    select.value = options[0].value;
  } else {
    select.value = '';
  }
  if (help) {
    if (!options.length) {
      help.textContent = 'Keine live erkannte Passthrough-GPU-Klasse gefunden. Details und Ursachen stehen unter /#panel=virtualization.';
      return;
    }
    help.textContent = 'Live erkannt: ' + String(options.length) + ' Passthrough-Klassen, '
      + String(Array.isArray(poolGpuInventoryHints.mdevTypes) ? poolGpuInventoryHints.mdevTypes.length : 0) + ' mdev-Typen, '
      + String(Array.isArray(poolGpuInventoryHints.sriovDevices) ? poolGpuInventoryHints.sriovDevices.length : 0) + ' SR-IOV-Geraete.';
  }
}

function loadPoolGpuInventoryHints() {
  if (!state.token) {
    poolGpuInventoryHints.mdevTypes = null;
    poolGpuInventoryHints.sriovDevices = null;
    poolGpuInventoryHints.loading = null;
    renderPoolGpuClassOptions();
    return Promise.resolve();
  }
  if (poolGpuInventoryHints.loading) {
    return poolGpuInventoryHints.loading;
  }
  poolGpuInventoryHints.loading = Promise.all([
    request('/virtualization/mdev/types').catch(() => ({ mdev_types: [] })),
    request('/virtualization/sriov').catch(() => ({ sriov_devices: [] }))
  ]).then((results) => {
    poolGpuInventoryHints.mdevTypes = Array.isArray(results[0] && results[0].mdev_types) ? results[0].mdev_types : [];
    poolGpuInventoryHints.sriovDevices = Array.isArray(results[1] && results[1].sriov_devices) ? results[1].sriov_devices : [];
    renderPoolGpuClassOptions();
  }).finally(() => {
    poolGpuInventoryHints.loading = null;
  });
  return poolGpuInventoryHints.loading;
}

function collectPoolWizardInput() {
  const poolIdRaw = String(qs('pool-id') ? qs('pool-id').value : '').trim();
  const poolId = poolIdRaw.toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  const templateId = String(qs('pool-template') ? qs('pool-template').value : '').trim();
  const poolType = String(qs('pool-type') ? qs('pool-type').value : 'desktop').trim() || 'desktop';
  const mode = String(qs('pool-mode') ? qs('pool-mode').value : 'floating_non_persistent').trim();
  const storagePool = String(qs('pool-storage') ? qs('pool-storage').value : 'local').trim() || 'local';
  const gpuClass = String(qs('pool-gpu-class') ? qs('pool-gpu-class').value : '').trim();
  const users = parseCommaList(qs('pool-users') ? qs('pool-users').value : '');
  const groups = parseCommaList(qs('pool-groups') ? qs('pool-groups').value : '');
  const sessionExtensionOptions = parseMinuteList(qs('pool-session-extensions') ? qs('pool-session-extensions').value : '');
  const payload = {
    pool_id: poolId,
    template_id: templateId,
    pool_type: poolType,
    mode,
    storage_pool: storagePool,
    gpu_class: gpuClass,
    min_pool_size: Number(qs('pool-min-size') ? qs('pool-min-size').value : '1') || 1,
    max_pool_size: Number(qs('pool-max-size') ? qs('pool-max-size').value : '5') || 5,
    warm_pool_size: Number(qs('pool-warm-size') ? qs('pool-warm-size').value : '2') || 2,
    cpu_cores: Number(qs('pool-cpu') ? qs('pool-cpu').value : '2') || 2,
    memory_mib: Number(qs('pool-memory') ? qs('pool-memory').value : '4096') || 4096,
    session_time_limit_minutes: Number(qs('pool-session-time-limit') ? qs('pool-session-time-limit').value : '0') || 0,
    session_cost_per_minute: Number(qs('pool-session-cost') ? qs('pool-session-cost').value : '0') || 0,
    session_extension_options_minutes: poolType === 'kiosk' ? sessionExtensionOptions : [],
    session_recording: String(qs('pool-session-recording') ? qs('pool-session-recording').value : 'disabled').trim() || 'disabled',
    recording_retention_days: Number(qs('pool-recording-retention-days') ? qs('pool-recording-retention-days').value : '30') || 30,
    recording_watermark_enabled: String(qs('pool-recording-watermark-enabled') ? qs('pool-recording-watermark-enabled').value : 'false').trim().toLowerCase() === 'true',
    recording_watermark_custom_text: String(qs('pool-recording-watermark-custom-text') ? qs('pool-recording-watermark-custom-text').value : '').trim(),
    streaming_profile: {
      encoder: String(qs('pool-stream-encoder') ? qs('pool-stream-encoder').value : 'auto').trim() || 'auto',
      color: String(qs('pool-stream-color') ? qs('pool-stream-color').value : 'h265').trim() || 'h265',
      bitrate_kbps: Number(qs('pool-stream-bitrate') ? qs('pool-stream-bitrate').value : '20000') || 20000,
      fps: Number(qs('pool-stream-fps') ? qs('pool-stream-fps').value : '60') || 60,
      resolution: String(qs('pool-stream-resolution') ? qs('pool-stream-resolution').value : '1920x1080').trim() || '1920x1080',
      hdr: Boolean(qs('pool-stream-hdr') ? qs('pool-stream-hdr').checked : false),
      audio_input_enabled: Boolean(qs('pool-stream-audio-input') ? qs('pool-stream-audio-input').checked : false),
      gamepad_redirect_enabled: Boolean(qs('pool-stream-gamepad') ? qs('pool-stream-gamepad').checked : false),
      wacom_tablet_enabled: Boolean(qs('pool-stream-wacom') ? qs('pool-stream-wacom').checked : false),
      usb_redirect_enabled: Boolean(qs('pool-stream-usb-redirect') ? qs('pool-stream-usb-redirect').checked : false)
    }
  };
  return { payload, users, groups };
}

function validatePoolWizardStep(step, payload) {
  if (step >= 1) {
    if (!payload.pool_id) {
      return 'Pool-ID ist erforderlich.';
    }
    if (!payload.template_id) {
      return 'Template ist erforderlich.';
    }
  }
  if (step >= 2) {
    if (payload.pool_type === 'gaming' && !payload.gpu_class) {
      return 'Gaming-Pools brauchen eine GPU-Klasse.';
    }
    if (payload.pool_type === 'kiosk' && Number(payload.session_time_limit_minutes) <= 0) {
      return 'Kiosk-Pools brauchen ein Session-Limit > 0 Minuten.';
    }
    if (payload.pool_type === 'kiosk' && (!Array.isArray(payload.session_extension_options_minutes) || !payload.session_extension_options_minutes.length)) {
      return 'Kiosk-Pools brauchen mindestens eine Verlaengerungsstufe.';
    }
    if (payload.max_pool_size < payload.min_pool_size) {
      return 'Max-Groesse muss >= Min-Groesse sein.';
    }
    if (payload.warm_pool_size > payload.max_pool_size) {
      return 'Warm-Pool darf nicht groesser als Max-Groesse sein.';
    }
    if (!/^\d{3,5}x\d{3,5}$/.test(String(payload.streaming_profile && payload.streaming_profile.resolution ? payload.streaming_profile.resolution : '').trim())) {
      return 'Streaming-Resolution muss als WIDTHxHEIGHT gesetzt sein.';
    }
    if (Number(payload.streaming_profile && payload.streaming_profile.bitrate_kbps) < 2000) {
      return 'Streaming-Bitrate muss mindestens 2000 Kbps betragen.';
    }
    if (Number(payload.streaming_profile && payload.streaming_profile.fps) < 24) {
      return 'Streaming-FPS muessen mindestens 24 betragen.';
    }
  }
  return '';
}

function renderPoolWizardSummary() {
  const node = qs('pool-wizard-summary');
  if (!node) {
    return;
  }
  const values = collectPoolWizardInput();
  const payload = values.payload;
  const users = values.users;
  const groups = values.groups;
  const error = validatePoolWizardStep(3, payload);
  if (error) {
    node.innerHTML = '<div class="banner warn">' + escapeHtml(error) + '</div>';
    return;
  }
  node.innerHTML =
    '<div class="detail-grid">' +
    fieldBlock('Template', payload.template_id || '-') +
    fieldBlock('Pool ID', payload.pool_id || '-') +
    fieldBlock('Pool-Typ', payload.pool_type || '-') +
    fieldBlock('Modus', payload.mode || '-') +
    fieldBlock('GPU-Klasse', payload.gpu_class || '-') +
    fieldBlock('Storage', payload.storage_pool || '-') +
    fieldBlock('Min/Max/Warm', String(payload.min_pool_size) + ' / ' + String(payload.max_pool_size) + ' / ' + String(payload.warm_pool_size)) +
    fieldBlock('CPU / RAM', String(payload.cpu_cores) + ' vCPU / ' + String(payload.memory_mib) + ' MiB') +
    fieldBlock('Session-Limit', payload.session_time_limit_minutes > 0 ? String(payload.session_time_limit_minutes) + ' Minuten' : 'unbegrenzt') +
    fieldBlock('Kosten / Minute', Number(payload.session_cost_per_minute || 0).toFixed(2)) +
    fieldBlock('Verlaengerungen', Array.isArray(payload.session_extension_options_minutes) && payload.session_extension_options_minutes.length ? payload.session_extension_options_minutes.join(', ') + ' Minuten' : '-') +
    fieldBlock('Session Recording', String(payload.session_recording || 'disabled')) +
    fieldBlock('Retention', String(payload.recording_retention_days || 30) + ' Tage') +
    fieldBlock('Watermark', (payload.recording_watermark_enabled ? 'enabled' : 'disabled') + (payload.recording_watermark_custom_text ? ' / ' + payload.recording_watermark_custom_text : '')) +
    fieldBlock('Streaming', String(payload.streaming_profile.encoder || '-') + ' / ' + String(payload.streaming_profile.color || '-') + ' / ' + String(payload.streaming_profile.resolution || '-')) +
    fieldBlock('Bitrate / FPS / HDR', String(payload.streaming_profile.bitrate_kbps || '-') + ' Kbps / ' + String(payload.streaming_profile.fps || '-') + ' fps / ' + (payload.streaming_profile.hdr ? 'on' : 'off')) +
    fieldBlock('Audio / Gamepad', (payload.streaming_profile.audio_input_enabled ? 'audio' : '-') + ' / ' + (payload.streaming_profile.gamepad_redirect_enabled ? 'gamepad' : '-')) +
    fieldBlock('Wacom / USB', (payload.streaming_profile.wacom_tablet_enabled ? 'wacom' : '-') + ' / ' + (payload.streaming_profile.usb_redirect_enabled ? 'usb' : '-')) +
    fieldBlock('Users', users.length ? users.join(', ') : '-') +
    fieldBlock('Groups', groups.length ? groups.join(', ') : '-') +
    '</div>';
}

function renderPoolWizardStepUi() {
  const current = Number(poolWizardStep) || 1;
  const panels = document.querySelectorAll('[data-pool-step]');
  panels.forEach((panel) => {
    const step = Number(panel.getAttribute('data-pool-step') || 0);
    panel.hidden = step !== current;
  });
  for (let idx = 1; idx <= POOL_WIZARD_STEPS; idx += 1) {
    const btn = qs('pool-step-btn-' + idx);
    if (!btn) {
      continue;
    }
    btn.classList.toggle('is-active', idx === current);
    btn.classList.toggle('is-complete', idx < current);
  }
  const prevBtn = qs('pool-wizard-prev');
  const nextBtn = qs('pool-wizard-next');
  const createBtn = qs('pool-create');
  if (prevBtn) {
    prevBtn.disabled = current <= 1;
  }
  if (nextBtn) {
    nextBtn.hidden = current >= POOL_WIZARD_STEPS;
  }
  if (createBtn) {
    createBtn.hidden = current < POOL_WIZARD_STEPS;
  }
  if (current >= POOL_WIZARD_STEPS) {
    renderPoolWizardSummary();
  }
}

export function setPoolWizardStep(nextStep) {
  const clamped = Math.max(1, Math.min(POOL_WIZARD_STEPS, Number(nextStep) || 1));
  poolWizardStep = clamped;
  renderPoolWizardStepUi();
}

export function nextPoolWizardStep() {
  const values = collectPoolWizardInput();
  const payload = values.payload;
  const error = validatePoolWizardStep(poolWizardStep, payload);
  if (error) {
    policyHooks.setBanner(error, 'warn');
    return;
  }
  setPoolWizardStep(poolWizardStep + 1);
}

export function prevPoolWizardStep() {
  setPoolWizardStep(poolWizardStep - 1);
}

function renderPoolTemplateOptions() {
  const select = qs('pool-template');
  if (!select) {
    return;
  }
  const templates = Array.isArray(state.poolTemplates) ? state.poolTemplates : [];
  if (!templates.length) {
    select.innerHTML = '<option value="">Keine Templates gefunden</option>';
    return;
  }
  select.innerHTML = templates.map((item) => {
    const id = String(item.template_id || '').trim();
    const name = String(item.template_name || id || 'template').trim();
    const selected = state.selectedTemplateId && state.selectedTemplateId === id ? ' selected' : '';
    return '<option value="' + escapeHtml(id) + '"' + selected + '>' + escapeHtml(name + ' (' + id + ')') + '</option>';
  }).join('');
  if (!state.selectedTemplateId) {
    state.selectedTemplateId = String(templates[0].template_id || '').trim();
    select.value = state.selectedTemplateId;
  }
}

function renderPoolOverviewSelect() {
  const select = qs('pool-overview-select');
  if (!select) {
    return;
  }
  const pools = Array.isArray(state.desktopPools) ? state.desktopPools : [];
  if (!pools.length) {
    select.innerHTML = '<option value="">Keine Pools</option>';
    state.selectedPoolId = '';
    return;
  }
  if (!state.selectedPoolId || !pools.some((item) => String(item.pool_id || '').trim() === state.selectedPoolId)) {
    state.selectedPoolId = String(pools[0].pool_id || '').trim();
  }
  select.innerHTML = pools.map((item) => {
    const poolId = String(item.pool_id || '').trim();
    const selected = state.selectedPoolId === poolId ? ' selected' : '';
    return '<option value="' + escapeHtml(poolId) + '"' + selected + '>' + escapeHtml(poolId) + '</option>';
  }).join('');
}

function renderPoolsList() {
  const node = qs('pools-list');
  if (!node) {
    return;
  }
  const pools = Array.isArray(state.desktopPools) ? state.desktopPools : [];
  if (!pools.length) {
    node.innerHTML = '<div class="empty-card">Keine Pools geladen.</div>';
    return;
  }
  node.innerHTML = pools.map((pool) => {
    const poolId = String(pool.pool_id || '').trim();
    const mode = String(pool.mode || 'unknown').trim();
    const poolType = String(pool.pool_type || 'desktop').trim();
    const stream = pool.streaming_profile && typeof pool.streaming_profile === 'object' ? pool.streaming_profile : null;
    const sessionRecording = String(pool.session_recording || 'disabled').trim() || 'disabled';
    const retentionDays = Number(pool.recording_retention_days || 30) || 30;
    const timeLimit = Number(pool.session_time_limit_minutes || 0) || 0;
    const watermarkEnabled = !!pool.recording_watermark_enabled;
    const watermarkCustom = String(pool.recording_watermark_custom_text || '').trim();
    const streamSummary = stream
      ? String(stream.encoder || 'auto') + ' / ' + String(stream.color || 'h265') + ' / ' + String(stream.resolution || '1920x1080')
      : 'default';
    const selectedClass = state.selectedPoolId === poolId ? ' active' : '';
    return '<article class="policy-card' + selectedClass + '" data-pool-id="' + escapeHtml(poolId) + '">' +
      '<div class="policy-head"><strong>' + escapeHtml(poolId) + '</strong>' + chip(poolType, 'muted') + chip(mode, 'muted') + '</div>' +
      '<div class="pool-card-meta">' +
      fieldBlock('Template', String(pool.template_id || '-'), 'mono') +
      fieldBlock('Warm/Max', String(pool.warm_pool_size || 0) + ' / ' + String(pool.max_pool_size || 0)) +
      fieldBlock('Session-Limit', timeLimit > 0 ? String(timeLimit) + ' Min' : 'unbegrenzt') +
      fieldBlock('Verlaengerungen', Array.isArray(pool.session_extension_options_minutes) && pool.session_extension_options_minutes.length ? pool.session_extension_options_minutes.join(', ') + ' Min' : '-') +
      fieldBlock('Recording', sessionRecording) +
      fieldBlock('Retention', String(retentionDays) + ' Tage') +
      fieldBlock('Watermark', (watermarkEnabled ? 'enabled' : 'disabled') + (watermarkCustom ? ' / ' + watermarkCustom : '')) +
      fieldBlock('Streaming', streamSummary) +
      '</div>' +
      '</article>';
  }).join('');
}

function renderPoolOverviewBody() {
  const body = qs('pool-overview-body');
  const statsNode = qs('pool-overview-stats');

  function renderStats(counts) {
    if (!statsNode) {
      return;
    }
    statsNode.innerHTML =
      '<span class="chip muted">free ' + String(counts.free || 0) + '</span>' +
      '<span class="chip ' + ((counts.in_use || 0) ? 'ok' : 'muted') + '">in_use ' + String(counts.in_use || 0) + '</span>' +
      '<span class="chip ' + ((counts.recycling || 0) ? 'warn' : 'muted') + '">recycling ' + String(counts.recycling || 0) + '</span>' +
      '<span class="chip ' + ((counts.error || 0) ? 'danger' : 'muted') + '">error ' + String(counts.error || 0) + '</span>';
  }

  if (!body) {
    return;
  }
  if (!state.selectedPoolId) {
    body.innerHTML = '<tr><td colspan="4" class="empty-cell">Kein Pool ausgewaehlt.</td></tr>';
    renderStats({ free: 0, in_use: 0, recycling: 0, error: 0 });
    return;
  }
  const vmRows = (state.poolVmStates && state.poolVmStates[state.selectedPoolId]) || [];
  if (!Array.isArray(vmRows) || !vmRows.length) {
    body.innerHTML = '<tr><td colspan="4" class="empty-cell">Keine VM-Slots fuer diesen Pool.</td></tr>';
    renderStats({ free: 0, in_use: 0, recycling: 0, error: 0 });
    return;
  }
  const counts = { free: 0, in_use: 0, recycling: 0, error: 0 };
  body.innerHTML = vmRows.map((row) => {
    const vmid = Number(row.vmid || 0);
    const userId = String(row.user_id || '-').trim() || '-';
    const status = String(row.state || 'unknown').trim();
    const assignedAt = String(row.assigned_at || '').trim();
    if (Object.prototype.hasOwnProperty.call(counts, status)) {
      counts[status] += 1;
    }
    const tone = status === 'in_use' ? 'ok' : status === 'recycling' ? 'warn' : 'muted';
    return '<tr class="pool-overview-row"><td>' + escapeHtml(String(vmid || '-')) + '</td><td>' + escapeHtml(userId) + '</td><td>' + chip(status, tone) + '</td><td>' + escapeHtml(assignedAt || '-') + '</td></tr>';
  }).join('');
  renderStats(counts);
}

function refreshSelectedPoolOverview() {
  if (!state.selectedPoolId) {
    renderPoolOverviewBody();
    return Promise.resolve();
  }
  return request('/pools/' + encodeURIComponent(state.selectedPoolId) + '/vms').then((payload) => {
    if (!state.poolVmStates || typeof state.poolVmStates !== 'object') {
      state.poolVmStates = Object.create(null);
    }
    state.poolVmStates[state.selectedPoolId] = Array.isArray(payload.vms) ? payload.vms : [];
    renderPoolOverviewBody();
  }).catch((error) => {
    renderPoolOverviewBody();
    policyHooks.setBanner('Pool-Status konnte nicht geladen werden: ' + error.message, 'warn');
  });
}

function formatMetricNumber(value, digits) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return '-';
  }
  return digits > 0 ? num.toFixed(digits) : String(Math.round(num));
}

function formatHandoverDuration(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return '-';
  }
  return num.toFixed(2) + ' s';
}

function formatHandoverTimestamp(value) {
  const text = String(value || '').trim();
  if (!text) {
    return '-';
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
}

function buildTrendSvg(points, valueKey, strokeClass) {
  const items = Array.isArray(points) ? points : [];
  if (!items.length) {
    return '<div class="empty-card">Noch keine Trenddaten.</div>';
  }
  const values = items.map((item) => Number(item && item[valueKey])).filter((value) => Number.isFinite(value));
  if (!values.length) {
    return '<div class="empty-card">Noch keine Trenddaten.</div>';
  }
  const min = Math.min.apply(null, values);
  const max = Math.max.apply(null, values);
  const width = 360;
  const height = 120;
  const spread = Math.max(1, max - min);
  const coords = items.map((item, idx) => {
    const value = Number(item && item[valueKey]);
    const x = items.length <= 1 ? width / 2 : (idx * (width - 16) / (items.length - 1)) + 8;
    const y = Number.isFinite(value)
      ? height - 10 - (((value - min) / spread) * (height - 28))
      : height - 10;
    return String(Math.round(x)) + ',' + String(Math.round(y));
  }).join(' ');
  const labels = items.map((item) => '<span>' + escapeHtml(String(item && item.label ? item.label : '-')) + '</span>').join('');
  return '<div class="gaming-trend-card">' +
    '<svg class="gaming-trend-svg" viewBox="0 0 ' + String(width) + ' ' + String(height) + '" role="img" aria-label="' + escapeHtml(valueKey) + ' trend">' +
    '<polyline class="gaming-trend-line ' + escapeHtml(strokeClass) + '" points="' + escapeHtml(coords) + '"></polyline>' +
    '</svg>' +
    '<div class="gaming-trend-labels">' + labels + '</div>' +
    '</div>';
}

export function renderGamingMetricsDashboard() {
  const node = qs('gaming-metrics-dashboard');
  if (!node) {
    return;
  }
  if (!state.token) {
    node.innerHTML = '<div class="empty-card">Anmeldung erforderlich.</div>';
    return;
  }
  const payload = state.gamingMetrics;
  if (!payload || typeof payload !== 'object') {
    node.innerHTML = '<div class="empty-card">Noch keine Gaming-Metriken geladen.</div>';
    return;
  }
  const overview = payload.overview && typeof payload.overview === 'object' ? payload.overview : {};
  const activeSessions = Array.isArray(payload.active_sessions) ? payload.active_sessions : [];
  const recentReports = Array.isArray(payload.recent_reports) ? payload.recent_reports : [];
  const trend = Array.isArray(payload.trend) ? payload.trend : [];
  const activeHtml = activeSessions.length
    ? '<div class="gaming-metrics-session-list">' + activeSessions.map((item) => {
      const latest = item.latest_sample && typeof item.latest_sample === 'object' ? item.latest_sample : {};
      const alerts = Array.isArray(item.alerts) ? item.alerts : [];
      return '<article class="gaming-session-card">' +
        '<div class="policy-head"><strong>' + escapeHtml(String(item.pool_id || '-')) + ' / VM ' + escapeHtml(String(item.vmid || '-')) + '</strong>' +
        chip(String(item.user_id || '-'), 'muted') + '</div>' +
        '<div class="detail-grid">' +
        fieldBlock('FPS', formatMetricNumber(latest.fps, 0)) +
        fieldBlock('RTT', formatMetricNumber(latest.rtt_ms, 0) + ' ms') +
        fieldBlock('GPU', formatMetricNumber(latest.gpu_util_pct, 0) + ' %') +
        fieldBlock('GPU Temp', formatMetricNumber(latest.gpu_temp_c, 0) + ' C') +
        fieldBlock('Encoder', formatMetricNumber(latest.encoder_util_pct, 0) + ' %') +
        fieldBlock('Samples', formatMetricNumber(item.sample_count, 0)) +
        '</div>' +
        (alerts.length ? '<div class="gaming-alert-list">' + alerts.map((alert) => chip(alert, 'warn')).join('') + '</div>' : '') +
        '</article>';
    }).join('') + '</div>'
    : '<div class="empty-card">Keine aktiven Gaming-Sessions.</div>';
  const recentRows = recentReports.length
    ? recentReports.slice(0, 8).map((item) => '<tr>' +
      '<td class="mono">' + escapeHtml(String(item.session_id || '-')) + '</td>' +
      '<td>' + escapeHtml(String(item.pool_id || '-')) + '</td>' +
      '<td>' + escapeHtml(formatMetricNumber(item.avg_fps, 1)) + '</td>' +
      '<td>' + escapeHtml(formatMetricNumber(item.avg_rtt_ms, 2)) + ' ms</td>' +
      '<td>' + escapeHtml(formatMetricNumber(item.max_gpu_temp_c, 1)) + ' C</td>' +
      '</tr>').join('')
    : '';
  node.innerHTML =
    '<div class="detail-grid gaming-kpi-grid">' +
    fieldBlock('Aktiv', formatMetricNumber(overview.active_sessions, 0)) +
    fieldBlock('Alerts', formatMetricNumber(overview.alert_count_active, 0)) +
    fieldBlock('Avg FPS', formatMetricNumber(overview.avg_fps_recent, 1)) +
    fieldBlock('Avg RTT', formatMetricNumber(overview.avg_rtt_ms_recent, 2) + ' ms') +
    fieldBlock('Peak GPU Temp', formatMetricNumber(overview.max_gpu_temp_c_recent, 1) + ' C') +
    fieldBlock('Reports', formatMetricNumber(overview.recent_sessions, 0)) +
    '</div>' +
    '<div class="gaming-metrics-trends">' +
    '<section class="gaming-metrics-trend-panel"><h3>FPS</h3>' + buildTrendSvg(trend, 'avg_fps', 'tone-fps') + '</section>' +
    '<section class="gaming-metrics-trend-panel"><h3>RTT</h3>' + buildTrendSvg(trend, 'avg_rtt_ms', 'tone-rtt') + '</section>' +
    '<section class="gaming-metrics-trend-panel"><h3>GPU Temp</h3>' + buildTrendSvg(trend, 'max_gpu_temp_c', 'tone-temp') + '</section>' +
    '</div>' +
    '<section class="panel-section section-spaced-tight"><h3>Aktive Gaming-Sessions</h3>' + activeHtml + '</section>' +
    '<section class="panel-section section-spaced-tight"><h3>Letzte Session-Reports</h3>' +
    (recentRows
      ? '<div class="table-wrap compact"><table class="vm-table compact-table"><thead><tr><th>Session</th><th>Pool</th><th>Avg FPS</th><th>Avg RTT</th><th>Peak GPU Temp</th></tr></thead><tbody>' + recentRows + '</tbody></table></div>'
      : '<div class="empty-card">Noch keine abgeschlossenen Gaming-Reports.</div>') +
    '</section>';
}

export function renderSessionHandoverDashboard() {
  const node = qs('session-handover-dashboard');
  if (!node) {
    return;
  }
  if (!state.token) {
    node.innerHTML = '<div class="empty-card">Anmeldung erforderlich.</div>';
    return;
  }
  const payload = state.handoverHistory;
  if (!payload || typeof payload !== 'object') {
    node.innerHTML = '<div class="empty-card">Noch keine Session-Handover-Daten geladen.</div>';
    return;
  }
  const events = Array.isArray(payload.events) ? payload.events : [];
  const alerts = Array.isArray(payload.alerts) ? payload.alerts : [];
  const completed = events.filter((item) => String(item && item.status || '').trim() === 'completed');
  const failed = events.filter((item) => String(item && item.status || '').trim() === 'failed');
  const avgDuration = completed.length
    ? (completed.reduce((sum, item) => sum + (Number(item && item.duration_seconds) || 0), 0) / completed.length)
    : NaN;
  const latestCompleted = completed.length ? completed[0] : null;
  const eventRows = events.length
    ? events.slice(0, 10).map((item) => {
      const status = String(item && item.status || '-').trim() || '-';
      const tone = status === 'completed' ? 'ok' : status === 'failed' ? 'danger' : 'muted';
      const route = [String(item && item.source_node || '-').trim() || '-', String(item && item.target_node || '-').trim() || '-'].join(' -> ');
      return '<tr>' +
        '<td class="mono">' + escapeHtml(String(item && item.session_id || '-')) + '</td>' +
        '<td>' + escapeHtml(String(item && item.user_id || '-')) + '</td>' +
        '<td>' + chip(status, tone) + '</td>' +
        '<td>' + escapeHtml(route) + '</td>' +
        '<td>' + escapeHtml(formatHandoverDuration(item && item.duration_seconds)) + '</td>' +
        '<td>' + escapeHtml(formatHandoverTimestamp(item && (item.completed_at || item.started_at))) + '</td>' +
        '</tr>';
    }).join('')
    : '';
  const alertCards = alerts.length
    ? '<div class="handover-alert-list">' + alerts.slice(0, 6).map((item) => {
      const threshold = Number(item && item.threshold);
      const currentValue = Number(item && item.current_value);
      return '<article class="handover-alert-card">' +
        '<div class="policy-head"><strong>' + escapeHtml(String(item && item.session_id || '-')) + '</strong>' + chip(String(item && item.severity || 'warning'), 'warn') + '</div>' +
        '<div class="detail-grid">' +
        fieldBlock('User', String(item && item.user_id || '-')) +
        fieldBlock('Metrik', String(item && item.metric || '-')) +
        fieldBlock('Ist', Number.isFinite(currentValue) ? currentValue.toFixed(2) : '-') +
        fieldBlock('Schwelle', Number.isFinite(threshold) ? threshold.toFixed(2) : '-') +
        fieldBlock('Ausgeloest', formatHandoverTimestamp(item && item.fired_at)) +
        '</div>' +
        '<p class="handover-alert-message">' + escapeHtml(String(item && item.message || '-')) + '</p>' +
        '</article>';
      }).join('') + '</div>'
    : '<div class="empty-card">Keine Slow-Handover-Alerts.</div>';
  node.innerHTML =
    '<div class="detail-grid gaming-kpi-grid">' +
    fieldBlock('Events', String(events.length)) +
    fieldBlock('Completed', String(completed.length)) +
    fieldBlock('Failed', String(failed.length)) +
    fieldBlock('Alerts', String(alerts.length)) +
    fieldBlock('Avg Dauer', formatHandoverDuration(avgDuration)) +
    fieldBlock('Letzte Route', latestCompleted ? (String(latestCompleted.source_node || '-') + ' -> ' + String(latestCompleted.target_node || '-')) : '-') +
    '</div>' +
    '<section class="panel-section section-spaced-tight"><h3>Slow-Handover-Alerts</h3>' + alertCards + '</section>' +
    '<section class="panel-section section-spaced-tight"><h3>Letzte Handover-Events</h3>' +
    (eventRows
      ? '<div class="table-wrap compact"><table class="vm-table compact-table"><thead><tr><th>Session</th><th>User</th><th>Status</th><th>Route</th><th>Dauer</th><th>Zeit</th></tr></thead><tbody>' + eventRows + '</tbody></table></div>'
      : '<div class="empty-card">Noch keine Handover-Events.</div>') +
    '</section>';
}

export function refreshGamingMetricsDashboard(force) {
  if (!state.token) {
    state.gamingMetrics = null;
    renderGamingMetricsDashboard();
    return Promise.resolve();
  }
  if (gamingMetricsLoadInFlight && !force) {
    return gamingMetricsLoadInFlight;
  }
  gamingMetricsLoadInFlight = request('/gaming/metrics', { __suppressAuthLock: true }).then((payload) => {
    state.gamingMetrics = payload;
    renderGamingMetricsDashboard();
    return payload;
  }).catch((error) => {
    state.gamingMetrics = {
      error: error.message,
      overview: {},
      active_sessions: [],
      recent_reports: [],
      trend: []
    };
    const node = qs('gaming-metrics-dashboard');
    if (node) {
      node.innerHTML = '<div class="empty-card">Gaming-Metriken konnten nicht geladen werden: ' + escapeHtml(error.message) + '</div>';
    }
    throw error;
  }).finally(() => {
    gamingMetricsLoadInFlight = null;
  });
  return gamingMetricsLoadInFlight;
}

export function refreshSessionHandoverDashboard(force) {
  if (!state.token) {
    state.handoverHistory = null;
    renderSessionHandoverDashboard();
    return Promise.resolve();
  }
  if (handoverHistoryLoadInFlight && !force) {
    return handoverHistoryLoadInFlight;
  }
  handoverHistoryLoadInFlight = request('/sessions/handover', { __suppressAuthLock: true }).then((payload) => {
    state.handoverHistory = payload;
    renderSessionHandoverDashboard();
    return payload;
  }).catch((error) => {
    state.handoverHistory = {
      error: error.message,
      events: [],
      alerts: []
    };
    const node = qs('session-handover-dashboard');
    if (node) {
      node.innerHTML = '<div class="empty-card">Session-Handover-Daten konnten nicht geladen werden: ' + escapeHtml(error.message) + '</div>';
    }
    throw error;
  }).finally(() => {
    handoverHistoryLoadInFlight = null;
  });
  return handoverHistoryLoadInFlight;
}

export function refreshPoolOverview() {
  return refreshSelectedPoolOverview();
}

export function refreshPoolData() {
  return Promise.all([
    request('/pools').catch(() => ({ pools: [] })),
    request('/pool-templates').catch(() => ({ templates: [] }))
  ]).then((results) => {
    state.desktopPools = Array.isArray(results[0] && results[0].pools) ? results[0].pools : [];
    state.poolTemplates = Array.isArray(results[1] && results[1].templates) ? results[1].templates : [];
    renderPoolTemplateOptions();
    renderPoolOverviewSelect();
    renderPoolsList();
    return refreshSelectedPoolOverview();
  });
}

export function selectPool(poolId) {
  state.selectedPoolId = String(poolId || '').trim();
  renderPoolOverviewSelect();
  renderPoolsList();
  refreshSelectedPoolOverview();
}

export function resetPoolWizard() {
  if (qs('pool-id')) {
    qs('pool-id').value = '';
  }
  if (qs('pool-mode')) {
    qs('pool-mode').value = 'floating_non_persistent';
  }
  if (qs('pool-type')) {
    qs('pool-type').value = 'desktop';
  }
  if (qs('pool-gpu-class')) {
    qs('pool-gpu-class').innerHTML = '<option value="">Keine GPU-Klasse erforderlich</option>';
    qs('pool-gpu-class').value = '';
  }
  if (qs('pool-storage')) {
    qs('pool-storage').value = 'local';
  }
  if (qs('pool-min-size')) {
    qs('pool-min-size').value = '1';
  }
  if (qs('pool-max-size')) {
    qs('pool-max-size').value = '5';
  }
  if (qs('pool-warm-size')) {
    qs('pool-warm-size').value = '2';
  }
  if (qs('pool-cpu')) {
    qs('pool-cpu').value = '2';
  }
  if (qs('pool-memory')) {
    qs('pool-memory').value = '4096';
  }
  if (qs('pool-session-time-limit')) {
    qs('pool-session-time-limit').value = '0';
  }
  if (qs('pool-session-cost')) {
    qs('pool-session-cost').value = '0';
  }
  if (qs('pool-session-extensions')) {
    qs('pool-session-extensions').value = '15,30,60';
  }
  if (qs('pool-users')) {
    qs('pool-users').value = '';
  }
  if (qs('pool-groups')) {
    qs('pool-groups').value = '';
  }
  if (qs('pool-stream-encoder')) {
    qs('pool-stream-encoder').value = 'auto';
  }
  if (qs('pool-stream-color')) {
    qs('pool-stream-color').value = 'h265';
  }
  if (qs('pool-stream-bitrate')) {
    qs('pool-stream-bitrate').value = '20000';
  }
  if (qs('pool-stream-fps')) {
    qs('pool-stream-fps').value = '60';
  }
  if (qs('pool-stream-resolution')) {
    qs('pool-stream-resolution').value = '1920x1080';
  }
  if (qs('pool-stream-hdr')) {
    qs('pool-stream-hdr').checked = false;
  }
  if (qs('pool-stream-audio-input')) {
    qs('pool-stream-audio-input').checked = false;
  }
  if (qs('pool-stream-gamepad')) {
    qs('pool-stream-gamepad').checked = false;
  }
  if (qs('pool-stream-wacom')) {
    qs('pool-stream-wacom').checked = false;
  }
  if (qs('pool-stream-usb-redirect')) {
    qs('pool-stream-usb-redirect').checked = false;
  }
  poolWizardStep = 1;
  renderPoolTemplateOptions();
  renderPoolGpuClassOptions();
  renderPoolWizardSummary();
  renderPoolWizardStepUi();
}

export function createPoolFromWizard() {
  const values = collectPoolWizardInput();
  const payload = values.payload;
  const users = values.users;
  const groups = values.groups;
  const error = validatePoolWizardStep(3, payload);
  if (error) {
    policyHooks.setBanner(error, 'warn');
    return;
  }
  runSingleFlight('pool-create:' + payload.pool_id, () => {
    policyHooks.setBanner('Pool ' + payload.pool_id + ' wird erstellt ...', 'info');
    return request('/pools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(() => {
      if (!users.length && !groups.length) {
        return null;
      }
      return request('/pools/' + encodeURIComponent(payload.pool_id) + '/entitlements', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ users, groups })
      });
    }).then(() => {
      state.selectedPoolId = payload.pool_id;
      policyHooks.addToActivityLog('pool-create', null, 'ok', payload.pool_id);
      return Promise.all([policyHooks.loadDashboard(), refreshPoolData()]);
    }).then(() => {
      policyHooks.setBanner('Pool ' + payload.pool_id + ' erstellt.', 'ok');
    }).catch((error) => {
      policyHooks.addToActivityLog('pool-create', null, 'warn', error.message);
      policyHooks.setBanner('Pool-Erstellung fehlgeschlagen: ' + error.message, 'warn');
    });
  });
}

export function renderPolicies() {
  renderPoolWizardStepUi();
  renderPoolTemplateOptions();
  renderPoolGpuClassOptions();
  renderPoolOverviewSelect();
  renderPoolsList();
  renderPoolOverviewBody();
  renderGamingMetricsDashboard();
  renderSessionHandoverDashboard();
  void renderKioskController();
  void loadPoolGpuInventoryHints();
  if (state.token && !state.gamingMetrics) {
    void refreshGamingMetricsDashboard(false);
  }
  if (state.token && !state.handoverHistory) {
    void refreshSessionHandoverDashboard(false);
  }
  if (state.selectedPoolId && (!state.poolVmStates || !Array.isArray(state.poolVmStates[state.selectedPoolId]))) {
    refreshSelectedPoolOverview();
  }

  const node = qs('policies-list');
  if (!node) {
    return;
  }
  if (!state.policies.length) {
    node.innerHTML = '<div class="empty-card">No policies found.</div>';
    return;
  }
  node.innerHTML = state.policies.map((policy) => {
    const selector = policy.selector || {};
    const profile = policy.profile || {};
    return '<article class="policy-card' + (state.selectedPolicyName === policy.name ? ' active' : '') + '" data-policy-name="' + escapeHtml(policy.name || '') + '">' +
      '<div class="policy-head"><strong>' + escapeHtml(policy.name || 'policy') + '</strong>' + chip('prio ' + String(policy.priority || 0), 'muted') + '</div>' +
      '<div class="policy-grid">' +
      fieldBlock('Selector', JSON.stringify(selector), 'mono') +
      fieldBlock('Profile', JSON.stringify(profile), 'mono') +
      '</div>' +
      '</article>';
  }).join('');
}

export function resetPolicyEditor() {
  state.selectedPolicyName = '';
  if (qs('policy-name')) {
    qs('policy-name').value = '';
  }
  if (qs('policy-priority')) {
    qs('policy-priority').value = '100';
  }
  if (qs('policy-enabled')) {
    qs('policy-enabled').checked = true;
  }
  if (qs('policy-selector')) {
    qs('policy-selector').value = '{\n  "vmid": 100\n}';
  }
  if (qs('policy-profile')) {
    qs('policy-profile').value = '{\n  "assigned_target": {\n    "vmid": 100\n  },\n  "beagle_role": "endpoint"\n}';
  }
  renderPolicies();
}

export function loadPolicyIntoEditor(name) {
  const policy = state.policies.find((item) => item.name === name);
  if (!policy) {
    return;
  }
  state.selectedPolicyName = policy.name || '';
  if (qs('policy-name')) {
    qs('policy-name').value = policy.name || '';
  }
  if (qs('policy-priority')) {
    qs('policy-priority').value = String(policy.priority == null ? 100 : policy.priority);
  }
  if (qs('policy-enabled')) {
    qs('policy-enabled').checked = policy.enabled !== false;
  }
  if (qs('policy-selector')) {
    qs('policy-selector').value = JSON.stringify(policy.selector || {}, null, 2);
  }
  if (qs('policy-profile')) {
    qs('policy-profile').value = JSON.stringify(policy.profile || {}, null, 2);
  }
  renderPolicies();
}

export function parseJsonField(id, label) {
  const raw = String(qs(id) ? qs(id).value : '').trim();
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(label + ' is not valid JSON');
  }
}

export function savePolicy() {
  let name = String(qs('policy-name') ? qs('policy-name').value : '').trim();
  let payload;
  try {
    name = sanitizeIdentifier(name, 'Policy-Name', POLICY_NAME_PATTERN, 2, 80);
  } catch (error) {
    policyHooks.setBanner(error.message, 'warn');
    return;
  }
  try {
    payload = {
      name,
      priority: Number(qs('policy-priority') ? qs('policy-priority').value : '100') || 0,
      enabled: Boolean(qs('policy-enabled') && qs('policy-enabled').checked),
      selector: parseJsonField('policy-selector', 'Selector'),
      profile: parseJsonField('policy-profile', 'Profile')
    };
  } catch (error) {
    policyHooks.setBanner(error.message, 'warn');
    return;
  }
  const updateExisting = Boolean(state.selectedPolicyName && state.selectedPolicyName === name);
  const path = updateExisting ? '/policies/' + encodeURIComponent(name) : '/policies';
  const method = updateExisting ? 'PUT' : 'POST';
  runSingleFlight('policy-save:' + name, () => {
    policyHooks.setBanner('Policy ' + name + ' saving...', 'info');
    return request(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(() => {
      state.selectedPolicyName = name;
      return policyHooks.loadDashboard();
    }).then(() => {
      loadPolicyIntoEditor(name);
      policyHooks.setBanner('Policy ' + name + ' saved.', 'ok');
    }).catch((error) => {
      policyHooks.setBanner('Failed to save policy:' + error.message, 'warn');
    });
  });
}

export function deleteSelectedPolicy() {
  const name = String(qs('policy-name') ? qs('policy-name').value : '').trim() || state.selectedPolicyName;
  if (!name) {
    policyHooks.setBanner('No policy selected.', 'warn');
    return;
  }
  policyHooks.requestConfirm({
    title: 'Policy loeschen?',
    message: 'Policy "' + name + '" wirklich loeschen?',
    confirmLabel: 'Loeschen',
    danger: true
  }).then((ok) => {
    if (!ok) {
      return;
    }
    runSingleFlight('policy-delete:' + name, () => {
      policyHooks.setBanner('Policy ' + name + ' deleting...', 'info');
      return request('/policies/' + encodeURIComponent(name), {
        method: 'DELETE'
      }).then(() => {
        policyHooks.addToActivityLog('policy-delete', null, 'ok', name);
        resetPolicyEditor();
        return policyHooks.loadDashboard();
      }).then(() => {
        policyHooks.setBanner('Policy ' + name + ' deleted.', 'ok');
      }).catch((error) => {
        policyHooks.addToActivityLog('policy-delete', null, 'warn', error.message);
        policyHooks.setBanner('Failed to delete policy:' + error.message, 'warn');
      });
    });
  });
}
