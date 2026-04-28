import { blobRequest, request } from './api.js';
import { escapeHtml, qs } from './dom.js';

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

function budgetRow(item) {
  return `<tr>
    <td>${escapeHtml(item.department ?? '-')}</td>
    <td>${formatEur(item.monthly_budget)}</td>
    <td>${escapeHtml(String(item.alert_at_percent ?? 80))}%</td>
    <td>${escapeHtml(item.last_alerted_at || '—')}</td>
  </tr>`;
}

function topVmRow(item) {
  return `<tr>
    <td>${escapeHtml(String(item.vm_id ?? '-'))}</td>
    <td>${escapeHtml(item.department ?? '-')}</td>
    <td>${escapeHtml(item.user_id ?? '-')}</td>
    <td>${escapeHtml(String(item.session_count ?? 0))}</td>
    <td>${formatEur(item.energy_cost_eur)}</td>
    <td><strong>${formatEur(item.total_cost_eur)}</strong></td>
  </tr>`;
}

export async function renderCostDashboard() {
  const container = qs('cost-dashboard-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Kostendaten…</p>';

  let report = null;
  let budgetAlerts = [];
  let modelPayload = null;
  const now = new Date();
  const month = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;

  try {
    [report, budgetAlerts, modelPayload] = await Promise.all([
      request(`/costs/chargeback?month=${month}`),
      request(`/costs/budget-alerts?month=${month}`).catch(() => ({ alerts: [] })),
      request('/costs/model').catch(() => ({ model: {}, budgets: [] }))
    ]);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  const departments = Array.isArray(report?.departments) ? report.departments : [];
  const alerts = Array.isArray(budgetAlerts?.alerts) ? budgetAlerts.alerts : [];
  const model = modelPayload?.model || {};
  const budgets = Array.isArray(modelPayload?.budgets) ? modelPayload.budgets : [];
  const topVms = Array.isArray(report?.top_vms) ? report.top_vms : [];
  const forecastTotal = Number(report?.forecast_total_cost_eur || 0);
  const totalEnergyCost = Number(report?.total_energy_cost_eur || 0);

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
  const budgetsHtml = budgets.length
    ? `<table class="data-table">
        <thead><tr><th>Abteilung</th><th>Budget</th><th>Alert bei</th><th>Letzter Alert</th></tr></thead>
        <tbody>${budgets.map(budgetRow).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine Budget-Regeln hinterlegt.</div>';
  const topVmHtml = topVms.length
    ? `<table class="data-table">
        <thead><tr><th>VM</th><th>Abteilung</th><th>User</th><th>Sessions</th><th>Energie</th><th>Gesamt</th></tr></thead>
        <tbody>${topVms.map(topVmRow).join('')}</tbody>
      </table>`
    : '<div class="empty-card">Keine VM-Kostendaten für diesen Monat.</div>';

  container.innerHTML = `
    ${alertsHtml}
    <section class="panel-section">
      <h3>Kosten nach Abteilung — ${escapeHtml(month)}</h3>
      <div class="detail-grid section-spaced-tight">
        <div><strong>Forecast Monatsende</strong><div>${formatEur(forecastTotal)}</div></div>
        <div><strong>Energiekosten gesamt</strong><div>${formatEur(totalEnergyCost)}</div></div>
      </div>
      ${tableHtml}
      <div class="panel-actions">${csvBtn}</div>
    </section>
    <section class="panel-section">
      <h3>Top-10 kostenintensive VMs</h3>
      ${topVmHtml}
    </section>
    <section class="panel-section">
      <h3>Kostenmodell</h3>
      <div class="detail-grid">
        <label>CPU €/h<input id="cost-model-cpu" type="number" step="0.0001" value="${escapeHtml(String(model.cpu_hour_cost ?? 0.002))}"></label>
        <label>RAM GB €/h<input id="cost-model-ram" type="number" step="0.0001" value="${escapeHtml(String(model.ram_gb_hour_cost ?? 0.0005))}"></label>
        <label>GPU €/h<input id="cost-model-gpu" type="number" step="0.0001" value="${escapeHtml(String(model.gpu_hour_cost ?? 0.1))}"></label>
        <label>Storage GB €/Monat<input id="cost-model-storage" type="number" step="0.0001" value="${escapeHtml(String(model.storage_gb_month_cost ?? 0.05))}"></label>
        <label>Strom €/kWh<input id="cost-model-electricity" type="number" step="0.0001" value="${escapeHtml(String(model.electricity_price_per_kwh ?? 0.3))}"></label>
      </div>
      <div class="panel-actions">
        <button class="btn btn-primary" id="cost-model-save-btn">Kostenmodell speichern</button>
      </div>
    </section>
    <section class="panel-section">
      <h3>Budget-Regeln</h3>
      ${budgetsHtml}
      <div class="detail-grid section-spaced-tight">
        <label>Abteilung<input id="cost-budget-department" type="text" placeholder="marketing"></label>
        <label>Monatsbudget €<input id="cost-budget-value" type="number" step="0.01" placeholder="1000"></label>
        <label>Alert bei %<input id="cost-budget-threshold" type="number" step="1" min="1" max="100" value="80"></label>
      </div>
      <div class="panel-actions">
        <button class="btn btn-secondary" id="cost-budget-save-btn">Budget-Regel speichern</button>
      </div>
    </section>`;

  const csvButton = container.querySelector('#cost-csv-export-btn');
  if (csvButton) {
    csvButton.addEventListener('click', async () => {
      csvButton.disabled = true;
      try {
        await blobRequest(`/costs/chargeback.csv?month=${month}`, `chargeback_${month}.csv`);
      } catch (err) {
        costHooks.setBanner(`CSV-Export Fehler: ${err.message ?? err}`);
      } finally {
        csvButton.disabled = false;
      }
    });
  }

  const saveModelButton = container.querySelector('#cost-model-save-btn');
  if (saveModelButton) {
    saveModelButton.addEventListener('click', async () => {
      saveModelButton.disabled = true;
      try {
        await request('/costs/model', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            cpu_hour_cost: Number(container.querySelector('#cost-model-cpu')?.value || 0),
            ram_gb_hour_cost: Number(container.querySelector('#cost-model-ram')?.value || 0),
            gpu_hour_cost: Number(container.querySelector('#cost-model-gpu')?.value || 0),
            storage_gb_month_cost: Number(container.querySelector('#cost-model-storage')?.value || 0),
            electricity_price_per_kwh: Number(container.querySelector('#cost-model-electricity')?.value || 0),
          }),
        });
        costHooks.setBanner('Kostenmodell gespeichert.');
        renderCostDashboard();
      } catch (err) {
        costHooks.setBanner(`Kostenmodell Fehler: ${err.message ?? err}`);
        saveModelButton.disabled = false;
      }
    });
  }

  const saveBudgetButton = container.querySelector('#cost-budget-save-btn');
  if (saveBudgetButton) {
    saveBudgetButton.addEventListener('click', async () => {
      const department = String(container.querySelector('#cost-budget-department')?.value || '').trim();
      if (!department) {
        costHooks.setBanner('Abteilung ist erforderlich.');
        return;
      }
      saveBudgetButton.disabled = true;
      try {
        await request('/costs/model', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            budget_alert: {
              department,
              monthly_budget: Number(container.querySelector('#cost-budget-value')?.value || 0),
              alert_at_percent: Number(container.querySelector('#cost-budget-threshold')?.value || 80),
            },
          }),
        });
        costHooks.setBanner(`Budget-Regel für ${department} gespeichert.`);
        renderCostDashboard();
      } catch (err) {
        costHooks.setBanner(`Budget-Regel Fehler: ${err.message ?? err}`);
        saveBudgetButton.disabled = false;
      }
    });
  }
}
