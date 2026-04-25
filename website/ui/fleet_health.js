import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';

const fleetHooks = {
  setBanner() {}
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

function deviceRow(device, anomalies, maintenance) {
  const deviceAnomalies = (anomalies || []).filter((a) => a.device_id === device.device_id);
  const mEntry = (maintenance || []).find((m) => m.device_id === device.device_id);
  return `<tr>
    <td>${escapeHtml(device.device_id ?? '-')}</td>
    <td>${escapeHtml(device.hostname ?? '-')}</td>
    <td>${anomalyBadges(deviceAnomalies)}</td>
    <td>${mEntry ? maintenanceLabel(mEntry) : '-'}</td>
  </tr>`;
}

export async function renderFleetHealth() {
  const container = qs('fleet-health-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Fleet-Status…</p>';

  let devices = [];
  let anomalies = [];
  let maintenance = [];

  try {
    [devices, anomalies, maintenance] = await Promise.all([
      request('GET', '/api/v1/fleet/devices').then((d) => Array.isArray(d) ? d : (d.devices ?? [])),
      request('GET', '/api/v1/fleet/anomalies').catch(() => []),
      request('GET', '/api/v1/fleet/maintenance').catch(() => [])
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

  container.innerHTML = `
    <div class="summary-strip">
      <span class="summary-item">${escapeHtml(String(devices.length))} Geräte</span>
      <span class="summary-item tone-${anomalyCount > 0 ? 'warn' : 'ok'}">${escapeHtml(String(anomalyCount))} Anomalien</span>
      <span class="summary-item tone-${maintCount > 0 ? 'warn' : 'ok'}">${escapeHtml(String(maintCount))} ausstehende Wartungen</span>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Gerät</th>
          <th>Hostname</th>
          <th>Anomalien</th>
          <th>Wartung</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}
