import {
  POLICY_NAME_PATTERN,
  state
} from './state.js';
import { chip, escapeHtml, fieldBlock, qs } from './dom.js';
import { request, runSingleFlight } from './api.js';
import { sanitizeIdentifier } from './auth.js';

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

export function configurePolicies(nextHooks) {
  Object.assign(policyHooks, nextHooks || {});
}

function parseCommaList(rawValue) {
  return String(rawValue || '')
    .split(',')
    .map((item) => String(item || '').trim())
    .filter((item, idx, all) => item && all.indexOf(item) === idx);
}

function collectPoolWizardInput() {
  const poolIdRaw = String(qs('pool-id') ? qs('pool-id').value : '').trim();
  const poolId = poolIdRaw.toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  const templateId = String(qs('pool-template') ? qs('pool-template').value : '').trim();
  const mode = String(qs('pool-mode') ? qs('pool-mode').value : 'floating_non_persistent').trim();
  const storagePool = String(qs('pool-storage') ? qs('pool-storage').value : 'local').trim() || 'local';
  const users = parseCommaList(qs('pool-users') ? qs('pool-users').value : '');
  const groups = parseCommaList(qs('pool-groups') ? qs('pool-groups').value : '');
  const payload = {
    pool_id: poolId,
    template_id: templateId,
    mode,
    storage_pool: storagePool,
    min_pool_size: Number(qs('pool-min-size') ? qs('pool-min-size').value : '1') || 1,
    max_pool_size: Number(qs('pool-max-size') ? qs('pool-max-size').value : '5') || 5,
    warm_pool_size: Number(qs('pool-warm-size') ? qs('pool-warm-size').value : '2') || 2,
    cpu_cores: Number(qs('pool-cpu') ? qs('pool-cpu').value : '2') || 2,
    memory_mib: Number(qs('pool-memory') ? qs('pool-memory').value : '4096') || 4096,
    streaming_profile: {
      encoder: String(qs('pool-stream-encoder') ? qs('pool-stream-encoder').value : 'auto').trim() || 'auto',
      color: String(qs('pool-stream-color') ? qs('pool-stream-color').value : 'h265').trim() || 'h265',
      bitrate_kbps: Number(qs('pool-stream-bitrate') ? qs('pool-stream-bitrate').value : '20000') || 20000,
      fps: Number(qs('pool-stream-fps') ? qs('pool-stream-fps').value : '60') || 60,
      resolution: String(qs('pool-stream-resolution') ? qs('pool-stream-resolution').value : '1920x1080').trim() || '1920x1080',
      hdr: Boolean(qs('pool-stream-hdr') ? qs('pool-stream-hdr').checked : false)
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
    fieldBlock('Modus', payload.mode || '-') +
    fieldBlock('Storage', payload.storage_pool || '-') +
    fieldBlock('Min/Max/Warm', String(payload.min_pool_size) + ' / ' + String(payload.max_pool_size) + ' / ' + String(payload.warm_pool_size)) +
    fieldBlock('CPU / RAM', String(payload.cpu_cores) + ' vCPU / ' + String(payload.memory_mib) + ' MiB') +
    fieldBlock('Streaming', String(payload.streaming_profile.encoder || '-') + ' / ' + String(payload.streaming_profile.color || '-') + ' / ' + String(payload.streaming_profile.resolution || '-')) +
    fieldBlock('Bitrate / FPS / HDR', String(payload.streaming_profile.bitrate_kbps || '-') + ' Kbps / ' + String(payload.streaming_profile.fps || '-') + ' fps / ' + (payload.streaming_profile.hdr ? 'on' : 'off')) +
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
    const stream = pool.streaming_profile && typeof pool.streaming_profile === 'object' ? pool.streaming_profile : null;
    const streamSummary = stream
      ? String(stream.encoder || 'auto') + ' / ' + String(stream.color || 'h265') + ' / ' + String(stream.resolution || '1920x1080')
      : 'default';
    const selectedClass = state.selectedPoolId === poolId ? ' active' : '';
    return '<article class="policy-card' + selectedClass + '" data-pool-id="' + escapeHtml(poolId) + '">' +
      '<div class="policy-head"><strong>' + escapeHtml(poolId) + '</strong>' + chip(mode, 'muted') + '</div>' +
      '<div class="pool-card-meta">' +
      fieldBlock('Template', String(pool.template_id || '-'), 'mono') +
      fieldBlock('Warm/Max', String(pool.warm_pool_size || 0) + ' / ' + String(pool.max_pool_size || 0)) +
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
  poolWizardStep = 1;
  renderPoolTemplateOptions();
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
  renderPoolOverviewSelect();
  renderPoolsList();
  renderPoolOverviewBody();
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