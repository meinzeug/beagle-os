import { request } from './api.js';
import { escapeHtml, qs } from './dom.js';
import { state } from './state.js';

const kioskHooks = {
  setBanner() {}
};

export function configureKioskController(nextHooks) {
  Object.assign(kioskHooks, nextHooks || {});
}

function formatRemaining(seconds) {
  if (seconds < 0) return '∞';
  if (seconds === 0) return 'Abgelaufen';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s < 10 ? '0' : ''}${s}s`;
}

function metricValue(value, suffix = '') {
  if (value === null || value === undefined || value === '') return '–';
  return `${value}${suffix}`;
}

function titleValue(streamHealth) {
  const title = String(streamHealth.window_title ?? streamHealth.game_title ?? '').trim();
  return title || '–';
}

function gpuValue(streamHealth) {
  const util = streamHealth.gpu_util_pct;
  const temp = streamHealth.gpu_temp_c;
  if ((util === null || util === undefined || util === '') && (temp === null || temp === undefined || temp === '')) {
    return '–';
  }
  const parts = [];
  if (util !== null && util !== undefined && util !== '') parts.push(`${util} %`);
  if (temp !== null && temp !== undefined && temp !== '') parts.push(`${temp} C`);
  return parts.join(' / ');
}

function sessionAlertChips(streamHealth) {
  const metrics = streamHealth && typeof streamHealth === 'object' ? streamHealth : {};
  const chips = [];
  const encoderLoad = Number(metrics.encoder_load);
  const droppedFrames = Number(metrics.dropped_frames);
  if (Number.isFinite(encoderLoad) && encoderLoad >= 90) {
    chips.push(`<span class="chip warn">Encoder ${escapeHtml(String(Math.round(encoderLoad)))} %</span>`);
  }
  if (Number.isFinite(droppedFrames) && droppedFrames > 0) {
    const tone = droppedFrames >= 10 ? 'warn' : 'muted';
    chips.push(`<span class="chip ${tone}">Drops ${escapeHtml(String(Math.round(droppedFrames)))}</span>`);
  }
  return chips.join('');
}

function extensionButtons(session) {
  const rawOptions = Array.isArray(session.session_extension_options_minutes)
    ? session.session_extension_options_minutes
    : [];
  const options = rawOptions
    .map((item) => Number(item))
    .filter((item, idx, all) => Number.isFinite(item) && item > 0 && all.indexOf(item) === idx)
    .sort((a, b) => a - b);
  return options.map((minutes) => `<button
        class="btn-sm"
        data-action="extend-kiosk-session"
        data-vmid="${escapeHtml(String(session.vm_id ?? ''))}"
        data-minutes="${escapeHtml(String(minutes))}"
        title="Session um ${escapeHtml(String(minutes))} Minuten verlaengern"
      >+${escapeHtml(String(minutes))}m</button>`).join('');
}

function sessionRow(session) {
  const remaining = formatRemaining(session.time_remaining_seconds ?? -1);
  const tone = session.time_remaining_seconds >= 0 && session.time_remaining_seconds < 300 ? 'warn' : 'ok';
  const streamHealth = session.stream_health ?? {};
  const title = titleValue(streamHealth);
  const fps = metricValue(streamHealth.fps);
  const rtt = metricValue(streamHealth.rtt_ms, ' ms');
  const gpu = gpuValue(streamHealth);
  const alertChips = sessionAlertChips(streamHealth);
  const extendActions = extensionButtons(session);
  return `<tr>
    <td>${escapeHtml(String(session.vm_id ?? ''))}</td>
    <td>${escapeHtml(session.user_id ?? '-')}</td>
    <td>${escapeHtml(session.pool_id ?? '-')}</td>
    <td>
      <div>${escapeHtml(title)}</div>
      ${alertChips ? `<div class="gaming-alert-list">${alertChips}</div>` : ''}
    </td>
    <td class="tone-${tone}">${escapeHtml(remaining)}</td>
    <td>${escapeHtml(fps)}</td>
    <td>${escapeHtml(rtt)}</td>
    <td>${escapeHtml(gpu)}</td>
    <td>
      ${extendActions}
      <button
        class="btn-sm btn-danger"
        data-action="end-kiosk-session"
        data-vmid="${escapeHtml(String(session.vm_id ?? ''))}"
        title="Session beenden und VM zuruecksetzen"
      >Beenden + Reset</button>
    </td>
  </tr>`;
}

export async function renderKioskController() {
  const container = qs('kiosk-controller-panel');
  if (!container) return;

  if (!state.token) {
    container.innerHTML = '<div class="empty-card">Anmeldung erforderlich.</div>';
    return;
  }

  container.innerHTML = '<p class="loading">Lade Kiosk-Sessions…</p>';

  let sessions = [];
  try {
    const data = await request('/pools/kiosk/sessions');
    sessions = Array.isArray(data) ? data : (data.sessions ?? []);
  } catch (err) {
    container.innerHTML = `<p class="error">Fehler beim Laden: ${escapeHtml(String(err.message ?? err))}</p>`;
    return;
  }

  if (sessions.length === 0) {
    container.innerHTML = '<div class="empty-card">Keine aktiven Kiosk-Sessions.</div>';
    return;
  }

  const rows = sessions.map(sessionRow).join('');
  container.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>VM</th>
          <th>Benutzer</th>
          <th>Pool</th>
          <th>Spiel</th>
          <th>Restzeit</th>
          <th>FPS</th>
          <th>RTT</th>
          <th>GPU</th>
          <th>Aktion</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;

  container.querySelectorAll('[data-action="extend-kiosk-session"]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const vmId = btn.dataset.vmid;
      const minutes = Number(btn.dataset.minutes || '15');
      btn.disabled = true;
      try {
        const payload = await request(`/pools/kiosk/sessions/${vmId}/extend`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ minutes })
        });
        const remaining = formatRemaining(Number(payload.time_remaining_seconds ?? -1));
        kioskHooks.setBanner(`Session fuer VM ${vmId} um ${minutes} Minuten verlaengert (${remaining} verbleibend).`, 'ok');
        renderKioskController();
      } catch (err) {
        kioskHooks.setBanner(`Fehler: ${err.message ?? err}`, 'warn');
        btn.disabled = false;
      }
    });
  });

  container.querySelectorAll('[data-action="end-kiosk-session"]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const vmId = btn.dataset.vmid;
      if (!confirm(`Kiosk-Session fuer VM ${vmId} wirklich beenden und die VM auf den Template-Stand zuruecksetzen?`)) return;
      btn.disabled = true;
      try {
        await request(`/pools/kiosk/sessions/${vmId}/end`, { method: 'POST' });
        kioskHooks.setBanner(`Session fuer VM ${vmId} beendet und Reset angestossen.`, 'ok');
        renderKioskController();
      } catch (err) {
        kioskHooks.setBanner(`Fehler: ${err.message ?? err}`, 'warn');
        btn.disabled = false;
      }
    });
  });
}
