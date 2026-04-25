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

function sessionRow(session) {
  const remaining = formatRemaining(session.time_remaining_seconds ?? -1);
  const tone = session.time_remaining_seconds >= 0 && session.time_remaining_seconds < 300 ? 'warn' : 'ok';
  return `<tr>
    <td>${escapeHtml(String(session.vm_id ?? ''))}</td>
    <td>${escapeHtml(session.user_id ?? '-')}</td>
    <td>${escapeHtml(session.pool_id ?? '-')}</td>
    <td class="tone-${tone}">${escapeHtml(remaining)}</td>
    <td>
      <button
        class="btn-sm btn-danger"
        data-action="end-kiosk-session"
        data-vmid="${escapeHtml(String(session.vm_id ?? ''))}"
        title="Session beenden"
      >Beenden</button>
    </td>
  </tr>`;
}

export async function renderKioskController() {
  const container = qs('kiosk-controller-panel');
  if (!container) return;

  container.innerHTML = '<p class="loading">Lade Kiosk-Sessions…</p>';

  let sessions = [];
  try {
    const data = await request('GET', '/api/v1/pools/kiosk/sessions');
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
          <th>Restzeit</th>
          <th>Aktion</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;

  container.querySelectorAll('[data-action="end-kiosk-session"]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const vmId = btn.dataset.vmid;
      if (!confirm(`Kiosk-Session für VM ${vmId} wirklich beenden?`)) return;
      btn.disabled = true;
      try {
        await request('POST', `/api/v1/pools/kiosk/sessions/${vmId}/end`);
        kioskHooks.setBanner(`Session für VM ${vmId} beendet.`);
        renderKioskController();
      } catch (err) {
        kioskHooks.setBanner(`Fehler: ${err.message ?? err}`);
        btn.disabled = false;
      }
    });
  });
}
