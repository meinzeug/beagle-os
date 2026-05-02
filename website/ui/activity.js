import {
  ACTIVITY_LOG_MAX,
  state
} from './state.js';
import { chip, escapeHtml, formatDate, qs } from './dom.js';
import { t } from './i18n.js';

let dashboardPollInterval = null;

const activityHooks = {
  loadDashboard() {
    return Promise.resolve();
  },
  loadAuditReport() {
    return Promise.resolve();
  },
  setBanner() {}
};

const activityLog = [];

export function configureActivity(nextHooks) {
  Object.assign(activityHooks, nextHooks || {});
}

export function addToActivityLog(action, vmid, result, message) {
  activityLog.unshift({
    ts: Date.now(),
    action: String(action || 'action'),
    vmid: vmid || null,
    result: String(result || 'ok'),
    message: String(message || '')
  });
  if (activityLog.length > ACTIVITY_LOG_MAX) {
    activityLog.length = ACTIVITY_LOG_MAX;
  }
  renderActivityLog();
}

export function renderActivityLog() {
  const body = qs('activity-log-body');
  if (!body) {
    return;
  }
  if (!activityLog.length) {
    body.innerHTML = '<tr><td colspan="4" class="empty-cell">' + escapeHtml(t('activity.none_logged')) + '</td></tr>';
    return;
  }
  body.innerHTML = activityLog.slice(0, 20).map((entry) => {
    const tone = entry.result === 'ok' ? 'ok' : entry.result === 'warn' ? 'warn' : 'muted';
    return '<tr>' +
      '<td class="vm-sub">' + escapeHtml(formatDate(new Date(entry.ts))) + '</td>' +
      '<td>' + escapeHtml(entry.action) + '</td>' +
      '<td>' + (entry.vmid ? escapeHtml(String(entry.vmid)) : '–') + '</td>' +
      '<td>' + chip(entry.result, tone) + '</td>' +
      '</tr>';
  }).join('');
}

export function updateFleetHealthAlert() {
  const alertNode = qs('fleet-health-alert');
  if (!alertNode) {
    return;
  }
  const rows = Array.isArray(state.endpointReports) ? state.endpointReports : [];
  const unhealthy = rows.filter((ep) => {
    const status = String(ep.status || ep.health_status || '').toLowerCase();
    return status === 'stale' || status === 'offline' || status === 'error' || status === 'unknown';
  });
  if (unhealthy.length) {
    alertNode.classList.remove('hidden');
    const names = unhealthy.slice(0, 5).map((ep) => {
      return ep.hostname || ep.endpoint_id || 'endpoint';
    });
    alertNode.textContent = t('activity.fleet_unhealthy', {
      count: unhealthy.length,
      names: names.join(', '),
      more: unhealthy.length > 5 ? ' ...' : ''
    });
  } else {
    alertNode.classList.add('hidden');
  }
}

export function startDashboardPoll() {
  if (dashboardPollInterval) {
    return;
  }
  dashboardPollInterval = window.setInterval(() => {
    if (!state.autoRefresh || !state.token || document.hidden) {
      return;
    }
    if (state.liveFeedConnected) {
      return;
    }
    if (state.activePanel === 'audit') {
      activityHooks.loadAuditReport();
      return;
    }
    activityHooks.loadDashboard();
  }, 30000);
}

export function stopDashboardPoll() {
  if (dashboardPollInterval) {
    window.clearInterval(dashboardPollInterval);
    dashboardPollInterval = null;
  }
}

export function toggleAutoRefresh() {
  state.autoRefresh = !state.autoRefresh;
  if (state.autoRefresh) {
    startDashboardPoll();
    activityHooks.setBanner(t('activity.auto_refresh_enabled'), 'info');
  } else {
    stopDashboardPoll();
    activityHooks.setBanner(t('activity.auto_refresh_paused'), 'warn');
  }
  updateAutoRefreshButton();
}

export function updateAutoRefreshButton() {
  const btn = qs('toggle-auto-refresh');
  if (!btn) {
    return;
  }
  if (state.autoRefresh) {
    btn.textContent = t('auto_refresh.on');
    btn.className = 'button ghost';
  } else {
    btn.textContent = t('auto_refresh.off');
    btn.className = 'button paused';
  }
}