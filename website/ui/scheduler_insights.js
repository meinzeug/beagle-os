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

export async function renderSchedulerInsights() {
  const container = qs('scheduler-insights-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Scheduler-Daten…</p>';

  let heatmap = [];
  let recommendations = [];
  try {
    const data = await request('/scheduler/insights');
    heatmap = Array.isArray(data.heatmap) ? data.heatmap : [];
    recommendations = Array.isArray(data.recommendations) ? data.recommendations : [];
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

  container.innerHTML = `
    <section class="panel-section">
      <h3>Node-Auslastung (Heatmap)</h3>
      ${heatHtml}
    </section>
    <section class="panel-section">
      <h3>Placement-Empfehlungen</h3>
      ${recHtml}
      <div class="panel-actions">${rebalanceBtn}</div>
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
}
