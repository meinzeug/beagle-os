import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';

const costHooks = {
  setBanner() {}
};

export function configureCostDashboard(nextHooks) {
  Object.assign(costHooks, nextHooks || {});
}

function formatEur(value) {
  return (Number(value) || 0).toFixed(2) + ' €';
}

function alertBadge(alert) {
  if (!alert) return '';
  const tone = alert.exceeded ? 'critical' : 'warn';
  return `<span class="badge tone-${tone}">${escapeHtml(alert.department)}: ${formatEur(alert.current)}/${formatEur(alert.budget)}</span>`;
}

function departmentRow(dept) {
  return `<tr>
    <td>${escapeHtml(dept.department ?? '-')}</td>
    <td>${escapeHtml(String(dept.session_count ?? 0))}</td>
    <td>${formatEur(dept.cpu_cost_eur)}</td>
    <td>${formatEur(dept.gpu_cost_eur)}</td>
    <td><strong>${formatEur(dept.total_cost_eur)}</strong></td>
  </tr>`;
}

export async function renderCostDashboard() {
  const container = qs('cost-dashboard-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Kostendaten…</p>';

  let report = null;
  let budgetAlerts = [];
  const now = new Date();
  const month = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;

  try {
    [report, budgetAlerts] = await Promise.all([
      request('GET', `/api/v1/costs/chargeback?month=${month}`),
      request('GET', '/api/v1/costs/budget-alerts').catch(() => [])
    ]);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  const departments = Array.isArray(report?.departments) ? report.departments : [];
  const alerts = Array.isArray(budgetAlerts) ? budgetAlerts : [];

  const alertsHtml = alerts.length > 0
    ? `<div class="alert-strip">${alerts.map(alertBadge).join(' ')}</div>`
    : '';

  let tableHtml = '<div class="empty-card">Keine Kostendaten für diesen Monat.</div>';
  if (departments.length > 0) {
    const rows = departments.map(departmentRow).join('');
    const total = departments.reduce((sum, d) => sum + (Number(d.total_cost_eur) || 0), 0);
    tableHtml = `<table class="data-table">
      <thead>
        <tr>
          <th>Abteilung</th>
          <th>Sessions</th>
          <th>CPU-Kosten</th>
          <th>GPU-Kosten</th>
          <th>Gesamt</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
      <tfoot>
        <tr>
          <td colspan="4"><strong>Gesamt</strong></td>
          <td><strong>${formatEur(total)}</strong></td>
        </tr>
      </tfoot>
    </table>`;
  }

  const csvBtn = `<button class="btn btn-secondary" id="cost-csv-export-btn">
    Chargeback CSV exportieren
  </button>`;

  container.innerHTML = `
    ${alertsHtml}
    <section class="panel-section">
      <h3>Kosten nach Abteilung — ${escapeHtml(month)}</h3>
      ${tableHtml}
      <div class="panel-actions">${csvBtn}</div>
    </section>`;

  const csvButton = container.querySelector('#cost-csv-export-btn');
  if (csvButton) {
    csvButton.addEventListener('click', async () => {
      csvButton.disabled = true;
      try {
        const csv = await request('GET', `/api/v1/costs/chargeback.csv?month=${month}`, null, { responseType: 'text' });
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chargeback_${month}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        costHooks.setBanner(`CSV-Export Fehler: ${err.message ?? err}`);
      } finally {
        csvButton.disabled = false;
      }
    });
  }
}
