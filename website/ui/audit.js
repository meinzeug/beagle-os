import { fetchWithTimeout, resolveApiTarget, request, runSingleFlight } from './api.js';
import { buildAuthHeaders } from './auth.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';
import { t } from './i18n.js';

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

function redactAuditDetail(value) {
  if (Array.isArray(value)) {
    return value.map((item) => redactAuditDetail(item));
  }
  if (value && typeof value === 'object') {
    const output = {};
    Object.keys(value).forEach((key) => {
      if (/(password|token|secret|key)/i.test(key)) {
        output[key] = '[REDACTED]';
      } else {
        output[key] = redactAuditDetail(value[key]);
      }
    });
    return output;
  }
  return value;
}

function describeFilters(filters) {
  const parts = [];
  if (filters.user_id) parts.push('User ' + filters.user_id);
  if (filters.action) parts.push('Action ' + filters.action);
  if (filters.resource_type) parts.push('Resource ' + filters.resource_type);
  if (filters.tenant_id) parts.push('Tenant ' + filters.tenant_id);
  return parts.join(', ') || t('audit.no_extra_filters');
}

function resultChip(result) {
  const r = String(result || '').toLowerCase();
  if (r === 'success' || r === 'ok') return '<span class="status-chip ok">' + escapeHtml(result) + '</span>';
  if (r === 'failure' || r === 'error' || r === 'denied') return '<span class="status-chip err">' + escapeHtml(result) + '</span>';
  return '<span class="status-chip">' + escapeHtml(result) + '</span>';
}

function renderAuditRows() {
  const body = qs('audit-table-body');
  if (!body) {
    return;
  }
  if (state.auditLoading) {
    body.innerHTML = '<tr><td colspan="7" class="empty-cell loading">' + escapeHtml(t('audit.loading')) + '</td></tr>';
    return;
  }
  if (state.auditError) {
    body.innerHTML = '<tr><td colspan="7" class="empty-cell">' +
      escapeHtml(t('audit.load_failed_inline', { error: String(state.auditError || '') })) +
      ' <button class="button ghost small" type="button" data-audit-retry="1">' +
      escapeHtml(t('action.retry')) +
      '</button></td></tr>';
    return;
  }
  const events = Array.isArray(state.auditReport) ? state.auditReport : [];
  if (!events.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-cell">' + escapeHtml(t('audit.no_events_current_filter')) + '</td></tr>';
    return;
  }
  body.innerHTML = events.map((event) => {
    const redacted = redactAuditDetail(event);
    const details = escapeHtml(JSON.stringify(redacted, null, 2));
    const hasRedaction = JSON.stringify(redacted).includes('[REDACTED]');
    return '<tr>' +
      '<td class="ts-cell">' + escapeHtml(String(event.timestamp || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.action || '')) + '</td>' +
      '<td>' + resultChip(event.result || '') + '</td>' +
      '<td>' + escapeHtml(String(event.user_id || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.resource_type || '')) + '</td>' +
      '<td>' + escapeHtml(String(event.resource_id || '')) + '</td>' +
      '<td><details><summary>JSON' + (hasRedaction ? ' <span class="status-chip warn">redacted</span>' : '') + '</summary><pre class="schema-code">' + details + '</pre></details></td>' +
      '</tr>';
  }).join('');
}

export function renderAuditExportTargets(targets) {
  const container = qs('audit-export-targets');
  if (!container) return;
  const list = Array.isArray(targets) ? targets : [];
  if (!list.length) {
    container.innerHTML = '<p class="empty-cell">Keine Export-Targets konfiguriert.</p>';
    return;
  }
  container.innerHTML = list.map((t) => {
    const enabled = t.enabled ? true : false;
    const chip = enabled
      ? '<span class="status-chip ok">aktiv</span>'
      : '<span class="status-chip off">inaktiv</span>';
    const detail = t.detail ? '<span class="audit-target-detail">' + escapeHtml(String(t.detail)) + '</span>' : '';
    const lastError = t.last_error ? '<span class="audit-target-error">Letzter Fehler: ' + escapeHtml(String(t.last_error)) + '</span>' : '';
    return '<div class="audit-target-card">' +
      '<span class="audit-target-label">' + escapeHtml(String(t.label || t.type || '')) + '</span>' +
      chip + detail + lastError +
      '<button class="button ghost small" type="button" data-audit-target-test="' + escapeHtml(String(t.type || '')) + '">Test</button>' +
      '</div>';
  }).join('');
}

export function loadAuditExportTargets() {
  return request('/audit/export-targets').then((payload) => {
    const targets = Array.isArray(payload && payload.targets) ? payload.targets : [];
    renderAuditExportTargets(targets);
  }).catch(() => {
    renderAuditExportTargets([]);
  });
}

export function renderAuditFailureQueue(failures) {
  const body = qs('audit-failures-body');
  if (!body) return;
  const list = Array.isArray(failures) ? failures : [];
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="4" class="empty-cell">Keine Export-Fehler.</td></tr>';
    return;
  }
  body.innerHTML = list.map((f) => {
    const hasPayload = f.payload ? '<span class="status-chip ok">replay-ready</span>' : '<span class="status-chip off">legacy</span>';
    return '<tr>' +
      '<td>' + escapeHtml(String(f.timestamp || '')) + '</td>' +
      '<td>' + escapeHtml(String(f.target || '')) + '</td>' +
      '<td>' + escapeHtml(String(f.event_id || '')) + '</td>' +
      '<td>' + hasPayload + ' ' + escapeHtml(String(f.error || '')) + '</td>' +
      '</tr>';
  }).join('');
}

export function loadAuditFailureQueue() {
  return request('/audit/failures').then((payload) => {
    const failures = Array.isArray(payload && payload.failures) ? payload.failures : [];
    renderAuditFailureQueue(failures);
  }).catch(() => {
    renderAuditFailureQueue([]);
  });
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
  if (qs('audit-builder-range')) qs('audit-builder-range').textContent = filters.range === 'custom' ? ((filters.start || '-') + ' bis ' + (filters.end || '-')) : filters.range;
  if (qs('audit-builder-filters')) qs('audit-builder-filters').textContent = describeFilters(filters);
  syncCustomRangeVisibility();
  renderAuditRows();
}

export function loadAuditReport() {
  const filters = readAuditFiltersFromDom();
  state.auditFilters = filters;
  state.auditLoading = true;
  state.auditError = '';
  renderAudit();
  const params = buildQueryFromFilters(filters);
  return runSingleFlight('audit-report-load', () => {
    return request('/audit/report?' + params.toString()).then((payload) => {
      state.auditLoading = false;
      state.auditError = '';
      state.auditReport = Array.isArray(payload && payload.events) ? payload.events : [];
      renderAudit();
      auditHooks.setBanner('Audit-Report aktualisiert.', 'info');
      return payload;
    }).catch((error) => {
      state.auditLoading = false;
      state.auditError = String(error && error.message ? error.message : error || 'unknown');
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

export function runAuditReportBuilder() {
  const format = String(qs('audit-builder-format') ? qs('audit-builder-format').value : 'csv');
  if (qs('audit-builder-status')) qs('audit-builder-status').textContent = 'Laeuft...';
  const startedAt = new Date().toISOString();
  const finish = (status) => {
    if (qs('audit-builder-status')) qs('audit-builder-status').textContent = status;
    const container = qs('audit-compliance-reports');
    if (container) {
      const filters = readAuditFiltersFromDom();
      const item = '<div class="audit-report-card">' +
        '<strong>' + escapeHtml(format.toUpperCase()) + ' Report</strong>' +
        '<span>' + escapeHtml(startedAt) + '</span>' +
        '<span>' + escapeHtml(describeFilters(filters)) + '</span>' +
        '<span>Checksum: browser-download</span>' +
        '</div>';
      container.innerHTML = item + container.innerHTML.replace('<p class="empty-cell">Noch keine Reports in dieser Sitzung erzeugt.</p>', '');
    }
  };
  if (format === 'json') {
    return loadAuditReport().then(() => finish('JSON geladen')).catch(() => {
      if (qs('audit-builder-status')) qs('audit-builder-status').textContent = 'Fehler';
    });
  }
  return exportAuditCsv().then(() => finish('CSV exportiert')).catch(() => {
    if (qs('audit-builder-status')) qs('audit-builder-status').textContent = 'Fehler';
  });
}

export function testAuditExportTarget(target) {
  const safeTarget = String(target || '').trim();
  if (!safeTarget) return Promise.resolve();
  return runSingleFlight('audit-target-test:' + safeTarget, () => {
    return request('/audit/export-targets/' + encodeURIComponent(safeTarget) + '/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    }).then(() => {
      auditHooks.setBanner('Audit-Exportziel getestet: ' + safeTarget, 'ok');
      return loadAuditExportTargets();
    }).catch((error) => {
      auditHooks.setBanner('Exportziel-Test fehlgeschlagen: ' + error.message, 'warn');
      return loadAuditExportTargets();
    });
  });
}

export function replayAuditFailures() {
  return runSingleFlight('audit-failure-replay', () => {
    return request('/audit/failures/replay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: 100 })
    }).then((payload) => {
      auditHooks.setBanner('Audit-Replay abgeschlossen: ' + String(payload.replayed || 0) + ' erneut gesendet.', 'ok');
      return loadAuditFailureQueue();
    }).catch((error) => {
      auditHooks.setBanner('Audit-Replay fehlgeschlagen: ' + error.message, 'warn');
    });
  });
}

export function onAuditRangeChanged() {
  state.auditFilters = Object.assign(activeFilters(), { range: String(qs('audit-filter-range') ? qs('audit-filter-range').value : '24h') });
  syncCustomRangeVisibility();
}
