import { request } from './api.js';
import { escapeHtml, fieldBlock, formatDate, qs } from './dom.js';
import { state } from './state.js';
import { t } from './i18n.js';

const sessionHooks = {
  setBanner() {}
};

export function configureSessions(nextHooks) {
  Object.assign(sessionHooks, nextHooks || {});
}

function numberOrDash(value, suffix) {
  if (value == null || value === '') {
    return '-';
  }
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return '-';
  }
  return String(Math.round(num)) + (suffix || '');
}

function qualityTone(metrics) {
  const rtt = Number(metrics && metrics.rtt_ms);
  const dropped = Number(metrics && metrics.dropped_frames);
  if (Number.isFinite(rtt) && rtt > 80) {
    return 'warn';
  }
  if (Number.isFinite(dropped) && dropped > 30) {
    return 'warn';
  }
  return 'ok';
}

function sessionSummary(metrics) {
  if (!metrics || typeof metrics !== 'object') {
    return t('sessions.telemetry_none');
  }
  return [
    'RTT ' + numberOrDash(metrics.rtt_ms, ' ms'),
    'FPS ' + numberOrDash(metrics.fps, ''),
    'Drop ' + numberOrDash(metrics.dropped_frames, ''),
    'Enc ' + numberOrDash(metrics.encoder_load, ' %')
  ].join(' · ');
}

function selectedSession() {
  const sessions = Array.isArray(state.sessions) ? state.sessions : [];
  return sessions.find((item) => String(item.session_id || '') === String(state.selectedSessionId || '')) || null;
}

function renderSessionDetail(session) {
  const detailNode = qs('session-detail-body');
  if (!detailNode) {
    return;
  }
  if (state.sessionsLoading) {
    detailNode.innerHTML = '<div class="empty-card loading">' + escapeHtml(t('sessions.loading')) + '</div>';
    return;
  }
  if (!session) {
    detailNode.innerHTML = '<div class="empty-card">' + escapeHtml(t('sessions.none_selected')) + '</div>';
    return;
  }
  const metrics = session.stream_health && typeof session.stream_health === 'object' ? session.stream_health : null;
  detailNode.innerHTML =
    '<div class="detail-grid">' +
    fieldBlock('Session ID', String(session.session_id || '-'), 'mono') +
    fieldBlock('User', String(session.user_id || '-')) +
    fieldBlock('Pool', String(session.pool_id || '-')) +
    fieldBlock('VMID', String(session.vmid || '-')) +
    fieldBlock('Modus', String(session.mode || '-')) +
    fieldBlock('Status', String(session.state || '-')) +
    fieldBlock('Zugeteilt', formatDate(session.assigned_at || '')) +
    fieldBlock('RTT', numberOrDash(metrics && metrics.rtt_ms, ' ms')) +
    fieldBlock('FPS', numberOrDash(metrics && metrics.fps, '')) +
    fieldBlock('Dropped Frames', numberOrDash(metrics && metrics.dropped_frames, '')) +
    fieldBlock('Encoder Load', numberOrDash(metrics && metrics.encoder_load, ' %')) +
    fieldBlock('Metrik-Update', formatDate(metrics && metrics.updated_at ? metrics.updated_at : '')) +
    '</div>';
}

export function renderSessionsPanel() {
  const bodyNode = qs('sessions-table-body');
  const countNode = qs('sessions-count-chip');
  if (!bodyNode) {
    return;
  }

  const sessions = Array.isArray(state.sessions) ? state.sessions.slice() : [];
  sessions.sort((a, b) => String(b.assigned_at || '').localeCompare(String(a.assigned_at || '')));

  if (countNode) {
    countNode.textContent = t('sessions.count_active', { count: sessions.length });
  }

  if (state.sessionsLoading) {
    bodyNode.innerHTML = '<tr><td colspan="6" class="empty-cell loading">' +
      escapeHtml(t('sessions.loading')) +
      '</td></tr>';
    renderSessionDetail(null);
    return;
  }

  if (state.sessionsError) {
    bodyNode.innerHTML = '<tr><td colspan="6" class="empty-cell">' +
      escapeHtml(t('sessions.load_failed_inline', { error: String(state.sessionsError || '') })) +
      ' <button type="button" class="button ghost small" data-sessions-retry="1">' +
      escapeHtml(t('action.retry')) +
      '</button></td></tr>';
    renderSessionDetail(null);
    return;
  }

  if (!sessions.length) {
    bodyNode.innerHTML = '<tr><td colspan="6" class="empty-cell">' + escapeHtml(t('empty.no_sessions')) + '</td></tr>';
    state.selectedSessionId = '';
    renderSessionDetail(null);
    return;
  }

  if (!state.selectedSessionId || !sessions.some((item) => String(item.session_id || '') === String(state.selectedSessionId))) {
    state.selectedSessionId = String(sessions[0].session_id || '');
  }

  bodyNode.innerHTML = sessions.map((item) => {
    const sid = String(item.session_id || '');
    const metrics = item.stream_health && typeof item.stream_health === 'object' ? item.stream_health : null;
    const selectedClass = sid === state.selectedSessionId ? ' active' : '';
    return '<tr class="session-row' + selectedClass + '" data-session-id="' + escapeHtml(sid) + '">' +
      '<td class="mono">' + escapeHtml(sid) + '</td>' +
      '<td>' + escapeHtml(String(item.user_id || '-')) + '</td>' +
      '<td>' + escapeHtml(String(item.pool_id || '-')) + '</td>' +
      '<td>' + escapeHtml(String(item.vmid || '-')) + '</td>' +
      '<td>' + escapeHtml(String(item.state || '-')) + '</td>' +
      '<td><span class="chip ' + qualityTone(metrics) + '">' + escapeHtml(sessionSummary(metrics)) + '</span></td>' +
      '</tr>';
  }).join('');

  renderSessionDetail(selectedSession());
}

export function reloadSessionsPanel() {
  state.sessionsLoading = true;
  state.sessionsError = '';
  renderSessionsPanel();
  return request('/sessions', { __suppressAuthLock: true }).then((payload) => {
    state.sessionsLoading = false;
    state.sessionsError = '';
    state.sessions = Array.isArray(payload && payload.sessions) ? payload.sessions : [];
    renderSessionsPanel();
    sessionHooks.setBanner(t('sessions.refreshed'), 'ok');
    return payload;
  }).catch((error) => {
    state.sessionsLoading = false;
    state.sessionsError = String(error && error.message ? error.message : error || 'unknown');
    renderSessionsPanel();
    sessionHooks.setBanner(t('sessions.load_failed', { error: state.sessionsError }), 'warn');
    throw error;
  });
}

export function bindSessionsEvents() {
  const refreshBtn = qs('sessions-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      reloadSessionsPanel().catch(() => {});
    });
  }

  const tableBody = qs('sessions-table-body');
  if (tableBody) {
    tableBody.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      if (target.closest('[data-sessions-retry]')) {
        reloadSessionsPanel().catch(() => {});
        return;
      }
      const row = target.closest('[data-session-id]');
      if (!row) {
        return;
      }
      state.selectedSessionId = String(row.getAttribute('data-session-id') || '');
      renderSessionsPanel();
    });
  }
}
