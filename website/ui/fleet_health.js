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

function deviceActionButtons(device) {
  const deviceId = String(device.device_id ?? '');
  const status = String(device.status ?? '').trim().toLowerCase();
  const buttons = [];
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
    <td>${escapeHtml(formatDate(device.last_seen ?? ''))}</td>
    <td>${anomalyBadges(deviceAnomalies)}</td>
    <td>${mEntry ? maintenanceLabel(mEntry) : '-'}</td>
    <td>${deviceActionButtons(device)}</td>
  </tr>`;
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

async function triggerDeviceAction(deviceId, action) {
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

  try {
    [devices, anomalies, maintenance] = await Promise.all([
      request('/fleet/devices').then((d) => Array.isArray(d) ? d : (d.devices ?? [])),
      request('/fleet/anomalies').catch(() => []),
      request('/fleet/maintenance').catch(() => [])
    ]);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  if (devices.length === 0) {
    container.innerHTML = '<div class="empty-card">Keine Geräte erfasst.</div>';
    return;
  }

  const rows = devices.map((d) => deviceRow(d, anomalies, maintenance)).join('');
  const anomalyCount = anomalies.length;
  const maintCount = maintenance.filter((m) => m.status === 'pending').length;

  const onlineCount = devices.filter((item) => String(item.status || '').trim() === 'online').length;

  container.innerHTML = `
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
