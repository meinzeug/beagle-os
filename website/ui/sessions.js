import { postJson, request } from './api.js';
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

const STREAM_PRESETS = {
  auto: { resolution: 'auto', fps: 'auto', bitrate: 'auto', packet_size: 'auto', video_codec: 'H.264', video_decoder: 'auto', audio_config: 'stereo', frame_pacing: 'auto', vsync: 'auto' },
  'lan-ultra': { resolution: 'auto', fps: 60, bitrate: 45000, packet_size: 1392, video_codec: 'H.264', video_decoder: 'auto', audio_config: 'stereo', frame_pacing: false, vsync: false },
  smooth: { resolution: '1920x1080', fps: 60, bitrate: 32000, packet_size: 1360, video_codec: 'H.264', video_decoder: 'auto', audio_config: 'stereo', frame_pacing: false, vsync: false },
  balanced: { resolution: '1920x1080', fps: 45, bitrate: 22000, packet_size: 1280, video_codec: 'H.264', video_decoder: 'auto', audio_config: 'stereo', frame_pacing: true, vsync: false },
  economy: { resolution: '1280x720', fps: 30, bitrate: 10000, packet_size: 1200, video_codec: 'H.264', video_decoder: 'software', audio_config: 'stereo', frame_pacing: true, vsync: false },
  survival: { resolution: '1280x720', fps: 24, bitrate: 3000, packet_size: 1100, video_codec: 'H.264', video_decoder: 'software', audio_config: 'stereo', frame_pacing: true, vsync: false }
};

const STREAM_PRESET_ALIASES = {
  lan_ultra: 'lan-ultra',
  fast: 'smooth',
  sharp: 'lan-ultra',
  slow_dsl: 'economy',
  'slow-dsl': 'economy',
  low: 'economy',
  medium: 'balanced',
  high: 'smooth',
  ultra: 'lan-ultra',
  manual: 'custom'
};

function canonicalPreset(value) {
  const preset = String(value || 'balanced').trim().toLowerCase().replace(/_/g, '-');
  if (STREAM_PRESET_ALIASES[preset]) {
    return STREAM_PRESET_ALIASES[preset];
  }
  if (preset === 'custom') {
    return preset;
  }
  if (Object.prototype.hasOwnProperty.call(STREAM_PRESETS, preset)) {
    return preset;
  }
  return 'balanced';
}

function numericOrAuto(value, fallback) {
  const text = String(value == null ? '' : value).trim();
  if (!text) {
    return fallback;
  }
  if (text.toLowerCase() === 'auto') {
    return 'auto';
  }
  const num = Number(text);
  return Number.isFinite(num) ? num : fallback;
}

function fpsLabel(value) {
  if (value == null || value === '') {
    return '-';
  }
  if (String(value).trim().toLowerCase() === 'auto') {
    return 'auto';
  }
  const num = Number(value);
  return Number.isFinite(num) ? String(Math.round(num)) + ' FPS' : '-';
}

function bitrateLabel(value) {
  if (value == null || value === '') {
    return '-';
  }
  if (String(value).trim().toLowerCase() === 'auto') {
    return 'auto';
  }
  const num = Number(value);
  return Number.isFinite(num) ? String(Math.round(num / 1000)) + ' Mbit' : '-';
}

function checkedBool(value) {
  const text = String(value == null ? '' : value).trim().toLowerCase();
  if (text === 'auto') {
    return false;
  }
  if (['1', 'true', 'yes', 'on'].includes(text)) {
    return true;
  }
  if (['0', 'false', 'no', 'off'].includes(text)) {
    return false;
  }
  return Boolean(value);
}

function setModalHidden(modal, hidden) {
  if (!modal) {
    return;
  }
  modal.hidden = Boolean(hidden);
  modal.setAttribute('aria-hidden', hidden ? 'true' : 'false');
  document.body.classList.toggle('modal-open', !hidden);
}

function encodeSessionId(sessionId) {
  return encodeURIComponent(String(sessionId || '')).replace(/%3A/gi, ':');
}

function updatePresetButtons(preset) {
  const selected = canonicalPreset(preset);
  document.querySelectorAll('[data-stream-preset]').forEach((button) => {
    button.classList.toggle('is-active', canonicalPreset(button.getAttribute('data-stream-preset') || '') === selected);
  });
}

function fillTuneForm(profile, preset) {
  const selectedPreset = canonicalPreset(preset || (profile && profile.preset) || 'balanced');
  const values = Object.assign({}, STREAM_PRESETS[selectedPreset] || STREAM_PRESETS.balanced, profile || {});
  const setValue = (id, value) => {
    const node = qs(id);
    if (node) {
      if (node.type === 'number' && String(value).trim().toLowerCase() === 'auto') {
        node.value = '';
      } else {
        node.value = String(value == null ? '' : value);
      }
    }
  };
  setValue('stream-tune-resolution', values.resolution || '1920x1080');
  setValue('stream-tune-fps', values.fps || 45);
  setValue('stream-tune-bitrate', values.bitrate || 16000);
  setValue('stream-tune-codec', values.video_codec || 'H.264');
  setValue('stream-tune-decoder', values.video_decoder || 'auto');
  setValue('stream-tune-audio', values.audio_config || 'stereo');
  setValue('stream-tune-packet', values.packet_size || 1200);
  const framePacing = qs('stream-tune-frame-pacing');
  const vsync = qs('stream-tune-vsync');
  if (framePacing) {
    framePacing.checked = checkedBool(values.frame_pacing);
  }
  if (vsync) {
    vsync.checked = checkedBool(values.vsync);
  }
  state.streamTunePreset = selectedPreset;
  updatePresetButtons(state.streamTunePreset);
}

function openTuneModal(session) {
  if (!session || !session.endpoint_id) {
    sessionHooks.setBanner('Diese Session kann noch nicht direkt getunt werden.', 'warn');
    return;
  }
  state.streamTuneSessionId = String(session.session_id || '');
  const label = qs('stream-tune-session-label');
  if (label) {
    label.textContent = 'Session ' + state.streamTuneSessionId + ' auf VM ' + String(session.vmid || '-') + '.';
  }
  const profile = session.stream_profile && typeof session.stream_profile === 'object' ? session.stream_profile : {};
  fillTuneForm(profile, canonicalPreset(profile.preset || 'balanced'));
  setModalHidden(qs('stream-tune-modal'), false);
}

function closeTuneModal() {
  setModalHidden(qs('stream-tune-modal'), true);
}

function collectTunePayload() {
  const value = (id, fallback) => {
    const node = qs(id);
    const raw = node ? String(node.value || '').trim() : '';
    return raw || fallback;
  };
  const preset = canonicalPreset(state.streamTunePreset || 'balanced');
  const presetValues = STREAM_PRESETS[preset] || STREAM_PRESETS.balanced;
  const checkboxValue = (id, fallback) => {
    if (String(fallback).trim().toLowerCase() === 'auto') {
      return 'auto';
    }
    const node = qs(id);
    return node ? Boolean(node.checked) : Boolean(fallback);
  };
  return {
    preset,
    manual: true,
    resolution: value('stream-tune-resolution', presetValues.resolution || '1920x1080'),
    fps: numericOrAuto(value('stream-tune-fps', presetValues.fps || 45), presetValues.fps || 45),
    bitrate: numericOrAuto(value('stream-tune-bitrate', presetValues.bitrate || 22000), presetValues.bitrate || 22000),
    packet_size: numericOrAuto(value('stream-tune-packet', presetValues.packet_size || 1280), presetValues.packet_size || 1280),
    video_codec: value('stream-tune-codec', presetValues.video_codec || 'H.264'),
    video_decoder: value('stream-tune-decoder', presetValues.video_decoder || 'auto'),
    audio_config: value('stream-tune-audio', presetValues.audio_config || 'stereo'),
    frame_pacing: checkboxValue('stream-tune-frame-pacing', presetValues.frame_pacing),
    vsync: checkboxValue('stream-tune-vsync', presetValues.vsync)
  };
}

function saveTuneProfile() {
  const sessionId = String(state.streamTuneSessionId || '');
  if (!sessionId) {
    return Promise.resolve();
  }
  const saveButton = qs('stream-tune-save');
  if (saveButton) {
    saveButton.disabled = true;
  }
  return postJson('/sessions/' + encodeSessionId(sessionId) + '/stream-profile', collectTunePayload()).then((payload) => {
    sessionHooks.setBanner('Stream-Einstellung gespeichert. Der Thinclient uebernimmt sie beim naechsten Sync.', 'ok');
    closeTuneModal();
    return reloadSessionsPanel().then(() => payload);
  }).catch((error) => {
    sessionHooks.setBanner('Stream-Einstellung fehlgeschlagen: ' + String(error && error.message ? error.message : error), 'warn');
    throw error;
  }).finally(() => {
    if (saveButton) {
      saveButton.disabled = false;
    }
  });
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
  const profile = session.stream_profile && typeof session.stream_profile === 'object' ? session.stream_profile : null;
  const tuneAction = session.endpoint_id ? '<button class="button primary small" type="button" data-session-tune="1">Stream einstellen</button>' : '';
  const sourceLabel = session.source === 'endpoint_report' ? 'Direkter Thinclient-Stream' : 'Pool-Session';
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
    '</div>' +
    '<div class="stream-profile-summary">' +
    '<span>' + escapeHtml(String(profile && profile.resolution ? profile.resolution : '-')) + '</span>' +
    '<span>' + escapeHtml(fpsLabel(profile && profile.fps)) + '</span>' +
    '<span>' + escapeHtml(bitrateLabel(profile && profile.bitrate)) + '</span>' +
    '<span>' + escapeHtml(String(profile && profile.video_codec ? profile.video_codec : '-')) + '</span>' +
    '</div>' +
    '<div class="session-detail-actions"><span class="session-source-chip">' + escapeHtml(sourceLabel) + '</span>' + tuneAction + '</div>';
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

  const detailBody = qs('session-detail-body');
  if (detailBody) {
    detailBody.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement) || !target.closest('[data-session-tune]')) {
        return;
      }
      openTuneModal(selectedSession());
    });
  }

  const closeButtons = [qs('stream-tune-close'), qs('stream-tune-cancel')];
  closeButtons.forEach((button) => {
    if (button) {
      button.addEventListener('click', closeTuneModal);
    }
  });
  document.querySelectorAll('[data-stream-preset]').forEach((button) => {
    button.addEventListener('click', () => {
      const preset = canonicalPreset(button.getAttribute('data-stream-preset') || 'balanced');
      state.streamTunePreset = preset;
      fillTuneForm(STREAM_PRESETS[preset] || STREAM_PRESETS.balanced, preset);
    });
  });
  const saveButton = qs('stream-tune-save');
  if (saveButton) {
    saveButton.addEventListener('click', () => {
      saveTuneProfile().catch(() => {});
    });
  }
}
