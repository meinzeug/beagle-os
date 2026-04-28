import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';

const schedulerHooks = {
  setBanner() {}
};

export function configureSchedulerInsights(nextHooks) {
  Object.assign(schedulerHooks, nextHooks || {});
}

function heatCell(value, max) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const tone = pct > 80 ? 'critical' : pct > 60 ? 'warn' : 'ok';
  return `<td class="heat-cell tone-${tone}" title="${value}/${max}" style="--heat:${pct}%">
    <span>${pct}%</span>
  </td>`;
}

function hourlyHeatTile(value) {
  const pct = Math.max(0, Math.min(100, Math.round(Number(value || 0))));
  const tone = pct > 80 ? 'critical' : pct > 60 ? 'warn' : pct > 30 ? 'ok' : 'muted';
  const background = tone === 'critical'
    ? `rgba(239, 68, 68, ${Math.max(0.18, pct / 120)})`
    : tone === 'warn'
    ? `rgba(245, 158, 11, ${Math.max(0.15, pct / 140)})`
    : tone === 'ok'
    ? `rgba(34, 197, 94, ${Math.max(0.12, pct / 180)})`
    : 'rgba(148, 163, 184, 0.12)';
  return `<div class="mini-heat-tile" title="${pct}% CPU" style="background:${background};border-radius:6px;padding:6px 4px;text-align:center;font-size:0.72rem;">${pct}</div>`;
}

function heatmapMatrix(nodeHeatmap) {
  const days = Array.isArray(nodeHeatmap?.days) ? nodeHeatmap.days : [];
  if (!days.length) return '<div class="empty-card">Keine stündlichen Heatmap-Daten vorhanden.</div>';
  return `<div class="section-spaced-tight">
    ${days.map((day) => `<div style="display:grid;grid-template-columns:90px repeat(24,minmax(22px,1fr));gap:4px;align-items:center;margin-bottom:4px;">
      <div class="muted-text">${escapeHtml(day.day ?? '-')}</div>
      ${Array.isArray(day.hours) ? day.hours.map((value) => hourlyHeatTile(value)).join('') : ''}
    </div>`).join('')}
  </div>`;
}

function placementRow(rec) {
  return `<tr>
    <td>${escapeHtml(rec.vm_id ?? '-')}</td>
    <td>${escapeHtml(rec.current_node ?? '-')}</td>
    <td>${escapeHtml(rec.recommended_node ?? '-')}</td>
    <td>${escapeHtml(rec.reason ?? '-')}</td>
    <td>
      <button
        class="btn-sm btn-primary"
        data-action="scheduler-migrate"
        data-vmid="${escapeHtml(String(rec.vm_id ?? ''))}"
        data-target="${escapeHtml(String(rec.recommended_node ?? ''))}"
        title="Migration ausführen"
      >Migrieren</button>
    </td>
  </tr>`;
}

function prewarmRow(item) {
  return `<tr>
    <td>${escapeHtml(String(item.vm_id ?? '-'))}</td>
    <td>${escapeHtml(item.name ?? '-')}</td>
    <td>${escapeHtml(item.node_id ?? '-')}</td>
    <td>${escapeHtml(String(item.avg_cpu_pct ?? 0))}%</td>
    <td>${escapeHtml(Array.isArray(item.peak_hours) ? item.peak_hours.join(', ') : '-')}</td>
  </tr>`;
}

function trendRow(item) {
  const points = Array.isArray(item.series) ? item.series.map((entry) => `${escapeHtml(entry.day ?? '-')}: ${escapeHtml(String(entry.avg_cpu_pct ?? 0))}%`).join('<br>') : '';
  return `<tr>
    <td>${escapeHtml(item.node_id ?? '-')}</td>
    <td>${points || '—'}</td>
  </tr>`;
}

function forecastRow(item) {
  const points = Array.isArray(item.hourly)
    ? item.hourly.slice(0, 8).map((entry) => `${String(entry.hour).padStart(2, '0')}:00 ${escapeHtml(String(entry.cpu_pct ?? 0))}%`).join('<br>')
    : '';
  return `<tr>
    <td>${escapeHtml(item.node_id ?? '-')}</td>
    <td>${points || '—'}</td>
  </tr>`;
}

export async function renderSchedulerInsights() {
  const container = qs('scheduler-insights-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Scheduler-Daten…</p>';

  let heatmap = [];
  let recommendations = [];
  let prewarmCandidates = [];
  let historicalTrend = [];
  let historicalHeatmap = [];
  let forecast24h = [];
  let config = {};
  let savedCpuHours = 0;
  let greenWindowActive = false;
  try {
    const data = await request('/scheduler/insights');
    heatmap = Array.isArray(data.heatmap) ? data.heatmap : [];
    recommendations = Array.isArray(data.recommendations) ? data.recommendations : [];
    prewarmCandidates = Array.isArray(data.prewarm_candidates) ? data.prewarm_candidates : [];
    historicalTrend = Array.isArray(data.historical_trend) ? data.historical_trend : [];
    historicalHeatmap = Array.isArray(data.historical_heatmap) ? data.historical_heatmap : [];
    forecast24h = Array.isArray(data.forecast_24h) ? data.forecast_24h : [];
    config = data.config || {};
    savedCpuHours = Number(data.saved_cpu_hours || 0);
    greenWindowActive = Boolean(data.green_window_active);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  // Build heatmap table
  let heatHtml = '<div class="empty-card">Keine Heatmap-Daten.</div>';
  if (heatmap.length > 0) {
    const maxVm = Math.max(...heatmap.map((r) => r.vm_count ?? 0), 1);
    const maxCpu = Math.max(...heatmap.map((r) => r.cpu_pct ?? 0), 1);
    const maxMem = Math.max(...heatmap.map((r) => r.mem_pct ?? 0), 1);
    const hmRows = heatmap.map((row) => `<tr>
      <td>${escapeHtml(row.node_id ?? '-')}</td>
      ${heatCell(row.vm_count ?? 0, maxVm)}
      ${heatCell(row.cpu_pct ?? 0, maxCpu)}
      ${heatCell(row.mem_pct ?? 0, maxMem)}
    </tr>`).join('');
    heatHtml = `<table class="data-table heat-table">
      <thead>
        <tr><th>Node</th><th>VMs</th><th>CPU %</th><th>RAM %</th></tr>
      </thead>
      <tbody>${hmRows}</tbody>
    </table>`;
  }

  // Build recommendations table
  let recHtml = '<div class="empty-card">Keine Placement-Empfehlungen.</div>';
  if (recommendations.length > 0) {
    const recRows = recommendations.map(placementRow).join('');
    recHtml = `<table class="data-table">
      <thead>
        <tr><th>VM</th><th>Aktuell</th><th>Empfohlen</th><th>Grund</th><th>Aktion</th></tr>
      </thead>
      <tbody>${recRows}</tbody>
    </table>`;
  }

  const rebalanceBtn = `<button class="btn btn-secondary" id="scheduler-rebalance-btn">
    Auto-Rebalance ausführen
  </button>`;
  const prewarmHtml = prewarmCandidates.length > 0
    ? `<table class="data-table">
        <thead><tr><th>VM</th><th>Name</th><th>Node</th><th>Ø CPU</th><th>Peak-Stunden</th></tr></thead>
        <tbody>${prewarmCandidates.map(prewarmRow).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine Prewarm-Kandidaten aus den letzten 14 Tagen erkannt.</div>';
  const trendHtml = historicalTrend.length > 0
    ? `<table class="data-table">
        <thead><tr><th>Node</th><th>Letzte 7 Tage Ø CPU</th></tr></thead>
        <tbody>${historicalTrend.map(trendRow).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine historischen Scheduler-Metriken vorhanden.</div>';
  const historicalHeatmapHtml = historicalHeatmap.length > 0
    ? historicalHeatmap.map((item) => `<section class="section-spaced-tight"><h4>${escapeHtml(item.node_id ?? '-')}</h4>${heatmapMatrix(item)}</section>`).join('')
    : '<div class="empty-card">Keine stündlichen Heatmap-Daten vorhanden.</div>';
  const forecastHtml = forecast24h.length > 0
    ? `<table class="data-table">
        <thead><tr><th>Node</th><th>Nächste 8 Stunden CPU-Prognose</th></tr></thead>
        <tbody>${forecast24h.map(forecastRow).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine 24h-Prognose verfügbar.</div>';

  container.innerHTML = `
    <section class="panel-section">
      <h3>Node-Auslastung (Heatmap)</h3>
      ${heatHtml}
      <div class="section-spaced-tight">
        <h4>Stündliche Heatmap der letzten 7 Tage</h4>
        ${historicalHeatmapHtml}
      </div>
    </section>
    <section class="panel-section">
      <h3>Placement-Empfehlungen</h3>
      ${recHtml}
      <div class="panel-actions">${rebalanceBtn}</div>
    </section>
    <section class="panel-section">
      <h3>Prewarm und Green Scheduling</h3>
      <p class="muted-text">Geschätzte eingesparte CPU-Stunden: <strong>${escapeHtml(String(savedCpuHours.toFixed(2)))}</strong></p>
      <p class="muted-text">Green Window aktuell: <strong>${greenWindowActive ? 'aktiv' : 'inaktiv'}</strong></p>
      ${prewarmHtml}
      ${trendHtml}
      ${forecastHtml}
      <div class="detail-grid section-spaced-tight">
        <label>Prewarm Minuten<input id="scheduler-config-prewarm" type="number" min="5" max="180" step="1" value="${escapeHtml(String(config.prewarm_minutes_ahead ?? 15))}"></label>
        <label class="checkbox-row"><input id="scheduler-config-green" type="checkbox" ${config.green_scheduling_enabled ? 'checked' : ''}> Green Scheduling aktiv</label>
        <label>Green Hours CSV<input id="scheduler-config-green-hours" type="text" value="${escapeHtml(Array.isArray(config.green_hours) ? config.green_hours.join(',') : '')}" placeholder="10,11,12,13"></label>
      </div>
      <div class="panel-actions">
        <button class="btn btn-primary" id="scheduler-config-save-btn">Scheduler-Konfiguration speichern</button>
      </div>
    </section>`;

  // Wire migration buttons
  container.querySelectorAll('[data-action="scheduler-migrate"]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const vmId = btn.dataset.vmid;
      const target = btn.dataset.target;
      if (!confirm(`VM ${vmId} zu ${target} migrieren?`)) return;
      btn.disabled = true;
      try {
        await request('/scheduler/migrate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ vm_id: vmId, target_node: target })
        });
        schedulerHooks.setBanner(`Migration von VM ${vmId} zu ${target} gestartet.`);
        renderSchedulerInsights();
      } catch (err) {
        schedulerHooks.setBanner(`Fehler: ${err.message ?? err}`);
        btn.disabled = false;
      }
    });
  });

  // Wire rebalance button
  const rebalBtn = container.querySelector('#scheduler-rebalance-btn');
  if (rebalBtn) {
    rebalBtn.addEventListener('click', async () => {
      rebalBtn.disabled = true;
      try {
        await request('/scheduler/rebalance', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        schedulerHooks.setBanner('Auto-Rebalance wurde angestoßen.');
        renderSchedulerInsights();
      } catch (err) {
        schedulerHooks.setBanner(`Fehler: ${err.message ?? err}`);
        rebalBtn.disabled = false;
      }
    });
  }

  const saveConfigButton = container.querySelector('#scheduler-config-save-btn');
  if (saveConfigButton) {
    saveConfigButton.addEventListener('click', async () => {
      saveConfigButton.disabled = true;
      try {
        await request('/scheduler/config', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prewarm_minutes_ahead: Number(container.querySelector('#scheduler-config-prewarm')?.value || 15),
            green_scheduling_enabled: Boolean(container.querySelector('#scheduler-config-green')?.checked),
            green_hours: String(container.querySelector('#scheduler-config-green-hours')?.value || '')
              .split(',')
              .map((value) => Number(String(value || '').trim()))
              .filter((value) => Number.isInteger(value)),
          })
        });
        schedulerHooks.setBanner('Scheduler-Konfiguration gespeichert.');
        renderSchedulerInsights();
      } catch (err) {
        schedulerHooks.setBanner(`Scheduler-Konfiguration Fehler: ${err.message ?? err}`);
        saveConfigButton.disabled = false;
      }
    });
  }
}
