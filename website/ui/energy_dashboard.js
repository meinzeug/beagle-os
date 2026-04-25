import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';

const energyHooks = {
  setBanner() {}
};

export function configureEnergyDashboard(nextHooks) {
  Object.assign(energyHooks, nextHooks || {});
}

function powerBar(node) {
  const pct = Math.min(100, Math.round((node.current_power_w / (node.max_power_w || 1)) * 100));
  const tone = pct > 85 ? 'critical' : pct > 65 ? 'warn' : 'ok';
  return `<div class="power-bar-row">
    <span class="power-label">${escapeHtml(node.node_id ?? '-')}</span>
    <div class="bar-track">
      <div class="bar-fill tone-${tone}" style="width:${pct}%"></div>
    </div>
    <span class="power-value">${escapeHtml(String(Math.round(node.current_power_w ?? 0)))} W</span>
    <span class="kwh-value">${escapeHtml((node.month_kwh ?? 0).toFixed(2))} kWh</span>
  </div>`;
}

function co2TrendRow(entry) {
  return `<tr>
    <td>${escapeHtml(entry.month ?? '-')}</td>
    <td>${escapeHtml((entry.total_kwh ?? 0).toFixed(3))}</td>
    <td>${escapeHtml((entry.total_co2_kg ?? 0).toFixed(3))}</td>
    <td>${escapeHtml(entry.total_cost_eur != null ? (entry.total_cost_eur.toFixed(2) + ' €') : '-')}</td>
  </tr>`;
}

export async function renderEnergyDashboard() {
  const container = qs('energy-dashboard-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Energiedaten…</p>';

  let nodes = [];
  let trend = [];

  try {
    [nodes, trend] = await Promise.all([
      request('GET', '/api/v1/energy/nodes').then((d) => Array.isArray(d) ? d : (d.nodes ?? [])),
      request('GET', '/api/v1/energy/trend').catch(() => [])
    ]);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  const powersHtml = nodes.length > 0
    ? `<div class="power-bars">${nodes.map(powerBar).join('')}</div>`
    : '<div class="empty-card">Keine Node-Daten.</div>';

  const trendRows = Array.isArray(trend) ? trend.map(co2TrendRow).join('') : '';
  const trendHtml = trendRows
    ? `<table class="data-table">
        <thead><tr><th>Monat</th><th>kWh</th><th>CO₂ (kg)</th><th>Kosten</th></tr></thead>
        <tbody>${trendRows}</tbody>
      </table>`
    : '<div class="empty-card">Kein CO₂-Verlauf verfügbar.</div>';

  const csrdBtn = `<button class="btn btn-secondary" id="csrd-export-btn">
    CSRD-Report exportieren
  </button>`;

  container.innerHTML = `
    <section class="panel-section">
      <h3>Node-Leistungsaufnahme</h3>
      ${powersHtml}
    </section>
    <section class="panel-section">
      <h3>CO₂-Verlauf</h3>
      ${trendHtml}
      <div class="panel-actions">${csrdBtn}</div>
    </section>`;

  const csrdButton = container.querySelector('#csrd-export-btn');
  if (csrdButton) {
    csrdButton.addEventListener('click', async () => {
      csrdButton.disabled = true;
      const now = new Date();
      const year = now.getUTCFullYear();
      const quarter = Math.ceil((now.getUTCMonth() + 1) / 3);
      try {
        const report = await request('GET', `/api/v1/energy/csrd?year=${year}&quarter=${quarter}`);
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `csrd_${year}_Q${quarter}.json`;
        a.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        energyHooks.setBanner(`CSRD-Export Fehler: ${err.message ?? err}`);
      } finally {
        csrdButton.disabled = false;
      }
    });
  }
}
