import { fetchWithTimeout, resolveApiTarget, request, runSingleFlight } from './api.js';
import { buildAuthHeaders } from './auth.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';

const auditHooks = {
  setBanner() {}
};

function activeFilters() {
  return Object.assign({
    range: '24h',
    start: '',
    end: '',
    tenant_id: '',
    action: '',
    resource_type: '',
    user_id: ''
  }, state.auditFilters || {});
}

function nowIso() {
  return new Date().toISOString();
}

function isoBefore(hours) {
  const value = new Date(Date.now() - (hours * 60 * 60 * 1000));
  return value.toISOString();
}

function buildQueryFromFilters(filters) {
  const params = new URLSearchParams();
  const range = String(filters.range || '24h');
  const start = String(filters.start || '').trim();
  const end = String(filters.end || '').trim();
  if (range === '1h') {
    params.set('start', isoBefore(1));
    params.set('end', nowIso());
  } else if (range === '24h') {
    params.set('start', isoBefore(24));
    params.set('end', nowIso());
  } else if (range === '7d') {
    params.set('start', isoBefore(24 * 7));
    params.set('end', nowIso());
  } else {
    if (start) params.set('start', start);
    if (end) params.set('end', end);
  }
  if (filters.tenant_id) params.set('tenant_id', String(filters.tenant_id));
  if (filters.action) params.set('action', String(filters.action));
  if (filters.resource_type) params.set('resource_type', String(filters.resource_type));
  if (filters.user_id) params.set('user_id', String(filters.user_id));
  return params;
}

function readAuditFiltersFromDom() {
  const range = String(qs('audit-filter-range') ? qs('audit-filter-range').value : '24h');
  return {
    range,
    start: String(qs('audit-filter-start') ? qs('audit-filter-start').value : '').trim(),
    end: String(qs('audit-filter-end') ? qs('audit-filter-end').value : '').trim(),
    tenant_id: String(qs('audit-filter-tenant') ? qs('audit-filter-tenant').value : '').trim(),
    action: String(qs('audit-filter-action') ? qs('audit-filter-action').value : '').trim(),
    resource_type: String(qs('audit-filter-resource') ? qs('audit-filter-resource').value : '').trim(),
    user_id: String(qs('audit-filter-user') ? qs('audit-filter-user').value : '').trim()
  };
}

function syncCustomRangeVisibility() {
  const filters = activeFilters();
  const custom = filters.range === 'custom';
  const startField = qs('audit-filter-start');
  const endField = qs('audit-filter-end');
  if (startField) startField.disabled = !custom;
  if (endField) endField.disabled = !custom;
}

function formatJsonCell(value) {
  if (value === null || value === undefined || value === '') {
    return 'null';
  }
  return JSON.stringify(value, null, 2);
}

function renderAuditRows() {
  const body = qs('audit-table-body');
  if (!body) {
    return;
  }
  const events = Array.isArray(state.auditReport) ? state.auditReport : [];
  if (!events.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-cell">Keine Audit-Events fuer den aktuellen Filter.</td></tr>';
    return;
  }
  body.innerHTML = events.map((event, index) => {
    const details = escapeHtml(JSON.stringify(event, null, 2));
    return '<tr>' +
      '<td>' + escapeHtml(String(event.timestamp || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.action || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.result || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.user_id || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.resource_type || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.resource_id || '')) + '</td>' +
      '<td><details><summary>JSON</summary><pre class="schema-code">' + details + '</pre></details></td>' +
      '</tr>';
  }).join('');
}

export function configureAudit(nextHooks) {
  Object.assign(auditHooks, nextHooks || {});
}

export function renderAudit() {
  const filters = activeFilters();
  if (qs('audit-filter-range')) qs('audit-filter-range').value = filters.range;
  if (qs('audit-filter-start')) qs('audit-filter-start').value = filters.start;
  if (qs('audit-filter-end')) qs('audit-filter-end').value = filters.end;
  if (qs('audit-filter-tenant')) qs('audit-filter-tenant').value = filters.tenant_id;
  if (qs('audit-filter-action')) qs('audit-filter-action').value = filters.action;
  if (qs('audit-filter-resource')) qs('audit-filter-resource').value = filters.resource_type;
  if (qs('audit-filter-user')) qs('audit-filter-user').value = filters.user_id;
  if (qs('audit-count')) qs('audit-count').textContent = String((state.auditReport || []).length);
  syncCustomRangeVisibility();
  renderAuditRows();
}

export function loadAuditReport() {
  const filters = readAuditFiltersFromDom();
  state.auditFilters = filters;
  const params = buildQueryFromFilters(filters);
  return runSingleFlight('audit-report-load', () => {
    return request('/audit/report?' + params.toString()).then((payload) => {
      state.auditReport = Array.isArray(payload && payload.events) ? payload.events : [];
      renderAudit();
      auditHooks.setBanner('Audit-Report aktualisiert.', 'info');
      return payload;
    }).catch((error) => {
      state.auditReport = [];
      renderAudit();
      auditHooks.setBanner('Audit-Report laden fehlgeschlagen: ' + error.message, 'warn');
      throw error;
    });
  });
}

export function resetAuditFilters() {
  state.auditFilters = {
    range: '24h',
    start: '',
    end: '',
    tenant_id: '',
    action: '',
    resource_type: '',
    user_id: ''
  };
  renderAudit();
}

export function exportAuditCsv() {
  const filters = readAuditFiltersFromDom();
  state.auditFilters = filters;
  const params = buildQueryFromFilters(filters);
  const target = resolveApiTarget('/audit/report?' + params.toString());
  return fetchWithTimeout(target, {
    method: 'GET',
    credentials: 'same-origin',
    headers: Object.assign({ Accept: 'text/csv' }, buildAuthHeaders())
  }).then((response) => {
    if (!response.ok) {
      throw new Error('HTTP ' + response.status + ' downloading');
    }
    return response.blob();
  }).then((blob) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'audit-report.csv';
    document.body.appendChild(link);
    link.click();
    window.setTimeout(() => {
      URL.revokeObjectURL(url);
      link.remove();
    }, 1000);
    auditHooks.setBanner('Audit-CSV exportiert.', 'ok');
  }).catch((error) => {
    auditHooks.setBanner('Audit-CSV Export fehlgeschlagen: ' + error.message, 'warn');
    throw error;
  });
}

export function onAuditRangeChanged() {
  state.auditFilters = Object.assign(activeFilters(), { range: String(qs('audit-filter-range') ? qs('audit-filter-range').value : '24h') });
  syncCustomRangeVisibility();
}