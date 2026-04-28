import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';

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

function rankingRow(item, unitLabel = 'kWh') {
  const amount = Number(item.energy_kwh ?? item.month_kwh ?? 0);
  const cost = Number(item.energy_cost_eur ?? 0);
  return `<tr>
    <td>${escapeHtml(String(item.vm_id ?? item.node_id ?? '-'))}</td>
    <td>${escapeHtml(item.department ?? item.status ?? '-')}</td>
    <td>${escapeHtml((amount || 0).toFixed(3))} ${unitLabel}</td>
    <td>${cost > 0 ? escapeHtml(cost.toFixed(2) + ' €') : '—'}</td>
  </tr>`;
}

function greenHourTile(item) {
  const hour = String(item.hour ?? 0).padStart(2, '0');
  const intensity = Number(item.estimated_co2_grams_per_kwh ?? 0);
  const price = Number(item.estimated_electricity_price_per_kwh ?? 0);
  const active = Boolean(item.is_green_hour);
  const background = active ? 'rgba(16, 185, 129, 0.24)' : 'rgba(148, 163, 184, 0.12)';
  const border = item.active_now ? '2px solid rgba(16, 185, 129, 0.8)' : '1px solid rgba(148, 163, 184, 0.2)';
  return `<div title="${hour}:00 · ${intensity.toFixed(1)} g/kWh · ${price.toFixed(4)} €/kWh" style="background:${background};border:${border};border-radius:8px;padding:10px 6px;text-align:center;">
    <div style="font-weight:700">${hour}</div>
    <div class="muted-text">${intensity.toFixed(0)} g</div>
    <div class="muted-text">${price.toFixed(2)} €</div>
  </div>`;
}

export async function renderEnergyDashboard() {
  const container = qs('energy-dashboard-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Energiedaten…</p>';

  let nodes = [];
  let trend = [];
  let rankings = {};
  let greenHours = {};
  let config = {};

  try {
    [nodes, trend, rankings, greenHours, config] = await Promise.all([
      request('/energy/nodes').then((d) => Array.isArray(d) ? d : (d.nodes ?? [])),
      request('/energy/trend').then((d) => Array.isArray(d) ? d : (d.trend ?? [])).catch(() => []),
      request('/energy/rankings').then((d) => d?.rankings ?? {}).catch(() => ({})),
      request('/energy/green-hours').then((d) => d?.green_hours ?? {}).catch(() => ({})),
      request('/energy/config').catch(() => ({ carbon_config: {}, scheduler: {} }))
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
  const highestNodes = Array.isArray(rankings?.highest_nodes) ? rankings.highest_nodes : [];
  const lowestNodes = Array.isArray(rankings?.lowest_nodes) ? rankings.lowest_nodes : [];
  const mostIntensiveVms = Array.isArray(rankings?.most_intensive_vms) ? rankings.most_intensive_vms : [];
  const mostEfficientVms = Array.isArray(rankings?.most_efficient_vms) ? rankings.most_efficient_vms : [];
  const greenHourRows = Array.isArray(greenHours?.hourly) ? greenHours.hourly : [];
  const rankingTable = (title, rows, unitLabel) => `<section class="panel-section">
      <h3>${title}</h3>
      ${rows.length > 0 ? `<table class="data-table">
        <thead><tr><th>Objekt</th><th>Kontext</th><th>Verbrauch</th><th>Kosten</th></tr></thead>
        <tbody>${rows.map((row) => rankingRow(row, unitLabel)).join('')}</tbody>
      </table>` : '<div class="empty-card">Keine Ranking-Daten.</div>'}
    </section>`;

  const csrdBtn = `<button class="btn btn-secondary" id="csrd-export-btn">
    CSRD-Report exportieren
  </button>`;
  const carbon = config?.carbon_config || {};
  const scheduler = config?.scheduler || {};

  container.innerHTML = `
    <section class="panel-section">
      <h3>Node-Leistungsaufnahme</h3>
      ${powersHtml}
    </section>
    <section class="panel-section">
      <h3>CO₂-Verlauf</h3>
      ${trendHtml}
      <div class="panel-actions">${csrdBtn}</div>
    </section>
    <section class="panel-section">
      <h3>Grüne Stunden Heatmap</h3>
      <div class="muted-text">Konfigurierter Green-Window-Fokus auf Basis aktueller Carbon- und Strompreis-Konfiguration.</div>
      <div style="display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:8px;margin-top:12px;">
        ${greenHourRows.map((item) => greenHourTile(item)).join('')}
      </div>
    </section>
    ${rankingTable('Höchster Node-Verbrauch', highestNodes, 'kWh')}
    ${rankingTable('Niedrigster Node-Verbrauch', lowestNodes, 'kWh')}
    ${rankingTable('Energieintensivste VMs', mostIntensiveVms, 'kWh')}
    ${rankingTable('Effizienteste VMs', mostEfficientVms, 'kWh')}
    <section class="panel-section">
      <h3>Carbon- und Green-Scheduling-Konfiguration</h3>
      <div class="detail-grid">
        <label>CO₂ g/kWh<input id="energy-co2" type="number" step="0.1" value="${escapeHtml(String(carbon.co2_grams_per_kwh ?? 400))}"></label>
        <label>Strom €/kWh<input id="energy-price" type="number" step="0.0001" value="${escapeHtml(String(carbon.electricity_price_per_kwh ?? 0.3))}"></label>
        <label>Prewarm Minuten<input id="scheduler-prewarm-minutes" type="number" step="1" min="5" max="180" value="${escapeHtml(String(scheduler.prewarm_minutes_ahead ?? 15))}"></label>
        <label class="checkbox-row"><input id="scheduler-green-enabled" type="checkbox" ${scheduler.green_scheduling_enabled ? 'checked' : ''}> Green Scheduling aktiv</label>
      </div>
      <div class="panel-actions">
        <button class="btn btn-primary" id="energy-config-save-btn">Konfiguration speichern</button>
      </div>
    </section>`;

  const csrdButton = container.querySelector('#csrd-export-btn');
  if (csrdButton) {
    csrdButton.addEventListener('click', async () => {
      csrdButton.disabled = true;
      const now = new Date();
      const year = now.getUTCFullYear();
      const quarter = Math.ceil((now.getUTCMonth() + 1) / 3);
      try {
        const response = await request(`/energy/csrd?year=${year}&quarter=${quarter}`);
        const report = response?.csrd ?? response;
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

  const saveButton = container.querySelector('#energy-config-save-btn');
  if (saveButton) {
    saveButton.addEventListener('click', async () => {
      saveButton.disabled = true;
      try {
        await request('/energy/config', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            co2_grams_per_kwh: Number(container.querySelector('#energy-co2')?.value || 0),
            electricity_price_per_kwh: Number(container.querySelector('#energy-price')?.value || 0),
            scheduler: {
              prewarm_minutes_ahead: Number(container.querySelector('#scheduler-prewarm-minutes')?.value || 15),
              green_scheduling_enabled: Boolean(container.querySelector('#scheduler-green-enabled')?.checked),
            },
          }),
        });
        energyHooks.setBanner('Carbon- und Scheduler-Konfiguration gespeichert.');
        renderEnergyDashboard();
      } catch (err) {
        energyHooks.setBanner(`Energy-Konfiguration Fehler: ${err.message ?? err}`);
        saveButton.disabled = false;
      }
    });
  }
}
