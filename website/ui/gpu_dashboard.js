import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';

const gpuHooks = {
  setBanner() {}
};

export function configureGpuDashboard(nextHooks) {
  Object.assign(gpuHooks, nextHooks || {});
}

function utilizationBar(pct) {
  const tone = pct > 85 ? 'critical' : pct > 65 ? 'warn' : 'ok';
  return `<div class="bar-track" title="${pct}%">
    <div class="bar-fill tone-${tone}" style="width:${Math.min(100, pct)}%"></div>
  </div>`;
}

function gpuRow(gpu) {
  const utilPct = Math.round(gpu.utilization_pct ?? 0);
  return `<tr>
    <td>${escapeHtml(gpu.gpu_id ?? '-')}</td>
    <td>${escapeHtml(gpu.node_id ?? '-')}</td>
    <td>${escapeHtml(gpu.model ?? '-')}</td>
    <td>${escapeHtml(gpu.gpu_class ?? '-')}</td>
    <td>${escapeHtml(String(gpu.vram_gb ?? 0))} GB</td>
    <td>${utilizationBar(utilPct)}<span>${utilPct}%</span></td>
    <td>${escapeHtml(gpu.assigned_vm_id ? String(gpu.assigned_vm_id) : '-')}</td>
    <td>
      ${gpu.assigned_vm_id
        ? `<button
            class="btn-sm btn-warning"
            data-action="gpu-migrate"
            data-gpuid="${escapeHtml(gpu.gpu_id ?? '')}"
            data-vmid="${escapeHtml(String(gpu.assigned_vm_id))}"
            title="VM migrieren"
          >Migrieren</button>`
        : '<span class="tone-ok">frei</span>'}
    </td>
  </tr>`;
}

function assignmentRow(a) {
  return `<tr>
    <td>${escapeHtml(a.gpu_id ?? '-')}</td>
    <td>${escapeHtml(String(a.vm_id ?? '-'))}</td>
    <td>${escapeHtml(a.mode ?? '-')}</td>
    <td>${escapeHtml(a.assigned_at ?? '-')}</td>
  </tr>`;
}

export async function renderGpuDashboard() {
  const container = qs('gpu-dashboard-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade GPU-Daten…</p>';

  let gpus = [];
  let assignments = [];
  let metrics = [];

  try {
    [gpus, assignments, metrics] = await Promise.all([
      request('GET', '/api/v1/gpus').then((d) => Array.isArray(d) ? d : (d.gpus ?? [])),
      request('GET', '/api/v1/gpus/assignments').catch(() => []),
      request('GET', '/api/v1/gpus/metrics').catch(() => [])
    ]);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  // Merge metrics into GPU objects
  const metricsMap = {};
  if (Array.isArray(metrics)) {
    metrics.forEach((m) => { metricsMap[m.gpu_id] = m; });
  }
  const gpusWithMetrics = gpus.map((g) => ({
    ...g,
    utilization_pct: metricsMap[g.gpu_id]?.avg_utilization_pct ?? 0
  }));

  const freeCount = gpus.filter((g) => !g.assigned_vm_id).length;
  const busyCount = gpus.length - freeCount;

  let gpuTableHtml = '<div class="empty-card">Keine GPUs erfasst.</div>';
  if (gpusWithMetrics.length > 0) {
    const rows = gpusWithMetrics.map(gpuRow).join('');
    gpuTableHtml = `<table class="data-table">
      <thead>
        <tr>
          <th>GPU</th>
          <th>Node</th>
          <th>Modell</th>
          <th>Klasse</th>
          <th>VRAM</th>
          <th>Auslastung</th>
          <th>Zugewiesen an</th>
          <th>Aktion</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  let assignHtml = '<div class="empty-card">Keine aktiven Zuweisungen.</div>';
  if (Array.isArray(assignments) && assignments.length > 0) {
    const aRows = assignments.map(assignmentRow).join('');
    assignHtml = `<table class="data-table">
      <thead>
        <tr><th>GPU</th><th>VM</th><th>Modus</th><th>Seit</th></tr>
      </thead>
      <tbody>${aRows}</tbody>
    </table>`;
  }

  container.innerHTML = `
    <div class="summary-strip">
      <span class="summary-item">${escapeHtml(String(gpus.length))} GPUs total</span>
      <span class="summary-item tone-ok">${escapeHtml(String(freeCount))} frei</span>
      <span class="summary-item tone-${busyCount > 0 ? 'warn' : 'ok'}">${escapeHtml(String(busyCount))} belegt</span>
    </div>
    <section class="panel-section">
      <h3>GPU-Pool-Auslastung</h3>
      ${gpuTableHtml}
    </section>
    <section class="panel-section">
      <h3>Aktive Zuweisungen</h3>
      ${assignHtml}
    </section>`;

  // Wire migration buttons
  container.querySelectorAll('[data-action="gpu-migrate"]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const gpuId = btn.dataset.gpuid;
      const vmId = btn.dataset.vmid;
      const target = prompt(`Ziel-Node für VM ${vmId} (GPU ${gpuId}):`)?.trim();
      if (!target) return;
      btn.disabled = true;
      try {
        await request('POST', '/api/v1/gpus/migrate', { gpu_id: gpuId, vm_id: vmId, target_node: target });
        gpuHooks.setBanner(`Migration von VM ${vmId} zu ${target} gestartet.`);
        renderGpuDashboard();
      } catch (err) {
        gpuHooks.setBanner(`Fehler: ${err.message ?? err}`);
        btn.disabled = false;
      }
    });
  });
}
