import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';
import { hasPermission, state } from './state.js';

const schedulerHooks = {
  setBanner() {}
};

export function configureSchedulerInsights(nextHooks) {
  Object.assign(schedulerHooks, nextHooks || {});
}

function renderAccessState(container) {
  if (!state.token) {
    container.innerHTML = '<div class="empty-card">Anmeldung erforderlich, um Scheduler-Insights zu laden.</div>';
    return false;
  }
  if (!hasPermission('settings:read')) {
    container.innerHTML = '<div class="empty-card">Keine Berechtigung fuer Scheduler-Insights. Erforderlich: settings:read.</div>';
    return false;
  }
  return true;
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
        ${hasPermission('settings:write') ? '' : 'disabled '}
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

function breakdownRow(item, key) {
  return `<tr>
    <td>${escapeHtml(String(item[key] ?? '-'))}</td>
    <td>${escapeHtml(String(item.candidate_count ?? 0))}</td>
    <td>${escapeHtml(Number(item.saved_cpu_hours ?? 0).toFixed(2))}</td>
  </tr>`;
}

function warmPoolRow(item) {
  return `<tr>
    <td>${escapeHtml(String(item.pool_id ?? '-'))}</td>
    <td>${escapeHtml(String(item.current_warm_pool_size ?? 0))}</td>
    <td>${escapeHtml(String(item.recommended_warm_pool_size ?? 0))}</td>
    <td>${escapeHtml(String(item.prewarm_hits ?? 0))} / ${escapeHtml(String(item.prewarm_misses ?? 0))}</td>
    <td>${escapeHtml(String(Math.round(Number(item.miss_rate ?? 0) * 100)))}%</td>
  </tr>`;
}

export async function renderSchedulerInsights() {
  const container = qs('scheduler-insights-panel');
  if (!container) return;
  if (!renderAccessState(container)) return;

  container.innerHTML = '<p class="loading">Lade Scheduler-Daten…</p>';
  const canWriteSettings = hasPermission('settings:write');

  let heatmap = [];
  let recommendations = [];
  let prewarmCandidates = [];
  let historicalTrend = [];
  let historicalHeatmap = [];
  let forecast24h = [];
  let config = {};
  let savedCpuHours = 0;
  let savedCpuHoursByPool = [];
  let savedCpuHoursByUser = [];
  let warmPoolRecommendations = [];
  let prewarmHitCount = 0;
  let prewarmMissCount = 0;
  let prewarmHitRate = 0;
  let greenWindowActive = false;
  let warmPoolAutoApply = {};
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
    savedCpuHoursByPool = Array.isArray(data.saved_cpu_hours_by_pool) ? data.saved_cpu_hours_by_pool : [];
    savedCpuHoursByUser = Array.isArray(data.saved_cpu_hours_by_user) ? data.saved_cpu_hours_by_user : [];
    warmPoolRecommendations = Array.isArray(data.warm_pool_recommendations) ? data.warm_pool_recommendations : [];
    prewarmHitCount = Number(data.prewarm_hit_count || 0);
    prewarmMissCount = Number(data.prewarm_miss_count || 0);
    prewarmHitRate = Number(data.prewarm_hit_rate || 0);
    greenWindowActive = Boolean(data.green_window_active);
    warmPoolAutoApply = data.warm_pool_auto_apply || {};
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

  const rebalanceBtn = `<button class="btn btn-secondary" id="scheduler-rebalance-btn" ${canWriteSettings ? '' : 'disabled'}>
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
  const byPoolHtml = savedCpuHoursByPool.length > 0
    ? `<table class="data-table">
        <thead><tr><th>Pool</th><th>Kandidaten</th><th>Saved CPU-Hours</th></tr></thead>
        <tbody>${savedCpuHoursByPool.map((item) => breakdownRow(item, 'pool_id')).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine Pool-Auswertung verfügbar.</div>';
  const byUserHtml = savedCpuHoursByUser.length > 0
    ? `<table class="data-table">
        <thead><tr><th>User</th><th>Kandidaten</th><th>Saved CPU-Hours</th></tr></thead>
        <tbody>${savedCpuHoursByUser.map((item) => breakdownRow(item, 'user_id')).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine User-Auswertung verfügbar.</div>';
  const warmPoolHtml = warmPoolRecommendations.length > 0
    ? `<table class="data-table">
        <thead><tr><th>Pool</th><th>Warm aktuell</th><th>Empfohlen</th><th>Hits / Misses</th><th>Miss-Rate</th></tr></thead>
        <tbody>${warmPoolRecommendations.map(warmPoolRow).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine Warm-Pool-Empfehlungen erforderlich.</div>';

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
      <p class="muted-text">Prewarm Hit Rate: <strong>${escapeHtml(String(Math.round(prewarmHitRate * 100)))}%</strong> (${escapeHtml(String(prewarmHitCount))} Hits / ${escapeHtml(String(prewarmMissCount))} Misses)</p>
      ${prewarmHtml}
      ${trendHtml}
      ${forecastHtml}
      <div class="section-spaced-tight">
        <h4>Saved CPU-Hours nach Pool</h4>
        ${byPoolHtml}
      </div>
      <div class="section-spaced-tight">
        <h4>Saved CPU-Hours nach User</h4>
        ${byUserHtml}
      </div>
      <div class="section-spaced-tight">
        <h4>Warm-Pool Empfehlungen</h4>
        ${warmPoolHtml}
        <p class="muted-text">Auto-Apply Status: <strong>${escapeHtml(String(warmPoolAutoApply.reason || 'disabled'))}</strong> · letzte Ausführung: <strong>${escapeHtml(String(warmPoolAutoApply.last_run_at || '—'))}</strong></p>
        <div class="panel-actions"><button class="btn btn-secondary" id="scheduler-apply-warm-pools-btn" ${canWriteSettings ? '' : 'disabled'}>Warm-Pool Empfehlungen anwenden</button></div>
      </div>
      <div class="detail-grid section-spaced-tight">
        <label>Prewarm Minuten<input id="scheduler-config-prewarm" type="number" min="5" max="180" step="1" value="${escapeHtml(String(config.prewarm_minutes_ahead ?? 15))}"></label>
        <label class="checkbox-row"><input id="scheduler-config-green" type="checkbox" ${config.green_scheduling_enabled ? 'checked' : ''}> Green Scheduling aktiv</label>
        <label class="checkbox-row"><input id="scheduler-config-warm-auto-apply" type="checkbox" ${config.warm_pool_auto_apply_enabled ? 'checked' : ''}> Warm-Pool Auto-Apply aktiv</label>
        <label>Green Hours CSV<input id="scheduler-config-green-hours" type="text" value="${escapeHtml(Array.isArray(config.green_hours) ? config.green_hours.join(',') : '')}" placeholder="10,11,12,13"></label>
        <label>Auto-Apply max Pools / Run<input id="scheduler-config-warm-auto-max-pools" type="number" min="1" max="20" step="1" value="${escapeHtml(String(config.warm_pool_auto_apply_max_pools_per_run ?? 3))}"></label>
        <label>Auto-Apply max Warm-Increase<input id="scheduler-config-warm-auto-max-increase" type="number" min="1" max="10" step="1" value="${escapeHtml(String(config.warm_pool_auto_apply_max_increase ?? 2))}"></label>
        <label>Auto-Apply min Miss-Rate<input id="scheduler-config-warm-auto-min-miss" type="number" min="0" max="1" step="0.05" value="${escapeHtml(String(config.warm_pool_auto_apply_min_miss_rate ?? 0.35))}"></label>
        <label>Auto-Apply Cooldown Minuten<input id="scheduler-config-warm-auto-cooldown" type="number" min="5" max="720" step="1" value="${escapeHtml(String(config.warm_pool_auto_apply_cooldown_minutes ?? 30))}"></label>
      </div>
      <div class="panel-actions">
        <button class="btn btn-primary" id="scheduler-config-save-btn" ${canWriteSettings ? '' : 'disabled'}>Scheduler-Konfiguration speichern</button>
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
            warm_pool_auto_apply_enabled: Boolean(container.querySelector('#scheduler-config-warm-auto-apply')?.checked),
            warm_pool_auto_apply_max_pools_per_run: Number(container.querySelector('#scheduler-config-warm-auto-max-pools')?.value || 3),
            warm_pool_auto_apply_max_increase: Number(container.querySelector('#scheduler-config-warm-auto-max-increase')?.value || 2),
            warm_pool_auto_apply_min_miss_rate: Number(container.querySelector('#scheduler-config-warm-auto-min-miss')?.value || 0.35),
            warm_pool_auto_apply_cooldown_minutes: Number(container.querySelector('#scheduler-config-warm-auto-cooldown')?.value || 30),
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

  const applyWarmPoolsButton = container.querySelector('#scheduler-apply-warm-pools-btn');
  if (applyWarmPoolsButton) {
    applyWarmPoolsButton.addEventListener('click', async () => {
      applyWarmPoolsButton.disabled = true;
      try {
        await request('/scheduler/warm-pools/apply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ recommendations: warmPoolRecommendations }),
        });
        schedulerHooks.setBanner('Warm-Pool Empfehlungen angewendet.');
        renderSchedulerInsights();
      } catch (err) {
        schedulerHooks.setBanner(`Warm-Pool Fehler: ${err.message ?? err}`);
        applyWarmPoolsButton.disabled = false;
      }
    });
  }
}
