import { request } from './api.js';
import { chip, escapeHtml, formatDate, qs } from './dom.js';

const fleetHooks = {
  setBanner() {},
  requestConfirm() {
    return Promise.resolve(window.confirm('Aktion ausfuehren?'));
  },
  loadDashboard() {
    return Promise.resolve();
  }
};

const fleetState = {
  devices: [],
  policies: [],
  assignments: { device_assignments: {}, group_assignments: {} },
  effectivePolicy: null,
};

export function configureFleetHealth(nextHooks) {
  Object.assign(fleetHooks, nextHooks || {});
}

function severityBadge(severity) {
  const tone = severity === 'critical' ? 'critical' : severity === 'warning' ? 'warn' : 'ok';
  return `<span class="badge tone-${tone}">${escapeHtml(severity ?? '-')}</span>`;
}

function anomalyBadges(anomalies) {
  if (!Array.isArray(anomalies) || anomalies.length === 0) return '<span class="badge tone-ok">OK</span>';
  return anomalies.map((a) => severityBadge(a.severity)).join(' ');
}

function maintenanceLabel(entry) {
  if (!entry) return '';
  return `<span class="badge tone-warn" title="${escapeHtml(entry.reason ?? '')}">
    Wartung: ${escapeHtml(entry.suggested_window ?? '-')}
  </span>`;
}

function actionButton(label, action, tone, deviceId) {
  return `<button type="button" class="btn btn-${escapeHtml(tone)}" data-fleet-action="${escapeHtml(action)}" data-device-id="${escapeHtml(deviceId)}">${escapeHtml(label)}</button>`;
}

function policyBadge(device) {
  const deviceAssignments = fleetState.assignments?.device_assignments || {};
  const groupAssignments = fleetState.assignments?.group_assignments || {};
  const deviceId = String(device.device_id ?? '');
  const group = String(device.group ?? '');
  const policyId = deviceAssignments[deviceId] || (group ? groupAssignments[group] : '') || '__default__';
  const tone = policyId === '__default__' ? 'muted' : 'info';
  return `<span class="badge tone-${tone}">${escapeHtml(policyId)}</span>`;
}

function deviceActionButtons(device) {
  const deviceId = String(device.device_id ?? '');
  const status = String(device.status ?? '').trim().toLowerCase();
  const buttons = [];
  buttons.push(actionButton('Policy', 'policy-select', 'primary', deviceId));
  if (status === 'locked') {
    buttons.push(actionButton('Entsperren', 'unlock', 'primary', deviceId));
  } else if (status !== 'wiped') {
    buttons.push(actionButton('Sperren', 'lock', 'ghost', deviceId));
  }
  if (status !== 'wiped' && status !== 'wipe_pending') {
    buttons.push(actionButton('Wipe', 'wipe', 'danger', deviceId));
  }
  return buttons.length ? `<div class="button-row compact-row">${buttons.join('')}</div>` : '<span class="badge tone-muted">-</span>';
}

function deviceRow(device, anomalies, maintenance) {
  const deviceAnomalies = (anomalies || []).filter((a) => a.device_id === device.device_id);
  const mEntry = (maintenance || []).find((m) => m.device_id === device.device_id);
  const hardware = device.hardware && typeof device.hardware === 'object' ? device.hardware : {};
  const hardwareSummary = [
    hardware.cpu_model ? String(hardware.cpu_model) : '',
    hardware.ram_gb ? String(hardware.ram_gb) + ' GB RAM' : '',
    hardware.gpu_model ? String(hardware.gpu_model) : ''
  ].filter(Boolean).join(' / ');
  return `<tr>
    <td>${escapeHtml(device.device_id ?? '-')}</td>
    <td>${escapeHtml(device.hostname ?? '-')}</td>
    <td>${escapeHtml(device.status ?? '-')}</td>
    <td>${escapeHtml(device.location ?? device.group ?? '-')}</td>
    <td>${escapeHtml(hardwareSummary || '-')}</td>
    <td>${policyBadge(device)}</td>
    <td>${escapeHtml(formatDate(device.last_seen ?? ''))}</td>
    <td>${anomalyBadges(deviceAnomalies)}</td>
    <td>${mEntry ? maintenanceLabel(mEntry) : '-'}</td>
    <td>${deviceActionButtons(device)}</td>
  </tr>`;
}

function locationTreeSection() {
  if (!fleetState.devices.length) {
    return '';
  }
  const locations = new Map();
  for (const device of fleetState.devices) {
    const location = String(device.location || 'Unbekannter Standort').trim() || 'Unbekannter Standort';
    const group = String(device.group || 'ohne Gruppe').trim() || 'ohne Gruppe';
    if (!locations.has(location)) {
      locations.set(location, new Map());
    }
    const groups = locations.get(location);
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group).push(device);
  }
  const cards = Array.from(locations.entries())
    .sort((left, right) => left[0].localeCompare(right[0], 'de'))
    .map(([location, groups]) => {
      const groupCards = Array.from(groups.entries())
        .sort((left, right) => left[0].localeCompare(right[0], 'de'))
        .map(([group, devices]) => {
          const online = devices.filter((item) => String(item.status || '').trim() === 'online').length;
          const assigned = devices
            .map((item) => String(item.device_id || ''))
            .filter(Boolean)
            .filter((deviceId) => Boolean((fleetState.assignments?.device_assignments || {})[deviceId])).length;
          return `<div class="card compact-card">
            <strong>${escapeHtml(group)}</strong>
            <div class="muted">${escapeHtml(String(devices.length))} Geraete • online ${escapeHtml(String(online))}</div>
            <div class="muted">direkte Policies ${escapeHtml(String(assigned))}</div>
            <div class="section-spaced-tight">${devices.map((device) => `<span class="badge tone-${String(device.status || '').trim() === 'online' ? 'ok' : 'muted'}">${escapeHtml(String(device.hostname || device.device_id || '-'))}</span>`).join(' ')}</div>
          </div>`;
        })
        .join('');
      return `<div class="card">
        <h3>${escapeHtml(location)}</h3>
        <div class="grid auto-grid section-spaced-tight">${groupCards}</div>
      </div>`;
    })
    .join('');
  return `
    <section class="section-spaced">
      <h3>Standort- und Gruppenansicht</h3>
      <div class="grid auto-grid section-spaced-tight">${cards}</div>
    </section>`;
}

function actionMeta(action) {
  if (action === 'unlock') {
    return {
      title: 'Geraet entsperren',
      message: 'Das Geraet wieder freigeben?',
      confirmLabel: 'Entsperren',
      success: 'Geraet entsperrt.'
    };
  }
  if (action === 'wipe') {
    return {
      title: 'Remote-Wipe anfordern',
      message: 'Das Geraet beim naechsten Heartbeat zum Wipe markieren?',
      confirmLabel: 'Wipe anfordern',
      danger: true,
      success: 'Remote-Wipe vorgemerkt.'
    };
  }
  return {
    title: 'Geraet sperren',
    message: 'Das Geraet sperren?',
    confirmLabel: 'Sperren',
    success: 'Geraet gesperrt.'
  };
}

function csvValue(value) {
  return Array.isArray(value) ? value.join(', ') : '';
}

function selectedPolicyId() {
  return String(qs('fleet-policy-id')?.value || '').trim();
}

function policyValidationMarkup(validation) {
  const errors = Array.isArray(validation?.errors) ? validation.errors : [];
  const warnings = Array.isArray(validation?.warnings) ? validation.warnings : [];
  if (!errors.length && !warnings.length) {
    return '<div class="muted">Keine Hinweise.</div>';
  }
  return `
    ${errors.map((item) => `<div class="badge tone-critical">${escapeHtml(String(item || ''))}</div>`).join(' ')}
    ${warnings.map((item) => `<div class="badge tone-warn">${escapeHtml(String(item || ''))}</div>`).join(' ')}
  `;
}

function formatDiagnosticValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : 'alle';
  }
  if (value === '' || value === null || value === undefined) {
    return 'default';
  }
  return String(value);
}

function policyDiffMarkup(diagnostics) {
  const sections = [
    ['group_vs_default', 'Gruppe vs Default'],
    ['device_vs_group', 'Device vs Gruppe'],
    ['effective_vs_default', 'Effektiv vs Default'],
  ];
  const content = sections.map(([key, label]) => {
    const entries = Array.isArray(diagnostics?.diffs?.[key]) ? diagnostics.diffs[key] : [];
    if (!entries.length) {
      return `<div class="card compact-card"><strong>${escapeHtml(label)}</strong><div class="muted">Keine Abweichungen.</div></div>`;
    }
    return `<div class="card compact-card">
      <strong>${escapeHtml(label)}</strong>
      <div class="section-spaced-tight">${entries.map((entry) => `<div class="muted">${escapeHtml(String(entry.field || ''))}: ${escapeHtml(formatDiagnosticValue(entry.baseline))} → ${escapeHtml(formatDiagnosticValue(entry.effective))}</div>`).join('')}</div>
    </div>`;
  }).join('');
  return `<div class="grid auto-grid section-spaced-tight">${content}</div>`;
}

function policyCards() {
  if (!fleetState.policies.length) {
    return '<div class="empty-card">Noch keine MDM-Policies vorhanden.</div>';
  }
  return fleetState.policies.map((policy) => {
    const policyId = String(policy.policy_id || '');
    const selected = policyId === selectedPolicyId();
    const subtitle = [
      policy.max_resolution ? String(policy.max_resolution) : 'unlimited',
      Array.isArray(policy.allowed_pools) && policy.allowed_pools.length ? `${policy.allowed_pools.length} Pools` : 'alle Pools',
      Array.isArray(policy.allowed_codecs) && policy.allowed_codecs.length ? policy.allowed_codecs.join('/') : 'alle Codecs'
    ].join(' • ');
    return `<button type="button" class="card compact-card fleet-policy-card${selected ? ' selected' : ''}" data-mdm-action="select-policy" data-policy-id="${escapeHtml(policyId)}">
      <strong>${escapeHtml(policy.name || policyId)}</strong>
      <div class="muted">${escapeHtml(policyId)}</div>
      <div class="muted">${escapeHtml(subtitle)}</div>
    </button>`;
  }).join('');
}

function policyEditorSection() {
  const effective = fleetState.effectivePolicy;
  const effectiveSource = effective ? `${String(effective.source_type || 'default')} • ${String(effective.source_id || '__default__')}` : 'kein Device ausgewaehlt';
  const effectiveSummary = effective?.policy ? [
    effective.policy.max_resolution ? String(effective.policy.max_resolution) : 'unlimited',
    Array.isArray(effective.policy.allowed_pools) && effective.policy.allowed_pools.length ? `${effective.policy.allowed_pools.length} Pools` : 'alle Pools',
    Array.isArray(effective.policy.allowed_codecs) && effective.policy.allowed_codecs.length ? effective.policy.allowed_codecs.join('/') : 'alle Codecs'
  ].join(' • ') : 'Keine effektive Policy geladen';
  const selected = fleetState.policies.find((policy) => String(policy.policy_id || '') === selectedPolicyId()) || null;
  const effectiveConflicts = Array.isArray(effective?.conflicts) ? effective.conflicts : [];
  const remediationHints = Array.isArray(effective?.remediation_hints) ? effective.remediation_hints : [];
  return `
    <section class="section-spaced">
      <div class="button-row compact-row section-spaced-tight">
        ${chip(`${fleetState.policies.length} Policies`, fleetState.policies.length ? 'info' : 'muted')}
        ${chip(`${Object.keys(fleetState.assignments?.device_assignments || {}).length} Device-Zuweisungen`, 'info')}
        ${chip(`${Object.keys(fleetState.assignments?.group_assignments || {}).length} Gruppen-Zuweisungen`, 'info')}
      </div>
      <div class="grid two-col section-spaced-tight">
        <div>
          <h3>MDM Policies</h3>
          <div class="grid auto-grid">${policyCards()}</div>
        </div>
        <div class="card">
          <h3>Policy Editor</h3>
          <div class="grid two-col section-spaced-tight">
            <label class="field"><span>Policy ID</span><input id="fleet-policy-id" type="text" autocomplete="off" placeholder="corp"></label>
            <label class="field"><span>Name</span><input id="fleet-policy-name" type="text" autocomplete="off" placeholder="Corporate"></label>
            <label class="field field-wide"><span>Allowed Pools</span><input id="fleet-policy-pools" type="text" autocomplete="off" placeholder="pool-a, pool-b"></label>
            <label class="field field-wide"><span>Allowed Networks</span><input id="fleet-policy-networks" type="text" autocomplete="off" placeholder="wg, office-vlan"></label>
            <label class="field"><span>Max Resolution</span><input id="fleet-policy-resolution" type="text" autocomplete="off" placeholder="1920x1080"></label>
            <label class="field"><span>Allowed Codecs</span><input id="fleet-policy-codecs" type="text" autocomplete="off" placeholder="h264, h265"></label>
            <label class="field"><span>Update Start</span><input id="fleet-policy-update-start" type="number" min="0" max="23" value="2"></label>
            <label class="field"><span>Update Ende</span><input id="fleet-policy-update-end" type="number" min="0" max="23" value="4"></label>
            <label class="field"><span>Screen Lock Timeout</span><input id="fleet-policy-lock-timeout" type="number" min="0" step="1" value="0"></label>
            <label class="field checkbox-field"><span>Auto Update</span><input id="fleet-policy-auto-update" type="checkbox" checked></label>
          </div>
          <div class="button-row compact-row section-spaced-tight">
            <button type="button" class="button primary" data-mdm-action="save-policy">Speichern</button>
            <button type="button" class="button ghost" data-mdm-action="new-policy">Neu</button>
            <button type="button" class="button danger" data-mdm-action="delete-policy">Loeschen</button>
          </div>
          <h3>Policy Validierung</h3>
          <div class="card compact-card">
            ${policyValidationMarkup(selected?.validation || null)}
          </div>
          <h3>Assignment</h3>
          <div class="grid two-col section-spaced-tight">
            <label class="field"><span>Device ID</span><input id="fleet-assign-device-id" type="text" autocomplete="off" placeholder="dev-001"></label>
            <label class="field"><span>Gruppe</span><input id="fleet-assign-group-id" type="text" autocomplete="off" placeholder="reception"></label>
            <label class="field"><span>Bulk Standort</span><input id="fleet-bulk-location" type="text" autocomplete="off" placeholder="Berlin-Office-1"></label>
            <label class="field field-wide"><span>Bulk Device IDs (eine pro Zeile oder komma)</span><textarea id="fleet-assign-device-ids" rows="4" autocomplete="off" placeholder="dev-001&#10;dev-002"></textarea></label>
          </div>
          <div class="button-row compact-row section-spaced-tight">
            <button type="button" class="button primary" data-mdm-action="assign-device">Policy dem Device zuweisen</button>
            <button type="button" class="button ghost" data-mdm-action="assign-group">Policy der Gruppe zuweisen</button>
            <button type="button" class="button ghost" data-mdm-action="assign-bulk-devices">Policy den gelisteten Devices zuweisen</button>
            <button type="button" class="button ghost" data-mdm-action="clear-device-assignment">Device-Zuweisung loeschen</button>
            <button type="button" class="button ghost" data-mdm-action="clear-group-assignment">Gruppen-Zuweisung loeschen</button>
            <button type="button" class="button ghost" data-mdm-action="clear-bulk-devices">Bulk-Device-Zuweisungen loeschen</button>
            <button type="button" class="button ghost" data-mdm-action="bulk-lock">Bulk sperren</button>
            <button type="button" class="button ghost" data-mdm-action="bulk-unlock">Bulk entsperren</button>
            <button type="button" class="button danger" data-mdm-action="bulk-wipe">Bulk wipe</button>
            <button type="button" class="button ghost" data-mdm-action="bulk-set-group">Bulk Gruppe setzen</button>
            <button type="button" class="button ghost" data-mdm-action="bulk-set-location">Bulk Standort setzen</button>
          </div>
          <h3>Effective Policy Preview</h3>
          <div class="card compact-card">
            <strong>${escapeHtml(String(effective?.policy?.name || 'Policy Preview'))}</strong>
            <div class="muted">${escapeHtml(effectiveSource)}</div>
            <div class="muted">${escapeHtml(effectiveSummary)}</div>
            <div class="section-spaced-tight">${policyValidationMarkup(effective?.policy?.validation || null)}</div>
            <div class="section-spaced-tight">${effectiveConflicts.map((item) => `<div class="badge tone-warn">${escapeHtml(String(item || ''))}</div>`).join(' ') || '<div class="muted">Keine Konflikte.</div>'}</div>
            <div class="section-spaced-tight">${policyDiffMarkup(effective?.diagnostics || null)}</div>
            <div class="section-spaced-tight">${remediationHints.map((item) => `<div class="badge tone-info">${escapeHtml(String(item || ''))}</div>`).join(' ') || '<div class="muted">Keine Remediation-Hinweise.</div>'}</div>
          </div>
        </div>
      </div>
    </section>`;
}

function loadPolicyIntoForm(policy) {
  qs('fleet-policy-id').value = String(policy?.policy_id || '');
  qs('fleet-policy-name').value = String(policy?.name || '');
  qs('fleet-policy-pools').value = csvValue(policy?.allowed_pools);
  qs('fleet-policy-networks').value = csvValue(policy?.allowed_networks);
  qs('fleet-policy-resolution').value = String(policy?.max_resolution || '');
  qs('fleet-policy-codecs').value = csvValue(policy?.allowed_codecs);
  qs('fleet-policy-update-start').value = String(policy?.update_window_start_hour ?? 2);
  qs('fleet-policy-update-end').value = String(policy?.update_window_end_hour ?? 4);
  qs('fleet-policy-lock-timeout').value = String(policy?.screen_lock_timeout_seconds ?? 0);
  qs('fleet-policy-auto-update').checked = Boolean(policy?.auto_update ?? true);
}

function policyPayloadFromForm() {
  return {
    policy_id: String(qs('fleet-policy-id')?.value || '').trim(),
    name: String(qs('fleet-policy-name')?.value || '').trim(),
    allowed_pools: String(qs('fleet-policy-pools')?.value || '').trim(),
    allowed_networks: String(qs('fleet-policy-networks')?.value || '').trim(),
    max_resolution: String(qs('fleet-policy-resolution')?.value || '').trim(),
    allowed_codecs: String(qs('fleet-policy-codecs')?.value || '').trim(),
    update_window_start_hour: Number(qs('fleet-policy-update-start')?.value || 2),
    update_window_end_hour: Number(qs('fleet-policy-update-end')?.value || 4),
    screen_lock_timeout_seconds: Number(qs('fleet-policy-lock-timeout')?.value || 0),
    auto_update: Boolean(qs('fleet-policy-auto-update')?.checked),
  };
}

async function savePolicy() {
  const payload = policyPayloadFromForm();
  if (!payload.policy_id || !payload.name) {
    throw new Error('Policy ID und Name sind erforderlich');
  }
  const existing = fleetState.policies.find((item) => String(item.policy_id || '') === payload.policy_id);
  const path = existing ? `/fleet/policies/${encodeURIComponent(payload.policy_id)}` : '/fleet/policies';
  const method = existing ? 'PUT' : 'POST';
  await request(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  fleetHooks.setBanner('MDM-Policy gespeichert.', 'ok');
  await fleetHooks.loadDashboard({ force: true });
}

async function deletePolicy() {
  const policyId = selectedPolicyId();
  if (!policyId) {
    throw new Error('Keine Policy ausgewaehlt');
  }
  const confirmed = await fleetHooks.requestConfirm({
    title: 'MDM-Policy loeschen',
    message: `Policy ${policyId} wirklich loeschen?`,
    confirmLabel: 'Loeschen',
    danger: true,
  });
  if (!confirmed) return;
  await request(`/fleet/policies/${encodeURIComponent(policyId)}`, { method: 'DELETE' });
  fleetHooks.setBanner('MDM-Policy geloescht.', 'ok');
  await fleetHooks.loadDashboard({ force: true });
}

async function assignPolicy(targetType, clearAssignment = false) {
  const targetId = String(qs(targetType === 'device' ? 'fleet-assign-device-id' : 'fleet-assign-group-id')?.value || '').trim();
  const policyId = clearAssignment ? '' : selectedPolicyId();
  if (!targetId) {
    throw new Error(targetType === 'device' ? 'Device ID fehlt' : 'Gruppe fehlt');
  }
  await request('/fleet/policies/assignments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_type: targetType, target_id: targetId, policy_id: policyId }),
  });
  fleetHooks.setBanner(clearAssignment ? 'Policy-Zuweisung geloescht.' : 'Policy zugewiesen.', 'ok');
  await fleetHooks.loadDashboard({ force: true });
}

function bulkDeviceIdsFromForm() {
  return String(qs('fleet-assign-device-ids')?.value || '')
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function bulkActionValue(action) {
  if (action === 'set-group') {
    return String(qs('fleet-assign-group-id')?.value || '').trim();
  }
  if (action === 'set-location') {
    return String(qs('fleet-bulk-location')?.value || '').trim();
  }
  return '';
}

async function assignBulkDevices(clearAssignment = false) {
  const targetIds = bulkDeviceIdsFromForm();
  const policyId = clearAssignment ? '' : selectedPolicyId();
  if (!targetIds.length) {
    throw new Error('Bulk Device IDs fehlen');
  }
  await request('/fleet/policies/assignments/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_type: 'device', target_ids: targetIds, policy_id: policyId }),
  });
  fleetHooks.setBanner(clearAssignment ? 'Bulk-Device-Zuweisungen geloescht.' : 'Policy bulk zugewiesen.', 'ok');
  await fleetHooks.loadDashboard({ force: true });
}

async function submitBulkDeviceAction(action) {
  const targetIds = bulkDeviceIdsFromForm();
  if (!targetIds.length) {
    throw new Error('Bulk Device IDs fehlen');
  }
  const value = bulkActionValue(action);
  if ((action === 'set-group' || action === 'set-location') && !value) {
    throw new Error(action === 'set-group' ? 'Bulk-Gruppe fehlt' : 'Bulk-Standort fehlt');
  }
  await request('/fleet/devices/actions/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, target_ids: targetIds, value }),
  });
  fleetHooks.setBanner(`Bulk-Aktion ${action} ausgefuehrt.`, 'ok');
  await fleetHooks.loadDashboard({ force: true });
}

async function loadEffectivePolicy(deviceId) {
  const payload = await request(`/fleet/devices/${encodeURIComponent(deviceId)}/effective-policy`);
  fleetState.effectivePolicy = payload;
  qs('fleet-assign-device-id').value = deviceId;
  await fleetHooks.loadDashboard({ force: true });
}

async function triggerDeviceAction(deviceId, action) {
  if (action === 'policy-select') {
    const policyId = (fleetState.assignments?.device_assignments || {})[deviceId] || '';
    const policy = fleetState.policies.find((item) => String(item.policy_id || '') === String(policyId));
    qs('fleet-assign-device-id').value = deviceId;
    if (policy) {
      loadPolicyIntoForm(policy);
    }
    await loadEffectivePolicy(deviceId);
    return;
  }
  const meta = actionMeta(action);
  const confirmed = await fleetHooks.requestConfirm({
    title: meta.title,
    message: meta.message,
    confirmLabel: meta.confirmLabel,
    danger: Boolean(meta.danger),
  });
  if (!confirmed) {
    return;
  }
  await request(`/fleet/devices/${encodeURIComponent(deviceId)}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  fleetHooks.setBanner(meta.success, 'ok');
  await fleetHooks.loadDashboard({ force: true });
}

export async function renderFleetHealth() {
  const container = qs('fleet-health-panel');
  if (!container) return;

  container.onclick = (event) => {
    const button = event.target.closest('[data-fleet-action]');
    if (!button) return;
    const action = String(button.getAttribute('data-fleet-action') || '').trim();
    const deviceId = String(button.getAttribute('data-device-id') || '').trim();
    if (!action || !deviceId) return;
    triggerDeviceAction(deviceId, action).catch((error) => {
      fleetHooks.setBanner('Fleet-Aktion fehlgeschlagen: ' + String(error.message ?? error), 'warn');
    });
  };

  container.innerHTML = '<p class="loading">Lade Fleet-Status…</p>';

  let devices = [];
  let anomalies = [];
  let maintenance = [];
  let policies = [];
  let assignments = { device_assignments: {}, group_assignments: {} };

  try {
    [devices, anomalies, maintenance, policies, assignments] = await Promise.all([
      request('/fleet/devices').then((d) => Array.isArray(d) ? d : (d.devices ?? [])),
      request('/fleet/anomalies').catch(() => []),
      request('/fleet/maintenance').catch(() => []),
      request('/fleet/policies').then((d) => Array.isArray(d) ? d : (d.policies ?? [])),
      request('/fleet/policies/assignments').catch(() => ({ device_assignments: {}, group_assignments: {} })),
    ]);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  fleetState.devices = devices;
  fleetState.policies = policies;
  fleetState.assignments = assignments;

  const rows = devices.map((d) => deviceRow(d, anomalies, maintenance)).join('');
  const anomalyCount = anomalies.length;
  const maintCount = maintenance.filter((m) => m.status === 'pending').length;
  const onlineCount = devices.filter((item) => String(item.status || '').trim() === 'online').length;

  if (devices.length === 0) {
    container.innerHTML = `${policyEditorSection()}<div class="empty-card">Keine Geräte erfasst.</div>`;
  } else {
    container.innerHTML = `
      ${policyEditorSection()}
      ${locationTreeSection()}
      <div class="button-row compact-row section-spaced-tight">
        ${chip(String(devices.length) + ' Geraete', devices.length ? 'info' : 'muted')}
        ${chip('online ' + String(onlineCount), onlineCount ? 'ok' : 'muted')}
        ${chip(String(anomalyCount) + ' Anomalien', anomalyCount > 0 ? 'warn' : 'ok')}
        ${chip(String(maintCount) + ' Wartungen', maintCount > 0 ? 'warn' : 'muted')}
      </div>
      <div class="table-wrap compact">
      <table class="vm-table compact-table">
        <thead>
          <tr>
            <th>Gerät</th>
            <th>Hostname</th>
            <th>Status</th>
            <th>Standort / Gruppe</th>
            <th>Hardware</th>
            <th>Policy</th>
            <th>Last Seen</th>
            <th>Anomalien</th>
            <th>Wartung</th>
            <th>Aktionen</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
      </div>`;
  }

  container.querySelectorAll('[data-policy-id]').forEach((item) => {
    item.addEventListener('click', () => {
      const policyId = String(item.getAttribute('data-policy-id') || '').trim();
      const policy = fleetState.policies.find((entry) => String(entry.policy_id || '') === policyId);
      if (policy) {
        loadPolicyIntoForm(policy);
      }
    });
  });

  const defaultPolicy = fleetState.policies[0];
  if (defaultPolicy) {
    loadPolicyIntoForm(defaultPolicy);
  }

  container.querySelectorAll('[data-mdm-action]').forEach((item) => {
    item.addEventListener('click', async () => {
      const action = String(item.getAttribute('data-mdm-action') || '').trim();
      try {
        if (action === 'new-policy') {
          loadPolicyIntoForm({});
          return;
        }
        if (action === 'save-policy') {
          await savePolicy();
          return;
        }
        if (action === 'delete-policy') {
          await deletePolicy();
          return;
        }
        if (action === 'assign-device') {
          await assignPolicy('device', false);
          return;
        }
        if (action === 'assign-group') {
          await assignPolicy('group', false);
          return;
        }
        if (action === 'assign-bulk-devices') {
          await assignBulkDevices(false);
          return;
        }
        if (action === 'clear-device-assignment') {
          await assignPolicy('device', true);
          return;
        }
        if (action === 'clear-group-assignment') {
          await assignPolicy('group', true);
          return;
        }
        if (action === 'clear-bulk-devices') {
          await assignBulkDevices(true);
          return;
        }
        if (action === 'bulk-lock') {
          await submitBulkDeviceAction('lock');
          return;
        }
        if (action === 'bulk-unlock') {
          await submitBulkDeviceAction('unlock');
          return;
        }
        if (action === 'bulk-wipe') {
          await submitBulkDeviceAction('wipe');
          return;
        }
        if (action === 'bulk-set-group') {
          await submitBulkDeviceAction('set-group');
          return;
        }
        if (action === 'bulk-set-location') {
          await submitBulkDeviceAction('set-location');
        }
      } catch (error) {
        fleetHooks.setBanner('MDM-Policy-Aktion fehlgeschlagen: ' + String(error.message ?? error), 'warn');
      }
    });
  });
}
